from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from .metadata import ToolMetadata, infer_tool_metadata


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


class CapabilityRegistry:
    """Typed capability view built from Shell's existing static catalog."""

    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = [dict(row) for row in rows]
        self._by_id = {str(row.get("id")): row for row in self._rows if row.get("id")}

    @classmethod
    def from_catalog(cls, rows: list[dict[str, Any]]) -> "CapabilityRegistry":
        enriched = enrich_catalog(rows)
        return cls(enriched)

    def all(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows]

    def get(self, tool_id: str) -> dict[str, Any] | None:
        row = self._by_id.get(str(tool_id))
        return dict(row) if row else None

    def filter(
        self,
        *,
        category: str | None = None,
        state: str | None = None,
        kind: str | None = None,
        enabled_only: bool = True,
    ) -> list[dict[str, Any]]:
        rows = self._rows
        if category:
            rows = [row for row in rows if row.get("category") == category]
        if kind:
            rows = [row for row in rows if row.get("kind") == kind]
        if state:
            rows = [row for row in rows if (row.get("readiness") or {}).get("state") == state]
        if enabled_only:
            rows = [row for row in rows if (row.get("metadata") or {}).get("enabled", True)]
        return [dict(row) for row in rows]

    def rank(self, query: str, *, category: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        tokens = [t for t in _norm(query).split() if t]
        candidates = self.filter(category=category, enabled_only=True)
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in candidates:
            haystack = _norm(" ".join(str(row.get(k, "")) for k in ("id", "name", "title", "description", "category")))
            lexical = sum(1.0 for token in tokens if token in haystack)
            if tokens and lexical == 0:
                continue
            meta = row.get("metadata") or {}
            readiness = row.get("readiness") or {}
            ready_bonus = 2.0 if readiness.get("ok") else -2.0
            reliability = float(meta.get("reliability_score", 0.5))
            latency = float(meta.get("latency_score", 0.5))
            reputation = 0.0
            try:
                from core.tools.reputation import ToolReputationStore

                reputation = ToolReputationStore().routing_adjustment(str(row.get("id") or ""))
            except Exception:
                reputation = 0.0
            score = lexical + ready_bonus + reliability - latency + reputation
            out = dict(row)
            out["rank_score"] = round(score, 3)
            scored.append((score, out))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _score, row in scored[:limit]]

    def duplicates(self) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self._rows:
            key = _duplicate_key(row)
            groups[key].append(row)
        return [
            {
                "group": key,
                "count": len(rows),
                "tools": [row.get("id") for row in rows],
            }
            for key, rows in sorted(groups.items())
            if len(rows) > 1
        ]


def _duplicate_key(row: dict[str, Any]) -> str:
    title = _norm(str(row.get("title") or row.get("name") or ""))
    category = str(row.get("category") or "general")
    return f"{category}:{title}"


def enrich_catalog(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    counts = Counter(_duplicate_key(row) for row in rows)
    for row in rows:
        item = dict(row)
        metadata: ToolMetadata = infer_tool_metadata(item)
        meta_dict = metadata.to_dict()
        duplicate_group = _duplicate_key(item)
        if counts[duplicate_group] > 1:
            meta_dict["duplicate_group"] = duplicate_group
        item["metadata"] = meta_dict
        item["readiness"] = meta_dict["readiness"]
        item["runtime_state"] = meta_dict["readiness"]["state"]
        item["enabled"] = meta_dict["enabled"]
        enriched.append(item)
    return enriched


def capability_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    state_counts = Counter((row.get("readiness") or {}).get("state", "UNKNOWN") for row in rows)
    safety_counts = Counter((row.get("metadata") or {}).get("safety_level", "unknown") for row in rows)
    online_counts = Counter((row.get("metadata") or {}).get("online_state", "unknown") for row in rows)
    registry = CapabilityRegistry(rows)
    return {
        "readiness_counts": dict(sorted(state_counts.items())),
        "safety_counts": dict(sorted(safety_counts.items())),
        "online_counts": dict(sorted(online_counts.items())),
        "duplicate_groups": registry.duplicates(),
    }
