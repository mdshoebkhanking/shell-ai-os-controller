from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class ExecutionTarget:
    target_id: str
    target_type: str
    capabilities: list[str] = field(default_factory=list)
    cost_score: float = 0.0
    latency_ms: float = 0.0
    online: bool = True
    locality: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"target_id": self.target_id, "target_type": self.target_type, "capabilities": list(self.capabilities), "cost_score": self.cost_score, "latency_ms": self.latency_ms, "online": self.online, "locality": self.locality}


class CloudEdgeOrchestrator:
    def choose(self, targets: list[ExecutionTarget], capability: str, *, offline: bool = False, prefer_local: bool = True) -> dict[str, Any]:
        viable = [target for target in targets if target.online and capability in target.capabilities and (not offline or target.target_type in {"local", "edge"})]
        if prefer_local:
            viable.sort(key=lambda target: (0 if target.target_type == "local" else 1, target.cost_score, target.latency_ms))
        else:
            viable.sort(key=lambda target: (target.cost_score, target.latency_ms))
        selected = viable[0] if viable else None
        result = {"target": selected.to_dict() if selected else None, "mode": "offline" if offline else "hybrid", "reason": "local/cloud/edge policy"}
        publish_event(AIEventType.CLOUD_EDGE_DECISION, result, source="core.cloud_edge")
        return result

    def replication_plan(self, capability: str, targets: list[ExecutionTarget]) -> dict[str, Any]:
        replicas = [target.to_dict() for target in targets if target.online and capability in target.capabilities][:3]
        plan = {"capability": capability, "replicas": replicas, "requires_confirmation": True}
        publish_event(AIEventType.CLOUD_EDGE_DECISION, {"replication": plan}, source="core.cloud_edge")
        return plan

