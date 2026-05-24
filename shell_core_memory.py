from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from shell_safe_executor import god_tier_tool as function_tool


MEMORY_PATH = Path(os.environ.get("SHELL_CORE_MEMORY_PATH", "~/.shell_core_memory.json")).expanduser()


def _load() -> list[dict[str, Any]]:
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        return [row for row in data if isinstance(row, dict)]
    except Exception:
        return []


def _save(rows: list[dict[str, Any]]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = MEMORY_PATH.with_suffix(MEMORY_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(MEMORY_PATH)


def _score(row: dict[str, Any], query: str) -> int:
    if not query:
        return 1
    hay = " ".join(
        [
            str(row.get("fact", "")),
            " ".join(str(tag) for tag in row.get("tags", [])),
        ]
    ).lower()
    score = 0
    for word in query.lower().split():
        if word and word in hay:
            score += 2 if word in str(row.get("fact", "")).lower() else 1
    return score


@function_tool(category="knowledge")
async def shell_save_core_memory_tool(fact: str, tags: str = "") -> dict[str, Any]:
    """Save a durable Shell core memory fact with optional comma-separated tags."""
    fact = str(fact or "").strip()
    if not fact:
        return {"ok": False, "message": "Memory fact is required."}
    rows = _load()
    item = {
        "fact": fact,
        "tags": [tag.strip() for tag in str(tags or "").split(",") if tag.strip()],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rows.append(item)
    _save(rows)
    return {"ok": True, "saved": item, "count": len(rows), "path": str(MEMORY_PATH)}


@function_tool(category="knowledge")
async def shell_recall_core_memory_tool(query: str = "", limit: int = 8) -> dict[str, Any]:
    """Recall matching Shell core memories using a local low-latency lexical search."""
    rows = _load()
    scored = [(row, _score(row, query)) for row in rows]
    scored = [(row, score) for row, score in scored if score > 0]
    scored.sort(key=lambda pair: (pair[1], pair[0].get("created_at", "")), reverse=True)
    max_rows = max(1, min(int(limit or 8), 50))
    return {
        "ok": True,
        "query": query,
        "count": len(scored),
        "memories": [row for row, _score_value in scored[:max_rows]],
        "path": str(MEMORY_PATH),
    }
