"""
Shell Rate Limiter - Token Bucket Rate Limiting
-------------------------------------------------
Prevents API overload with per-tool rate limiting.

Usage:
    from shell_rate_limiter import RateLimiterRegistry

    # In god_tier_tool:
    limiter = RateLimiterRegistry.get().get_limiter("google_search")
    await limiter.wait()

    # Or as decorator:
    @rate_limited("google_search")
    async def my_search(query):
        ...
"""

import time
import asyncio
import threading
import functools
import inspect


class TokenBucket:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: Tokens added per second (e.g., 1.0 = 1 request/sec)
            capacity: Maximum tokens (burst size)
        """
        self._rate = rate
        self._capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()
        # Stats
        self._total_requests = 0
        self._total_waits = 0

    def _refill(self):
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def try_consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate limited."""
        with self._lock:
            self._refill()
            self._total_requests += 1
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            self._total_waits += 1
            return False

    async def wait(self, tokens: int = 1):
        """Async wait until tokens are available. Non-blocking for event loop."""
        while True:
            with self._lock:
                self._refill()
                self._total_requests += 1
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                self._total_waits += 1
                # Calculate wait time
                deficit = tokens - self._tokens
                wait_time = deficit / self._rate
            await asyncio.sleep(min(wait_time, 5.0))  # Cap at 5s

    def stats(self) -> dict:
        return {
            "rate": self._rate,
            "capacity": self._capacity,
            "tokens_available": round(self._tokens, 2),
            "total_requests": self._total_requests,
            "total_waits": self._total_waits,
        }


class RateLimiterRegistry:
    """Global registry of named rate limiters."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Set the initialised flag BEFORE running _setup_defaults so a
        # concurrent/reentrant __init__ cannot wipe the limiters dict mid-setup.
        if self._initialized:
            return
        self._initialized = True
        self._limiters = {}
        self._setup_defaults()

    def _setup_defaults(self):
        """Configure default rate limiters for known APIs."""
        self._limiters = {
            "google_search": TokenBucket(rate=1.0, capacity=5),
            "weather_api": TokenBucket(rate=0.5, capacity=3),
            "news_api": TokenBucket(rate=0.2, capacity=2),
            "image_gen": TokenBucket(rate=0.1, capacity=2),
            "email_send": TokenBucket(rate=0.2, capacity=3),
            "instagram": TokenBucket(rate=0.3, capacity=2),
            "telegram": TokenBucket(rate=2.0, capacity=10),
            "whatsapp": TokenBucket(rate=0.5, capacity=3),
            "browser": TokenBucket(rate=3.0, capacity=15),
            "system": TokenBucket(rate=5.0, capacity=20),
            "default": TokenBucket(rate=5.0, capacity=20),
        }

    @classmethod
    def get(cls) -> "RateLimiterRegistry":
        return cls()

    def get_limiter(self, name: str) -> TokenBucket:
        """Get limiter by name. Falls back to 'default'."""
        return self._limiters.get(name, self._limiters["default"])

    def configure(self, name: str, rate: float, capacity: int):
        """Add or update a rate limiter."""
        self._limiters[name] = TokenBucket(rate=rate, capacity=capacity)

    def stats(self) -> dict:
        """Get all limiter stats."""
        return {name: limiter.stats() for name, limiter in self._limiters.items()}


def rate_limited(limiter_name: str = "default"):
    """Decorator to rate-limit a function. Works with async and sync."""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            limiter = RateLimiterRegistry.get().get_limiter(limiter_name)
            await limiter.wait()
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            limiter = RateLimiterRegistry.get().get_limiter(limiter_name)
            if not limiter.try_consume():
                time.sleep(1.0 / limiter._rate)
            return func(*args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
