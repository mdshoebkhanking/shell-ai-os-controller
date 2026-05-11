from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class MetricRecord:
    category: str
    name: str
    value: float
    tags: dict[str, str] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category, "name": self.name, "value": self.value, "tags": dict(self.tags), "ts": self.ts}


class AnalyticsEngine:
    def __init__(self):
        self._records: list[MetricRecord] = []

    def record(self, category: str, name: str, value: float, *, tags: dict[str, str] | None = None) -> MetricRecord:
        metric = MetricRecord(category, name, float(value), dict(tags or {}))
        self._records.append(metric)
        publish_event(AIEventType.ANALYTICS_RECORDED, metric.to_dict(), source="core.analytics")
        return metric

    def heatmap(self, category: str) -> dict[str, float]:
        heat: dict[str, float] = {}
        for record in self._records:
            if record.category == category:
                heat[record.name] = heat.get(record.name, 0.0) + record.value
        return heat

    def bottlenecks(self, *, threshold: float) -> list[dict[str, Any]]:
        rows = [record.to_dict() for record in self._records if record.value >= threshold]
        rows.sort(key=lambda row: row["value"], reverse=True)
        return rows

