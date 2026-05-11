from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import replay_events


@dataclass(frozen=True)
class TimelineEvent:
    event_type: str
    ts: float
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"event_type": self.event_type, "ts": self.ts, "source": self.source, "payload": dict(self.payload), "trace_id": self.trace_id}


class EventStream:
    def __init__(self, persistence_path: str | Path = ".shell_runtime/event_stream.jsonl"):
        self.persistence_path = Path(persistence_path)

    def current(self, *, limit: int = 200) -> list[TimelineEvent]:
        return [
            TimelineEvent(
                event_type=row.get("event_type", ""),
                ts=float(row.get("ts", 0.0)),
                source=row.get("source", ""),
                payload=dict(row.get("payload") or {}),
                trace_id=row.get("trace_id", ""),
            )
            for row in replay_events(limit=limit)
        ]

    def persist_current(self, *, limit: int = 200) -> int:
        events = self.current(limit=limit)
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        with self.persistence_path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False, default=str) + "\n")
        return len(events)

    def reconstruct(self, *, trace_id: str = "") -> list[dict[str, Any]]:
        rows = [event.to_dict() for event in self.current(limit=1000)]
        if trace_id:
            rows = [row for row in rows if row.get("trace_id") == trace_id]
        rows.sort(key=lambda row: row.get("ts", 0.0))
        return rows

