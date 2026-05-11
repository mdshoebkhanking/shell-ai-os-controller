from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class EcosystemNode:
    node_id: str
    node_type: str
    name: str
    capabilities: list[str] = field(default_factory=list)
    trust_score: float = 0.5
    online: bool = True
    last_seen: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "name": self.name,
            "capabilities": list(self.capabilities),
            "trust_score": self.trust_score,
            "online": self.online,
            "last_seen": self.last_seen,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class EcosystemRoute:
    capability: str
    node: EcosystemNode | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"capability": self.capability, "node": self.node.to_dict() if self.node else None, "reason": self.reason}


class EcosystemCoordinator:
    def __init__(self):
        self._nodes: dict[str, EcosystemNode] = {}
        self.shared_context: dict[str, Any] = {}

    def register_node(self, node_type: str, name: str, *, capabilities: list[str] | None = None, trust_score: float = 0.5) -> EcosystemNode:
        node = EcosystemNode(uuid.uuid4().hex, node_type, name, list(capabilities or []), max(0.0, min(1.0, float(trust_score))))
        self._nodes[node.node_id] = node
        publish_event(AIEventType.ECOSYSTEM_COORDINATED, {"registered": node.to_dict()}, source="core.ecosystem")
        return node

    def discover(self, capability: str = "") -> list[EcosystemNode]:
        rows = [
            node for node in self._nodes.values()
            if node.online and (not capability or capability in node.capabilities)
        ]
        rows.sort(key=lambda node: (node.trust_score, node.last_seen), reverse=True)
        return rows

    def route(self, capability: str, *, min_trust: float = 0.5) -> EcosystemRoute:
        nodes = [node for node in self.discover(capability) if node.trust_score >= min_trust]
        route = EcosystemRoute(capability, nodes[0] if nodes else None, "highest-trust capable node" if nodes else "no trusted capable node")
        publish_event(AIEventType.ECOSYSTEM_COORDINATED, {"route": route.to_dict()}, source="core.ecosystem")
        return route

    def sync_context(self, key: str, value: Any, *, source_node: str = "") -> dict[str, Any]:
        row = {"key": key, "value": value, "source_node": source_node, "updated_at": time.time()}
        self.shared_context[key] = row
        publish_event(AIEventType.ECOSYSTEM_COORDINATED, {"context": row}, source="core.ecosystem")
        return row

