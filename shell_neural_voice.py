from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from shell_safe_executor import god_tier_tool as function_tool


@dataclass
class StreamingVoiceState:
    session_id: str = "shell-voice"
    active: bool = False
    started_at: float = 0.0
    last_event_at: float = 0.0
    partial_transcript: str = ""
    response_buffer: str = ""
    first_partial_ms: float | None = None
    first_response_ms: float | None = None
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=80))

    def snapshot(self) -> dict[str, Any]:
        now = time.perf_counter()
        age_ms = round((now - self.started_at) * 1000.0, 3) if self.started_at else 0.0
        return {
            "session_id": self.session_id,
            "active": self.active,
            "age_ms": age_ms,
            "partial_transcript": self.partial_transcript,
            "response_chars": len(self.response_buffer),
            "first_partial_ms": self.first_partial_ms,
            "first_response_ms": self.first_response_ms,
            "events": list(self.events),
            "targets": {
                "voice_first_partial_ms": 100,
                "ui_update_ms": 16,
                "end_to_end_ms": 100,
            },
        }


class StreamingVoiceCoordinator:
    """Transport-agnostic voice streaming tracker.

    The real microphone and TTS paths live in the UI/runtime modules. This
    coordinator gives those paths a tiny, thread-safe state layer that can be
    queried by tools, tests, and diagnostics without importing PyQt.
    """

    def __init__(self) -> None:
        self._state = StreamingVoiceState()
        self._lock = threading.Lock()

    def start(self, session_id: str = "shell-voice") -> dict[str, Any]:
        now = time.perf_counter()
        with self._lock:
            self._state = StreamingVoiceState(
                session_id=str(session_id or "shell-voice"),
                active=True,
                started_at=now,
                last_event_at=now,
            )
            self._record_locked("started")
            return self._state.snapshot()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._state.active = False
            self._record_locked("stopped")
            return self._state.snapshot()

    def partial(self, text: str) -> dict[str, Any]:
        now = time.perf_counter()
        with self._lock:
            if not self._state.active:
                self._state = StreamingVoiceState(
                    session_id=self._state.session_id or "shell-voice",
                    active=True,
                    started_at=now,
                    last_event_at=now,
                )
                self._record_locked("started")
            self._state.partial_transcript = str(text or "")
            if self._state.first_partial_ms is None and self._state.started_at:
                self._state.first_partial_ms = round((now - self._state.started_at) * 1000.0, 3)
            self._record_locked("partial", chars=len(self._state.partial_transcript))
            return self._state.snapshot()

    def response_chunk(self, chunk: str) -> dict[str, Any]:
        now = time.perf_counter()
        with self._lock:
            if not self._state.active:
                self._state = StreamingVoiceState(
                    session_id=self._state.session_id or "shell-voice",
                    active=True,
                    started_at=now,
                    last_event_at=now,
                )
                self._record_locked("started")
            self._state.response_buffer += str(chunk or "")
            if self._state.first_response_ms is None and self._state.started_at:
                self._state.first_response_ms = round((now - self._state.started_at) * 1000.0, 3)
            self._record_locked("response_chunk", chars=len(str(chunk or "")))
            return self._state.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._state.snapshot()

    def _record_locked(self, event: str, **payload: Any) -> None:
        now = time.perf_counter()
        self._state.last_event_at = now
        item = {
            "event": str(event),
            "t_ms": round((now - self._state.started_at) * 1000.0, 3)
            if self._state.started_at
            else 0.0,
        }
        item.update(payload)
        self._state.events.append(item)


VOICE_COORDINATOR = StreamingVoiceCoordinator()


@function_tool(category="voice")
async def shell_streaming_voice_status_tool() -> dict[str, Any]:
    """Return the current Shell streaming voice state and latency targets."""
    return VOICE_COORDINATOR.snapshot()


@function_tool(category="voice")
async def shell_streaming_voice_prime_tool(session_id: str = "shell-voice") -> dict[str, Any]:
    """Prime a low-latency Shell voice session state before microphone audio arrives."""
    return VOICE_COORDINATOR.start(session_id=session_id)


@function_tool(category="voice")
async def shell_streaming_voice_partial_tool(text: str) -> dict[str, Any]:
    """Record a live partial transcript chunk as soon as speech recognition emits it."""
    return VOICE_COORDINATOR.partial(text)
