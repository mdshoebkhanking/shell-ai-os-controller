from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class ToolReputation:
    tool_id: str
    total: int = 0
    successes: int = 0
    failures: int = 0
    cancellations: int = 0
    total_latency_ms: float = 0.0
    failure_categories: dict[str, int] = field(default_factory=dict)
    last_error: str = ""
    updated_at: float = 0.0

    @property
    def success_rate(self) -> float:
        return round(self.successes / self.total, 3) if self.total else 0.0

    @property
    def average_latency_ms(self) -> float:
        return round(self.total_latency_ms / self.successes, 3) if self.successes else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "total": self.total,
            "successes": self.successes,
            "failures": self.failures,
            "cancellations": self.cancellations,
            "total_latency_ms": self.total_latency_ms,
            "average_latency_ms": self.average_latency_ms,
            "success_rate": self.success_rate,
            "failure_categories": dict(self.failure_categories),
            "last_error": self.last_error,
            "updated_at": self.updated_at,
        }


class ToolReputationStore:
    def __init__(self, path: str | Path | None = None):
        if path is None:
            path = os.environ.get("SHELL_TOOL_REPUTATION_PATH") or ".shell_runtime/tool_reputation.json"
        self.path = Path(path)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"tools": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"tools": {}}
        except Exception:
            return {"tools": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def get(self, tool_id: str) -> ToolReputation:
        row = (self._load().get("tools") or {}).get(str(tool_id), {})
        return ToolReputation(
            tool_id=str(tool_id),
            total=int(row.get("total", 0)),
            successes=int(row.get("successes", 0)),
            failures=int(row.get("failures", 0)),
            cancellations=int(row.get("cancellations", 0)),
            total_latency_ms=float(row.get("total_latency_ms", 0.0)),
            failure_categories=dict(row.get("failure_categories") or {}),
            last_error=str(row.get("last_error") or ""),
            updated_at=float(row.get("updated_at", 0.0)),
        )

    def record(
        self,
        tool_id: str,
        *,
        ok: bool,
        latency_ms: float = 0.0,
        failure_category: str = "",
        cancelled: bool = False,
        error: str = "",
    ) -> ToolReputation:
        data = self._load()
        tools = data.setdefault("tools", {})
        current = self.get(tool_id)
        categories = dict(current.failure_categories)
        failures = current.failures
        successes = current.successes
        cancellations = current.cancellations + (1 if cancelled else 0)
        total = current.total + 1
        latency_total = current.total_latency_ms
        if ok:
            successes += 1
            latency_total += max(0.0, float(latency_ms or 0.0))
        else:
            failures += 1
            category = failure_category or "unknown"
            categories[category] = categories.get(category, 0) + 1
        rep = ToolReputation(
            tool_id=str(tool_id),
            total=total,
            successes=successes,
            failures=failures,
            cancellations=cancellations,
            total_latency_ms=latency_total,
            failure_categories=categories,
            last_error=str(error or "")[:300],
            updated_at=time.time(),
        )
        tools[str(tool_id)] = rep.to_dict()
        self._write(data)
        publish_event(AIEventType.TOOL_EXECUTED, rep.to_dict(), source="core.tools.reputation")
        return rep

    def all(self) -> dict[str, dict[str, Any]]:
        return dict((self._load().get("tools") or {}))

    def routing_adjustment(self, tool_id: str) -> float:
        rep = self.get(tool_id)
        if not rep.total:
            return 0.0
        latency_penalty = min(0.4, rep.average_latency_ms / 5000.0)
        cancel_penalty = min(0.3, rep.cancellations / max(1, rep.total))
        return round(rep.success_rate - latency_penalty - cancel_penalty, 3)

