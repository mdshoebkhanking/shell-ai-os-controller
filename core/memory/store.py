from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    namespace: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "namespace": self.namespace,
            "text": self.text,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


class LocalMemoryStore:
    """Simple JSON-backed local memory with vector-DB hooks left external."""

    DEFAULT_NAMESPACES = {
        "conversation",
        "episodic",
        "failure",
        "procedural",
        "semantic",
        "workflow",
        "tool_success",
        "user_preference",
    }

    def __init__(self, path: str | Path = ".shell_memory_store.json"):
        self.path = Path(path)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"records": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"records": []}
        except Exception:
            return {"records": []}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def remember(self, namespace: str, text: str, metadata: dict[str, Any] | None = None) -> MemoryRecord:
        ns = str(namespace or "conversation").strip() or "conversation"
        record = MemoryRecord(
            record_id=uuid.uuid4().hex,
            namespace=ns,
            text=str(text or ""),
            metadata=dict(metadata or {}),
        )
        data = self._load()
        records = data.setdefault("records", [])
        records.append(record.to_dict())
        self._write(data)
        return record

    def search(self, query: str, *, namespace: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        data = self._load()
        tokens = {t.lower() for t in str(query or "").split() if t.strip()}
        rows = []
        for row in data.get("records", []):
            if namespace and row.get("namespace") != namespace:
                continue
            text = str(row.get("text") or "")
            haystack = text.lower()
            score = sum(1 for token in tokens if token in haystack)
            if tokens and score <= 0:
                continue
            out = dict(row)
            out["score"] = score
            rows.append(out)
        rows.sort(key=lambda r: (r.get("score", 0), r.get("created_at", 0)), reverse=True)
        return rows[: max(0, int(limit))]

    def remember_episode(self, text: str, metadata: dict[str, Any] | None = None) -> MemoryRecord:
        return self.remember("episodic", text, metadata)

    def remember_procedure(self, text: str, metadata: dict[str, Any] | None = None) -> MemoryRecord:
        return self.remember("procedural", text, metadata)

    def remember_semantic(self, text: str, metadata: dict[str, Any] | None = None) -> MemoryRecord:
        return self.remember("semantic", text, metadata)

    def remember_failure(self, text: str, metadata: dict[str, Any] | None = None) -> MemoryRecord:
        return self.remember("failure", text, metadata)

    def summarize(self, *, namespace: str | None = None, limit: int = 20, max_chars: int = 1800) -> str:
        data = self._load()
        rows = [
            row for row in data.get("records", [])
            if namespace is None or row.get("namespace") == namespace
        ]
        rows.sort(key=lambda row: row.get("created_at", 0), reverse=True)
        lines = []
        for row in rows[: max(0, int(limit))]:
            lines.append(f"{row.get('namespace')}: {row.get('text')}")
        return "\n".join(lines)[:max_chars]

    def compact(self, *, namespace: str | None = None, keep: int = 200) -> int:
        data = self._load()
        rows = data.get("records", [])
        selected = [
            row for row in rows
            if namespace is None or row.get("namespace") == namespace
        ]
        selected.sort(key=lambda row: row.get("created_at", 0), reverse=True)
        keep_ids = {row.get("record_id") for row in selected[: max(0, int(keep))]}
        if namespace is None:
            new_rows = [row for row in rows if row.get("record_id") in keep_ids]
        else:
            new_rows = [
                row for row in rows
                if row.get("namespace") != namespace or row.get("record_id") in keep_ids
            ]
        removed = len(rows) - len(new_rows)
        if removed:
            data["records"] = new_rows
            self._write(data)
        return removed

    def record_tool_result(self, tool_id: str, ok: bool, latency_ms: float, metadata: dict[str, Any] | None = None) -> MemoryRecord:
        return self.remember(
            "tool_success",
            f"{tool_id} ok={bool(ok)} latency_ms={round(float(latency_ms), 2)}",
            {"tool_id": tool_id, "ok": bool(ok), "latency_ms": latency_ms, **dict(metadata or {})},
        )
