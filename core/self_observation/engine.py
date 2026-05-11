from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class ObservationReport:
    quality_score: float
    reliability_score: float
    bottlenecks: list[str] = field(default_factory=list)
    anomaly_risk: float = 0.0
    hallucination_risk: float = 0.0
    predictive_failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "quality_score": self.quality_score,
            "reliability_score": self.reliability_score,
            "bottlenecks": list(self.bottlenecks),
            "anomaly_risk": self.anomaly_risk,
            "hallucination_risk": self.hallucination_risk,
            "predictive_failures": list(self.predictive_failures),
        }


class SelfObservationEngine:
    def analyze(self, metrics: dict[str, Any]) -> ObservationReport:
        failures = int(metrics.get("failures", 0) or 0)
        total = max(1, int(metrics.get("total", 1) or 1))
        retries = int(metrics.get("retries", 0) or 0)
        ambiguous_routes = int(metrics.get("ambiguous_routes", 0) or 0)
        latency = float(metrics.get("avg_latency_ms", 0.0) or 0.0)
        reliability = max(0.0, 1.0 - failures / total)
        quality = max(0.0, reliability - min(0.2, retries / total * 0.1))
        bottlenecks = []
        if latency > 2000:
            bottlenecks.append("latency")
        if retries > 3:
            bottlenecks.append("retry pressure")
        predictive = []
        if failures >= 3:
            predictive.append("failure rate may destabilize workflow")
        report = ObservationReport(round(quality, 3), round(reliability, 3), bottlenecks, min(1.0, failures / total + retries * 0.03), min(1.0, ambiguous_routes / total), predictive)
        publish_event(AIEventType.SELF_OBSERVATION_REPORTED, report.to_dict(), source="core.self_observation")
        return report

