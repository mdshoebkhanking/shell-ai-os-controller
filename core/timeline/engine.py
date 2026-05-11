from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class TemporalRecord:
    record_id: str
    project: str
    event_type: str
    summary: str
    ts: float = field(default_factory=time.time)
    snapshot: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "project": self.project,
            "event_type": self.event_type,
            "summary": self.summary,
            "ts": self.ts,
            "snapshot": dict(self.snapshot),
            "tags": list(self.tags),
        }


class TimelineEngine:
    def __init__(self, path: str | Path = ".shell_runtime/timeline.json"):
        self.path = Path(path)

    def record(self, project: str, event_type: str, summary: str, *, snapshot: dict[str, Any] | None = None, tags: list[str] | None = None) -> TemporalRecord:
        record = TemporalRecord(uuid.uuid4().hex, project, event_type, summary, time.time(), dict(snapshot or {}), list(tags or []))
        data = self._load()
        data.setdefault("records", []).append(record.to_dict())
        self._write(data)
        publish_event(AIEventType.TIMELINE_RECORDED, record.to_dict(), source="core.timeline")
        return record

    def reconstruct(self, project: str, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = [row for row in self._load().get("records", []) if row.get("project") == project]
        rows.sort(key=lambda row: row.get("ts", 0.0))
        return rows[-max(0, int(limit)):]

    def last_checkpoint(self, project: str) -> dict[str, Any] | None:
        rows = [row for row in self.reconstruct(project) if row.get("event_type") == "checkpoint"]
        return rows[-1] if rows else None

    def semantic_search(self, query: str, *, project: str = "", limit: int = 10) -> list[dict[str, Any]]:
        tokens = {token.lower() for token in str(query or "").split() if token.strip()}
        rows = self._load().get("records", [])
        out = []
        for row in rows:
            if project and row.get("project") != project:
                continue
            hay = f"{row.get('summary')} {' '.join(row.get('tags') or [])}".lower()
            score = sum(1 for token in tokens if token in hay)
            if score:
                item = dict(row)
                item["score"] = score
                out.append(item)
        out.sort(key=lambda row: (row.get("score", 0), row.get("ts", 0.0)), reverse=True)
        return out[: max(0, int(limit))]

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"records": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"records": []}
        except Exception:
            return {"records": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

