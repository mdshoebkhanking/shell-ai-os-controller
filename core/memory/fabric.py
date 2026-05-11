from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .store import LocalMemoryStore


@dataclass(frozen=True)
class MemoryQuery:
    query: str
    layers: list[str]
    limit: int = 10


class MemoryFabric:
    LAYERS = {
        "active": "conversation",
        "semantic": "semantic",
        "execution": "tool_success",
        "skill": "procedural",
        "workflow": "workflow",
        "project": "semantic",
        "incident": "failure",
    }

    def __init__(self, store: LocalMemoryStore | None = None):
        self.store = store or LocalMemoryStore()

    def retrieve(self, query: MemoryQuery) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        now = time.time()
        for layer in query.layers:
            namespace = self.LAYERS.get(layer, layer)
            for row in self.store.search(query.query, namespace=namespace, limit=query.limit):
                age_s = max(0.0, now - float(row.get("created_at", now)))
                temporal = 1.0 / (1.0 + age_s / 86400.0)
                row["layer"] = layer
                row["temporal_score"] = round(temporal, 3)
                row["rank"] = round(float(row.get("score", 0)) + temporal, 3)
                rows.append(row)
        rows.sort(key=lambda row: row.get("rank", 0), reverse=True)
        return rows[: query.limit]

    def resolve_conflicts(self, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_text: dict[str, dict[str, Any]] = {}
        for row in memories:
            key = str(row.get("text") or "").strip().lower()
            if not key:
                continue
            current = by_text.get(key)
            if not current or row.get("rank", 0) > current.get("rank", 0):
                by_text[key] = row
        return sorted(by_text.values(), key=lambda row: row.get("rank", 0), reverse=True)

