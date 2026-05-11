from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class InteractionSignal:
    modality: str
    urgency: float = 0.0
    confidence: float = 0.5
    user_busy: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "modality": self.modality,
            "urgency": self.urgency,
            "confidence": self.confidence,
            "user_busy": self.user_busy,
            "metadata": dict(self.metadata),
            "ts": self.ts,
        }


class InteractionFabric:
    def select_channel(self, signals: list[InteractionSignal]) -> dict[str, Any]:
        if not signals:
            result = {"channel": "text", "interrupt": False, "reason": "default channel"}
        else:
            ranked = sorted(signals, key=lambda sig: (sig.urgency, sig.confidence), reverse=True)
            signal = ranked[0]
            interrupt = signal.urgency >= 0.8 and not signal.user_busy
            channel = "notification" if interrupt else signal.modality
            result = {"channel": channel, "interrupt": interrupt, "reason": f"selected {signal.modality} by urgency/confidence"}
        publish_event(AIEventType.INTERACTION_FABRIC_DECISION, result, source="core.interaction_fabric")
        return result

    def interruption_policy(self, signal: InteractionSignal) -> dict[str, Any]:
        policy = {
            "allow": signal.urgency >= 0.85 and not signal.user_busy,
            "defer": signal.user_busy and signal.urgency < 0.95,
            "reason": "urgent and user available" if signal.urgency >= 0.85 and not signal.user_busy else "defer or use passive channel",
        }
        publish_event(AIEventType.INTERACTION_FABRIC_DECISION, {"policy": policy, "signal": signal.to_dict()}, source="core.interaction_fabric")
        return policy

