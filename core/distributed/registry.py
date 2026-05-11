from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event


class NodeState(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class ExecutionNode:
    node_id: str
    name: str
    endpoint: str
    capabilities: list[str] = field(default_factory=list)
    platform: str = "local"
    state: NodeState = NodeState.ONLINE
    last_heartbeat: float = field(default_factory=time.time)
    max_concurrency: int = 1
    load: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "endpoint": self.endpoint,
            "capabilities": list(self.capabilities),
            "platform": self.platform,
            "state": self.state.value,
            "last_heartbeat": self.last_heartbeat,
            "max_concurrency": self.max_concurrency,
            "load": self.load,
            "metadata": dict(self.metadata),
        }


class NodeRegistry:
    def __init__(self, path: str | Path = ".shell_runtime/nodes.json", stale_after_s: float = 30.0):
        self.path = Path(path)
        self.stale_after_s = float(stale_after_s)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"nodes": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"nodes": {}}
        except Exception:
            return {"nodes": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def register(
        self,
        *,
        name: str = "local",
        endpoint: str = "local://shell",
        capabilities: list[str] | None = None,
        platform: str = "local",
        max_concurrency: int = 1,
        metadata: dict[str, Any] | None = None,
        node_id: str | None = None,
    ) -> ExecutionNode:
        node = ExecutionNode(
            node_id=node_id or uuid.uuid4().hex,
            name=name,
            endpoint=endpoint,
            capabilities=list(capabilities or []),
            platform=platform,
            max_concurrency=max(1, int(max_concurrency)),
            metadata=dict(metadata or {}),
        )
        data = self._load()
        data.setdefault("nodes", {})[node.node_id] = node.to_dict()
        self._write(data)
        publish_event(AIEventType.WORKER_REGISTERED, node.to_dict(), source="core.distributed")
        return node

    def heartbeat(self, node_id: str, *, load: float = 0.0, state: NodeState | str = NodeState.ONLINE) -> ExecutionNode | None:
        data = self._load()
        row = (data.get("nodes") or {}).get(node_id)
        if not row:
            return None
        row["last_heartbeat"] = time.time()
        row["load"] = max(0.0, min(1.0, float(load)))
        row["state"] = state.value if isinstance(state, NodeState) else str(state)
        self._write(data)
        node = self._node_from(row)
        publish_event(AIEventType.WORKER_HEARTBEAT, node.to_dict(), source="core.distributed")
        return node

    def nodes(self) -> list[ExecutionNode]:
        data = self._load()
        return [self._node_from(row) for row in (data.get("nodes") or {}).values()]

    def healthy_nodes(self, *, required_capability: str = "") -> list[ExecutionNode]:
        now = time.time()
        rows = []
        for node in self.nodes():
            stale = now - node.last_heartbeat > self.stale_after_s
            if stale or node.state not in {NodeState.ONLINE, NodeState.DEGRADED}:
                continue
            if required_capability and required_capability not in node.capabilities:
                continue
            rows.append(node)
        rows.sort(key=lambda node: (node.load, -node.max_concurrency))
        return rows

    def best_node(self, required_capability: str = "") -> ExecutionNode | None:
        nodes = self.healthy_nodes(required_capability=required_capability)
        return nodes[0] if nodes else None

    def _node_from(self, row: dict[str, Any]) -> ExecutionNode:
        return ExecutionNode(
            node_id=str(row.get("node_id") or ""),
            name=str(row.get("name") or ""),
            endpoint=str(row.get("endpoint") or ""),
            capabilities=list(row.get("capabilities") or []),
            platform=str(row.get("platform") or "local"),
            state=NodeState(row.get("state", NodeState.OFFLINE.value)),
            last_heartbeat=float(row.get("last_heartbeat", 0.0)),
            max_concurrency=int(row.get("max_concurrency", 1)),
            load=float(row.get("load", 0.0)),
            metadata=dict(row.get("metadata") or {}),
        )

