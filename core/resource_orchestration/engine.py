from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class ResourceRequest:
    request_id: str
    cpu: float = 0.0
    gpu: float = 0.0
    memory_mb: float = 0.0
    tokens: int = 0
    bandwidth_mb: float = 0.0
    cloud_cost: float = 0.0
    priority: int = 5
    semantic_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"request_id": self.request_id, "cpu": self.cpu, "gpu": self.gpu, "memory_mb": self.memory_mb, "tokens": self.tokens, "bandwidth_mb": self.bandwidth_mb, "cloud_cost": self.cloud_cost, "priority": self.priority, "semantic_tags": list(self.semantic_tags)}


class ResourceOrchestrationEngine:
    def schedule(self, requests: list[ResourceRequest], capacity: dict[str, float]) -> dict[str, Any]:
        remaining = dict(capacity)
        accepted: list[str] = []
        throttled: list[str] = []
        for req in sorted(requests, key=lambda item: item.priority, reverse=True):
            demand = req.to_dict()
            keys = ["cpu", "gpu", "memory_mb", "tokens", "bandwidth_mb", "cloud_cost"]
            fits = all(float(demand[key]) <= float(remaining.get(key, 0.0)) for key in keys)
            if fits:
                accepted.append(req.request_id)
                for key in keys:
                    remaining[key] = float(remaining.get(key, 0.0)) - float(demand[key])
            else:
                throttled.append(req.request_id)
        result = {"accepted": accepted, "throttled": throttled, "remaining": remaining}
        publish_event(AIEventType.RESOURCE_ORCHESTRATION_DECISION, result, source="core.resource_orchestration")
        return result

    def predict(self, requests: list[ResourceRequest]) -> dict[str, float]:
        totals = {"cpu": 0.0, "gpu": 0.0, "memory_mb": 0.0, "tokens": 0.0, "bandwidth_mb": 0.0, "cloud_cost": 0.0}
        for req in requests:
            row = req.to_dict()
            for key in totals:
                totals[key] += float(row[key])
        publish_event(AIEventType.RESOURCE_ORCHESTRATION_DECISION, {"prediction": totals}, source="core.resource_orchestration")
        return totals

