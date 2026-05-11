from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.observability.events import emit_debug_event
from core.tools.registry import CapabilityRegistry


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    action: str
    tool_id: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    readiness: dict[str, Any] = field(default_factory=dict)
    timeout_s: float = 30.0
    retry_limit: int = 1
    rollback_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "tool_id": self.tool_id,
            "args": dict(self.args),
            "readiness": dict(self.readiness),
            "timeout_s": self.timeout_s,
            "retry_limit": self.retry_limit,
            "rollback_hint": self.rollback_hint,
        }


@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    goal: str
    created_at: float
    steps: list[PlanStep]
    status: str = "planned"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "created_at": self.created_at,
            "status": self.status,
            "notes": list(self.notes),
            "steps": [step.to_dict() for step in self.steps],
        }


class Planner:
    """Deterministic planner that preserves current router behavior.

    This is intentionally not an autonomous LLM planner. It turns a goal into
    a conservative execution plan and annotates readiness so callers can avoid
    hallucinated or unavailable tool calls.
    """

    def __init__(self, registry: CapabilityRegistry | None = None):
        self.registry = registry

    def plan(self, goal: str) -> ExecutionPlan:
        notes: list[str] = []
        steps: list[PlanStep] = []
        try:
            from shell_nl_router import route_natural_command

            route = route_natural_command(goal)
        except Exception as exc:
            route = None
            notes.append(f"router unavailable: {exc}")

        if route:
            tool_id = str(route.get("tool") or "")
            capability = self.registry.get(tool_id) if self.registry else None
            readiness = (capability or {}).get("readiness") or route.get("readiness") or {}
            if readiness and not readiness.get("ok", True):
                notes.append(f"selected tool is not ready: {readiness.get('state')}")
            steps.append(PlanStep(
                step_id=uuid.uuid4().hex,
                action=f"Run {tool_id}",
                tool_id=tool_id,
                args=dict(route.get("args") or {}),
                readiness=dict(readiness),
                retry_limit=1,
            ))
        else:
            notes.append("no deterministic route found; ask AI provider or user before executing tools")

        plan = ExecutionPlan(
            plan_id=uuid.uuid4().hex,
            goal=str(goal or ""),
            created_at=time.time(),
            steps=steps,
            status="planned" if steps else "needs_clarification",
            notes=notes,
        )
        emit_debug_event("planner.plan", "core.planner", plan.to_dict())
        return plan

