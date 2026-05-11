from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class GovernanceApproval:
    approval_id: str
    action: str
    required_approvers: list[str] = field(default_factory=list)
    approved_by: list[str] = field(default_factory=list)
    propagated_nodes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"approval_id": self.approval_id, "action": self.action, "required_approvers": list(self.required_approvers), "approved_by": list(self.approved_by), "propagated_nodes": list(self.propagated_nodes)}


class DistributedGovernanceEngine:
    def request_chain(self, action: str, approvers: list[str], nodes: list[str]) -> GovernanceApproval:
        approval = GovernanceApproval(uuid.uuid4().hex, action, list(approvers), [], list(nodes))
        publish_event(AIEventType.DISTRIBUTED_GOVERNANCE_DECISION, {"request": approval.to_dict()}, source="core.distributed_governance")
        return approval

    def approve(self, approval: GovernanceApproval, approver: str) -> GovernanceApproval:
        approved_by = list(dict.fromkeys([*approval.approved_by, approver]))
        updated = GovernanceApproval(approval.approval_id, approval.action, list(approval.required_approvers), approved_by, list(approval.propagated_nodes))
        publish_event(AIEventType.DISTRIBUTED_GOVERNANCE_DECISION, {"approval": updated.to_dict(), "complete": self.is_complete(updated)}, source="core.distributed_governance")
        return updated

    def is_complete(self, approval: GovernanceApproval) -> bool:
        return set(approval.required_approvers) <= set(approval.approved_by)

    def dashboard(self, approvals: list[GovernanceApproval]) -> dict[str, Any]:
        return {"approvals": [a.to_dict() for a in approvals], "policy_propagation": True, "human_override": True}

