from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DecisionExplanation:
    summary: str
    confidence: float
    factors: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "confidence": self.confidence,
            "factors": list(self.factors),
            "diagnostics": dict(self.diagnostics),
        }


def explain_tool_choice(route: dict[str, Any], alternatives: list[dict[str, Any]] | None = None) -> DecisionExplanation:
    tool = route.get("tool") or route.get("id") or "unknown"
    readiness = route.get("readiness") or {}
    factors = [
        f"matched route/tool id: {tool}",
        f"confidence: {route.get('confidence', 'unknown')}",
    ]
    if readiness:
        factors.append(f"runtime state: {readiness.get('state')}")
        if readiness.get("reasons"):
            factors.extend(str(r) for r in readiness.get("reasons", [])[:3])
    if alternatives:
        factors.append(f"alternatives considered: {len(alternatives)}")
    return DecisionExplanation(
        summary=f"Selected {tool} because it best matched the request and current readiness constraints.",
        confidence=float(route.get("confidence", 0.5) or 0.5),
        factors=factors,
        diagnostics={"readiness": readiness, "alternatives": alternatives or []},
    )


def explain_failure(result: dict[str, Any]) -> DecisionExplanation:
    state = result.get("state") or result.get("status") or "unknown"
    reasons = [str(r) for r in result.get("reasons", [])]
    message = str(result.get("message") or result.get("error") or "execution failed")
    factors = [message, *reasons]
    return DecisionExplanation(
        summary=f"Execution did not complete because the runtime reported {state}.",
        confidence=0.8 if reasons else 0.55,
        factors=factors,
        diagnostics=dict(result),
    )

