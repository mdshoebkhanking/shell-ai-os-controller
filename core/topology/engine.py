from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class TopologyNode:
    node_id: str
    node_type: str
    locality: str
    capabilities: list[str] = field(default_factory=list)
    heat: float = 0.0
    healthy: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "locality": self.locality,
            "capabilities": list(self.capabilities),
            "heat": self.heat,
            "healthy": self.healthy,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TopologyEdge:
    source_id: str
    target_id: str
    relation: str
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "target_id": self.target_id, "relation": self.relation, "weight": self.weight}


class ExecutionTopology:
    def __init__(self):
        self._nodes: dict[str, TopologyNode] = {}
        self._edges: list[TopologyEdge] = []

    def add_node(self, node_type: str, locality: str, *, capabilities: list[str] | None = None, heat: float = 0.0, metadata: dict[str, Any] | None = None) -> TopologyNode:
        node = TopologyNode(uuid.uuid4().hex, node_type, locality, list(capabilities or []), max(0.0, float(heat)), True, dict(metadata or {}))
        self._nodes[node.node_id] = node
        self._emit()
        return node

    def connect(self, source_id: str, target_id: str, relation: str, *, weight: float = 1.0) -> TopologyEdge:
        edge = TopologyEdge(source_id, target_id, relation, max(0.0, float(weight)))
        self._edges.append(edge)
        self._emit()
        return edge

    def heatmap(self) -> dict[str, float]:
        heat: dict[str, float] = {}
        for node in self._nodes.values():
            heat[node.locality] = heat.get(node.locality, 0.0) + node.heat
        return heat

    def route(self, capability: str, *, preferred_locality: str = "") -> dict[str, Any]:
        candidates = [node for node in self._nodes.values() if node.healthy and capability in node.capabilities]
        scored = []
        for node in candidates:
            locality_bonus = 0.3 if preferred_locality and node.locality == preferred_locality else 0.0
            score = max(0.0, 1.0 - min(1.0, node.heat) + locality_bonus)
            scored.append((score, node))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[0][1] if scored else None
        result = {"capability": capability, "selected": selected.to_dict() if selected else None, "score": round(scored[0][0], 3) if scored else 0.0}
        publish_event(AIEventType.TOPOLOGY_UPDATED, {"route": result}, source="core.topology")
        return result

    def graph(self) -> dict[str, Any]:
        return {"nodes": [node.to_dict() for node in self._nodes.values()], "edges": [edge.to_dict() for edge in self._edges], "heatmap": self.heatmap()}

    def _emit(self) -> None:
        publish_event(AIEventType.TOPOLOGY_UPDATED, self.graph(), source="core.topology")

