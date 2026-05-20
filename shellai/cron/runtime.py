from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, Optional

from shellai.config import ShellAIConfig
from shellai.memory import MemoryStore
from shellai.monitor import list_trace_snapshots, trace_log_path


JobFunc = Callable[[ShellAIConfig, MemoryStore, bool], dict[str, Any]]


def _memory_maintenance(config: ShellAIConfig, memory: MemoryStore, dry_run: bool) -> dict[str, Any]:
    cutoff = time.time() - (30 * 24 * 60 * 60)
    with memory._connect() as conn:
        rows = conn.execute(
            "SELECT id, metadata_json FROM conversation_memory WHERE timestamp < ? LIMIT 100",
            (cutoff,),
        ).fetchall()
        if not dry_run:
            for row in rows:
                try:
                    metadata = json.loads(row["metadata_json"] or "{}")
                except Exception:
                    metadata = {}
                metadata["maintenance_checked_at"] = time.time()
                conn.execute(
                    "UPDATE conversation_memory SET metadata_json = ? WHERE id = ?",
                    (json.dumps(metadata, ensure_ascii=False, sort_keys=True), row["id"]),
                )
            conn.commit()
    return {"job": "memory_maintenance", "dry_run": dry_run, "matched_rows": len(rows)}


def _skill_usage_report(config: ShellAIConfig, memory: MemoryStore, dry_run: bool) -> dict[str, Any]:
    skills = memory.list_skills({"limit": 200})
    top = sorted(skills, key=lambda item: int(item.get("success_count") or 0), reverse=True)[:10]
    return {
        "job": "skill_usage_report",
        "dry_run": dry_run,
        "skill_count": len(skills),
        "top_skills": [
            {
                "skill_id": skill.get("skill_id"),
                "name": skill.get("name"),
                "success_count": skill.get("success_count"),
                "failure_count": skill.get("failure_count"),
            }
            for skill in top
        ],
    }


def _trace_cleanup(config: ShellAIConfig, memory: MemoryStore, dry_run: bool) -> dict[str, Any]:
    path = trace_log_path(config)
    if not path.exists():
        return {"job": "trace_cleanup", "dry_run": dry_run, "before": 0, "after": 0}
    rows = list_trace_snapshots(config, limit=10000)
    keep = rows[:500]
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in reversed(keep):
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {"job": "trace_cleanup", "dry_run": dry_run, "before": len(rows), "after": len(keep)}


_JOBS: Dict[str, JobFunc] = {
    "memory_maintenance": _memory_maintenance,
    "skill_usage_report": _skill_usage_report,
    "trace_cleanup": _trace_cleanup,
}


def list_jobs() -> list[dict[str, Any]]:
    return [
        {"name": name, "enabled_by_default": False}
        for name in sorted(_JOBS)
    ]


def run_job(
    name: str,
    dry_run: bool = False,
    *,
    config: Optional[ShellAIConfig] = None,
    memory_store: Optional[MemoryStore] = None,
) -> dict[str, Any]:
    key = str(name or "").strip()
    if key not in _JOBS:
        raise KeyError(f"Unknown cron job: {name}")
    active_config = config or ShellAIConfig.load()
    memory = memory_store or MemoryStore(active_config.paths.memory_db, config=active_config)
    result = _JOBS[key](active_config, memory, bool(dry_run))
    result["status"] = "ok"
    return result


__all__ = ["list_jobs", "run_job"]
