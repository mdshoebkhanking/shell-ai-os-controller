from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class RealtimeUpdate:
    update_id: str
    session_id: str
    channel: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"update_id": self.update_id, "session_id": self.session_id, "channel": self.channel, "payload": dict(self.payload), "ts": self.ts}


@dataclass(frozen=True)
class RealtimeSession:
    session_id: str
    topic: str
    participants: list[str] = field(default_factory=list)
    open: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"session_id": self.session_id, "topic": self.topic, "participants": list(self.participants), "open": self.open, "created_at": self.created_at}


class RealtimeCoordinator:
    def __init__(self):
        self._sessions: dict[str, RealtimeSession] = {}
        self._updates: list[RealtimeUpdate] = []

    def open_session(self, topic: str, participants: list[str] | None = None) -> RealtimeSession:
        session = RealtimeSession(uuid.uuid4().hex, topic, list(participants or []))
        self._sessions[session.session_id] = session
        return session

    def publish(self, session_id: str, channel: str, payload: dict[str, Any]) -> RealtimeUpdate:
        if session_id not in self._sessions or not self._sessions[session_id].open:
            raise ValueError("realtime session is not open")
        update = RealtimeUpdate(uuid.uuid4().hex, session_id, channel, dict(payload))
        self._updates.append(update)
        publish_event(AIEventType.REALTIME_UPDATE, update.to_dict(), source="core.realtime")
        return update

    def latest(self, session_id: str, *, limit: int = 20) -> list[RealtimeUpdate]:
        rows = [update for update in self._updates if update.session_id == session_id]
        return rows[-max(0, int(limit)):]

    def close(self, session_id: str) -> RealtimeSession | None:
        session = self._sessions.get(session_id)
        if not session:
            return None
        closed = RealtimeSession(session.session_id, session.topic, list(session.participants), False, session.created_at)
        self._sessions[session_id] = closed
        return closed

