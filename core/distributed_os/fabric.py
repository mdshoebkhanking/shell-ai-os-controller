from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class DistributedOSNode:
    node_id: str
    node_type: str
    name: str
    capabilities: list[str] = field(default_factory=list)
    locality: str = "local"
    trust_score: float = 0.5
    load: float = 0.0
    online: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "name": self.name,
            "capabilities": list(self.capabilities),
            "locality": self.locality,
            "trust_score": self.trust_score,
            "load": self.load,
            "online": self.online,
            "metadata": dict(self.metadata),
            "last_seen": self.last_seen,
        }


@dataclass(frozen=True)
class WorkloadPlacement:
    workload_id: str
    capability: str
    node: DistributedOSNode | None
    reason: str
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {"workload_id": self.workload_id, "capability": self.capability, "node": self.node.to_dict() if self.node else None, "reason": self.reason, "confidence": self.confidence}


class DistributedOSFabric:
    def __init__(self):
        self._nodes: dict[str, DistributedOSNode] = {}
        self._bus: list[dict[str, Any]] = []

    def register_node(self, node_type: str, name: str, *, capabilities: list[str] | None = None, locality: str = "local", trust_score: float = 0.5, load: float = 0.0, metadata: dict[str, Any] | None = None) -> DistributedOSNode:
        node = DistributedOSNode(uuid.uuid4().hex, node_type, name, list(capabilities or []), locality, max(0.0, min(1.0, float(trust_score))), max(0.0, min(1.0, float(load))), True, dict(metadata or {}))
        self._nodes[node.node_id] = node
        publish_event(AIEventType.DISTRIBUTED_OS_UPDATED, {"registered": node.to_dict()}, source="core.distributed_os")
        return node

    def negotiate_capability(self, capability: str, *, min_trust: float = 0.5) -> list[DistributedOSNode]:
        nodes = [node for node in self._nodes.values() if node.online and capability in node.capabilities and node.trust_score >= min_trust]
        nodes.sort(key=lambda node: (node.load, -node.trust_score))
        return nodes

    def place_workload(self, workload_id: str, capability: str, *, preferred_locality: str = "", min_trust: float = 0.5) -> WorkloadPlacement:
        candidates = self.negotiate_capability(capability, min_trust=min_trust)
        scored = []
        for node in candidates:
            locality_bonus = 0.2 if preferred_locality and node.locality == preferred_locality else 0.0
            score = max(0.0, 1.0 - node.load + locality_bonus + node.trust_score * 0.2)
            scored.append((score, node))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[0][1] if scored else None
        placement = WorkloadPlacement(workload_id, capability, selected, "semantic trust/load/locality placement" if selected else "no trusted capable node", round(scored[0][0], 3) if scored else 0.0)
        publish_event(AIEventType.DISTRIBUTED_OS_UPDATED, {"placement": placement.to_dict()}, source="core.distributed_os")
        return placement

    def publish_bus(self, topic: str, payload: dict[str, Any], *, semantic_tags: list[str] | None = None) -> dict[str, Any]:
        row = {"topic": topic, "payload": dict(payload), "semantic_tags": list(semantic_tags or []), "ts": time.time()}
        self._bus.append(row)
        publish_event(AIEventType.DISTRIBUTED_OS_UPDATED, {"bus": row}, source="core.distributed_os")
        return row

    def continuity_plan(self, source_node: str, target_node: str, workload_id: str) -> dict[str, Any]:
        return {"source_node": source_node, "target_node": target_node, "workload_id": workload_id, "requires_confirmation": True, "mode": "cross-device-continuity"}

