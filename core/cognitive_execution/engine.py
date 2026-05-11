from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event
from core.reasoning import AdaptiveReasoningEngine


@dataclass(frozen=True)
class CognitiveExecutionPlan:
    plan_id: str
    goal: str
    strategy: str
    reasoning_depth: str
    runtime_hint: str
    tool_chain: list[str] = field(default_factory=list)
    confidence: float = 0.5
    requires_validation: bool = True
    uncertainty_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "strategy": self.strategy,
            "reasoning_depth": self.reasoning_depth,
            "runtime_hint": self.runtime_hint,
            "tool_chain": list(self.tool_chain),
            "confidence": self.confidence,
            "requires_validation": self.requires_validation,
            "uncertainty_notes": list(self.uncertainty_notes),
        }


class CognitiveExecutionEngine:
    def plan(self, goal: str, *, context: dict[str, Any] | None = None, available_tools: list[str] | None = None) -> CognitiveExecutionPlan:
        profile = AdaptiveReasoningEngine().select_profile(goal, context or {})
        tools = list(available_tools or [])
        selected_tools = tools[: profile.max_tool_calls]
        strategy = "semantic_multi_step" if profile.validation_required or len(selected_tools) > 2 else "direct"
        uncertainty_notes = [] if profile.confidence >= 0.65 else ["low confidence, ask for clarification before risky execution"]
        plan = CognitiveExecutionPlan(
            uuid.uuid4().hex,
            goal,
            strategy,
            profile.depth.value,
            profile.model_hint,
            selected_tools,
            profile.confidence,
            profile.validation_required,
            uncertainty_notes,
        )
        publish_event(AIEventType.COGNITIVE_EXECUTION_PLANNED, plan.to_dict(), source="core.cognitive_execution")
        return plan

