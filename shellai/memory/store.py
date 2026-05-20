from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from shellai.config import DEFAULT_USER_PROFILE, ShellAIConfig
from shellai.observability import RequestTrace, get_logger
from shellai.protocol import AgentRole


def _json_dump(data: Any) -> str:
    return json.dumps(data if data is not None else {}, ensure_ascii=False, sort_keys=True)


def _json_load(raw: str | None, fallback: Any = None) -> Any:
    if not raw:
        return {} if fallback is None else fallback
    try:
        return json.loads(raw)
    except Exception:
        return {} if fallback is None else fallback


def _merge_dicts(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


class MemoryStore:
    """SQLite-backed memory facade for future MemoryAgent use."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str | Path | None = None, config: ShellAIConfig | None = None) -> None:
        self.config = config or ShellAIConfig.load()
        self.db_path = Path(db_path).expanduser() if db_path else self.config.paths.memory_db
        self.logger = get_logger("shellai.memory")
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    agent_role TEXT NOT NULL,
                    user_input TEXT NOT NULL DEFAULT '',
                    agent_output TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    embedding_ref TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_conversation_memory_conversation_id
                    ON conversation_memory(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_conversation_memory_timestamp
                    ON conversation_memory(timestamp);

                CREATE TABLE IF NOT EXISTS user_profile_memory (
                    user_id TEXT PRIMARY KEY,
                    updated_at REAL NOT NULL,
                    preferences_json TEXT NOT NULL DEFAULT '{}',
                    dev_workflows_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS skill_memory (
                    skill_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_used_at REAL,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    avg_duration_ms REAL
                );
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
                ("schema_version", str(self.SCHEMA_VERSION)),
            )
            conn.commit()

    def _record(
        self,
        trace: RequestTrace | None,
        *,
        memory_type: str,
        operation: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "memory_type": memory_type,
            "operation": operation,
            **dict(metadata or {}),
        }
        self.logger.info("memory.%s.%s %s", memory_type, operation, status)
        if trace is not None:
            trace.add_step("MemoryStore", status, f"{operation} {memory_type}", payload)

    def save_memory(self, memory_type: str, data: dict[str, Any], *, trace: RequestTrace | None = None) -> dict[str, Any]:
        try:
            if memory_type == "conversation":
                result = self.save_conversation(data, trace=trace)
            elif memory_type == "user_profile":
                result = self.update_user_profile(data, trace=trace)
            elif memory_type == "skill":
                result = self.save_skill(data, trace=trace)
            else:
                raise ValueError(f"Unsupported memory type: {memory_type}")
            self._record(trace, memory_type=memory_type, operation="save", status="ok", metadata={"result": result})
            return result
        except Exception as exc:
            self._record(trace, memory_type=memory_type, operation="save", status="error", metadata={"error": str(exc)})
            raise

    def search_memory(
        self,
        memory_type: str,
        query: str,
        *,
        limit: int = 10,
        trace: RequestTrace | None = None,
    ) -> list[dict[str, Any]]:
        try:
            if memory_type == "conversation":
                rows = self.search_conversations(query, limit=limit)
            elif memory_type == "user_profile":
                rows = self.search_user_profiles(query, limit=limit)
            elif memory_type == "skill":
                rows = self.list_skills({"query": query, "limit": limit})
            else:
                raise ValueError(f"Unsupported memory type: {memory_type}")
            self._record(
                trace,
                memory_type=memory_type,
                operation="search",
                status="ok",
                metadata={"query": query, "rows": len(rows)},
            )
            return rows
        except Exception as exc:
            self._record(trace, memory_type=memory_type, operation="search", status="error", metadata={"error": str(exc)})
            raise

    def save_conversation(self, data: dict[str, Any], *, trace: RequestTrace | None = None) -> dict[str, Any]:
        conversation_id = str(data.get("conversation_id") or uuid.uuid4().hex)
        role = AgentRole.normalize(data.get("agent_role") or AgentRole.COORDINATOR)
        timestamp = float(data.get("timestamp") or time.time())
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO conversation_memory (
                    conversation_id, timestamp, agent_role, user_input,
                    agent_output, summary, embedding_ref, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    timestamp,
                    role,
                    str(data.get("user_input") or ""),
                    str(data.get("agent_output") or ""),
                    str(data.get("summary") or ""),
                    str(data.get("embedding_ref") or ""),
                    _json_dump(data.get("metadata") or {}),
                ),
            )
            conn.commit()
            return {"id": int(cursor.lastrowid), "conversation_id": conversation_id}

    def search_conversations(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        pattern = f"%{str(query or '').strip()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM conversation_memory
                WHERE user_input LIKE ?
                   OR agent_output LIKE ?
                   OR summary LIKE ?
                   OR metadata_json LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, max(1, int(limit))),
            ).fetchall()
        return [self._conversation_row(row) for row in rows]

    @staticmethod
    def _conversation_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "conversation_id": row["conversation_id"],
            "timestamp": row["timestamp"],
            "agent_role": row["agent_role"],
            "user_input": row["user_input"],
            "agent_output": row["agent_output"],
            "summary": row["summary"],
            "embedding_ref": row["embedding_ref"],
            "metadata": _json_load(row["metadata_json"]),
        }

    def update_user_profile(
        self,
        patch: dict[str, Any],
        *,
        user_id: str = "local",
        trace: RequestTrace | None = None,
    ) -> dict[str, Any]:
        current = self.get_user_profile(user_id=user_id)
        preferences = _merge_dicts(dict(current.get("preferences") or {}), dict(patch.get("preferences") or {}))
        dev_workflows = _merge_dicts(dict(current.get("dev_workflows") or {}), dict(patch.get("dev_workflows") or {}))
        metadata_patch = dict(patch.get("metadata") or {})
        direct_preferences = {
            key: value
            for key, value in patch.items()
            if key not in {"preferences", "dev_workflows", "metadata", "user_id"}
        }
        if direct_preferences:
            preferences = _merge_dicts(preferences, direct_preferences)
        metadata = _merge_dicts(dict(current.get("metadata") or {}), metadata_patch)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profile_memory (
                    user_id, updated_at, preferences_json, dev_workflows_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    preferences_json = excluded.preferences_json,
                    dev_workflows_json = excluded.dev_workflows_json,
                    metadata_json = excluded.metadata_json
                """,
                (
                    user_id,
                    time.time(),
                    _json_dump(preferences),
                    _json_dump(dev_workflows),
                    _json_dump(metadata),
                ),
            )
            conn.commit()
        return self.get_user_profile(user_id=user_id)

    def get_user_profile(self, *, user_id: str = "local") -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_profile_memory WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return {
                "user_id": user_id,
                "updated_at": None,
                "preferences": dict(DEFAULT_USER_PROFILE),
                "dev_workflows": {
                    "tools": list(DEFAULT_USER_PROFILE.get("high_priority_tools", [])),
                    "os_priority": list(DEFAULT_USER_PROFILE.get("os_priority", [])),
                },
                "metadata": {},
            }
        return {
            "user_id": row["user_id"],
            "updated_at": row["updated_at"],
            "preferences": _json_load(row["preferences_json"]),
            "dev_workflows": _json_load(row["dev_workflows_json"]),
            "metadata": _json_load(row["metadata_json"]),
        }

    def search_user_profiles(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        pattern = f"%{str(query or '').strip()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM user_profile_memory
                WHERE user_id LIKE ?
                   OR preferences_json LIKE ?
                   OR dev_workflows_json LIKE ?
                   OR metadata_json LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, max(1, int(limit))),
            ).fetchall()
        return [
            {
                "user_id": row["user_id"],
                "updated_at": row["updated_at"],
                "preferences": _json_load(row["preferences_json"]),
                "dev_workflows": _json_load(row["dev_workflows_json"]),
                "metadata": _json_load(row["metadata_json"]),
            }
            for row in rows
        ]

    def save_skill(self, data: dict[str, Any], *, trace: RequestTrace | None = None) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("Skill name is required")
        skill_id = str(data.get("skill_id") or uuid.uuid5(uuid.NAMESPACE_URL, f"shellai.skill:{name}").hex)
        now = time.time()
        metadata = dict(data.get("metadata") or {})
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT created_at, success_count, failure_count, avg_duration_ms, last_used_at FROM skill_memory WHERE skill_id = ? OR name = ?",
                (skill_id, name),
            ).fetchone()
            created_at = float(existing["created_at"]) if existing else now
            conn.execute(
                """
                INSERT INTO skill_memory (
                    skill_id, name, description, metadata_json, created_at, updated_at,
                    last_used_at, success_count, failure_count, avg_duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(skill_id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    skill_id,
                    name,
                    str(data.get("description") or ""),
                    _json_dump(metadata),
                    created_at,
                    now,
                    existing["last_used_at"] if existing else None,
                    int(existing["success_count"]) if existing else 0,
                    int(existing["failure_count"]) if existing else 0,
                    existing["avg_duration_ms"] if existing else None,
                ),
            )
            conn.commit()
        return {"skill_id": skill_id, "name": name}

    def get_skill(self, name_or_id: str) -> dict[str, Any] | None:
        key = str(name_or_id or "").strip()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM skill_memory WHERE skill_id = ? OR name = ?",
                (key, key),
            ).fetchone()
        return self._skill_row(row) if row else None

    def list_skills(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = dict(filters or {})
        query = str(filters.get("query") or "").strip()
        limit = max(1, int(filters.get("limit") or 50))
        with self._connect() as conn:
            if query:
                pattern = f"%{query}%"
                rows = conn.execute(
                    """
                    SELECT * FROM skill_memory
                    WHERE name LIKE ? OR description LIKE ? OR metadata_json LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (pattern, pattern, pattern, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM skill_memory ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._skill_row(row) for row in rows]

    def record_skill_usage(self, skill_id: str, success: bool, duration_ms: int | None = None) -> dict[str, Any]:
        skill = self.get_skill(skill_id)
        if not skill:
            raise KeyError(f"Unknown skill: {skill_id}")
        old_avg = skill.get("avg_duration_ms")
        old_success = int(skill.get("success_count") or 0)
        old_failure = int(skill.get("failure_count") or 0)
        new_success = old_success + (1 if success else 0)
        new_failure = old_failure + (0 if success else 1)
        new_avg = old_avg
        if duration_ms is not None:
            previous_count = old_success + old_failure
            if old_avg is None or previous_count <= 0:
                new_avg = float(duration_ms)
            else:
                new_avg = ((float(old_avg) * previous_count) + float(duration_ms)) / (previous_count + 1)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE skill_memory
                SET last_used_at = ?, success_count = ?, failure_count = ?, avg_duration_ms = ?
                WHERE skill_id = ?
                """,
                (time.time(), new_success, new_failure, new_avg, skill["skill_id"]),
            )
            conn.commit()
        return self.get_skill(skill["skill_id"]) or {}

    @staticmethod
    def _skill_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "skill_id": row["skill_id"],
            "name": row["name"],
            "description": row["description"],
            "metadata": _json_load(row["metadata_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_used_at": row["last_used_at"],
            "success_count": row["success_count"],
            "failure_count": row["failure_count"],
            "avg_duration_ms": row["avg_duration_ms"],
        }
