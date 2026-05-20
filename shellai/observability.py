from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any


_LOGGING_CONFIGURED = False
_LOGGING_LOCK = threading.Lock()


def get_logger(name: str = "shellai") -> logging.Logger:
    """Return the central ShellAI logger.

    Logging setup is process-local and deliberately simple for Stage 1. Later
    stages can attach file sinks or structured exporters without changing
    callers.
    """
    global _LOGGING_CONFIGURED
    with _LOGGING_LOCK:
        if not _LOGGING_CONFIGURED:
            level_name = os.environ.get("SHELLAI_LOG_LEVEL", "INFO").upper()
            level = getattr(logging, level_name, logging.INFO)
            logging.basicConfig(
                level=level,
                format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            )
            _LOGGING_CONFIGURED = True
    return logging.getLogger(name)


@dataclass(frozen=True)
class TraceStep:
    name: str
    status: str
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp,
        }


@dataclass
class RequestTrace:
    request_id: str
    user_input: str
    started_at: float = field(default_factory=time.time)
    steps: list[TraceStep] = field(default_factory=list)

    def add_step(
        self,
        name: str,
        status: str,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TraceStep:
        step = TraceStep(
            name=name,
            status=status,
            message=message,
            metadata=dict(metadata or {}),
        )
        self.steps.append(step)
        return step

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user_input": self.user_input,
            "started_at": self.started_at,
            "elapsed_ms": round((time.time() - self.started_at) * 1000.0, 3),
            "steps": [step.to_dict() for step in self.steps],
        }


class InMemoryTraceStore:
    """Small ring buffer of request traces for local debugging."""

    def __init__(self, max_traces: int = 200) -> None:
        self._traces: deque[RequestTrace] = deque(maxlen=max(1, int(max_traces)))
        self._lock = threading.Lock()

    def start_trace(self, user_input: str) -> RequestTrace:
        trace = RequestTrace(request_id=uuid.uuid4().hex, user_input=str(user_input or ""))
        with self._lock:
            self._traces.append(trace)
        return trace

    def get(self, request_id: str) -> RequestTrace | None:
        with self._lock:
            for trace in self._traces:
                if trace.request_id == request_id:
                    return trace
        return None

    def recent(self, limit: int = 20) -> list[RequestTrace]:
        with self._lock:
            traces = list(self._traces)[-max(0, int(limit)):]
        traces.reverse()
        return traces

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()


TRACE_STORE = InMemoryTraceStore()


__all__ = [
    "InMemoryTraceStore",
    "RequestTrace",
    "TRACE_STORE",
    "TraceStep",
    "get_logger",
]
