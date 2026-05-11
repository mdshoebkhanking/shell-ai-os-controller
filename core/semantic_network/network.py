from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class SemanticChannel:
    channel_id: str
    source: str
    target: str
    intent: str
    encrypted: bool = True
    dependencies: list[str] = field(default_factory=list)
    trust_score: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {"channel_id": self.channel_id, "source": self.source, "target": self.target, "intent": self.intent, "encrypted": self.encrypted, "dependencies": list(self.dependencies), "trust_score": self.trust_score}


class SemanticNetworkLayer:
    def __init__(self):
        self._channels: list[SemanticChannel] = []

    def open_channel(self, source: str, target: str, intent: str, *, dependencies: list[str] | None = None, encrypted: bool = True, trust_score: float = 0.5) -> SemanticChannel:
        channel = SemanticChannel(uuid.uuid4().hex, source, target, intent, encrypted, list(dependencies or []), max(0.0, min(1.0, float(trust_score))))
        self._channels.append(channel)
        publish_event(AIEventType.SEMANTIC_NETWORK_ROUTED, {"channel": channel.to_dict()}, source="core.semantic_network")
        return channel

    def route(self, intent: str, *, dependency: str = "") -> dict[str, Any]:
        candidates = [channel for channel in self._channels if intent.lower() in channel.intent.lower() and channel.encrypted and channel.trust_score >= 0.5]
        if dependency:
            candidates = [channel for channel in candidates if dependency in channel.dependencies]
        candidates.sort(key=lambda channel: channel.trust_score, reverse=True)
        result = {"intent": intent, "channel": candidates[0].to_dict() if candidates else None, "reason": "trusted encrypted semantic route" if candidates else "no trusted channel"}
        publish_event(AIEventType.SEMANTIC_NETWORK_ROUTED, {"route": result}, source="core.semantic_network")
        return result

    def stream_event(self, channel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"channel_id": channel_id, "payload": dict(payload), "encrypted": True}
        publish_event(AIEventType.SEMANTIC_NETWORK_ROUTED, {"stream": row}, source="core.semantic_network")
        return row

