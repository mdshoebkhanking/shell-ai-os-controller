from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class ExecutionNode:
    node_id: str
    label: str
    kind: str
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "kind": self.kind,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ExecutionEdge:
    source_id: str
    target_id: str
    relation: str = "depends_on"

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "target_id": self.target_id, "relation": self.relation}


class ExecutionGraph:
    def __init__(self):
        self._nodes: dict[str, ExecutionNode] = {}
        self._edges: list[ExecutionEdge] = []

    def add_node(self, label: str, kind: str, metadata: dict[str, Any] | None = None) -> ExecutionNode:
        node = ExecutionNode(uuid.uuid4().hex, label, kind, "running", time.time(), 0.0, dict(metadata or {}))
        self._nodes[node.node_id] = node
        self._emit()
        return node

    def add_edge(self, source_id: str, target_id: str, relation: str = "depends_on") -> ExecutionEdge:
        edge = ExecutionEdge(source_id, target_id, relation)
        self._edges.append(edge)
        self._emit()
        return edge

    def mark(self, node_id: str, status: str, metadata: dict[str, Any] | None = None) -> ExecutionNode | None:
        current = self._nodes.get(node_id)
        if not current:
            return None
        updated = ExecutionNode(
            current.node_id,
            current.label,
            current.kind,
            status,
            current.started_at,
            time.time() if status in {"completed", "failed", "cancelled"} else current.completed_at,
            {**current.metadata, **dict(metadata or {})},
        )
        self._nodes[node_id] = updated
        self._emit()
        return updated

    def replay_order(self) -> list[dict[str, Any]]:
        rows = [node.to_dict() for node in self._nodes.values()]
        rows.sort(key=lambda row: row.get("started_at", 0.0))
        return rows

    def failures(self) -> list[dict[str, Any]]:
        return [node.to_dict() for node in self._nodes.values() if node.status == "failed"]

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": [node.to_dict() for node in self._nodes.values()], "edges": [edge.to_dict() for edge in self._edges]}

    def _emit(self) -> None:
        publish_event(AIEventType.EXECUTION_GRAPH_UPDATED, self.to_dict(), source="core.execution_graph")

