from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class CognitionShard:
    shard_id: str
    role: str
    node_id: str
    scope: str
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"shard_id": self.shard_id, "role": self.role, "node_id": self.node_id, "scope": self.scope, "confidence": self.confidence, "metadata": dict(self.metadata)}


class DistributedCognitionFabric:
    def __init__(self):
        self._shards: dict[str, CognitionShard] = {}

    def partition(self, goal: str, nodes: list[str]) -> list[CognitionShard]:
        roles = ["planner", "reasoner", "memory", "validator", "executor"]
        shards = []
        for idx, node_id in enumerate(nodes):
            role = roles[idx % len(roles)]
            shard = CognitionShard(uuid.uuid4().hex, role, node_id, goal, 0.6)
            self._shards[shard.shard_id] = shard
            shards.append(shard)
        publish_event(AIEventType.DISTRIBUTED_COGNITION_UPDATED, {"partition": [s.to_dict() for s in shards]}, source="core.distributed_cognition")
        return shards

    def coordinate(self, shards: list[CognitionShard], partials: list[dict[str, Any]]) -> dict[str, Any]:
        weighted = sorted(partials, key=lambda row: float(row.get("confidence", 0.0)), reverse=True)
        result = {"shards": [s.to_dict() for s in shards], "selected": weighted[0] if weighted else None, "conflicts": len({str(p.get("result")) for p in partials}) > 1}
        publish_event(AIEventType.DISTRIBUTED_COGNITION_UPDATED, {"coordination": result}, source="core.distributed_cognition")
        return result

    def resolve_conflict(self, proposals: list[dict[str, Any]]) -> dict[str, Any]:
        proposals = sorted(proposals, key=lambda row: float(row.get("confidence", 0.0)), reverse=True)
        result = {"resolution": proposals[0] if proposals else None, "method": "highest-confidence-with-validator-review"}
        publish_event(AIEventType.DISTRIBUTED_COGNITION_UPDATED, {"resolution": result}, source="core.distributed_cognition")
        return result

