from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class SemanticWorkflowStep:
    intent: str
    action: str
    meaning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"intent": self.intent, "action": self.action, "meaning": self.meaning}


@dataclass(frozen=True)
class SemanticWorkflow:
    workflow_id: str
    name: str
    goal: str
    steps: list[SemanticWorkflowStep] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {"workflow_id": self.workflow_id, "name": self.name, "goal": self.goal, "steps": [step.to_dict() for step in self.steps], "confidence": self.confidence}


class SemanticWorkflowEngine:
    def compose(self, name: str, goal: str, steps: list[dict[str, Any]]) -> SemanticWorkflow:
        parsed = [SemanticWorkflowStep(str(row.get("intent") or ""), str(row.get("action") or ""), str(row.get("meaning") or "")) for row in steps]
        confidence = min(1.0, 0.4 + len(parsed) * 0.1)
        workflow = SemanticWorkflow(uuid.uuid4().hex, name, goal, parsed, confidence)
        publish_event(AIEventType.SEMANTIC_WORKFLOW_UPDATED, workflow.to_dict(), source="core.semantic_workflows")
        return workflow

    def predict_refinement(self, workflow: SemanticWorkflow, *, failures: list[str] | None = None) -> dict[str, Any]:
        failures = list(failures or [])
        suggestions = []
        if failures:
            suggestions.append("add validation step before failing action")
        if workflow.confidence < 0.7:
            suggestions.append("ask user to confirm workflow intent")
        result = {"workflow_id": workflow.workflow_id, "suggestions": suggestions, "failure_count": len(failures)}
        publish_event(AIEventType.SEMANTIC_WORKFLOW_UPDATED, {"refinement": result}, source="core.semantic_workflows")
        return result

