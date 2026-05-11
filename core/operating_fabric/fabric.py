from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class FabricEvent:
    event_id: str
    topic: str
    payload: dict[str, Any]
    semantic_tags: list[str] = field(default_factory=list)
    stateful: bool = True
    replayable: bool = True
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "topic": self.topic,
            "payload": dict(self.payload),
            "semantic_tags": list(self.semantic_tags),
            "stateful": self.stateful,
            "replayable": self.replayable,
            "ts": self.ts,
        }


class OperatingFabric:
    def __init__(self):
        self._events: list[FabricEvent] = []
        self._state: dict[str, Any] = {}

    def publish(self, topic: str, payload: dict[str, Any], *, semantic_tags: list[str] | None = None, stateful: bool = True) -> FabricEvent:
        event = FabricEvent(uuid.uuid4().hex, topic, dict(payload), list(semantic_tags or []), stateful, True)
        self._events.append(event)
        if stateful:
            self._state[topic] = event.to_dict()
        publish_event(AIEventType.OPERATING_FABRIC_EVENT, event.to_dict(), source="core.operating_fabric")
        return event

    def replay(self, *, topic: str = "") -> list[dict[str, Any]]:
        rows = [event.to_dict() for event in self._events if event.replayable and (not topic or event.topic == topic)]
        rows.sort(key=lambda row: row["ts"])
        return rows

    def state(self) -> dict[str, Any]:
        return dict(self._state)

    def coordinate(self, semantic_tag: str) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._events if semantic_tag in event.semantic_tags]

