from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class FederatedWorker:
    worker_id: str
    worker_type: str
    locality: str
    capabilities: list[str] = field(default_factory=list)
    capacity: float = 1.0
    load: float = 0.0
    healthy: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"worker_id": self.worker_id, "worker_type": self.worker_type, "locality": self.locality, "capabilities": list(self.capabilities), "capacity": self.capacity, "load": self.load, "healthy": self.healthy, "metadata": dict(self.metadata)}


@dataclass(frozen=True)
class FederatedTask:
    task_id: str
    capability: str
    priority: int = 5
    locality_hint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "capability": self.capability, "priority": self.priority, "locality_hint": self.locality_hint, "metadata": dict(self.metadata)}


class FederatedClusterEngine:
    def __init__(self):
        self._workers: dict[str, FederatedWorker] = {}

    def register_worker(self, worker_type: str, locality: str, *, capabilities: list[str] | None = None, capacity: float = 1.0, load: float = 0.0, metadata: dict[str, Any] | None = None) -> FederatedWorker:
        worker = FederatedWorker(uuid.uuid4().hex, worker_type, locality, list(capabilities or []), max(0.1, float(capacity)), max(0.0, min(1.0, float(load))), True, dict(metadata or {}))
        self._workers[worker.worker_id] = worker
        publish_event(AIEventType.FEDERATION_DECISION, {"registered": worker.to_dict()}, source="core.federation")
        return worker

    def schedule(self, task: FederatedTask) -> dict[str, Any]:
        candidates = [worker for worker in self._workers.values() if worker.healthy and task.capability in worker.capabilities]
        scored = []
        for worker in candidates:
            locality = 0.25 if task.locality_hint and worker.locality == task.locality_hint else 0.0
            score = worker.capacity - worker.load + locality + task.priority * 0.01
            scored.append((score, worker))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[0][1] if scored else None
        result = {"task": task.to_dict(), "worker": selected.to_dict() if selected else None, "reason": "capacity/load/locality schedule" if selected else "no healthy worker"}
        publish_event(AIEventType.FEDERATION_DECISION, {"schedule": result}, source="core.federation")
        return result

    def migrate(self, task_id: str, source_worker: str, target_capability: str) -> dict[str, Any]:
        candidates = [worker for worker in self._workers.values() if worker.worker_id != source_worker and worker.healthy and target_capability in worker.capabilities]
        candidates.sort(key=lambda worker: (worker.load, -worker.capacity))
        result = {"task_id": task_id, "from": source_worker, "to": candidates[0].worker_id if candidates else "", "requires_checkpoint": True}
        publish_event(AIEventType.FEDERATION_DECISION, {"migration": result}, source="core.federation")
        return result

    def failover(self, failed_worker: str, capability: str) -> dict[str, Any]:
        return self.migrate("*", failed_worker, capability)

