from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class OrchestrationNode:
    node_id: str
    kind: str
    capability: str
    status: str = "pending"
    load_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "capability": self.capability,
            "status": self.status,
            "load_score": self.load_score,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class OrchestrationEdge:
    source_id: str
    target_id: str
    relation: str = "depends_on"

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "target_id": self.target_id, "relation": self.relation}


class CognitiveOrchestrator:
    def __init__(self):
        self._nodes: dict[str, OrchestrationNode] = {}
        self._edges: list[OrchestrationEdge] = []

    def add_node(self, kind: str, capability: str, *, load_score: float = 0.0, metadata: dict[str, Any] | None = None) -> OrchestrationNode:
        node = OrchestrationNode(uuid.uuid4().hex, kind, capability, "ready", max(0.0, min(1.0, float(load_score))), dict(metadata or {}))
        self._nodes[node.node_id] = node
        self._emit("node_added", node.to_dict())
        return node

    def connect(self, source_id: str, target_id: str, relation: str = "depends_on") -> OrchestrationEdge:
        edge = OrchestrationEdge(source_id, target_id, relation)
        self._edges.append(edge)
        self._emit("edge_added", edge.to_dict())
        return edge

    def route(self, capability: str, *, semantic_tags: list[str] | None = None) -> dict[str, Any]:
        tags = {tag.lower() for tag in semantic_tags or []}
        candidates = [node for node in self._nodes.values() if node.capability == capability and node.status == "ready"]
        scored = []
        for node in candidates:
            node_tags = {str(tag).lower() for tag in node.metadata.get("tags", [])}
            semantic_bonus = len(tags & node_tags) * 0.2
            score = max(0.0, 1.0 - node.load_score + semantic_bonus)
            scored.append((score, node))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[0][1] if scored else None
        result = {"capability": capability, "selected": selected.to_dict() if selected else None, "score": round(scored[0][0], 3) if scored else 0.0}
        self._emit("route", result)
        return result

    def adapt(self, node_id: str, *, status: str, load_score: float | None = None) -> OrchestrationNode | None:
        current = self._nodes.get(node_id)
        if not current:
            return None
        updated = OrchestrationNode(
            current.node_id,
            current.kind,
            current.capability,
            status,
            current.load_score if load_score is None else max(0.0, min(1.0, float(load_score))),
            dict(current.metadata),
        )
        self._nodes[node_id] = updated
        self._emit("adapt", updated.to_dict())
        return updated

    def graph(self) -> dict[str, Any]:
        return {
            "generated_at": time.time(),
            "nodes": [node.to_dict() for node in self._nodes.values()],
            "edges": [edge.to_dict() for edge in self._edges],
        }

    def _emit(self, action: str, payload: dict[str, Any]) -> None:
        publish_event(AIEventType.COGNITIVE_ORCHESTRATION_UPDATED, {"action": action, **payload}, source="core.cognitive_orchestrator")

