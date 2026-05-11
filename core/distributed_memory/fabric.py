from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class MemoryReplica:
    replica_id: str
    node_id: str
    namespace: str
    text: str
    version: int = 1
    trust_score: float = 0.5
    ts: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "replica_id": self.replica_id,
            "node_id": self.node_id,
            "namespace": self.namespace,
            "text": self.text,
            "version": self.version,
            "trust_score": self.trust_score,
            "ts": self.ts,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MemoryMergeResult:
    accepted: list[MemoryReplica]
    rejected: list[MemoryReplica]
    consistency_model: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": [replica.to_dict() for replica in self.accepted],
            "rejected": [replica.to_dict() for replica in self.rejected],
            "consistency_model": self.consistency_model,
            "reason": self.reason,
        }


class DistributedMemoryFabric:
    def __init__(self, consistency_model: str = "eventual"):
        self.consistency_model = consistency_model
        self._replicas: dict[str, MemoryReplica] = {}

    def replicate(self, node_id: str, namespace: str, text: str, *, version: int = 1, trust_score: float = 0.5, metadata: dict[str, Any] | None = None) -> MemoryReplica:
        replica = MemoryReplica(uuid.uuid4().hex, node_id, namespace, text, version, max(0.0, min(1.0, float(trust_score))), time.time(), dict(metadata or {}))
        self._replicas[replica.replica_id] = replica
        publish_event(AIEventType.DISTRIBUTED_MEMORY_SYNCED, {"replica": replica.to_dict()}, source="core.distributed_memory")
        return replica

    def merge(self, replicas: list[MemoryReplica], *, min_trust: float = 0.5) -> MemoryMergeResult:
        accepted = [replica for replica in replicas if replica.trust_score >= min_trust]
        rejected = [replica for replica in replicas if replica.trust_score < min_trust]
        by_text: dict[str, MemoryReplica] = {}
        for replica in accepted:
            current = by_text.get(replica.text)
            if not current or (replica.version, replica.trust_score, replica.ts) > (current.version, current.trust_score, current.ts):
                by_text[replica.text] = replica
        result = MemoryMergeResult(list(by_text.values()), rejected, self.consistency_model, "trust-aware latest-version merge")
        publish_event(AIEventType.DISTRIBUTED_MEMORY_SYNCED, {"merge": result.to_dict()}, source="core.distributed_memory")
        return result

    def retrieve(self, query: str, *, namespace: str = "", limit: int = 10) -> list[dict[str, Any]]:
        tokens = {token.lower() for token in str(query or "").split() if token.strip()}
        rows = []
        for replica in self._replicas.values():
            if namespace and replica.namespace != namespace:
                continue
            score = sum(1 for token in tokens if token in replica.text.lower())
            if tokens and score <= 0:
                continue
            row = replica.to_dict()
            row["score"] = score + replica.trust_score
            rows.append(row)
        rows.sort(key=lambda row: (row["score"], row["version"], row["ts"]), reverse=True)
        return rows[: max(0, int(limit))]

    def compress(self, namespace: str) -> dict[str, Any]:
        rows = [replica for replica in self._replicas.values() if replica.namespace == namespace]
        text = "\n".join(replica.text for replica in sorted(rows, key=lambda item: item.ts)[-20:])
        return {"namespace": namespace, "count": len(rows), "summary": text[:1200]}

