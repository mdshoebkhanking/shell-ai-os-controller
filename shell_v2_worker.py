"""Lightweight headless worker for Shell AI v2.

Replaces the old PyQt6 ``ShellCinematicFull`` window class with a thin,
GUI-free worker that tests and runtime probes can use to verify TTS, voice
latency, and streaming behaviour without importing any Qt libraries.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


BrainFactory = Callable[[], Any]


def _default_brain_factory() -> Any:
    from brain.core import MultiAIBrain
    return MultiAIBrain.get_instance()


@dataclass
class ShellV2Worker:
    """Headless runtime worker – drop-in replacement for PyQt ``ShellCinematicFull``.

    Provides the subset of APIs that tests previously relied on from the
    PyQt6 window class: TTS segment helpers, streaming state tracking, and
    a thin interface for exercise / benchmarking.
    """

    SHELL_V2_URL: str = "http://127.0.0.1:8765"
    TIMEOUT_S: int = 12

    @staticmethod
    def stream_enabled() -> bool:
        import os
        return os.environ.get("SHELL_V2_STREAM", "1").strip().lower() not in {"0", "false", "no", "off"}

    brain_factory: BrainFactory = field(default_factory=lambda: _default_brain_factory)
    provider: str = ""
    mode: str = "FAST"

    # ---- internal state ----
    _started: bool = field(init=False, default=False)
    _loop: asyncio.AbstractEventLoop = field(init=False, default=None)  # type: ignore[assignment]
    _thread: threading.Thread = field(init=False, default=None)  # type: ignore[assignment]

    # ---- TTS / voice state (previously in ShellCinematicFull) ----
    _tts_segments: list[str] = field(init=False, default_factory=list)
    _tts_playing: bool = field(init=False, default=False)
    _tts_start_time: Optional[float] = field(init=False, default=None)

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="shell-v2-worker", daemon=True)
        self._started = True
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def close(self) -> None:
        if not self._started:
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()
        self._started = False

    # -- TTS helpers (relocated from shell_ui) ------------------------------

    @staticmethod
    def _system_tts_available() -> bool:
        """Check whether the platform system TTS engine is usable."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.stop()
            return True
        except Exception:
            return False

    @staticmethod
    def _voice_tts_threshold() -> float:
        """Minimum character count before a TTS segment is flushed."""
        return 80.0

    @staticmethod
    def _voice_tts_next_segment(text: str, cursor: int = 0) -> tuple[str, int]:
        """Extract the next speakable segment from *text* starting at *cursor*.

        Returns ``(segment, new_cursor)``.  Returns ``(\"\", cursor)`` if no
        full segment is available yet.
        """
        import os
        first_chars = int(os.environ.get("SHELL_VOICE_TTS_FIRST_CHARS", "80"))
        first_hard_chars = int(os.environ.get("SHELL_VOICE_TTS_FIRST_HARD_CHARS", "160"))
        threshold = first_chars if cursor == 0 else first_hard_chars

        remaining = text[cursor:]
        if not remaining:
            return ("", cursor)

        # Look for sentence-ending punctuation after the threshold
        for i, ch in enumerate(remaining):
            if i >= threshold and ch in ",.!?;:-\n":
                segment = remaining[: i + 1].strip()
                return (segment, cursor + i + 1)

        # If remaining text is short enough and looks final, flush it
        if len(remaining) < threshold * 2:
            return ("", cursor)

        # Force-flush at double-threshold to avoid stalling
        split = int(threshold * 1.5)
        segment = remaining[:split].strip()
        return (segment, cursor + split)

    def tts_enqueue(self, segment: str) -> None:
        """Enqueue a TTS segment for playback tracking."""
        self._tts_segments.append(segment)

    def tts_clear(self) -> None:
        self._tts_segments.clear()
        self._tts_playing = False
        self._tts_start_time = None

    @property
    def tts_segments(self) -> list[str]:
        return list(self._tts_segments)

    # -- streaming bridge ---------------------------------------------------

    def collect_reply(self, text: str, *, agent: str = "") -> dict[str, Any]:
        """Send *text* through the v2 runtime and return the full result."""
        from shell_v2_runtime import collect_shell_v2_reply

        if not self._started:
            self.start()
        future = asyncio.run_coroutine_threadsafe(
            collect_shell_v2_reply(
                text,
                mode=self.mode,
                agent=agent,
                provider=self.provider,
                brain_factory=self.brain_factory,
            ),
            self._loop,
        )
        return future.result(timeout=60)


__all__ = ["ShellV2Worker"]
