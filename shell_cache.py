"""
Shell Cache - Universal Caching Layer
---------------------------------------
Thread-safe TTL + LRU cache with stats tracking.

Usage:
    from shell_cache import search_cache, weather_cache

    # Direct usage:
    search_cache.set("query:python", results, ttl=300)
    data = search_cache.get("query:python")

    # Decorator usage:
    @cached(ttl=300, cache=search_cache)
    async def my_search(query: str) -> str:
        ...
"""

import time
import asyncio
import inspect
import threading
import functools
from collections import OrderedDict


_MISSING = object()  # Sentinel to distinguish cache miss from stored None


class ShellCache:
    """Thread-safe in-memory cache with TTL and LRU eviction."""

    def __init__(self, max_size: int = 1024, default_ttl: int = 300, name: str = "default"):
        self._store = OrderedDict()  # key -> (value, expiry_time)
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self.name = name
        # Stats
        self._hits = 0
        self._misses = 0

    def get(self, key: str, default=_MISSING):
        """Get value if exists and not expired. Returns default on miss (None if not specified)."""
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None if default is _MISSING else default
            value, expiry = self._store[key]
            if time.time() > expiry:
                del self._store[key]
                self._misses += 1
                return None if default is _MISSING else default
            # Move to end (most recently used)
            self._store.move_to_end(key)
            self._hits += 1
            return value

    def has(self, key: str) -> bool:
        """Check if key exists and is not expired (without counting as hit/miss)."""
        with self._lock:
            if key not in self._store:
                return False
            _, expiry = self._store[key]
            if time.time() > expiry:
                del self._store[key]
                return False
            return True

    def set(self, key: str, value, ttl: int = None):
        """Set value with TTL. Evicts expired entries first, then LRU."""
        ttl = ttl if ttl is not None else self._default_ttl
        expiry = time.time() + ttl
        with self._lock:
            # Evict expired entries FIRST so they don't waste capacity slots
            # (otherwise a long-lived expired entry could force eviction of
            # a fresh but recently-accessed entry with a short TTL).
            now = time.time()
            stale = [k for k, (_, exp) in self._store.items() if now > exp and k != key]
            for k in stale:
                del self._store[k]

            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, expiry)
            # Evict LRU entries if still over capacity
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if existed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self):
        """Clear all entries."""
        with self._lock:
            self._store.clear()

    def cleanup_expired(self):
        """Remove all expired entries."""
        now = time.time()
        with self._lock:
            expired = [k for k, (_, exp) in self._store.items() if now > exp]
            for k in expired:
                del self._store[k]

    @property
    def size(self) -> int:
        return len(self._store)

    def stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "name": self.name,
            "size": len(self._store),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0,
        }


def cached(ttl: int = 300, cache: ShellCache = None):
    """Decorator for caching function results. Works with sync and async functions.

    Usage:
        @cached(ttl=300, cache=search_cache)
        async def search(query: str) -> str:
            ...
    """
    def decorator(func):
        _cache = cache or _default_cache

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            if _cache.has(cache_key):
                return _cache.get(cache_key)
            result = await func(*args, **kwargs)
            _cache.set(cache_key, result, ttl)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            if _cache.has(cache_key):
                return _cache.get(cache_key)
            result = func(*args, **kwargs)
            _cache.set(cache_key, result, ttl)
            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ── Pre-built Named Caches ──────────────────────────────────────

_default_cache = ShellCache(max_size=1024, default_ttl=300, name="default")
search_cache = ShellCache(max_size=256, default_ttl=300, name="search")
weather_cache = ShellCache(max_size=128, default_ttl=600, name="weather")
api_cache = ShellCache(max_size=512, default_ttl=120, name="api")
image_cache = ShellCache(max_size=64, default_ttl=7200, name="image")


def get_all_stats() -> list:
    """Get stats from all named caches."""
    return [
        _default_cache.stats(),
        search_cache.stats(),
        weather_cache.stats(),
        api_cache.stats(),
        image_cache.stats(),
    ]
