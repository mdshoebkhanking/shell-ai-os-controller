from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, List, Optional

from shellai.config import ShellAIConfig
from shellai.observability import RequestTrace


TRACE_LOG_FILE = "traces.jsonl"
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret)=\S+"),
    re.compile(r"(?i)(--api-key|--token|--password|--secret)\s+\S+"),
]


def trace_log_path(config: Optional[ShellAIConfig] = None) -> Path:
    active_config = config or ShellAIConfig.load()
    return active_config.paths.traces_dir / TRACE_LOG_FILE


def redact_text(value: Any) -> str:
    text = str(value or "")
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + "=<redacted>" if "=" in m.group(0) else m.group(1) + " <redacted>", text)
    return text


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _redact_value(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def record_trace_snapshot(
    config: ShellAIConfig,
    trace: RequestTrace,
    *,
    status: str,
    summary: str,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    config.paths.ensure_runtime_dirs()
    payload = {
        "trace_id": trace.request_id,
        "timestamp": time.time(),
        "status": str(status or "unknown"),
        "summary": redact_text(summary),
        "user_input": redact_text(trace.user_input),
        "trace": _redact_value(trace.to_dict()),
        "metadata": _redact_value(dict(metadata or {})),
    }
    path = trace_log_path(config)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return payload


def list_trace_snapshots(
    config: Optional[ShellAIConfig] = None,
    *,
    limit: int = 20,
    status_filter: str = "",
) -> List[dict[str, Any]]:
    active_config = config or ShellAIConfig.load()
    path = trace_log_path(active_config)
    if not path.exists():
        return []
    rows: List[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if status_filter and str(row.get("status")) != status_filter:
                continue
            rows.append(row)
    rows = rows[-max(1, int(limit)):]
    rows.reverse()
    return rows


def compact_trace_rows(rows: List[dict[str, Any]]) -> List[dict[str, Any]]:
    return [
        {
            "trace_id": row.get("trace_id"),
            "timestamp": row.get("timestamp"),
            "status": row.get("status"),
            "summary": row.get("summary"),
            "user_input": row.get("user_input"),
        }
        for row in rows
    ]


__all__ = [
    "TRACE_LOG_FILE",
    "compact_trace_rows",
    "list_trace_snapshots",
    "record_trace_snapshot",
    "redact_text",
    "trace_log_path",
]
