from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event
from core.security import SecurityClass


class InteractionMode(str, Enum):
    CONVERSATION = "conversation"
    COMMAND = "command"
    VISUAL = "visual"
    VOICE = "voice"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class InteractionDecision:
    mode: InteractionMode
    action: str
    should_interrupt: bool
    requires_confirmation: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "action": self.action,
            "should_interrupt": self.should_interrupt,
            "requires_confirmation": self.requires_confirmation,
            "reasons": list(self.reasons),
        }


class InteractionEngine:
    def decide(
        self,
        *,
        mode: InteractionMode | str,
        security_class: SecurityClass | str = SecurityClass.SAFE,
        confidence: float = 0.5,
        user_idle: bool = False,
    ) -> InteractionDecision:
        mode_enum = mode if isinstance(mode, InteractionMode) else InteractionMode(str(mode))
        cls = security_class if isinstance(security_class, SecurityClass) else SecurityClass(str(security_class))
        reasons: list[str] = [f"confidence={round(float(confidence), 3)}", f"security={cls.value}"]
        if cls in {SecurityClass.RESTRICTED, SecurityClass.CRITICAL}:
            decision = InteractionDecision(mode_enum, "confirm", True, True, [*reasons, "restricted action"])
        elif confidence < 0.45:
            decision = InteractionDecision(mode_enum, "ask", user_idle, False, [*reasons, "low confidence"])
        elif mode_enum in {InteractionMode.VISUAL, InteractionMode.VOICE}:
            decision = InteractionDecision(mode_enum, "preview", False, True, [*reasons, "interactive mode requires explicit approval"])
        else:
            decision = InteractionDecision(mode_enum, "automate", False, False, reasons)
        publish_event(AIEventType.INTERACTION_DECISION, decision.to_dict(), source="core.interaction")
        return decision

