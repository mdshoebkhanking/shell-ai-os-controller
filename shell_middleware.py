"""
Shell Middleware — Pre/Post Execution Pipeline
-------------------------------------------------
Hooks that run before/after every tool execution.
Input sanitization, logging, metrics, circuit breaking.

Usage:
    from shell_middleware import MiddlewareChain, sanitize_middleware, logging_middleware

    chain = MiddlewareChain.get()
    chain.add_pre(sanitize_middleware)
    chain.add_post(logging_middleware)
"""

import time
import logging
import threading
from typing import Callable, Optional, Any

logger = logging.getLogger("shell_middleware")


class ToolContext:
    """Context object passed through middleware chain."""
    __slots__ = ("tool_name", "args", "kwargs", "result", "error",
                 "start_time", "end_time", "metadata", "cancelled")

    def __init__(self, tool_name: str, args: tuple, kwargs: dict):
        self.tool_name = tool_name
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.error = None
        self.start_time = time.time()
        self.end_time = 0.0
        self.metadata: dict = {}
        self.cancelled = False

    @property
    def elapsed_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000


class CircuitBreaker:
    """Per-tool circuit breaker — stops calling tools that keep failing."""

    # Explicit states — no more implicit "give one free retry" via failure count.
    _STATE_CLOSED = "closed"
    _STATE_OPEN = "open"
    _STATE_HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_time: float = 60.0):
        self._failure_threshold = failure_threshold
        self._recovery_time = recovery_time
        self._failures: dict[str, int] = {}
        self._open_since: dict[str, float] = {}
        self._state: dict[str, str] = {}
        self._lock = threading.Lock()

    def is_open(self, tool_name: str) -> bool:
        """Check if circuit is open (tool is blocked).

        States:
          * closed    — normal operation
          * open      — all calls blocked until recovery_time elapses
          * half_open — one probe permitted; next outcome decides open↔closed
        """
        with self._lock:
            state = self._state.get(tool_name, self._STATE_CLOSED)
            if state == self._STATE_CLOSED:
                return False
            if state == self._STATE_HALF_OPEN:
                # Probe already granted elsewhere — don't spam-allow more.
                return False
            # state == open: check recovery window
            opened_at = self._open_since.get(tool_name, 0.0)
            elapsed = time.time() - opened_at
            if elapsed >= self._recovery_time:
                # Transition open → half_open. Exactly ONE probe call
                # will be permitted; failure or success decides next.
                self._state[tool_name] = self._STATE_HALF_OPEN
                return False
            return True

    def record_success(self, tool_name: str):
        """Reset failure count on success (half_open probe passes → closed)."""
        with self._lock:
            self._failures.pop(tool_name, None)
            self._open_since.pop(tool_name, None)
            self._state[tool_name] = self._STATE_CLOSED

    def record_failure(self, tool_name: str):
        """Record failure; transition closed→open or half_open→open explicitly."""
        with self._lock:
            state = self._state.get(tool_name, self._STATE_CLOSED)
            if state == self._STATE_HALF_OPEN:
                # Probe failed — reopen immediately, reset recovery timer.
                self._state[tool_name] = self._STATE_OPEN
                self._open_since[tool_name] = time.time()
                logger.warning("Circuit re-OPENED for '%s' after half-open probe failed.", tool_name)
                return
            self._failures[tool_name] = self._failures.get(tool_name, 0) + 1
            if self._failures[tool_name] >= self._failure_threshold:
                self._state[tool_name] = self._STATE_OPEN
                self._open_since[tool_name] = time.time()
                logger.warning(
                    f"Circuit OPEN for '{tool_name}' after {self._failures[tool_name]} failures. "
                    f"Will retry in {self._recovery_time}s."
                )

    def get_status(self) -> dict:
        """Get all circuit states."""
        with self._lock:
            return {
                "open": list(self._open_since.keys()),
                "failures": dict(self._failures),
            }


class MiddlewareChain:
    """Singleton middleware chain for tool execution."""

    _instance = None
    _cls_lock = threading.Lock()

    def __init__(self):
        self._pre_hooks: list[Callable] = []
        self._post_hooks: list[Callable] = []
        self._circuit_breaker = CircuitBreaker()
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> "MiddlewareChain":
        if cls._instance is None:
            with cls._cls_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def add_pre(self, hook: Callable):
        """Add pre-execution hook. Signature: hook(ctx: ToolContext) -> None"""
        with self._lock:
            self._pre_hooks.append(hook)

    def add_post(self, hook: Callable):
        """Add post-execution hook. Signature: hook(ctx: ToolContext) -> None"""
        with self._lock:
            self._post_hooks.append(hook)

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker

    def run_pre(self, ctx: ToolContext):
        """Execute all pre-hooks."""
        # Check circuit breaker first
        if self._circuit_breaker.is_open(ctx.tool_name):
            ctx.cancelled = True
            ctx.error = f"Circuit breaker OPEN for '{ctx.tool_name}'. Tool temporarily disabled due to repeated failures."
            return

        for hook in self._pre_hooks:
            try:
                hook(ctx)
                if ctx.cancelled:
                    break
            except Exception as e:
                logger.warning(f"Pre-hook {hook.__name__} error: {e}")

    def run_post(self, ctx: ToolContext):
        """Execute all post-hooks."""
        ctx.end_time = time.time()

        # Update circuit breaker
        if ctx.error:
            self._circuit_breaker.record_failure(ctx.tool_name)
        else:
            self._circuit_breaker.record_success(ctx.tool_name)

        for hook in self._post_hooks:
            try:
                hook(ctx)
            except Exception as e:
                logger.warning(f"Post-hook {hook.__name__} error: {e}")


# ── Built-in Middleware Hooks ────────────────────────────────────

def sanitize_middleware(ctx: ToolContext):
    """Sanitize string inputs to prevent injection."""
    try:
        from shell_validator import sanitize_query
    except ImportError:
        return

    new_kwargs = {}
    for key, value in ctx.kwargs.items():
        if isinstance(value, str) and key in ("query", "search_query", "text", "prompt"):
            new_kwargs[key] = sanitize_query(value)
        else:
            new_kwargs[key] = value
    ctx.kwargs = new_kwargs


def logging_middleware(ctx: ToolContext):
    """Log tool execution results."""
    if ctx.error:
        logger.warning(
            f"Tool '{ctx.tool_name}' FAILED in {ctx.elapsed_ms:.0f}ms: {str(ctx.error)[:100]}"
        )
    else:
        logger.debug(
            f"Tool '{ctx.tool_name}' OK in {ctx.elapsed_ms:.0f}ms"
        )


def error_tracking_middleware(ctx: ToolContext):
    """Feed errors to ErrorTracker."""
    if not ctx.error:
        return
    try:
        from shell_error_tracker import ErrorTracker
        ErrorTracker.get().record(
            tool_name=ctx.tool_name,
            error=ctx.error,
            context={"elapsed_ms": ctx.elapsed_ms},
        )
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)


def registry_call_counter(ctx: ToolContext):
    """Increment call counter in ToolRegistry."""
    try:
        from shell_tool_registry import ToolRegistry
        ToolRegistry.get().record_call(ctx.tool_name)
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)


def setup_default_middleware():
    """Install all default middleware hooks."""
    chain = MiddlewareChain.get()
    chain.add_pre(sanitize_middleware)
    chain.add_post(logging_middleware)
    chain.add_post(error_tracking_middleware)
    chain.add_post(registry_call_counter)
    logger.info("Default middleware installed (sanitize, logging, error_tracking, call_counter)")
