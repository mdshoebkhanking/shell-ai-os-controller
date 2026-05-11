from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event
from core.security import SecurityClass, SecurityModel


@dataclass(frozen=True)
class SafetyCheckpoint:
    action: str
    intent: str
    risk_score: float
    security_class: SecurityClass
    allowed: bool
    requires_approval: bool
    reasons: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "intent": self.intent,
            "risk_score": self.risk_score,
            "security_class": self.security_class.value,
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "reasons": list(self.reasons),
            "created_at": self.created_at,
        }


class HighTrustSafetyFramework:
    RISK_BY_CLASS = {
        SecurityClass.SAFE: 0.1,
        SecurityClass.ELEVATED: 0.45,
        SecurityClass.RESTRICTED: 0.75,
        SecurityClass.CRITICAL: 1.0,
    }

    def evaluate(self, action: str, *, intent: str = "", metadata: dict[str, Any] | None = None) -> SafetyCheckpoint:
        decision = SecurityModel().classify(action, metadata)
        risk = self.RISK_BY_CLASS[decision.security_class]
        if not intent.strip():
            risk = min(1.0, risk + 0.15)
        checkpoint = SafetyCheckpoint(
            action=str(action),
            intent=str(intent),
            risk_score=round(risk, 3),
            security_class=decision.security_class,
            allowed=decision.allowed and risk < 0.75,
            requires_approval=risk >= 0.45 or decision.requires_secure_mode,
            reasons=list(decision.reasons) + ([] if intent.strip() else ["missing explicit intent"]),
        )
        publish_event(AIEventType.SAFETY_CHECKPOINT, checkpoint.to_dict(), source="core.safety")
        return checkpoint

