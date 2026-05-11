from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class RecoveryStrategy(str, Enum):
    RETRY = "RETRY"
    FAILOVER = "FAILOVER"
    DEGRADE = "DEGRADE"
    RESTORE_CHECKPOINT = "RESTORE_CHECKPOINT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True)
class ResilienceDecision:
    strategy: RecoveryStrategy
    target: str
    actions: list[str] = field(default_factory=list)
    safe_to_apply: bool = True
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "target": self.target,
            "actions": list(self.actions),
            "safe_to_apply": self.safe_to_apply,
            "reason": self.reason,
        }


class ResilienceEngine:
    def decide(self, failure: dict[str, Any]) -> ResilienceDecision:
        kind = str(failure.get("kind") or "").lower()
        target = str(failure.get("target") or "unknown")
        if kind in {"node_failure", "runtime_crash"}:
            decision = ResilienceDecision(RecoveryStrategy.FAILOVER, target, ["route_to_redundant_node", "record_incident"], True, "redundant execution preferred")
        elif kind in {"api_outage", "provider_down"}:
            decision = ResilienceDecision(RecoveryStrategy.DEGRADE, target, ["switch_local_provider", "pause_cloud_workflows"], True, "external dependency unavailable")
        elif kind in {"memory_inconsistency", "state_corruption"}:
            decision = ResilienceDecision(RecoveryStrategy.RESTORE_CHECKPOINT, target, ["load_last_checkpoint", "reconcile_state"], False, "state restore requires confirmation")
        elif int(failure.get("attempts", 0) or 0) < 2:
            decision = ResilienceDecision(RecoveryStrategy.RETRY, target, ["retry_with_backoff"], True, "bounded retry available")
        else:
            decision = ResilienceDecision(RecoveryStrategy.MANUAL_REVIEW, target, ["surface_to_operator"], False, "no safe automatic strategy")
        publish_event(AIEventType.RESILIENCE_DECISION, {"failure": dict(failure), "decision": decision.to_dict()}, source="core.resilience")
        return decision

    def degradation_plan(self, unavailable_capabilities: list[str]) -> dict[str, Any]:
        return {
            "mode": "degraded",
            "unavailable": list(unavailable_capabilities),
            "fallbacks": [{"capability": cap, "fallback": "local_or_manual"} for cap in unavailable_capabilities],
        }

