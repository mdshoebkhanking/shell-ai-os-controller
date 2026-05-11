from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event
from core.security import SecurityModel


@dataclass(frozen=True)
class SecurityFabricDecision:
    allowed: bool
    trust_score: float
    threat_level: str
    isolation_required: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "trust_score": self.trust_score,
            "threat_level": self.threat_level,
            "isolation_required": self.isolation_required,
            "reasons": list(self.reasons),
        }


class SecurityFabric:
    def validate(self, subject: str, action: str, *, trust_score: float = 0.5, metadata: dict[str, Any] | None = None) -> SecurityFabricDecision:
        security = SecurityModel().classify(action, metadata)
        reasons = list(security.reasons)
        if trust_score < 0.5:
            reasons.append("trust below threshold")
        threat = "critical" if security.security_class.value == "CRITICAL" else "high" if security.requires_secure_mode or trust_score < 0.5 else "low"
        isolation = threat in {"high", "critical"} or bool((metadata or {}).get("plugin"))
        allowed = security.allowed and trust_score >= 0.5 and threat != "critical"
        decision = SecurityFabricDecision(allowed, round(max(0.0, min(1.0, float(trust_score))), 3), threat, isolation, reasons)
        publish_event(AIEventType.SECURITY_FABRIC_DECISION, {"subject": subject, "action": action, "decision": decision.to_dict()}, source="core.security_fabric")
        return decision

    def secure_channel_plan(self, source: str, target: str) -> dict[str, Any]:
        return {"source": source, "target": target, "encryption": "required", "mutual_trust_validation": True}

