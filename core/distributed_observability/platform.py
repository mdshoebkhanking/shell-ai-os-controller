from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class TraceEvent:
    trace_id: str
    node_id: str
    span: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "node_id": self.node_id, "span": self.span, "payload": dict(self.payload), "ts": self.ts}


@dataclass(frozen=True)
class NodeTelemetry:
    node_id: str
    metrics: dict[str, float] = field(default_factory=dict)
    semantic_tags: list[str] = field(default_factory=list)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "metrics": dict(self.metrics), "semantic_tags": list(self.semantic_tags), "ts": self.ts}


class DistributedObservabilityPlatform:
    def __init__(self):
        self._traces: list[TraceEvent] = []
        self._telemetry: list[NodeTelemetry] = []

    def record_trace(self, node_id: str, span: str, payload: dict[str, Any] | None = None, *, trace_id: str = "") -> TraceEvent:
        event = TraceEvent(trace_id or uuid.uuid4().hex, node_id, span, dict(payload or {}))
        self._traces.append(event)
        publish_event(AIEventType.DISTRIBUTED_OBSERVABILITY_RECORDED, {"trace": event.to_dict()}, source="core.distributed_observability")
        return event

    def record_telemetry(self, node_id: str, metrics: dict[str, float], *, semantic_tags: list[str] | None = None) -> NodeTelemetry:
        row = NodeTelemetry(node_id, dict(metrics), list(semantic_tags or []))
        self._telemetry.append(row)
        publish_event(AIEventType.DISTRIBUTED_OBSERVABILITY_RECORDED, {"telemetry": row.to_dict()}, source="core.distributed_observability")
        return row

    def timeline(self, trace_id: str) -> list[dict[str, Any]]:
        rows = [trace.to_dict() for trace in self._traces if trace.trace_id == trace_id]
        rows.sort(key=lambda row: row["ts"])
        return rows

    def node_health(self) -> dict[str, float]:
        health: dict[str, float] = {}
        for row in self._telemetry:
            error_rate = float(row.metrics.get("error_rate", 0.0))
            cpu = float(row.metrics.get("cpu", 0.0))
            health[row.node_id] = round(max(0.0, 1.0 - error_rate - max(0.0, cpu - 0.8)), 3)
        return health

