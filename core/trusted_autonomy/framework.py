from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.autonomy_limits import AutonomyBoundarySystem
from core.events import AIEventType, publish_event
from core.governance import ExecutionContract, GovernanceEngine


@dataclass(frozen=True)
class TrustedAutonomyDecision:
    allowed: bool
    zone: str
    autonomy_level: str
    requires_human_override: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "zone": self.zone,
            "autonomy_level": self.autonomy_level,
            "requires_human_override": self.requires_human_override,
            "reasons": list(self.reasons),
        }


class TrustedAutonomyFramework:
    def decide(self, action: str, *, approved: bool = False, emergency_stop: bool = False, contract: ExecutionContract | None = None) -> TrustedAutonomyDecision:
        boundary = AutonomyBoundarySystem().classify(action, approved=approved, emergency_stop=emergency_stop)
        governance = GovernanceEngine().evaluate(contract or ExecutionContract(action=action, actor="trusted_autonomy", reversible=approved))
        allowed = boundary.allowed and governance.allowed and not emergency_stop
        reasons = [*boundary.reasons, *governance.reasons]
        decision = TrustedAutonomyDecision(allowed, boundary.zone.value, boundary.level.value, not allowed or governance.requires_approval, reasons)
        publish_event(AIEventType.TRUSTED_AUTONOMY_DECISION, decision.to_dict(), source="core.trusted_autonomy")
        return decision

    def emergency_shutdown(self, reason: str = "operator requested") -> TrustedAutonomyDecision:
        decision = TrustedAutonomyDecision(False, "SHUTDOWN", "BLOCKED", True, [reason])
        publish_event(AIEventType.TRUSTED_AUTONOMY_DECISION, decision.to_dict(), source="core.trusted_autonomy")
        return decision

