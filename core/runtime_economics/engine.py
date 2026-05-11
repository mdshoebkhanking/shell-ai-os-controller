from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class RuntimeOption:
    runtime_id: str
    cost: float
    latency_ms: float
    energy_score: float
    token_capacity: int
    gpu_required: bool = False
    bandwidth_mb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "energy_score": self.energy_score,
            "token_capacity": self.token_capacity,
            "gpu_required": self.gpu_required,
            "bandwidth_mb": self.bandwidth_mb,
        }


@dataclass(frozen=True)
class RuntimePlan:
    option: RuntimeOption | None
    score: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"option": self.option.to_dict() if self.option else None, "score": self.score, "reasons": list(self.reasons)}


class RuntimeEconomicsEngine:
    def choose(self, options: list[RuntimeOption], *, max_cost: float = 1.0, max_latency_ms: float = 10000, gpu_available: bool = True, token_need: int = 0) -> RuntimePlan:
        viable = [
            option for option in options
            if option.cost <= max_cost
            and option.latency_ms <= max_latency_ms
            and option.token_capacity >= token_need
            and (gpu_available or not option.gpu_required)
        ]
        if not viable:
            plan = RuntimePlan(None, 0.0, ["no runtime met budget constraints"])
        else:
            scored = []
            for option in viable:
                score = 1.0 - min(0.5, option.cost / max(0.01, max_cost) * 0.25) - min(0.3, option.latency_ms / max_latency_ms * 0.3) - min(0.2, option.energy_score * 0.2)
                scored.append((score, option))
            scored.sort(key=lambda item: item[0], reverse=True)
            plan = RuntimePlan(scored[0][1], round(scored[0][0], 3), ["budget-aware runtime selection"])
        publish_event(AIEventType.RUNTIME_ECONOMICS_DECISION, plan.to_dict(), source="core.runtime_economics")
        return plan

