from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class ReasoningDepth(str, Enum):
    FAST = "FAST"
    STANDARD = "STANDARD"
    DEEP = "DEEP"


@dataclass(frozen=True)
class ReasoningProfile:
    depth: ReasoningDepth
    complexity_score: float
    confidence: float
    model_hint: str
    validation_required: bool
    max_tool_calls: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "depth": self.depth.value,
            "complexity_score": self.complexity_score,
            "confidence": self.confidence,
            "model_hint": self.model_hint,
            "validation_required": self.validation_required,
            "max_tool_calls": self.max_tool_calls,
            "reasons": list(self.reasons),
        }


class AdaptiveReasoningEngine:
    COMPLEXITY_TERMS = ("refactor", "architecture", "debug", "multi-step", "production", "security", "distributed", "workflow")
    UNCERTAINTY_TERMS = ("maybe", "unknown", "unclear", "failing", "error", "intermittent", "ambiguous")

    def estimate_complexity(self, goal: str, signals: dict[str, Any] | None = None) -> float:
        text = f"{goal} {signals or {}}".lower()
        score = min(1.0, len(str(goal or "")) / 600.0)
        score += 0.08 * sum(1 for term in self.COMPLEXITY_TERMS if term in text)
        if int((signals or {}).get("steps", 0) or 0) >= 3:
            score += 0.2
        if (signals or {}).get("risky"):
            score += 0.15
        return round(max(0.0, min(1.0, score)), 3)

    def uncertainty(self, goal: str, signals: dict[str, Any] | None = None) -> float:
        text = f"{goal} {signals or {}}".lower()
        score = 0.1 + 0.12 * sum(1 for term in self.UNCERTAINTY_TERMS if term in text)
        if (signals or {}).get("missing_context"):
            score += 0.25
        return round(max(0.0, min(1.0, score)), 3)

    def select_profile(self, goal: str, signals: dict[str, Any] | None = None) -> ReasoningProfile:
        complexity = self.estimate_complexity(goal, signals)
        uncertainty = self.uncertainty(goal, signals)
        confidence = round(max(0.1, 1.0 - (uncertainty * 0.65)), 3)
        reasons = [f"complexity={complexity}", f"uncertainty={uncertainty}"]
        if complexity >= 0.7 or uncertainty >= 0.5:
            profile = ReasoningProfile(ReasoningDepth.DEEP, complexity, confidence, "reasoning", True, 12, reasons)
        elif complexity >= 0.35:
            profile = ReasoningProfile(ReasoningDepth.STANDARD, complexity, confidence, "balanced", True, 6, reasons)
        else:
            profile = ReasoningProfile(ReasoningDepth.FAST, complexity, confidence, "lightweight", False, 2, reasons)
        publish_event(AIEventType.REASONING_PROFILE_SELECTED, profile.to_dict(), source="core.reasoning")
        return profile

