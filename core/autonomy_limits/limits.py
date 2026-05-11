from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class AutonomyLevel(str, Enum):
    RECOMMEND = "RECOMMEND"
    ASSIST = "ASSIST"
    APPROVED_AUTOMATION = "APPROVED_AUTOMATION"
    BLOCKED = "BLOCKED"


class TrustZone(str, Enum):
    SAFE = "SAFE"
    USER_APPROVED = "USER_APPROVED"
    RESTRICTED = "RESTRICTED"
    SHUTDOWN = "SHUTDOWN"


@dataclass(frozen=True)
class AutonomyBoundary:
    level: AutonomyLevel
    zone: TrustZone
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    human_override_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "zone": self.zone.value,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "human_override_available": self.human_override_available,
        }


class AutonomyBoundarySystem:
    def classify(self, action: str, *, approved: bool = False, emergency_stop: bool = False) -> AutonomyBoundary:
        text = str(action or "").lower()
        if emergency_stop:
            boundary = AutonomyBoundary(AutonomyLevel.BLOCKED, TrustZone.SHUTDOWN, False, ["emergency shutdown active"], True)
        elif any(term in text for term in ("self-modify", "permission", "bypass", "unrestricted", "silent")):
            boundary = AutonomyBoundary(AutonomyLevel.BLOCKED, TrustZone.RESTRICTED, False, ["attempted autonomy boundary violation"], True)
        elif any(term in text for term in ("execute", "write", "desktop", "shell")):
            boundary = AutonomyBoundary(AutonomyLevel.APPROVED_AUTOMATION, TrustZone.USER_APPROVED if approved else TrustZone.RESTRICTED, approved, ["requires explicit approval"])
        else:
            boundary = AutonomyBoundary(AutonomyLevel.ASSIST, TrustZone.SAFE, True, [])
        publish_event(AIEventType.AUTONOMY_BOUNDARY_DECISION, boundary.to_dict(), source="core.autonomy_limits")
        return boundary

