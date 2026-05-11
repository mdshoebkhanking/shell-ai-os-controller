from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class TransparencyNarrative:
    narrative_id: str
    title: str
    summary: str
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.5
    uncertainty: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "narrative_id": self.narrative_id,
            "title": self.title,
            "summary": self.summary,
            "reasons": list(self.reasons),
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "created_at": self.created_at,
        }


class TransparencyEngine:
    def explain(self, title: str, *, decision: dict[str, Any], alternatives: list[dict[str, Any]] | None = None) -> TransparencyNarrative:
        confidence = float(decision.get("confidence", decision.get("score", 0.5)) or 0.5)
        reasons = [str(reason) for reason in decision.get("reasons", [])]
        if alternatives:
            reasons.append(f"alternatives considered: {len(alternatives)}")
        uncertainty = "low" if confidence >= 0.75 else "medium" if confidence >= 0.45 else "high"
        narrative = TransparencyNarrative(
            uuid.uuid4().hex,
            title,
            str(decision.get("summary") or decision.get("reason") or "Decision was made from available structured signals."),
            reasons,
            max(0.0, min(1.0, confidence)),
            uncertainty,
        )
        publish_event(AIEventType.TRANSPARENCY_NARRATIVE_CREATED, narrative.to_dict(), source="core.transparency")
        return narrative

