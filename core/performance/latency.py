from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LatencySample:
    name: str
    duration_ms: float
    ts: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": round(float(self.duration_ms), 3),
            "ts": self.ts,
            "metadata": dict(self.metadata),
        }


class InteractionLatencyRecorder:
    """Small in-process latency ring buffer for UI/runtime hot paths."""

    def __init__(self, maxlen: int = 500):
        self._samples: deque[LatencySample] = deque(maxlen=max(1, int(maxlen)))
        self._lock = threading.Lock()

    def record(self, name: str, duration_ms: float, **metadata: Any) -> LatencySample:
        sample = LatencySample(str(name), max(0.0, float(duration_ms or 0.0)), metadata=dict(metadata))
        with self._lock:
            self._samples.append(sample)
        return sample

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = list(self._samples)[-max(0, int(limit)):]
        return [row.to_dict() for row in rows]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self._samples)
        if not rows:
            return {"count": 0, "by_name": {}}
        by_name: dict[str, list[float]] = {}
        for row in rows:
            by_name.setdefault(row.name, []).append(row.duration_ms)
        return {
            "count": len(rows),
            "by_name": {
                name: {
                    "count": len(values),
                    "avg_ms": round(sum(values) / len(values), 3),
                    "max_ms": round(max(values), 3),
                }
                for name, values in sorted(by_name.items())
            },
        }


LOW_LATENCY_RECORDER = InteractionLatencyRecorder()

