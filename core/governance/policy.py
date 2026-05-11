from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event
from core.security import SecurityClass, SecurityModel


@dataclass(frozen=True)
class ExecutionContract:
    action: str
    actor: str
    permissions: list[str] = field(default_factory=list)
    zone: str = "standard"
    reversible: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "actor": self.actor,
            "permissions": list(self.permissions),
            "zone": self.zone,
            "reversible": self.reversible,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class GovernanceDecision:
    allowed: bool
    requires_approval: bool
    policy: str
    reasons: list[str] = field(default_factory=list)
    security_class: str = "SAFE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "policy": self.policy,
            "reasons": list(self.reasons),
            "security_class": self.security_class,
        }


class GovernanceEngine:
    RESTRICTED_PERMISSIONS = {"shell.execute", "desktop.control", "filesystem.write", "api.keys"}

    def evaluate(self, contract: ExecutionContract) -> GovernanceDecision:
        security = SecurityModel().classify(contract.action, {"permissions": contract.permissions, **contract.metadata})
        reasons = list(security.reasons)
        restricted_perms = sorted(set(contract.permissions) & self.RESTRICTED_PERMISSIONS)
        if restricted_perms:
            reasons.append(f"restricted permissions: {', '.join(restricted_perms)}")
        if contract.zone == "restricted" and not contract.reversible:
            reasons.append("restricted zone requires reversibility")
        allowed = security.allowed and not restricted_perms and not (contract.zone == "restricted" and not contract.reversible)
        requires_approval = not allowed or security.security_class in {SecurityClass.ELEVATED, SecurityClass.RESTRICTED, SecurityClass.CRITICAL}
        decision = GovernanceDecision(allowed, requires_approval, "default-governance", reasons, security.security_class.value)
        publish_event(AIEventType.GOVERNANCE_DECISION, {"contract": contract.to_dict(), "decision": decision.to_dict()}, source="core.governance")
        return decision

