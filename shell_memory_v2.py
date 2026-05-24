#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from core.memory.v2 import (
    MemoryV2Store,
    default_memory_v2_path,
    memory_v2_enabled,
    migrate_legacy_memory as _migrate_legacy_memory,
    normalize_tags,
)
from shell_safe_executor import god_tier_tool as function_tool


def _store(store: MemoryV2Store | None = None) -> MemoryV2Store:
    return store or MemoryV2Store(default_memory_v2_path())


def _importance_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    if parsed < 0:
        return None
    return max(0, min(100, parsed))


def save_memory(
    text: str,
    tags: str | Iterable[str] | None = None,
    importance: int | None = None,
    *,
    source: str = "manual",
    metadata: dict[str, Any] | None = None,
    store: MemoryV2Store | None = None,
) -> dict[str, Any]:
    record = _store(store).save_memory(
        text,
        tags=tags,
        importance=importance,
        source=source,
        metadata=metadata,
    )
    return {"ok": True, "memory": record.to_dict()}


def recall_memory(
    query: str,
    *,
    limit: int = 5,
    tags: str | Iterable[str] | None = None,
    store: MemoryV2Store | None = None,
) -> dict[str, Any]:
    results = [item.to_dict() for item in _store(store).recall_memory(query, limit=limit, tags=tags)]
    return {"ok": True, "query": query, "count": len(results), "memories": results}


def forget_memory(
    *,
    memory_id: str | None = None,
    query: str | None = None,
    tag: str | None = None,
    store: MemoryV2Store | None = None,
) -> dict[str, Any]:
    count = _store(store).forget_memory(memory_id=memory_id, query=query, tag=tag)
    return {"ok": True, "forgotten": count}


def migrate_legacy_memory(
    legacy_path: str | Path | None = None,
    *,
    store: MemoryV2Store | None = None,
) -> dict[str, Any]:
    result = _store(store).migrate_legacy(legacy_path)
    return {"ok": True, **result}


def format_recall_results(result: dict[str, Any], *, empty_message: str | None = None) -> str:
    memories = list(result.get("memories") or [])
    if not memories:
        return empty_message or "No Memory v2 entries matched."
    lines = [f"--- MEMORY V2 RECALL: {result.get('query', '')} ---"]
    for index, row in enumerate(memories, 1):
        tags = ", ".join(row.get("tags") or [])
        score = row.get("score", 0)
        lines.append(
            f"{index}. {row.get('redacted_text') or row.get('text')} "
            f"(score={score}, importance={row.get('importance')}, tags={tags})"
        )
    return "\n".join(lines)


def _disabled_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "enabled": False,
        "message": "Memory v2 disabled. Set SHELL_MEMORY_V2_ENABLED=1 to enable the SQLite memory layer.",
    }


@function_tool(category="memory")
async def memory_v2_save_tool(text: str, tags: str = "", importance: int = -1) -> dict[str, Any]:
    """
    Save a redacted, tagged Memory v2 entry in the local SQLite store.
    Args:
        text: Important information to remember.
        tags: Optional comma/space separated tags.
        importance: Optional 0-100 importance score. Use -1 for automatic scoring.
    """
    if not memory_v2_enabled():
        return _disabled_payload()
    return save_memory(
        text,
        tags=normalize_tags(tags),
        importance=_importance_or_none(importance),
        source="tool",
    )


@function_tool(category="memory")
async def memory_v2_recall_tool(query: str, limit: int = 5, tags: str = "") -> dict[str, Any]:
    """
    Recall relevant Memory v2 entries with importance, recency decay, and tag filtering.
    Args:
        query: Search phrase.
        limit: Maximum number of memories to return.
        tags: Optional comma/space separated tags that must be present.
    """
    if not memory_v2_enabled():
        return _disabled_payload()
    return recall_memory(query, limit=max(1, int(limit)), tags=normalize_tags(tags))


@function_tool(category="memory")
async def memory_v2_forget_tool(memory_id: str = "", query: str = "", tag: str = "") -> dict[str, Any]:
    """
    Soft-delete Memory v2 entries by id, query, tag, or a combination of filters.
    Args:
        memory_id: Exact memory id to forget.
        query: Query terms to match before forgetting.
        tag: Tag that must exist on the memory.
    """
    if not memory_v2_enabled():
        return _disabled_payload()
    return forget_memory(memory_id=memory_id or None, query=query or None, tag=tag or None)


@function_tool(category="memory")
async def memory_v2_migrate_legacy_tool(legacy_path: str = "") -> dict[str, Any]:
    """
    Import legacy ~/.shell_smart_memory.json entries into Memory v2.
    Args:
        legacy_path: Optional path to a legacy JSON memory file.
    """
    if not memory_v2_enabled():
        return _disabled_payload()
    return migrate_legacy_memory(legacy_path or None)


@function_tool(category="memory")
async def memory_v2_status_tool() -> dict[str, Any]:
    """Return Memory v2 enablement, store path, counts, and recall audit size."""
    store = MemoryV2Store(default_memory_v2_path())
    return {"ok": True, **store.stats()}


__all__ = [
    "forget_memory",
    "format_recall_results",
    "memory_v2_enabled",
    "memory_v2_forget_tool",
    "memory_v2_migrate_legacy_tool",
    "memory_v2_recall_tool",
    "memory_v2_save_tool",
    "memory_v2_status_tool",
    "migrate_legacy_memory",
    "recall_memory",
    "save_memory",
]
