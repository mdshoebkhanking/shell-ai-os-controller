from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class SupervisionState:
    running_tasks: int = 0
    recursion_depth: int = 0
    loop_iterations: int = 0
    recent_failures: int = 0
    plugin_errors: int = 0
    queue_backlog: int = 0
    emergency_stop: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "running_tasks": self.running_tasks,
            "recursion_depth": self.recursion_depth,
            "loop_iterations": self.loop_iterations,
            "recent_failures": self.recent_failures,
            "plugin_errors": self.plugin_errors,
            "queue_backlog": self.queue_backlog,
            "emergency_stop": self.emergency_stop,
        }


@dataclass(frozen=True)
class SupervisionDecision:
    action: str
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    throttle_to: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "allowed": self.allowed, "reasons": list(self.reasons), "throttle_to": self.throttle_to}


class Supervisor:
    def evaluate(self, state: SupervisionState) -> SupervisionDecision:
        reasons: list[str] = []
        if state.emergency_stop:
            decision = SupervisionDecision("stop_all", False, ["emergency stop active"], 0)
        elif state.recursion_depth > 3 or state.loop_iterations > 100:
            reasons.append("runaway recursion or loop risk")
            decision = SupervisionDecision("stop_workflow", False, reasons, 0)
        elif state.recent_failures >= 5 or state.plugin_errors >= 3:
            reasons.append("high failure rate")
            decision = SupervisionDecision("quarantine_and_throttle", False, reasons, 1)
        elif state.queue_backlog > 50:
            reasons.append("queue backlog high")
            decision = SupervisionDecision("throttle", True, reasons, 2)
        else:
            decision = SupervisionDecision("allow", True, [])
        if decision.action != "allow":
            publish_event(AIEventType.SUPERVISOR_ALERT, {"state": state.to_dict(), "decision": decision.to_dict()}, source="core.supervisor")
        return decision

