from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
DEFAULT_DECAY_HALF_LIFE_DAYS = 30.0

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_KEY_VALUE_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd)\s*[:=]\s*(['\"]?)[^\s'\"\n]{6,}\2"
)
_LONG_SECRET_RE = re.compile(r"\b(?:sk|pk|ghp|gho|xoxb|xoxp|ya29)[-_][A-Za-z0-9._~+/=-]{10,}\b")
_LONG_NUMBER_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{8,}\d(?!\w)")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_./+=-]+")


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def memory_v2_enabled() -> bool:
    return _truthy(os.environ.get("SHELL_MEMORY_V2_ENABLED"))


def default_memory_v2_path() -> Path:
    raw = os.environ.get("SHELL_MEMORY_V2_PATH")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".shell_memory_v2.sqlite3"


def _json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _json_load(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _clamp_importance(value: Any) -> int:
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return 50


def normalize_tags(tags: str | Iterable[str] | None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        raw_items = re.split(r"[,#\s]+", tags)
    else:
        raw_items = [str(item) for item in tags]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        tag = re.sub(r"[^a-z0-9_.:-]+", "-", str(item).strip().lower()).strip("-")
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def redact_sensitive_text(text: str) -> str:
    safe = str(text or "")
    safe = _KEY_VALUE_SECRET_RE.sub(lambda match: f"{match.group(1)}=<redacted:secret>", safe)
    safe = _BEARER_RE.sub("Bearer <redacted:token>", safe)
    safe = _LONG_SECRET_RE.sub("<redacted:token>", safe)
    safe = _EMAIL_RE.sub("<redacted:email>", safe)
    safe = _LONG_NUMBER_RE.sub("<redacted:number>", safe)
    safe = _PHONE_RE.sub("<redacted:phone>", safe)
    return safe


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(str(text or "")) if len(match.group(0)) >= 2}


def estimate_importance(text: str, tags: Iterable[str] | None = None) -> int:
    tag_set = set(normalize_tags(tags))
    blob = f"{text} {' '.join(tag_set)}".lower()
    score = 45
    if any(word in blob for word in ("important", "remember", "preference", "goal", "deadline", "project")):
        score += 18
    if any(tag in tag_set for tag in ("preference", "goal", "project", "workflow", "security")):
        score += 14
    if any(word in blob for word in ("password", "token", "secret", "api key")):
        score += 8
    if len(str(text or "")) > 180:
        score += 6
    return _clamp_importance(score)


@dataclass(frozen=True)
class MemoryV2Record:
    memory_id: str
    text: str
    redacted_text: str
    tags: list[str]
    importance: int
    source: str = "manual"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_recalled_at: float | None = None
    recall_count: int = 0
    deleted_at: float | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "MemoryV2Record":
        return cls(
            memory_id=str(row["id"]),
            text=str(row["text"] or ""),
            redacted_text=str(row["redacted_text"] or row["text"] or ""),
            tags=list(_json_load(row["tags_json"], [])),
            importance=int(row["importance"] or 0),
            source=str(row["source"] or "manual"),
            metadata=dict(_json_load(row["metadata_json"], {})),
            created_at=float(row["created_at"] or 0.0),
            updated_at=float(row["updated_at"] or 0.0),
            last_recalled_at=float(row["last_recalled_at"]) if row["last_recalled_at"] is not None else None,
            recall_count=int(row["recall_count"] or 0),
            deleted_at=float(row["deleted_at"]) if row["deleted_at"] is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "text": self.text,
            "redacted_text": self.redacted_text,
            "tags": list(self.tags),
            "importance": self.importance,
            "source": self.source,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_recalled_at": self.last_recalled_at,
            "recall_count": self.recall_count,
            "deleted_at": self.deleted_at,
        }


@dataclass(frozen=True)
class MemoryRecallResult:
    record: MemoryV2Record
    score: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = self.record.to_dict()
        payload["score"] = round(float(self.score), 4)
        payload["reason"] = self.reason
        return payload


class MemoryV2Store:
    """SQLite-backed local memory with redaction, decay scoring, and audit logs."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        decay_half_life_days: float | None = None,
    ) -> None:
        self.db_path = Path(db_path).expanduser() if db_path else default_memory_v2_path()
        env_half_life = os.environ.get("SHELL_MEMORY_V2_DECAY_DAYS")
        if decay_half_life_days is None and env_half_life:
            try:
                decay_half_life_days = float(env_half_life)
            except ValueError:
                decay_half_life_days = None
        self.decay_half_life_days = max(1.0, float(decay_half_life_days or DEFAULT_DECAY_HALF_LIFE_DAYS))
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.DatabaseError:
            pass
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    redacted_text TEXT NOT NULL,
                    raw_text_sha256 TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    importance INTEGER NOT NULL DEFAULT 50,
                    source TEXT NOT NULL DEFAULT 'manual',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_recalled_at REAL,
                    recall_count INTEGER NOT NULL DEFAULT 0,
                    deleted_at REAL,
                    deleted_reason TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_memory_v2_deleted_updated
                    ON memories(deleted_at, updated_at);
                CREATE INDEX IF NOT EXISTS idx_memory_v2_source
                    ON memories(source);

                CREATE TABLE IF NOT EXISTS recall_audit (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    query_sha256 TEXT NOT NULL,
                    memory_id TEXT NOT NULL,
                    score REAL NOT NULL,
                    reason TEXT NOT NULL,
                    recalled_at REAL NOT NULL,
                    FOREIGN KEY(memory_id) REFERENCES memories(id)
                );

                CREATE INDEX IF NOT EXISTS idx_memory_v2_audit_time
                    ON recall_audit(recalled_at);
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            conn.commit()

    def save_memory(
        self,
        text: str,
        *,
        tags: str | Iterable[str] | None = None,
        importance: int | None = None,
        source: str = "manual",
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
        created_at: float | None = None,
    ) -> MemoryV2Record:
        raw_text = str(text or "").strip()
        if not raw_text:
            raise ValueError("Memory text is required")
        normalized_tags = normalize_tags(tags)
        redacted = redact_sensitive_text(raw_text)
        now = time.time()
        record_id = str(memory_id or uuid.uuid4().hex)
        importance_value = _clamp_importance(
            importance if importance is not None else estimate_importance(redacted, normalized_tags)
        )
        with self._connect() as conn:
            existing = conn.execute("SELECT created_at FROM memories WHERE id = ?", (record_id,)).fetchone()
            first_created_at = float(existing["created_at"]) if existing else float(created_at or now)
            conn.execute(
                """
                INSERT INTO memories (
                    id, text, redacted_text, raw_text_sha256, tags_json,
                    importance, source, metadata_json, created_at, updated_at,
                    last_recalled_at, recall_count, deleted_at, deleted_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL, '')
                ON CONFLICT(id) DO UPDATE SET
                    text = excluded.text,
                    redacted_text = excluded.redacted_text,
                    raw_text_sha256 = excluded.raw_text_sha256,
                    tags_json = excluded.tags_json,
                    importance = excluded.importance,
                    source = excluded.source,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at,
                    deleted_at = NULL,
                    deleted_reason = ''
                """,
                (
                    record_id,
                    redacted,
                    redacted,
                    _sha256(raw_text),
                    _json_dump(normalized_tags),
                    importance_value,
                    str(source or "manual"),
                    _json_dump(metadata or {}),
                    first_created_at,
                    now,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise RuntimeError("Memory save failed")
        return MemoryV2Record.from_row(row)

    def recall_memory(
        self,
        query: str,
        *,
        limit: int = 5,
        tags: str | Iterable[str] | None = None,
        include_deleted: bool = False,
    ) -> list[MemoryRecallResult]:
        safe_query = redact_sensitive_text(str(query or "").strip())
        wanted_tags = set(normalize_tags(tags))
        query_tokens = _tokens(safe_query)
        now = time.time()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memories
                WHERE (? = 1 OR deleted_at IS NULL)
                ORDER BY updated_at DESC
                LIMIT 1000
                """,
                (1 if include_deleted else 0,),
            ).fetchall()
            scored: list[MemoryRecallResult] = []
            for row in rows:
                record = MemoryV2Record.from_row(row)
                score, reason, relevant = self._score_record(record, safe_query, query_tokens, wanted_tags, now)
                if not relevant:
                    continue
                scored.append(MemoryRecallResult(record=record, score=score, reason=reason))
            scored.sort(key=lambda item: (item.score, item.record.updated_at), reverse=True)
            results = scored[: max(1, int(limit))]
            if results:
                recalled_at = time.time()
                for item in results:
                    conn.execute(
                        """
                        INSERT INTO recall_audit (
                            id, query, query_sha256, memory_id, score, reason, recalled_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            uuid.uuid4().hex,
                            safe_query,
                            _sha256(str(query or "")),
                            item.record.memory_id,
                            float(item.score),
                            item.reason,
                            recalled_at,
                        ),
                    )
                    conn.execute(
                        """
                        UPDATE memories
                        SET last_recalled_at = ?, recall_count = recall_count + 1
                        WHERE id = ?
                        """,
                        (recalled_at, item.record.memory_id),
                    )
                conn.commit()
        return results

    def _score_record(
        self,
        record: MemoryV2Record,
        query: str,
        query_tokens: set[str],
        wanted_tags: set[str],
        now: float,
    ) -> tuple[float, str, bool]:
        record_tags = set(record.tags)
        if wanted_tags and not wanted_tags.issubset(record_tags):
            return 0.0, "tag-filter-miss", False

        text_l = record.redacted_text.lower()
        record_tokens = _tokens(record.redacted_text)
        lexical = 0.0
        reasons: list[str] = []
        if query:
            if query.lower() in text_l:
                lexical += 35.0
                reasons.append("phrase")
            if query_tokens:
                overlap = query_tokens & record_tokens
                if overlap:
                    lexical += 45.0 * (len(overlap) / max(1, len(query_tokens)))
                    reasons.append(f"tokens:{len(overlap)}")
        tag_bonus = 0.0
        if wanted_tags:
            tag_bonus = 18.0
            reasons.append("tags")

        relevant = bool(not query_tokens and not query) or lexical > 0.0 or tag_bonus > 0.0
        if not relevant:
            return 0.0, "no-match", False

        age_days = max(0.0, (now - record.updated_at) / 86400.0)
        decay_factor = math.pow(0.5, age_days / self.decay_half_life_days)
        importance_bonus = (float(record.importance) / 100.0) * 30.0 * decay_factor
        recency_bonus = 6.0 * decay_factor
        recall_bonus = min(8.0, float(record.recall_count) * 1.25)
        total = lexical + tag_bonus + importance_bonus + recency_bonus + recall_bonus
        reasons.extend([f"importance:{record.importance}", f"decay:{decay_factor:.3f}"])
        return total, ",".join(reasons), True

    def forget_memory(
        self,
        *,
        memory_id: str | None = None,
        query: str | None = None,
        tag: str | None = None,
        reason: str = "user_request",
    ) -> int:
        wanted_tags = set(normalize_tags(tag))
        safe_query = redact_sensitive_text(str(query or "").strip())
        query_tokens = _tokens(safe_query)
        now = time.time()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM memories WHERE deleted_at IS NULL").fetchall()
            matched: list[str] = []
            for row in rows:
                record = MemoryV2Record.from_row(row)
                if memory_id and record.memory_id != memory_id:
                    continue
                if wanted_tags and not wanted_tags.issubset(set(record.tags)):
                    continue
                if query_tokens and not (query_tokens & _tokens(record.redacted_text)):
                    continue
                if not memory_id and not wanted_tags and not query_tokens:
                    continue
                matched.append(record.memory_id)
            for item_id in matched:
                conn.execute(
                    "UPDATE memories SET deleted_at = ?, deleted_reason = ? WHERE id = ?",
                    (now, str(reason or "user_request"), item_id),
                )
            conn.commit()
        return len(matched)

    def migrate_legacy(self, legacy_path: str | Path | None = None) -> dict[str, int]:
        path = Path(legacy_path).expanduser() if legacy_path else Path.home() / ".shell_smart_memory.json"
        if not path.exists():
            return {"migrated": 0, "skipped": 0}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"migrated": 0, "skipped": 0}
        migrated = 0
        skipped = 0
        if not isinstance(payload, dict):
            return {"migrated": 0, "skipped": 1}
        for category, entries in payload.items():
            if not isinstance(entries, dict):
                skipped += 1
                continue
            for key, value in entries.items():
                text = f"{key}: {value}"
                record_id = uuid.uuid5(uuid.NAMESPACE_URL, f"shell-memory-v2:{category}:{key}:{value}").hex
                self.save_memory(
                    text,
                    tags=[str(category), str(key), "legacy"],
                    importance=estimate_importance(str(value), [str(category), str(key)]),
                    source="legacy_shell_memory",
                    metadata={"legacy_category": category, "legacy_key": key},
                    memory_id=record_id,
                )
                migrated += 1
        return {"migrated": migrated, "skipped": skipped}

    def audit_log(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM recall_audit
                ORDER BY recalled_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "query": row["query"],
                "memory_id": row["memory_id"],
                "score": row["score"],
                "reason": row["reason"],
                "recalled_at": row["recalled_at"],
            }
            for row in rows
        ]

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            active = conn.execute("SELECT COUNT(*) AS c FROM memories WHERE deleted_at IS NULL").fetchone()
            deleted = conn.execute("SELECT COUNT(*) AS c FROM memories WHERE deleted_at IS NOT NULL").fetchone()
            audits = conn.execute("SELECT COUNT(*) AS c FROM recall_audit").fetchone()
        return {
            "path": str(self.db_path),
            "enabled": memory_v2_enabled(),
            "active_memories": int(active["c"] if active else 0),
            "deleted_memories": int(deleted["c"] if deleted else 0),
            "audit_entries": int(audits["c"] if audits else 0),
            "decay_half_life_days": self.decay_half_life_days,
            "schema_version": SCHEMA_VERSION,
        }


def get_default_store() -> MemoryV2Store:
    return MemoryV2Store(default_memory_v2_path())


def save_memory(
    text: str,
    tags: str | Iterable[str] | None = None,
    importance: int | None = None,
    *,
    source: str = "manual",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return get_default_store().save_memory(
        text,
        tags=tags,
        importance=importance,
        source=source,
        metadata=metadata,
    ).to_dict()


def recall_memory(
    query: str,
    *,
    limit: int = 5,
    tags: str | Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    return [item.to_dict() for item in get_default_store().recall_memory(query, limit=limit, tags=tags)]


def forget_memory(
    *,
    memory_id: str | None = None,
    query: str | None = None,
    tag: str | None = None,
) -> int:
    return get_default_store().forget_memory(memory_id=memory_id, query=query, tag=tag)


def migrate_legacy_memory(legacy_path: str | Path | None = None) -> dict[str, int]:
    return get_default_store().migrate_legacy(legacy_path)


__all__ = [
    "MemoryRecallResult",
    "MemoryV2Record",
    "MemoryV2Store",
    "default_memory_v2_path",
    "estimate_importance",
    "forget_memory",
    "get_default_store",
    "memory_v2_enabled",
    "migrate_legacy_memory",
    "normalize_tags",
    "recall_memory",
    "redact_sensitive_text",
    "save_memory",
]
