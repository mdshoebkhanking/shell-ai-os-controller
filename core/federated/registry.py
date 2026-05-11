from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class FederatedNode:
    node_id: str
    name: str
    endpoint: str
    capabilities: list[str] = field(default_factory=list)
    trust_score: float = 0.5
    last_sync: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "endpoint": self.endpoint,
            "capabilities": list(self.capabilities),
            "trust_score": self.trust_score,
            "last_sync": self.last_sync,
            "metadata": dict(self.metadata),
        }


class FederatedRegistry:
    def __init__(self):
        self._nodes: dict[str, FederatedNode] = {}

    def register(self, name: str, endpoint: str, *, capabilities: list[str] | None = None, trust_score: float = 0.5) -> FederatedNode:
        node = FederatedNode(uuid.uuid4().hex, name, endpoint, list(capabilities or []), max(0.0, min(1.0, float(trust_score))))
        self._nodes[node.node_id] = node
        publish_event(AIEventType.FEDERATED_NODE_SYNCED, node.to_dict(), source="core.federated")
        return node

    def sync(self, node_id: str, metadata: dict[str, Any] | None = None) -> FederatedNode | None:
        node = self._nodes.get(node_id)
        if not node:
            return None
        updated = FederatedNode(node.node_id, node.name, node.endpoint, list(node.capabilities), node.trust_score, time.time(), dict(metadata or node.metadata))
        self._nodes[node_id] = updated
        publish_event(AIEventType.FEDERATED_NODE_SYNCED, updated.to_dict(), source="core.federated")
        return updated

    def capable(self, capability: str, *, min_trust: float = 0.5) -> list[FederatedNode]:
        rows = [node for node in self._nodes.values() if capability in node.capabilities and node.trust_score >= min_trust]
        rows.sort(key=lambda node: (node.trust_score, node.last_sync), reverse=True)
        return rows

