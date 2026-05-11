from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class CollaborationProposal:
    proposal_id: str
    goal: str
    steps: list[str] = field(default_factory=list)
    confidence: float = 0.5
    uncertainty: str = ""
    requires_approval: bool = True
    suggestion_score: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "goal": self.goal,
            "steps": list(self.steps),
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "requires_approval": self.requires_approval,
            "suggestion_score": self.suggestion_score,
        }


class CollaborationAIEngine:
    def propose(self, goal: str, *, context: dict[str, Any] | None = None, confidence: float = 0.5) -> CollaborationProposal:
        uncertainty = "low" if confidence >= 0.75 else "medium" if confidence >= 0.45 else "high"
        steps = ["confirm goal", "prepare plan", "execute approved steps", "summarize outcome"]
        if (context or {}).get("risky"):
            steps.insert(1, "run safety checkpoint")
        proposal = CollaborationProposal(
            uuid.uuid4().hex,
            goal,
            steps,
            max(0.0, min(1.0, float(confidence))),
            uncertainty,
            confidence < 0.85 or bool((context or {}).get("risky")),
            round(max(0.0, min(1.0, float(confidence))) * (0.8 if (context or {}).get("interrupting") else 1.0), 3),
        )
        publish_event(AIEventType.COLLABORATION_AI_DECISION, proposal.to_dict(), source="core.collaboration_ai")
        return proposal

    def approval_record(self, proposal: CollaborationProposal, *, approved: bool, approver: str = "user") -> dict[str, Any]:
        record = {"proposal_id": proposal.proposal_id, "approved": bool(approved), "approver": approver}
        publish_event(AIEventType.COLLABORATION_AI_DECISION, {"approval": record}, source="core.collaboration_ai")
        return record

