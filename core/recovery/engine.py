from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class Incident:
    incident_id: str
    kind: str
    target: str
    severity: str
    message: str
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "kind": self.kind,
            "target": self.target,
            "severity": self.severity,
            "message": self.message,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RecoveryAction:
    action: str
    allowed: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "allowed": self.allowed, "reason": self.reason, "metadata": dict(self.metadata)}


@dataclass(frozen=True)
class RecoveryPolicy:
    allow_restart: bool = False
    allow_quarantine: bool = True
    allow_provider_fallback: bool = True
    max_retries: int = 2


class RecoveryEngine:
    def __init__(self, path: str | Path = ".shell_runtime/incidents.json", policy: RecoveryPolicy | None = None):
        self.path = Path(path)
        self.policy = policy or RecoveryPolicy()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"incidents": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"incidents": []}
        except Exception:
            return {"incidents": []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def record_incident(self, kind: str, target: str, message: str, *, severity: str = "warning", metadata: dict[str, Any] | None = None) -> Incident:
        incident = Incident(uuid.uuid4().hex, kind, target, severity, message, metadata=dict(metadata or {}))
        data = self._load()
        data.setdefault("incidents", []).append(incident.to_dict())
        self._write(data)
        publish_event(AIEventType.INCIDENT_CREATED, incident.to_dict(), source="core.recovery")
        return incident

    def diagnose(self, incident: Incident) -> list[RecoveryAction]:
        actions: list[RecoveryAction] = []
        if incident.kind in {"runtime_crash", "stuck_task"}:
            actions.append(RecoveryAction("restart_runtime", self.policy.allow_restart, "runtime restart requires explicit policy"))
        if incident.kind in {"dead_api", "provider_failure"}:
            actions.append(RecoveryAction("fallback_provider", self.policy.allow_provider_fallback, "provider fallback is bounded"))
        if incident.kind in {"broken_plugin", "failed_worker"}:
            actions.append(RecoveryAction("quarantine", self.policy.allow_quarantine, "isolate unstable component"))
        if not actions:
            actions.append(RecoveryAction("manual_review", True, "no automatic recovery policy matched"))
        return actions

    def incidents(self) -> list[dict[str, Any]]:
        return list(self._load().get("incidents") or [])

