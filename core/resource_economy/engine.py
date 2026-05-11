from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class ResourceBudget:
    compute: float
    memory_mb: float
    storage_mb: float
    bandwidth_mb: float
    gpu: float = 0.0
    tokens: int = 0
    cloud_cost: float = 0.0
    energy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ResourceWorkload:
    workload_id: str
    priority: int
    demand: ResourceBudget

    def to_dict(self) -> dict[str, Any]:
        return {"workload_id": self.workload_id, "priority": self.priority, "demand": self.demand.to_dict()}


class ResourceEconomyEngine:
    def allocate(self, workloads: list[ResourceWorkload], capacity: ResourceBudget) -> dict[str, Any]:
        remaining = {
            "compute": capacity.compute,
            "memory_mb": capacity.memory_mb,
            "storage_mb": capacity.storage_mb,
            "bandwidth_mb": capacity.bandwidth_mb,
            "gpu": capacity.gpu,
            "tokens": capacity.tokens,
            "cloud_cost": capacity.cloud_cost,
            "energy": capacity.energy,
        }
        accepted: list[str] = []
        throttled: list[str] = []
        for workload in sorted(workloads, key=lambda item: item.priority, reverse=True):
            demand = workload.demand.to_dict()
            fits = all(float(demand[key]) <= float(remaining[key]) for key in remaining)
            if fits:
                accepted.append(workload.workload_id)
                for key in remaining:
                    remaining[key] -= demand[key]
            else:
                throttled.append(workload.workload_id)
        result = {"accepted": accepted, "throttled": throttled, "remaining": remaining}
        publish_event(AIEventType.RESOURCE_ECONOMY_DECISION, result, source="core.resource_economy")
        return result

    def forecast(self, history: list[ResourceBudget]) -> ResourceBudget:
        if not history:
            return ResourceBudget(0, 0, 0, 0)
        n = len(history)
        totals = {key: sum(float(budget.to_dict()[key]) for budget in history) / n for key in history[0].to_dict()}
        return ResourceBudget(**totals)

