"""
Reusable provider transport layer.

The provider modules stay lazy, but once a real async provider is used we should
reuse its HTTP session safely instead of creating a new ClientSession per call.
Sessions are scoped to the current asyncio event loop because aiohttp sessions
cannot be shared across loops.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class _SessionEntry:
    owner: str
    loop: asyncio.AbstractEventLoop
    session: Any
    created_at: float
    uses: int = 0


_SESSIONS: dict[tuple[str, int], _SessionEntry] = {}
_SESSION_FACTORY: Callable[[str, float], Any] | None = None


def _is_closed(session: Any) -> bool:
    return bool(getattr(session, "closed", False))


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def set_session_factory_for_tests(factory: Callable[[str, float], Any] | None) -> None:
    """Inject a lightweight fake session factory for tests/probes."""
    global _SESSION_FACTORY
    _SESSION_FACTORY = factory


async def get_aiohttp_session(owner: str, *, timeout_s: float = 60.0) -> Any:
    loop = asyncio.get_running_loop()
    key = (str(owner), id(loop))
    entry = _SESSIONS.get(key)
    if entry is not None and entry.loop is loop and not _is_closed(entry.session):
        entry.uses += 1
        return entry.session

    if _SESSION_FACTORY is not None:
        session = await _maybe_await(_SESSION_FACTORY(str(owner), float(timeout_s)))
    else:
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=float(timeout_s))
        connector = aiohttp.TCPConnector(limit_per_host=4, ttl_dns_cache=300)
        session = aiohttp.ClientSession(timeout=timeout, connector=connector)

    _SESSIONS[key] = _SessionEntry(
        owner=str(owner),
        loop=loop,
        session=session,
        created_at=time.time(),
        uses=1,
    )
    return session


async def close_aiohttp_sessions(owner: str | None = None) -> int:
    """Close sessions owned by the current event loop.

    Cross-loop sessions are intentionally not closed here; their owning event
    loop must perform cleanup before it shuts down.
    """
    loop = asyncio.get_running_loop()
    selected: list[tuple[tuple[str, int], _SessionEntry]] = []
    for key, entry in list(_SESSIONS.items()):
        if entry.loop is not loop:
            continue
        if owner is not None and entry.owner != owner:
            continue
        selected.append((key, entry))

    closed = 0
    for key, entry in selected:
        _SESSIONS.pop(key, None)
        if _is_closed(entry.session):
            continue
        close = getattr(entry.session, "close", None)
        if close is not None:
            await _maybe_await(close())
            closed += 1
    return closed


def provider_transport_stats() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for entry in _SESSIONS.values():
        items.append(
            {
                "owner": entry.owner,
                "loop_id": id(entry.loop),
                "closed": _is_closed(entry.session),
                "uses": entry.uses,
                "age_s": round(time.time() - entry.created_at, 3),
            }
        )
    return {
        "session_count": len(items),
        "sessions": sorted(items, key=lambda item: (item["owner"], item["loop_id"])),
    }


__all__ = [
    "close_aiohttp_sessions",
    "get_aiohttp_session",
    "provider_transport_stats",
    "set_session_factory_for_tests",
]
