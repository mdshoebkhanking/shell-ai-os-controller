from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class NodeRuntimeState(str, Enum):
    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


@dataclass(frozen=True)
class NodeDescriptor:
    node_id: str
    capabilities: list[str] = field(default_factory=list)
    trust_score: float = 0.5
    capacity: dict[str, float] = field(default_factory=dict)
    models: list[str] = field(default_factory=list)
    state: NodeRuntimeState = NodeRuntimeState.STARTING
    memory_permissions: list[str] = field(default_factory=list)
    sandboxed: bool = True
    last_heartbeat: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "capabilities": list(self.capabilities),
            "trust_score": self.trust_score,
            "capacity": dict(self.capacity),
            "models": list(self.models),
            "state": self.state.value,
            "memory_permissions": list(self.memory_permissions),
            "sandboxed": self.sandboxed,
            "last_heartbeat": self.last_heartbeat,
        }


class AINodeRuntime:
    def __init__(self):
        self._nodes: dict[str, NodeDescriptor] = {}

    def register(self, *, capabilities: list[str] | None = None, trust_score: float = 0.5, capacity: dict[str, float] | None = None, models: list[str] | None = None, memory_permissions: list[str] | None = None) -> NodeDescriptor:
        node = NodeDescriptor(uuid.uuid4().hex, list(capabilities or []), max(0.0, min(1.0, float(trust_score))), dict(capacity or {}), list(models or []), NodeRuntimeState.READY, list(memory_permissions or []), True)
        self._nodes[node.node_id] = node
        publish_event(AIEventType.NODE_RUNTIME_UPDATED, {"registered": node.to_dict()}, source="core.node_runtime")
        return node

    def heartbeat(self, node_id: str, *, state: NodeRuntimeState | str = NodeRuntimeState.READY, capacity: dict[str, float] | None = None) -> NodeDescriptor | None:
        node = self._nodes.get(node_id)
        if not node:
            return None
        state_enum = state if isinstance(state, NodeRuntimeState) else NodeRuntimeState(str(state))
        updated = NodeDescriptor(node.node_id, list(node.capabilities), node.trust_score, dict(capacity or node.capacity), list(node.models), state_enum, list(node.memory_permissions), node.sandboxed, time.time())
        self._nodes[node_id] = updated
        publish_event(AIEventType.NODE_RUNTIME_UPDATED, {"heartbeat": updated.to_dict()}, source="core.node_runtime")
        return updated

    def discover(self, capability: str) -> list[NodeDescriptor]:
        rows = [node for node in self._nodes.values() if node.state == NodeRuntimeState.READY and capability in node.capabilities]
        rows.sort(key=lambda node: node.trust_score, reverse=True)
        return rows

    def negotiate_trust(self, node_id: str, required: float = 0.5) -> dict[str, Any]:
        node = self._nodes.get(node_id)
        ok = bool(node and node.trust_score >= required and node.sandboxed)
        result = {"node_id": node_id, "ok": ok, "trust_score": node.trust_score if node else 0.0, "sandboxed": node.sandboxed if node else False}
        publish_event(AIEventType.NODE_RUNTIME_UPDATED, {"trust": result}, source="core.node_runtime")
        return result

