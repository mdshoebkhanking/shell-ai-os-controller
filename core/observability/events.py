from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class DebugEvent:
    event_id: str
    event_type: str
    source: str
    ts: float
    trace_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "ts": self.ts,
            "trace_id": self.trace_id,
            "payload": dict(self.payload),
        }


class EventBus:
    """In-process debug event bus with a bounded recent-event buffer."""

    _instance: "EventBus | None" = None
    _instance_lock = threading.Lock()

    def __init__(self, max_events: int = 1000):
        self._events: deque[DebugEvent] = deque(maxlen=max_events)
        self._subscribers: list[Callable[[DebugEvent], None]] = []
        self._lock = threading.RLock()

    @classmethod
    def get(cls) -> "EventBus":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def emit(self, event_type: str, source: str, payload: dict[str, Any] | None = None, *, trace_id: str = "") -> DebugEvent:
        event = DebugEvent(
            event_id=uuid.uuid4().hex,
            event_type=str(event_type),
            source=str(source),
            ts=time.time(),
            trace_id=str(trace_id or ""),
            payload=dict(payload or {}),
        )
        with self._lock:
            self._events.append(event)
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber(event)
            except Exception:
                pass
        return event

    def subscribe(self, callback: Callable[[DebugEvent], None]) -> None:
        if not callable(callback):
            return
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[DebugEvent], None]) -> None:
        with self._lock:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                pass

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._events)[-max(0, int(limit)):]
        return [row.to_dict() for row in rows]

    def replay(
        self,
        *,
        event_types: Iterable[str] | None = None,
        since_ts: float = 0.0,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        wanted = {str(t) for t in event_types or []}
        with self._lock:
            rows = [
                event for event in self._events
                if event.ts >= float(since_ts or 0.0)
                and (not wanted or event.event_type in wanted)
            ]
        return [row.to_dict() for row in rows[-max(0, int(limit)):]]


def emit_debug_event(event_type: str, source: str, payload: dict[str, Any] | None = None, *, trace_id: str = "") -> DebugEvent:
    return EventBus.get().emit(event_type, source, payload, trace_id=trace_id)
