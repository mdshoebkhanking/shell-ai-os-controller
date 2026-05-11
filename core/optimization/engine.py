from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class OptimizationRecommendation:
    target: str
    action: str
    expected_impact: str
    safe_to_apply: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "action": self.action,
            "expected_impact": self.expected_impact,
            "safe_to_apply": self.safe_to_apply,
            "metadata": dict(self.metadata),
        }


class OptimizationEngine:
    def recommend(self, metrics: dict[str, Any]) -> list[OptimizationRecommendation]:
        recs: list[OptimizationRecommendation] = []
        if float(metrics.get("startup_ms", 0.0)) > 3000:
            recs.append(OptimizationRecommendation("startup", "lazy_load_plugins", "reduce startup latency"))
        if float(metrics.get("ram_percent", 0.0)) >= 80:
            recs.append(OptimizationRecommendation("memory", "unload_cold_models", "reduce RAM pressure"))
        if int(metrics.get("plugin_count", 0)) > 50:
            recs.append(OptimizationRecommendation("plugins", "defer_inactive_plugins", "reduce import and scan cost"))
        if float(metrics.get("cache_hit_rate", 1.0)) < 0.4:
            recs.append(OptimizationRecommendation("cache", "increase_hot_cache_ttl", "reduce repeated work"))
        publish_event(AIEventType.OPTIMIZATION_DECISION, {"metrics": dict(metrics), "recommendations": [r.to_dict() for r in recs]}, source="core.optimization")
        return recs

