from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    condition: str = ""
    retry_limit: int = 0
    rollback: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"step_id": self.step_id, "action": self.action, "params": dict(self.params), "condition": self.condition, "retry_limit": self.retry_limit, "rollback": self.rollback}


@dataclass(frozen=True)
class Workflow:
    workflow_id: str
    name: str
    trigger: str
    steps: list[WorkflowStep]

    def to_dict(self) -> dict[str, Any]:
        return {"workflow_id": self.workflow_id, "name": self.name, "trigger": self.trigger, "steps": [s.to_dict() for s in self.steps]}


class WorkflowEngine:
    def __init__(self, handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None):
        self.handlers = dict(handlers or {})

    def create(self, name: str, trigger: str, steps: list[dict[str, Any]]) -> Workflow:
        workflow = Workflow(
            workflow_id=uuid.uuid4().hex,
            name=name,
            trigger=trigger,
            steps=[
                WorkflowStep(
                    step_id=str(row.get("step_id") or uuid.uuid4().hex),
                    action=str(row.get("action") or ""),
                    params=dict(row.get("params") or {}),
                    condition=str(row.get("condition") or ""),
                    retry_limit=int(row.get("retry_limit", 0)),
                    rollback=str(row.get("rollback") or ""),
                )
                for row in steps
            ],
        )
        return workflow

    def run(self, workflow: Workflow, context: dict[str, Any] | None = None) -> dict[str, Any]:
        publish_event(AIEventType.WORKFLOW_STARTED, workflow.to_dict(), source="core.workflows")
        context = dict(context or {})
        results = []
        for step in workflow.steps:
            if step.condition and not self._condition(step.condition, context):
                results.append({"step_id": step.step_id, "status": "skipped"})
                continue
            handler = self.handlers.get(step.action)
            if not handler:
                return {"status": "failed", "step_id": step.step_id, "error": f"no handler for {step.action}", "results": results}
            attempts = 0
            while attempts <= step.retry_limit:
                attempts += 1
                result = handler(step.params)
                if result.get("status") == "success":
                    results.append({"step_id": step.step_id, "status": "success", "result": result})
                    break
                if attempts > step.retry_limit:
                    return {"status": "failed", "step_id": step.step_id, "error": result.get("error") or result.get("message"), "results": results}
        out = {"status": "success", "workflow_id": workflow.workflow_id, "completed_at": time.time(), "results": results}
        publish_event(AIEventType.WORKFLOW_COMPLETED, out, source="core.workflows")
        return out

    def _condition(self, condition: str, context: dict[str, Any]) -> bool:
        if "==" in condition:
            key, expected = [part.strip().strip("'\"") for part in condition.split("==", 1)]
            return str(context.get(key)) == expected
        return bool(context.get(condition))

