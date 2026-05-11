from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event
from core.security import SecurityModel


@dataclass(frozen=True)
class AutomationAction:
    action_id: str
    kind: str
    target: str
    params: dict[str, Any] = field(default_factory=dict)
    reversible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"action_id": self.action_id, "kind": self.kind, "target": self.target, "params": dict(self.params), "reversible": self.reversible}


@dataclass(frozen=True)
class AutomationPlan:
    plan_id: str
    title: str
    actions: list[AutomationAction]
    requires_confirmation: bool
    risk: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "actions": [action.to_dict() for action in self.actions],
            "requires_confirmation": self.requires_confirmation,
            "risk": self.risk,
        }


class TrustedAutomationLayer:
    def __init__(self, audit_path: str | Path = ".shell_runtime/automation_audit.jsonl"):
        self.audit_path = Path(audit_path)

    def preview(self, title: str, actions: list[dict[str, Any]]) -> AutomationPlan:
        parsed = [
            AutomationAction(
                action_id=str(row.get("action_id") or uuid.uuid4().hex),
                kind=str(row.get("kind") or ""),
                target=str(row.get("target") or ""),
                params=dict(row.get("params") or {}),
                reversible=bool(row.get("reversible", False)),
            )
            for row in actions
        ]
        risk_scores = [SecurityModel().classify(action.kind, {"target": action.target, **action.params}) for action in parsed]
        severity = {"SAFE": 0, "ELEVATED": 1, "RESTRICTED": 2, "CRITICAL": 3}
        risk = max((decision.security_class.value for decision in risk_scores), key=lambda value: severity.get(value, 0), default="SAFE")
        requires_confirmation = any(not decision.allowed or decision.requires_secure_mode for decision in risk_scores) or bool(parsed)
        plan = AutomationPlan(uuid.uuid4().hex, title, parsed, requires_confirmation, risk)
        publish_event(AIEventType.AUTOMATION_PREVIEWED, plan.to_dict(), source="core.automation")
        self.audit("preview", plan.to_dict())
        return plan

    def dry_run(self, plan: AutomationPlan) -> dict[str, Any]:
        return {"status": "dry_run", "plan": plan.to_dict(), "would_execute": [a.to_dict() for a in plan.actions]}

    def audit(self, event: str, payload: dict[str, Any]) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"ts": time.time(), "event": event, "payload": payload}, ensure_ascii=False, default=str) + "\n")
