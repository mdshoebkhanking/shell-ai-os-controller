from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event


class TaskQueueState(str, Enum):
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class DistributedTask:
    task_id: str
    tool_id: str
    args: dict[str, Any] = field(default_factory=dict)
    required_capability: str = ""
    priority: int = 5
    state: TaskQueueState = TaskQueueState.QUEUED
    assigned_node: str = ""
    attempts: int = 0
    max_attempts: int = 2
    scheduled_at: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "tool_id": self.tool_id,
            "args": dict(self.args),
            "required_capability": self.required_capability,
            "priority": self.priority,
            "state": self.state.value,
            "assigned_node": self.assigned_node,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "scheduled_at": self.scheduled_at,
            "created_at": self.created_at,
            "result": dict(self.result),
            "error": self.error,
        }


class PersistentTaskQueue:
    def __init__(self, path: str | Path = ".shell_runtime/distributed_queue.json"):
        self.path = Path(path)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"tasks": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"tasks": {}}
        except Exception:
            return {"tasks": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def enqueue(self, tool_id: str, args: dict[str, Any] | None = None, *, required_capability: str = "", priority: int = 5) -> DistributedTask:
        task = DistributedTask(
            task_id=uuid.uuid4().hex,
            tool_id=str(tool_id),
            args=dict(args or {}),
            required_capability=required_capability,
            priority=int(priority),
        )
        data = self._load()
        data.setdefault("tasks", {})[task.task_id] = task.to_dict()
        self._write(data)
        publish_event(AIEventType.DISTRIBUTED_TASK_QUEUED, task.to_dict(), source="core.distributed")
        return task

    def next_ready(self) -> DistributedTask | None:
        now = time.time()
        tasks = [
            self._task_from(row)
            for row in (self._load().get("tasks") or {}).values()
            if row.get("state") in {TaskQueueState.QUEUED.value, TaskQueueState.RETRY_SCHEDULED.value}
            and float(row.get("scheduled_at", 0.0)) <= now
        ]
        tasks.sort(key=lambda task: (-task.priority, task.created_at))
        return tasks[0] if tasks else None

    def assign(self, task_id: str, node_id: str) -> DistributedTask | None:
        return self._update(task_id, state=TaskQueueState.ASSIGNED, assigned_node=node_id, attempts_delta=1)

    def complete(self, task_id: str, result: dict[str, Any]) -> DistributedTask | None:
        return self._update(task_id, state=TaskQueueState.COMPLETED, result=dict(result), error="")

    def fail(self, task_id: str, error: str, *, retry_delay_s: float = 0.0) -> DistributedTask | None:
        task = self.get(task_id)
        if not task:
            return None
        retry = task.attempts < task.max_attempts
        state = TaskQueueState.RETRY_SCHEDULED if retry else TaskQueueState.FAILED
        return self._update(task_id, state=state, error=error, scheduled_at=time.time() + retry_delay_s)

    def get(self, task_id: str) -> DistributedTask | None:
        row = (self._load().get("tasks") or {}).get(task_id)
        return self._task_from(row) if row else None

    def list(self) -> list[DistributedTask]:
        return [self._task_from(row) for row in (self._load().get("tasks") or {}).values()]

    def _update(self, task_id: str, *, state: TaskQueueState, attempts_delta: int = 0, **updates: Any) -> DistributedTask | None:
        data = self._load()
        row = (data.get("tasks") or {}).get(task_id)
        if not row:
            return None
        row.update(updates)
        row["state"] = state.value
        row["attempts"] = int(row.get("attempts", 0)) + attempts_delta
        data["tasks"][task_id] = row
        self._write(data)
        task = self._task_from(row)
        if state == TaskQueueState.ASSIGNED:
            publish_event(AIEventType.DISTRIBUTED_TASK_ASSIGNED, task.to_dict(), source="core.distributed")
        return task

    def _task_from(self, row: dict[str, Any]) -> DistributedTask:
        return DistributedTask(
            task_id=str(row.get("task_id") or ""),
            tool_id=str(row.get("tool_id") or ""),
            args=dict(row.get("args") or {}),
            required_capability=str(row.get("required_capability") or ""),
            priority=int(row.get("priority", 5)),
            state=TaskQueueState(row.get("state", TaskQueueState.QUEUED.value)),
            assigned_node=str(row.get("assigned_node") or ""),
            attempts=int(row.get("attempts", 0)),
            max_attempts=int(row.get("max_attempts", 2)),
            scheduled_at=float(row.get("scheduled_at", time.time())),
            created_at=float(row.get("created_at", time.time())),
            result=dict(row.get("result") or {}),
            error=str(row.get("error") or ""),
        )

