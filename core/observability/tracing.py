from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

from .events import emit_debug_event


current_trace_id: ContextVar[str] = ContextVar("shell_current_trace_id", default="")


@dataclass
class TraceSpan:
    span_id: str
    trace_id: str
    name: str
    start_ts: float
    metadata: dict[str, Any] = field(default_factory=dict)
    end_ts: float = 0.0
    ok: bool = True
    error: str = ""

    @property
    def duration_ms(self) -> float:
        end = self.end_ts or time.time()
        return round((end - self.start_ts) * 1000.0, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "duration_ms": self.duration_ms,
            "ok": self.ok,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


@dataclass
class ExecutionTrace:
    trace_id: str
    name: str
    start_ts: float
    metadata: dict[str, Any] = field(default_factory=dict)
    spans: list[TraceSpan] = field(default_factory=list)
    end_ts: float = 0.0
    ok: bool = True
    error: str = ""

    @property
    def duration_ms(self) -> float:
        end = self.end_ts or time.time()
        return round((end - self.start_ts) * 1000.0, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "duration_ms": self.duration_ms,
            "ok": self.ok,
            "error": self.error,
            "metadata": dict(self.metadata),
            "spans": [span.to_dict() for span in self.spans],
        }


class ExecutionTracer:
    """Small in-process tracer for tool, route, and agent execution."""

    _instance: "ExecutionTracer | None" = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._traces: dict[str, ExecutionTrace] = {}
        self._lock = threading.RLock()

    @classmethod
    def get(cls) -> "ExecutionTracer":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def start_trace(self, name: str, metadata: dict[str, Any] | None = None) -> str:
        trace_id = uuid.uuid4().hex
        trace = ExecutionTrace(trace_id=trace_id, name=str(name), start_ts=time.time(), metadata=dict(metadata or {}))
        with self._lock:
            self._traces[trace_id] = trace
        current_trace_id.set(trace_id)
        emit_debug_event("trace.start", "core.tracing", {"name": name, "metadata": metadata or {}}, trace_id=trace_id)
        return trace_id

    def finish_trace(self, trace_id: str, *, ok: bool = True, error: str = "") -> None:
        with self._lock:
            trace = self._traces.get(trace_id)
            if trace is None:
                return
            trace.end_ts = time.time()
            trace.ok = bool(ok)
            trace.error = str(error or "")
            payload = trace.to_dict()
        emit_debug_event("trace.end", "core.tracing", payload, trace_id=trace_id)

    def start_span(self, trace_id: str, name: str, metadata: dict[str, Any] | None = None) -> str:
        span = TraceSpan(
            span_id=uuid.uuid4().hex,
            trace_id=str(trace_id),
            name=str(name),
            start_ts=time.time(),
            metadata=dict(metadata or {}),
        )
        with self._lock:
            trace = self._traces.get(trace_id)
            if trace is not None:
                trace.spans.append(span)
        emit_debug_event("span.start", "core.tracing", {"name": name, "metadata": metadata or {}}, trace_id=trace_id)
        return span.span_id

    def finish_span(self, trace_id: str, span_id: str, *, ok: bool = True, error: str = "") -> None:
        span = None
        with self._lock:
            trace = self._traces.get(trace_id)
            if trace is not None:
                for candidate in trace.spans:
                    if candidate.span_id == span_id:
                        span = candidate
                        break
            if span is None:
                return
            span.end_ts = time.time()
            span.ok = bool(ok)
            span.error = str(error or "")
            payload = span.to_dict()
        emit_debug_event("span.end", "core.tracing", payload, trace_id=trace_id)

    @contextmanager
    def trace(self, name: str, metadata: dict[str, Any] | None = None) -> Iterator[str]:
        trace_id = self.start_trace(name, metadata)
        try:
            yield trace_id
        except Exception as exc:
            self.finish_trace(trace_id, ok=False, error=str(exc))
            raise
        else:
            self.finish_trace(trace_id, ok=True)

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        with self._lock:
            trace = self._traces.get(trace_id)
            return trace.to_dict() if trace else None

    def recent_traces(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._traces.values())[-max(0, int(limit)):]
        return [row.to_dict() for row in rows]

