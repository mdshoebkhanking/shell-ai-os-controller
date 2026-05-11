from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    action: str
    preview: dict[str, Any]
    risk: str = "unknown"
    reversible: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"request_id": self.request_id, "action": self.action, "preview": dict(self.preview), "risk": self.risk, "reversible": self.reversible, "created_at": self.created_at}


class HumanGovernanceLayer:
    def request_approval(self, action: str, preview: dict[str, Any], *, risk: str = "unknown", reversible: bool = False) -> ApprovalRequest:
        req = ApprovalRequest(uuid.uuid4().hex, action, dict(preview), risk, reversible)
        publish_event(AIEventType.HUMAN_GOVERNANCE_DECISION, {"request": req.to_dict()}, source="core.human_governance")
        return req

    def decide(self, request: ApprovalRequest, *, approved: bool, operator: str = "user") -> dict[str, Any]:
        decision = {"request_id": request.request_id, "approved": bool(approved), "operator": operator, "rollback_available": request.reversible}
        publish_event(AIEventType.HUMAN_GOVERNANCE_DECISION, {"decision": decision}, source="core.human_governance")
        return decision

    def governance_dashboard(self, pending: list[ApprovalRequest]) -> dict[str, Any]:
        return {"pending": [req.to_dict() for req in pending], "operator_control": True, "emergency_stop_available": True}

