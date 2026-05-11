from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .queue import DistributedTask, PersistentTaskQueue
from .registry import ExecutionNode, NodeRegistry


@dataclass(frozen=True)
class RouteDecision:
    task: DistributedTask
    node: ExecutionNode | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "node": self.node.to_dict() if self.node else None,
            "reason": self.reason,
        }


class ExecutionRouter:
    def __init__(self, registry: NodeRegistry | None = None, queue: PersistentTaskQueue | None = None):
        self.registry = registry or NodeRegistry()
        self.queue = queue or PersistentTaskQueue()

    def route_next(self) -> RouteDecision | None:
        task = self.queue.next_ready()
        if not task:
            return None
        node = self.registry.best_node(task.required_capability)
        if not node:
            return RouteDecision(task, None, "no healthy node with required capability")
        assigned = self.queue.assign(task.task_id, node.node_id) or task
        return RouteDecision(assigned, node, "assigned to lowest-load healthy node")

