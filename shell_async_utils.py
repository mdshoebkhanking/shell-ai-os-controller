"""
Shell Async Utils — Async Helper Functions
--------------------------------------------
Timeout wrappers, safe gather, retry logic, batch execution.

Usage:
    from shell_async_utils import with_timeout, safe_gather, retry_async, run_batch

    result = await with_timeout(some_coro(), timeout=10)
    results = await safe_gather(coro1(), coro2(), coro3())
    result = await retry_async(flaky_func, args=("hello",), max_retries=3)
"""

import asyncio
import inspect
import logging
import time
from typing import Any, Callable, Optional, Coroutine

logger = logging.getLogger("shell_async_utils")


async def with_timeout(coro: Coroutine, timeout: float = 30.0,
                       default: Any = None, label: str = "") -> Any:
    """Run a coroutine with timeout. Returns default on timeout instead of raising."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        name = label or "coroutine"
        logger.warning(f"Timeout after {timeout}s: {name}")
        return default
    except asyncio.CancelledError:
        raise
    except Exception as e:
        name = label or "coroutine"
        logger.error(f"Error in {name}: {e}")
        return default


async def safe_gather(*coros: Coroutine, return_exceptions: bool = True) -> list:
    """Like asyncio.gather but never crashes. Failed tasks return their exception."""
    results = await asyncio.gather(*coros, return_exceptions=return_exceptions)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"safe_gather task {i} failed: {result}")
    return results


async def retry_async(func: Callable, args: tuple = (), kwargs: Optional[dict] = None,
                      max_retries: int = 3, backoff_base: float = 1.0,
                      backoff_max: float = 30.0,
                      retry_on: tuple = (Exception,),
                      label: str = "") -> Any:
    """Retry an async function with exponential backoff."""
    kwargs = kwargs or {}
    name = label or getattr(func, "__name__", "function")
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return await asyncio.to_thread(func, *args, **kwargs)
        except retry_on as e:
            last_error = e
            if attempt < max_retries:
                wait = min(backoff_base * (2 ** attempt), backoff_max)
                logger.warning(f"Retry {attempt + 1}/{max_retries} for {name}: {e} (wait {wait:.1f}s)")
                await asyncio.sleep(wait)
            else:
                logger.error(f"All {max_retries + 1} attempts failed for {name}: {e}")

    raise last_error


async def run_batch(items: list, processor: Callable, concurrency: int = 5,
                    timeout_per_item: float = 30.0) -> list:
    """Process items concurrently with limited parallelism.

    Args:
        items: List of items to process
        processor: Async function that takes one item
        concurrency: Max parallel executions
        timeout_per_item: Timeout per item in seconds

    Returns:
        List of (item, result_or_exception) tuples
    """
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def _process(item):
        async with semaphore:
            try:
                result = await asyncio.wait_for(processor(item), timeout=timeout_per_item)
                return (item, result)
            except Exception as e:
                return (item, e)

    tasks = [_process(item) for item in items]
    results = await asyncio.gather(*tasks)
    return list(results)


async def debounce(coro_factory: Callable, delay: float = 0.5) -> Any:
    """Debounce a coroutine — wait for delay, then execute.
    Useful for preventing rapid duplicate calls.
    """
    await asyncio.sleep(delay)
    return await coro_factory()


class AsyncRateLimiter:
    """Simple async rate limiter using token bucket."""

    def __init__(self, rate: float = 1.0, burst: int = 1):
        """
        Args:
            rate: Tokens per second
            burst: Max tokens (burst capacity)
        """
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            # Need to wait
            wait_time = (1.0 - self._tokens) / self._rate
            self._tokens = 0.0

        await asyncio.sleep(wait_time)

        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_refill = now
            self._tokens = max(0, self._tokens - 1.0)


class BackgroundTaskManager:
    """Manages fire-and-forget background tasks with tracking."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._results: dict[str, Any] = {}

    def spawn(self, name: str, coro: Coroutine) -> asyncio.Task:
        """Spawn a named background task."""
        # Cancel existing task with same name
        if name in self._tasks and not self._tasks[name].done():
            self._tasks[name].cancel()

        async def _tracked():
            try:
                result = await coro
                self._results[name] = {"status": "ok", "result": result}
                return result
            except asyncio.CancelledError:
                self._results[name] = {"status": "cancelled"}
                raise
            except Exception as e:
                self._results[name] = {"status": "error", "error": str(e)}
                logger.warning(f"Background task '{name}' failed: {e}")

        task = asyncio.create_task(_tracked())
        self._tasks[name] = task
        return task

    def cancel(self, name: str) -> bool:
        """Cancel a named task."""
        task = self._tasks.get(name)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_running(self, name: str) -> bool:
        """Check if a named task is still running."""
        task = self._tasks.get(name)
        return task is not None and not task.done()

    def get_status(self) -> dict:
        """Get status of all tasks."""
        status = {}
        for name, task in self._tasks.items():
            if task.done():
                result = self._results.get(name, {})
                status[name] = result.get("status", "done")
            else:
                status[name] = "running"
        return status

    async def cancel_all(self):
        """Cancel all running tasks."""
        for name, task in self._tasks.items():
            if not task.done():
                task.cancel()
        # Wait for cancellations to complete
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)


# Global background task manager
_bg_manager = BackgroundTaskManager()


def get_bg_manager() -> BackgroundTaskManager:
    return _bg_manager
