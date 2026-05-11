from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class TopologyRecommendation:
    action: str
    target: str
    reason: str
    requires_confirmation: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "target": self.target, "reason": self.reason, "requires_confirmation": self.requires_confirmation, "metadata": dict(self.metadata)}


class TopologyIntelligenceEngine:
    def analyze(self, topology: dict[str, Any]) -> list[TopologyRecommendation]:
        recs: list[TopologyRecommendation] = []
        for node in topology.get("nodes", []):
            heat = float(node.get("heat", 0.0) or 0.0)
            if heat >= 0.8:
                recs.append(TopologyRecommendation("migrate_workload", str(node.get("node_id")), "node heat is high", True, {"heat": heat}))
            if node.get("healthy") is False:
                recs.append(TopologyRecommendation("failover_node", str(node.get("node_id")), "node unhealthy", True))
        if not recs and topology.get("heatmap"):
            hottest = max(topology["heatmap"].items(), key=lambda item: item[1])
            if hottest[1] >= 1.5:
                recs.append(TopologyRecommendation("rebalance_locality", hottest[0], "locality heat concentrated", True, {"heat": hottest[1]}))
        publish_event(AIEventType.TOPOLOGY_INTELLIGENCE_REPORTED, {"recommendations": [r.to_dict() for r in recs]}, source="core.topology_intelligence")
        return recs

