from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from core.events import AIEventType, publish_event
except Exception:  # pragma: no cover - event bus is optional for headless tests
    AIEventType = None  # type: ignore

    def publish_event(*_args: Any, **_kwargs: Any) -> None:
        return None


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def workflow_checkpoints_enabled() -> bool:
    return _truthy(os.environ.get("SHELL_WORKFLOW_CHECKPOINTS_ENABLED"))


def _runtime_path(default_name: str) -> Path:
    return Path(os.environ.get("SHELL_WORKFLOW_CHECKPOINTS_PATH", f".shell_runtime/{default_name}")).expanduser()


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(dict(value or {}), ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return dict(parsed) if isinstance(parsed, dict) else {"value": parsed}
    except Exception:
        return {}


@dataclass(frozen=True)
class WorkflowCheckpoint:
    checkpoint_id: str
    workflow_id: str
    step_index: int
    action: str
    state: dict[str, Any] = field(default_factory=dict)
    rollback_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    parent_checkpoint_id: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "workflow_id": self.workflow_id,
            "step_index": self.step_index,
            "action": self.action,
            "state": dict(self.state),
            "rollback_state": dict(self.rollback_state),
            "metadata": dict(self.metadata),
            "status": self.status,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class WorkflowState:
    workflow_id: str
    latest_checkpoint_id: str = ""
    last_action: str = ""
    step_index: int = 0
    state: dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    checkpoint_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "latest_checkpoint_id": self.latest_checkpoint_id,
            "last_action": self.last_action,
            "step_index": self.step_index,
            "state": dict(self.state),
            "status": self.status,
            "checkpoint_count": self.checkpoint_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class WorkflowCheckpointConfig:
    path: Path = field(default_factory=lambda: _runtime_path("workflow_checkpoints.sqlite3"))
    backend: str = field(default_factory=lambda: os.environ.get("SHELL_WORKFLOW_CHECKPOINTS_BACKEND", "sqlite").strip().lower() or "sqlite")
    max_per_workflow: int = 100

    @classmethod
    def from_environment(cls) -> "WorkflowCheckpointConfig":
        backend = os.environ.get("SHELL_WORKFLOW_CHECKPOINTS_BACKEND", "sqlite").strip().lower() or "sqlite"
        default_name = "workflow_checkpoints.json" if backend == "json" else "workflow_checkpoints.sqlite3"
        try:
            max_per_workflow = int(os.environ.get("SHELL_WORKFLOW_CHECKPOINTS_MAX_PER_WORKFLOW", "100"))
        except Exception:
            max_per_workflow = 100
        return cls(
            path=Path(os.environ.get("SHELL_WORKFLOW_CHECKPOINTS_PATH", f".shell_runtime/{default_name}")).expanduser(),
            backend=backend,
            max_per_workflow=max(1, min(1000, max_per_workflow)),
        )


class WorkflowCheckpointManager:
    def __init__(self, config: WorkflowCheckpointConfig | None = None):
        self.config = config or WorkflowCheckpointConfig.from_environment()
        if self.config.backend not in {"sqlite", "json"}:
            raise ValueError(f"unsupported checkpoint backend: {self.config.backend}")

    def save_checkpoint(
        self,
        workflow_id: str,
        state: dict[str, Any],
        *,
        action: str = "",
        step_index: int | None = None,
        rollback_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "running",
    ) -> WorkflowCheckpoint:
        workflow_id = str(workflow_id or "").strip()
        if not workflow_id:
            raise ValueError("workflow_id is required")
        previous = self.get_workflow(workflow_id)
        resolved_step = int(step_index) if step_index is not None else ((previous.step_index + 1) if previous else 1)
        checkpoint = WorkflowCheckpoint(
            checkpoint_id=uuid.uuid4().hex,
            workflow_id=workflow_id,
            step_index=resolved_step,
            action=str(action or "checkpoint"),
            state=dict(state or {}),
            rollback_state=dict(rollback_state or {}),
            metadata=dict(metadata or {}),
            status=str(status or "running"),
            parent_checkpoint_id=previous.latest_checkpoint_id if previous else "",
        )
        if self.config.backend == "json":
            self._json_save_checkpoint(checkpoint)
        else:
            self._sqlite_save_checkpoint(checkpoint)
        self._publish("STATE_SNAPSHOT_CREATED", checkpoint.to_dict())
        return checkpoint

    def load_checkpoint(self, workflow_id: str, checkpoint_id: str = "") -> WorkflowCheckpoint | None:
        if self.config.backend == "json":
            return self._json_load_checkpoint(workflow_id, checkpoint_id)
        return self._sqlite_load_checkpoint(workflow_id, checkpoint_id)

    def list_checkpoints(self, workflow_id: str, *, limit: int = 20) -> list[WorkflowCheckpoint]:
        if self.config.backend == "json":
            return self._json_list_checkpoints(workflow_id, limit=limit)
        return self._sqlite_list_checkpoints(workflow_id, limit=limit)

    def get_workflow(self, workflow_id: str) -> WorkflowState | None:
        if self.config.backend == "json":
            return self._json_get_workflow(workflow_id)
        return self._sqlite_get_workflow(workflow_id)

    def status(self, workflow_id: str = "") -> dict[str, Any]:
        if workflow_id:
            state = self.get_workflow(workflow_id)
            return {
                "ok": state is not None,
                "enabled": workflow_checkpoints_enabled(),
                "backend": self.config.backend,
                "path": str(self.config.path),
                "workflow": state.to_dict() if state else None,
            }
        return {
            "ok": True,
            "enabled": workflow_checkpoints_enabled(),
            "backend": self.config.backend,
            "path": str(self.config.path),
            "workflow_count": self._workflow_count(),
            "max_per_workflow": self.config.max_per_workflow,
        }

    def rollback(self, workflow_id: str, checkpoint_id: str = "") -> dict[str, Any]:
        target = self.load_checkpoint(workflow_id, checkpoint_id)
        if not target:
            return {"ok": False, "error": "checkpoint not found", "workflow_id": workflow_id, "checkpoint_id": checkpoint_id}
        restored_state = dict(target.rollback_state or target.state)
        rollback_cp = self.save_checkpoint(
            workflow_id,
            restored_state,
            action=f"rollback:{target.checkpoint_id[:12]}",
            step_index=target.step_index,
            rollback_state=target.state,
            metadata={"rollback_target": target.checkpoint_id},
            status="rolled_back",
        )
        payload = {
            "ok": True,
            "workflow_id": workflow_id,
            "target_checkpoint_id": target.checkpoint_id,
            "restored_state": restored_state,
            "checkpoint": rollback_cp.to_dict(),
        }
        self._publish("WORKSPACE_RESTORED", payload)
        return payload

    def _sqlite_connect(self) -> sqlite3.Connection:
        self.config.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.config.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                action TEXT NOT NULL,
                state_json TEXT NOT NULL,
                rollback_state_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                status TEXT NOT NULL,
                parent_checkpoint_id TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workflows (
                workflow_id TEXT PRIMARY KEY,
                latest_checkpoint_id TEXT NOT NULL,
                last_action TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                status TEXT NOT NULL,
                checkpoint_count INTEGER NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_workflow_created ON checkpoints(workflow_id, created_at)")
        return conn

    def _sqlite_save_checkpoint(self, checkpoint: WorkflowCheckpoint) -> None:
        with self._sqlite_connect() as conn:
            now = time.time()
            existing = self._sqlite_get_workflow(checkpoint.workflow_id, conn=conn)
            created_at = existing.created_at if existing else now
            checkpoint_count = (existing.checkpoint_count if existing else 0) + 1
            conn.execute(
                """
                INSERT INTO checkpoints (
                    checkpoint_id, workflow_id, step_index, action, state_json,
                    rollback_state_json, metadata_json, status, parent_checkpoint_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.checkpoint_id,
                    checkpoint.workflow_id,
                    checkpoint.step_index,
                    checkpoint.action,
                    _json_dumps(checkpoint.state),
                    _json_dumps(checkpoint.rollback_state),
                    _json_dumps(checkpoint.metadata),
                    checkpoint.status,
                    checkpoint.parent_checkpoint_id,
                    checkpoint.created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO workflows (
                    workflow_id, latest_checkpoint_id, last_action, step_index,
                    state_json, status, checkpoint_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id) DO UPDATE SET
                    latest_checkpoint_id=excluded.latest_checkpoint_id,
                    last_action=excluded.last_action,
                    step_index=excluded.step_index,
                    state_json=excluded.state_json,
                    status=excluded.status,
                    checkpoint_count=excluded.checkpoint_count,
                    updated_at=excluded.updated_at
                """,
                (
                    checkpoint.workflow_id,
                    checkpoint.checkpoint_id,
                    checkpoint.action,
                    checkpoint.step_index,
                    _json_dumps(checkpoint.state),
                    checkpoint.status,
                    checkpoint_count,
                    created_at,
                    now,
                ),
            )
            self._sqlite_prune(checkpoint.workflow_id, conn=conn)

    def _sqlite_load_checkpoint(self, workflow_id: str, checkpoint_id: str = "") -> WorkflowCheckpoint | None:
        with self._sqlite_connect() as conn:
            if checkpoint_id:
                row = conn.execute(
                    "SELECT * FROM checkpoints WHERE workflow_id=? AND checkpoint_id=?",
                    (workflow_id, checkpoint_id),
                ).fetchone()
            else:
                workflow = self._sqlite_get_workflow(workflow_id, conn=conn)
                if not workflow:
                    return None
                row = conn.execute(
                    "SELECT * FROM checkpoints WHERE workflow_id=? AND checkpoint_id=?",
                    (workflow_id, workflow.latest_checkpoint_id),
                ).fetchone()
            return self._checkpoint_from_row(row) if row else None

    def _sqlite_list_checkpoints(self, workflow_id: str, *, limit: int = 20) -> list[WorkflowCheckpoint]:
        with self._sqlite_connect() as conn:
            rows = conn.execute(
                "SELECT * FROM checkpoints WHERE workflow_id=? ORDER BY created_at DESC LIMIT ?",
                (workflow_id, max(1, int(limit))),
            ).fetchall()
        return [self._checkpoint_from_row(row) for row in rows]

    def _sqlite_get_workflow(self, workflow_id: str, *, conn: sqlite3.Connection | None = None) -> WorkflowState | None:
        owns_conn = conn is None
        if conn is None:
            conn = self._sqlite_connect()
        try:
            row = conn.execute("SELECT * FROM workflows WHERE workflow_id=?", (workflow_id,)).fetchone()
            return self._workflow_from_row(row) if row else None
        finally:
            if owns_conn:
                conn.close()

    def _sqlite_prune(self, workflow_id: str, *, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            "SELECT checkpoint_id FROM checkpoints WHERE workflow_id=? ORDER BY created_at DESC",
            (workflow_id,),
        ).fetchall()
        stale = [row["checkpoint_id"] for row in rows[self.config.max_per_workflow :]]
        if stale:
            conn.executemany("DELETE FROM checkpoints WHERE checkpoint_id=?", [(item,) for item in stale])

    def _workflow_count(self) -> int:
        if self.config.backend == "json":
            return len(self._json_load().get("workflows", {}))
        with self._sqlite_connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0])

    @staticmethod
    def _checkpoint_from_row(row: sqlite3.Row) -> WorkflowCheckpoint:
        return WorkflowCheckpoint(
            checkpoint_id=str(row["checkpoint_id"]),
            workflow_id=str(row["workflow_id"]),
            step_index=int(row["step_index"]),
            action=str(row["action"]),
            state=_json_loads(row["state_json"]),
            rollback_state=_json_loads(row["rollback_state_json"]),
            metadata=_json_loads(row["metadata_json"]),
            status=str(row["status"]),
            parent_checkpoint_id=str(row["parent_checkpoint_id"] or ""),
            created_at=float(row["created_at"]),
        )

    @staticmethod
    def _workflow_from_row(row: sqlite3.Row) -> WorkflowState:
        return WorkflowState(
            workflow_id=str(row["workflow_id"]),
            latest_checkpoint_id=str(row["latest_checkpoint_id"]),
            last_action=str(row["last_action"]),
            step_index=int(row["step_index"]),
            state=_json_loads(row["state_json"]),
            status=str(row["status"]),
            checkpoint_count=int(row["checkpoint_count"]),
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
        )

    def _json_load(self) -> dict[str, Any]:
        if not self.config.path.exists():
            return {"workflows": {}, "checkpoints": {}}
        try:
            data = json.loads(self.config.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"workflows": {}, "checkpoints": {}}
        except Exception:
            return {"workflows": {}, "checkpoints": {}}

    def _json_write(self, data: dict[str, Any]) -> None:
        self.config.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.config.path.with_suffix(self.config.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.config.path)

    def _json_save_checkpoint(self, checkpoint: WorkflowCheckpoint) -> None:
        data = self._json_load()
        workflows = data.setdefault("workflows", {})
        checkpoints = data.setdefault("checkpoints", {})
        rows = list(checkpoints.get(checkpoint.workflow_id) or [])
        previous = workflows.get(checkpoint.workflow_id) or {}
        rows.append(checkpoint.to_dict())
        if len(rows) > self.config.max_per_workflow:
            rows = rows[-self.config.max_per_workflow :]
        checkpoints[checkpoint.workflow_id] = rows
        now = time.time()
        workflows[checkpoint.workflow_id] = {
            "workflow_id": checkpoint.workflow_id,
            "latest_checkpoint_id": checkpoint.checkpoint_id,
            "last_action": checkpoint.action,
            "step_index": checkpoint.step_index,
            "state": dict(checkpoint.state),
            "status": checkpoint.status,
            "checkpoint_count": len(rows),
            "created_at": float(previous.get("created_at") or now),
            "updated_at": now,
        }
        self._json_write(data)

    def _json_load_checkpoint(self, workflow_id: str, checkpoint_id: str = "") -> WorkflowCheckpoint | None:
        rows = list((self._json_load().get("checkpoints") or {}).get(workflow_id) or [])
        if checkpoint_id:
            matches = [row for row in rows if row.get("checkpoint_id") == checkpoint_id]
            row = matches[0] if matches else None
        else:
            row = rows[-1] if rows else None
        return self._checkpoint_from_dict(row) if row else None

    def _json_list_checkpoints(self, workflow_id: str, *, limit: int = 20) -> list[WorkflowCheckpoint]:
        rows = list((self._json_load().get("checkpoints") or {}).get(workflow_id) or [])
        return [self._checkpoint_from_dict(row) for row in reversed(rows[-max(1, int(limit)) :])]

    def _json_get_workflow(self, workflow_id: str) -> WorkflowState | None:
        row = (self._json_load().get("workflows") or {}).get(workflow_id)
        if not row:
            return None
        return WorkflowState(
            workflow_id=str(row.get("workflow_id") or workflow_id),
            latest_checkpoint_id=str(row.get("latest_checkpoint_id") or ""),
            last_action=str(row.get("last_action") or ""),
            step_index=int(row.get("step_index") or 0),
            state=dict(row.get("state") or {}),
            status=str(row.get("status") or "running"),
            checkpoint_count=int(row.get("checkpoint_count") or 0),
            created_at=float(row.get("created_at") or 0.0),
            updated_at=float(row.get("updated_at") or 0.0),
        )

    @staticmethod
    def _checkpoint_from_dict(row: dict[str, Any]) -> WorkflowCheckpoint:
        return WorkflowCheckpoint(
            checkpoint_id=str(row.get("checkpoint_id") or ""),
            workflow_id=str(row.get("workflow_id") or ""),
            step_index=int(row.get("step_index") or 0),
            action=str(row.get("action") or ""),
            state=dict(row.get("state") or {}),
            rollback_state=dict(row.get("rollback_state") or {}),
            metadata=dict(row.get("metadata") or {}),
            status=str(row.get("status") or "running"),
            parent_checkpoint_id=str(row.get("parent_checkpoint_id") or ""),
            created_at=float(row.get("created_at") or 0.0),
        )

    @staticmethod
    def _publish(event_name: str, payload: dict[str, Any]) -> None:
        try:
            event_type = getattr(AIEventType, event_name, event_name) if AIEventType else event_name
            publish_event(event_type, payload, source="core.workflow_checkpoints")
        except Exception:
            pass


__all__ = [
    "WorkflowCheckpoint",
    "WorkflowCheckpointConfig",
    "WorkflowCheckpointManager",
    "WorkflowState",
    "workflow_checkpoints_enabled",
]
