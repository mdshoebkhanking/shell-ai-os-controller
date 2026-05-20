from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from shellai.config import ShellAIConfig


DAEMON_STATE_FILE = "daemon_state.json"
DAEMON_ENABLED_ENV = "SHELLAI_DAEMON_ENABLED"


def daemon_enabled() -> bool:
    return os.environ.get(DAEMON_ENABLED_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


class ShellAIDaemon:
    """Minimal file-backed task queue for opt-in local daemon mode."""

    def __init__(self, config: Optional[ShellAIConfig] = None) -> None:
        self.config = config or ShellAIConfig.load()
        self.path = self.config.paths.data_dir / DAEMON_STATE_FILE

    def _default_state(self) -> dict[str, Any]:
        return {"running": False, "queue": [], "results": [], "updated_at": time.time()}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default_state()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                state = self._default_state()
                state.update(data)
                return state
        except Exception:
            pass
        return self._default_state()

    def _save(self, state: dict[str, Any]) -> dict[str, Any]:
        self.config.paths.ensure_runtime_dirs()
        state["updated_at"] = time.time()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)
        return state

    def start(self) -> dict[str, Any]:
        state = self._load()
        if not daemon_enabled():
            state["running"] = False
            state["enabled"] = False
            state["message"] = f"Daemon disabled. Set {DAEMON_ENABLED_ENV}=1 to enable."
            self._save(state)
            return self.status()
        state["running"] = True
        state["enabled"] = True
        state["message"] = "Daemon marked running."
        self._save(state)
        return self.status()

    def stop(self) -> dict[str, Any]:
        state = self._load()
        state["running"] = False
        state["enabled"] = daemon_enabled()
        state["message"] = "Daemon stopped."
        self._save(state)
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self._load()
        return {
            "enabled": daemon_enabled(),
            "running": bool(state.get("running")),
            "queued_tasks": len(state.get("queue") or []),
            "recent_results": list(state.get("results") or [])[-5:],
            "state_file": str(self.path),
            "message": state.get("message", ""),
        }

    def enqueue_task(self, text: str, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        state = self._load()
        task = {
            "id": uuid.uuid4().hex,
            "text": str(text or ""),
            "context": dict(context or {}),
            "created_at": time.time(),
        }
        queue = list(state.get("queue") or [])
        queue.append(task)
        state["queue"] = queue
        self._save(state)
        return task

    def process_next(self) -> Optional[dict[str, Any]]:
        state = self._load()
        queue = list(state.get("queue") or [])
        if not queue:
            self._save(state)
            return None
        task = queue.pop(0)
        from shellai.api import run_shellai_task

        result = run_shellai_task(
            str(task.get("text") or ""),
            context=dict(task.get("context") or {}),
            auto_approve_ask=False,
        )
        record = {
            "task": task,
            "result": {
                "ok": result.get("ok"),
                "status": result.get("status"),
                "summary": result.get("summary"),
                "trace_id": result.get("trace_id"),
            },
            "processed_at": time.time(),
        }
        results = list(state.get("results") or [])
        results.append(record)
        state["queue"] = queue
        state["results"] = results[-50:]
        self._save(state)
        return record

    def process_all(self, limit: int = 10) -> list[dict[str, Any]]:
        processed = []
        for _index in range(max(1, int(limit))):
            item = self.process_next()
            if item is None:
                break
            processed.append(item)
        return processed


__all__ = ["DAEMON_ENABLED_ENV", "ShellAIDaemon", "daemon_enabled"]
