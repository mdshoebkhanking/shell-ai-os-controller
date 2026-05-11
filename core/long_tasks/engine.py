from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event


class LongTaskState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    task_id: str
    label: str
    state: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"checkpoint_id": self.checkpoint_id, "task_id": self.task_id, "label": self.label, "state": dict(self.state), "created_at": self.created_at}


@dataclass(frozen=True)
class LongTask:
    task_id: str
    title: str
    state: LongTaskState = LongTaskState.PENDING
    progress: float = 0.0
    checkpoints: list[Checkpoint] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    resume_after: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "state": self.state.value,
            "progress": self.progress,
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
            "dependencies": list(self.dependencies),
            "resume_after": self.resume_after,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class LongTaskEngine:
    def __init__(self, path: str | Path = ".shell_runtime/long_tasks.json"):
        self.path = Path(path)

    def create_task(self, title: str, *, dependencies: list[str] | None = None, resume_after: float = 0.0) -> LongTask:
        task = LongTask(uuid.uuid4().hex, title, dependencies=list(dependencies or []), resume_after=resume_after)
        data = self._load()
        data.setdefault("tasks", {})[task.task_id] = task.to_dict()
        self._write(data)
        publish_event(AIEventType.TASK_STARTED, task.to_dict(), source="core.long_tasks")
        return task

    def checkpoint(self, task_id: str, label: str, state: dict[str, Any] | None = None, *, progress: float | None = None) -> LongTask | None:
        task = self.get(task_id)
        if not task:
            return None
        cp = Checkpoint(uuid.uuid4().hex, task_id, label, dict(state or {}))
        return self._update(
            task_id,
            checkpoints=[*task.checkpoints, cp],
            progress=task.progress if progress is None else max(0.0, min(1.0, float(progress))),
            state=LongTaskState.RUNNING,
            event_payload=cp.to_dict(),
        )

    def pause(self, task_id: str) -> LongTask | None:
        return self._update(task_id, state=LongTaskState.PAUSED)

    def resume(self, task_id: str) -> LongTask | None:
        return self._update(task_id, state=LongTaskState.RUNNING, resume_after=0.0)

    def complete(self, task_id: str) -> LongTask | None:
        return self._update(task_id, state=LongTaskState.COMPLETED, progress=1.0)

    def get(self, task_id: str) -> LongTask | None:
        row = (self._load().get("tasks") or {}).get(task_id)
        return self._task_from(row) if row else None

    def list_due(self, *, now: float | None = None) -> list[LongTask]:
        now_ts = time.time() if now is None else float(now)
        return [
            task for task in self.list()
            if task.state in {LongTaskState.PENDING, LongTaskState.WAITING, LongTaskState.PAUSED}
            and task.resume_after <= now_ts
        ]

    def list(self) -> list[LongTask]:
        return [self._task_from(row) for row in (self._load().get("tasks") or {}).values()]

    def _update(self, task_id: str, *, event_payload: dict[str, Any] | None = None, **updates: Any) -> LongTask | None:
        data = self._load()
        row = (data.get("tasks") or {}).get(task_id)
        if not row:
            return None
        for key, value in updates.items():
            if key == "state" and isinstance(value, LongTaskState):
                row[key] = value.value
            elif key == "checkpoints":
                row[key] = [cp.to_dict() if isinstance(cp, Checkpoint) else dict(cp) for cp in value]
            else:
                row[key] = value
        row["updated_at"] = time.time()
        self._write(data)
        task = self._task_from(row)
        publish_event(AIEventType.LONG_TASK_CHECKPOINTED, event_payload or task.to_dict(), source="core.long_tasks")
        return task

    def _task_from(self, row: dict[str, Any]) -> LongTask:
        checkpoints = [
            Checkpoint(
                checkpoint_id=str(cp.get("checkpoint_id") or ""),
                task_id=str(cp.get("task_id") or row.get("task_id") or ""),
                label=str(cp.get("label") or ""),
                state=dict(cp.get("state") or {}),
                created_at=float(cp.get("created_at", 0.0)),
            )
            for cp in row.get("checkpoints", [])
        ]
        return LongTask(
            task_id=str(row.get("task_id") or ""),
            title=str(row.get("title") or ""),
            state=LongTaskState(row.get("state", LongTaskState.PENDING.value)),
            progress=float(row.get("progress", 0.0)),
            checkpoints=checkpoints,
            dependencies=list(row.get("dependencies") or []),
            resume_after=float(row.get("resume_after", 0.0)),
            created_at=float(row.get("created_at", 0.0)),
            updated_at=float(row.get("updated_at", 0.0)),
        )

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

