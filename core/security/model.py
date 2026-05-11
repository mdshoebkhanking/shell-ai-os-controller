from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class SecurityClass(str, Enum):
    SAFE = "SAFE"
    ELEVATED = "ELEVATED"
    RESTRICTED = "RESTRICTED"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class SecurityDecision:
    security_class: SecurityClass
    allowed: bool
    requires_secure_mode: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "security_class": self.security_class.value,
            "allowed": self.allowed,
            "requires_secure_mode": self.requires_secure_mode,
            "reasons": list(self.reasons),
        }


class SecurityModel:
    def classify(self, action: str, metadata: dict[str, Any] | None = None) -> SecurityDecision:
        text = f"{action} {metadata or {}}".lower()
        reasons: list[str] = []
        cls = SecurityClass.SAFE
        if any(w in text for w in ("registry", "credential", "secret", "delete", "kill", "shell.execute")):
            cls = SecurityClass.RESTRICTED
            reasons.append("sensitive system or secret operation")
        if any(w in text for w in ("format", "wipe", "self-modify", "hotpatch core", "unrestricted")):
            cls = SecurityClass.CRITICAL
            reasons.append("critical irreversible operation")
        elif any(w in text for w in ("network", "filesystem.write", "desktop.control", "plugin")) and cls == SecurityClass.SAFE:
            cls = SecurityClass.ELEVATED
            reasons.append("elevated permission requested")
        allowed = cls in {SecurityClass.SAFE, SecurityClass.ELEVATED}
        decision = SecurityDecision(cls, allowed, cls in {SecurityClass.RESTRICTED, SecurityClass.CRITICAL}, reasons)
        publish_event(AIEventType.SECURITY_DECISION, decision.to_dict(), source="core.security")
        return decision

