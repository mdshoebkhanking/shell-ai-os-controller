from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class StateSnapshot:
    snapshot_id: str
    label: str
    state: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    rollback_parent: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, "label": self.label, "state": dict(self.state), "created_at": self.created_at, "rollback_parent": self.rollback_parent}


class OperatingStateEngine:
    def __init__(self, path: str | Path = ".shell_runtime/state_snapshots.json"):
        self.path = Path(path)

    def snapshot(self, label: str, state: dict[str, Any], *, rollback_parent: str = "") -> StateSnapshot:
        snap = StateSnapshot(uuid.uuid4().hex, label, dict(state), time.time(), rollback_parent)
        data = self._load()
        data.setdefault("snapshots", []).append(snap.to_dict())
        self._write(data)
        publish_event(AIEventType.STATE_SNAPSHOT_CREATED, snap.to_dict(), source="core.state_engine")
        return snap

    def latest(self) -> StateSnapshot | None:
        rows = self._load().get("snapshots", [])
        return self._from_row(rows[-1]) if rows else None

    def replay(self) -> list[dict[str, Any]]:
        rows = list(self._load().get("snapshots", []))
        rows.sort(key=lambda row: row.get("created_at", 0.0))
        return rows

    def rollback_plan(self, snapshot_id: str) -> dict[str, Any]:
        rows = [row for row in self._load().get("snapshots", []) if row.get("snapshot_id") == snapshot_id]
        return {"status": "preview", "requires_confirmation": True, "target": rows[0] if rows else None}

    def _from_row(self, row: dict[str, Any]) -> StateSnapshot:
        return StateSnapshot(str(row.get("snapshot_id") or ""), str(row.get("label") or ""), dict(row.get("state") or {}), float(row.get("created_at", 0.0)), str(row.get("rollback_parent") or ""))

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"snapshots": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"snapshots": []}
        except Exception:
            return {"snapshots": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

