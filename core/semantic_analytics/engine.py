from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class SemanticMetric:
    dimension: str
    semantic_label: str
    value: float
    context: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"dimension": self.dimension, "semantic_label": self.semantic_label, "value": self.value, "context": dict(self.context), "ts": self.ts}


class SemanticAnalyticsEngine:
    def __init__(self):
        self._metrics: list[SemanticMetric] = []

    def record(self, dimension: str, semantic_label: str, value: float, *, context: dict[str, Any] | None = None) -> SemanticMetric:
        metric = SemanticMetric(dimension, semantic_label, float(value), dict(context or {}))
        self._metrics.append(metric)
        publish_event(AIEventType.SEMANTIC_ANALYTICS_RECORDED, metric.to_dict(), source="core.semantic_analytics")
        return metric

    def summarize(self, dimension: str) -> dict[str, Any]:
        rows = [metric for metric in self._metrics if metric.dimension == dimension]
        by_label: dict[str, float] = {}
        for metric in rows:
            by_label[metric.semantic_label] = by_label.get(metric.semantic_label, 0.0) + metric.value
        return {"dimension": dimension, "count": len(rows), "by_label": by_label}

    def ecosystem_health(self) -> float:
        if not self._metrics:
            return 1.0
        risk = sum(metric.value for metric in self._metrics if "risk" in metric.semantic_label.lower())
        total = sum(abs(metric.value) for metric in self._metrics) or 1.0
        return round(max(0.0, 1.0 - min(1.0, risk / total)), 3)

