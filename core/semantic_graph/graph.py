from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class SemanticNode:
    node_id: str
    node_type: str
    label: str
    cluster: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "node_type": self.node_type, "label": self.label, "cluster": self.cluster, "metadata": dict(self.metadata)}


@dataclass(frozen=True)
class SemanticRelationship:
    source_id: str
    target_id: str
    relation: str
    score: float = 0.5
    temporal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "target_id": self.target_id, "relation": self.relation, "score": self.score, "temporal": self.temporal}


class SemanticGraph:
    def __init__(self):
        self._nodes: dict[str, SemanticNode] = {}
        self._edges: list[SemanticRelationship] = []

    def add_node(self, node_type: str, label: str, *, cluster: str = "", metadata: dict[str, Any] | None = None) -> SemanticNode:
        node = SemanticNode(uuid.uuid4().hex, node_type, label, cluster, dict(metadata or {}))
        self._nodes[node.node_id] = node
        self._emit()
        return node

    def connect(self, source_id: str, target_id: str, relation: str, *, score: float = 0.5, temporal: bool = False) -> SemanticRelationship:
        edge = SemanticRelationship(source_id, target_id, relation, max(0.0, min(1.0, float(score))), temporal)
        self._edges.append(edge)
        self._emit()
        return edge

    def neighbors(self, node_id: str, *, min_score: float = 0.0) -> list[dict[str, Any]]:
        out = []
        for edge in self._edges:
            if edge.score < min_score:
                continue
            other = edge.target_id if edge.source_id == node_id else edge.source_id if edge.target_id == node_id else ""
            if other and other in self._nodes:
                out.append({"node": self._nodes[other].to_dict(), "relationship": edge.to_dict()})
        return out

    def clusters(self) -> dict[str, list[str]]:
        clusters: dict[str, list[str]] = {}
        for node in self._nodes.values():
            clusters.setdefault(node.cluster or "default", []).append(node.node_id)
        return clusters

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": [node.to_dict() for node in self._nodes.values()], "relationships": [edge.to_dict() for edge in self._edges]}

    def _emit(self) -> None:
        publish_event(AIEventType.SEMANTIC_GRAPH_UPDATED, self.to_dict(), source="core.semantic_graph")

