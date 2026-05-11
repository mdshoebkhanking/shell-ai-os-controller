from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class RecoveryCheckpoint:
    checkpoint_id: str
    scope: str
    state: dict[str, Any]
    distributed: bool = True
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"checkpoint_id": self.checkpoint_id, "scope": self.scope, "state": dict(self.state), "distributed": self.distributed, "ts": self.ts}


class DisasterRecoveryEngine:
    def __init__(self):
        self._checkpoints: list[RecoveryCheckpoint] = []

    def checkpoint(self, scope: str, state: dict[str, Any]) -> RecoveryCheckpoint:
        cp = RecoveryCheckpoint(uuid.uuid4().hex, scope, dict(state))
        self._checkpoints.append(cp)
        publish_event(AIEventType.DISASTER_RECOVERY_DECISION, {"checkpoint": cp.to_dict()}, source="core.disaster_recovery")
        return cp

    def recover(self, incident: dict[str, Any]) -> dict[str, Any]:
        kind = str(incident.get("kind") or "")
        latest = self._checkpoints[-1].to_dict() if self._checkpoints else None
        if kind in {"cluster_crash", "network_partition"}:
            action = "rebuild_topology"
        elif kind in {"corrupted_workflow", "orchestration_failure"}:
            action = "restore_workflow"
        else:
            action = "manual_recovery"
        plan = {"incident": dict(incident), "action": action, "checkpoint": latest, "requires_confirmation": True}
        publish_event(AIEventType.DISASTER_RECOVERY_DECISION, {"plan": plan}, source="core.disaster_recovery")
        return plan

    def replay_state(self, checkpoint_id: str) -> dict[str, Any]:
        rows = [cp for cp in self._checkpoints if cp.checkpoint_id == checkpoint_id]
        return {"status": "preview", "checkpoint": rows[0].to_dict() if rows else None, "requires_confirmation": True}

