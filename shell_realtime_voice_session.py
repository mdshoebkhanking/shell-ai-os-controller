from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def _now() -> float:
    return time.perf_counter()


@dataclass
class RealtimeVoiceSession:
    """Small state controller for one continuous voice session.

    This is intentionally transport-agnostic. The UI, Shell-v2 bridge, and
    future WebSocket/WebRTC audio paths can all report the same lifecycle
    events without coupling provider code to Qt widgets.
    """

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: float = field(default_factory=_now)
    state: str = "idle"
    turn_id: int = 0
    turn_count: int = 0
    interruption_count: int = 0
    prewarm_count: int = 0
    last_prewarm_ms: float | None = None
    shell_v2_ready: bool = False
    provider_count: int = 0
    last_event_at: float = field(default_factory=_now)
    events: list[dict[str, Any]] = field(default_factory=list)

    def _record(self, event: str, **payload: Any) -> None:
        ts = _now()
        self.last_event_at = ts
        item = {
            "event": str(event),
            "t_ms": round((ts - self.started_at) * 1000.0, 3),
        }
        item.update(payload)
        self.events.append(item)
        if len(self.events) > 80:
            self.events = self.events[-80:]

    def start(self) -> None:
        self.state = "listening"
        self._record("session_started")

    def stop(self) -> None:
        self.state = "stopped"
        self._record("session_stopped")

    def user_speech_started(self) -> None:
        self.state = "user_speaking"
        self._record("user_speech_started")

    def user_speech_ended(self) -> None:
        self.state = "processing"
        self._record("user_speech_ended")

    def text_committed(self, text: str, turn_id: int) -> None:
        self.turn_id = int(turn_id or 0)
        self.turn_count += 1
        self.state = "thinking"
        self._record("text_committed", chars=len(str(text or "")), turn_id=self.turn_id)

    def assistant_speech_started(self, *, transport: str = "") -> None:
        self.state = "assistant_speaking"
        self._record("assistant_speech_started", transport=str(transport or ""))

    def assistant_speech_done(self) -> None:
        self.state = "listening"
        self._record("assistant_speech_done")

    def interrupt(self, reason: str = "barge_in") -> None:
        self.interruption_count += 1
        self.state = "interrupted"
        self._record("interrupted", reason=str(reason or "barge_in"))

    def should_prewarm(self) -> bool:
        return self.prewarm_count == 0

    def prewarm_started(self) -> None:
        self.prewarm_count += 1
        self._record("prewarm_started")

    def prewarm_done(
        self,
        *,
        elapsed_ms: float,
        shell_v2_ready: bool,
        provider_count: int,
    ) -> None:
        self.last_prewarm_ms = round(float(elapsed_ms), 3)
        self.shell_v2_ready = bool(shell_v2_ready)
        self.provider_count = int(provider_count or 0)
        self._record(
            "prewarm_done",
            elapsed_ms=self.last_prewarm_ms,
            shell_v2_ready=self.shell_v2_ready,
            provider_count=self.provider_count,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "turn_id": self.turn_id,
            "turn_count": self.turn_count,
            "interruption_count": self.interruption_count,
            "prewarm_count": self.prewarm_count,
            "last_prewarm_ms": self.last_prewarm_ms,
            "shell_v2_ready": self.shell_v2_ready,
            "provider_count": self.provider_count,
            "age_ms": round((_now() - self.started_at) * 1000.0, 3),
            "events": list(self.events),
        }

