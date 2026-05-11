"""
Shell HTTP - Shared HTTP Client
---------------------------------
Global connection-pooled sessions for both async (aiohttp) and sync (requests).

Usage:
    from shell_http import get_async_session, get_sync_session, async_get

    # Async:
    session = await get_async_session()
    async with session.get(url) as resp:
        data = await resp.json()

    # Or use helpers:
    data = await async_get("https://api.example.com/data")

    # Sync:
    session = get_sync_session()
    resp = session.get(url)
"""

import asyncio
import logging

logger = logging.getLogger("shell_http")

# ── Async (aiohttp) ──────────────────────────────────────────────

_aio_session = None


async def get_async_session():
    """Get or create global aiohttp ClientSession with connection pooling."""
    global _aio_session
    try:
        import aiohttp
    except ImportError:
        logger.warning("aiohttp not installed — async HTTP not available")
        return None

    if _aio_session is None or _aio_session.closed:
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
        _aio_session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={"User-Agent": "Shell-AI/1.0"},
        )
    return _aio_session


async def async_get(url: str, params: dict = None, timeout: int = 15, retries: int = 2):
    """GET with retry and exponential backoff. Returns parsed JSON or text."""
    session = await get_async_session()
    if session is None:
        raise RuntimeError("aiohttp not available")

    import aiohttp

    last_error = None
    for attempt in range(retries + 1):
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get("Content-Type", "")
                    if "json" in content_type:
                        return await resp.json()
                    return await resp.text()
                elif resp.status == 429:
                    # Rate limited — wait and retry
                    wait = min(2 ** attempt, 10)
                    logger.warning(f"Rate limited on {url}, waiting {wait}s")
                    await asyncio.sleep(wait)
                    continue
                else:
                    last_error = f"HTTP {resp.status}: {await resp.text()}"
        except asyncio.TimeoutError:
            last_error = f"Timeout after {timeout}s"
        except Exception as e:
            last_error = str(e)

        if attempt < retries:
            wait = 2 ** attempt
            logger.warning(f"Retry {attempt + 1}/{retries} for {url}: {last_error}")
            await asyncio.sleep(wait)

    raise RuntimeError(f"Failed after {retries + 1} attempts: {last_error}")


async def async_post(url: str, json: dict = None, data=None, timeout: int = 15, retries: int = 2):
    """POST with retry. Returns parsed JSON or text."""
    session = await get_async_session()
    if session is None:
        raise RuntimeError("aiohttp not available")

    import aiohttp

    last_error = None
    for attempt in range(retries + 1):
        try:
            async with session.post(
                url, json=json, data=data,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status in (200, 201):
                    content_type = resp.headers.get("Content-Type", "")
                    if "json" in content_type:
                        return await resp.json()
                    return await resp.text()
                else:
                    last_error = f"HTTP {resp.status}"
        except asyncio.TimeoutError:
            last_error = f"Timeout after {timeout}s"
        except Exception as e:
            last_error = str(e)

        if attempt < retries:
            await asyncio.sleep(2 ** attempt)

    raise RuntimeError(f"POST failed after {retries + 1} attempts: {last_error}")


async def close_async_session():
    """Gracefully close the async session. Call on shutdown."""
    global _aio_session
    if _aio_session and not _aio_session.closed:
        await _aio_session.close()
        _aio_session = None
        logger.info("Async HTTP session closed")


# ── Sync (requests) ──────────────────────────────────────────────

_sync_session = None


def get_sync_session():
    """Get or create global requests.Session with connection pooling."""
    global _sync_session
    if _sync_session is None:
        import requests
        _sync_session = requests.Session()
        _sync_session.headers.update({"User-Agent": "Shell-AI/1.0"})
        # Connection pool adapter
        from requests.adapters import HTTPAdapter
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20)
        _sync_session.mount("http://", adapter)
        _sync_session.mount("https://", adapter)
    return _sync_session


def close_sync_session():
    """Close sync session."""
    global _sync_session
    if _sync_session:
        _sync_session.close()
        _sync_session = None


async def cleanup_sessions():
    """Close both async and sync sessions. Convenience for shutdown."""
    await close_async_session()
    close_sync_session()
