from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event
from core.governance import ExecutionContract, GovernanceEngine


@dataclass(frozen=True)
class SelfOptimizationProposal:
    proposal_id: str
    target: str
    action: str
    reversible: bool
    allowed_by_policy: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "target": self.target,
            "action": self.action,
            "reversible": self.reversible,
            "allowed_by_policy": self.allowed_by_policy,
            "reasons": list(self.reasons),
        }


class SelfOptimizationEngine:
    def propose(self, target: str, action: str, *, reversible: bool = True) -> SelfOptimizationProposal:
        contract = ExecutionContract(action=action, actor="self_optimization", permissions=[], zone="standard", reversible=reversible)
        decision = GovernanceEngine().evaluate(contract)
        proposal = SelfOptimizationProposal(uuid.uuid4().hex, target, action, reversible, decision.allowed, decision.reasons)
        publish_event(AIEventType.SELF_OPTIMIZATION_PROPOSED, proposal.to_dict(), source="core.self_optimization")
        return proposal

