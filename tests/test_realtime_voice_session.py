from __future__ import annotations

import pytest


class _TextTarget:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, value: str) -> None:
        self.text = str(value)


class _VoicePage:
    def __init__(self) -> None:
        self.status_badge = _TextTarget()
        self._desc = _TextTarget()
        self.transcript: list[tuple[str, str]] = []

    def add_transcript(self, role: str, text: str) -> None:
        self.transcript.append((role, text))


class _TopBar:
    def __init__(self) -> None:
        self.tokens = 0

    def add_tokens(self, count: int) -> None:
        self.tokens += int(count)


class _SystemPage:
    def __init__(self) -> None:
        self.logs = []

    def add_log_entry(self, *args) -> None:
        self.logs.append(args)


class _ChatPage:
    def __init__(self) -> None:
        self.messages = []

    def add_message(self, role: str, text: str) -> None:
        self.messages.append((role, text))


class _TTSRecorder:
    def __init__(self) -> None:
        self.calls = []

    def speak(self, text: str, force: bool = False) -> None:
        self.calls.append((text, force))


def test_realtime_voice_session_tracks_duplex_lifecycle() -> None:
    from shell_realtime_voice_session import RealtimeVoiceSession

    session = RealtimeVoiceSession(session_id="probe")
    session.start()
    session.user_speech_started()
    assert session.should_prewarm() is True
    session.prewarm_started()
    session.prewarm_done(elapsed_ms=3.25, shell_v2_ready=True, provider_count=7)
    session.user_speech_ended()
    session.text_committed("hello", turn_id=4)
    session.assistant_speech_started(transport="shell_v2")
    session.interrupt("barge_in")
    session.assistant_speech_done()

    snap = session.snapshot()
    assert snap["state"] == "listening"
    assert snap["turn_id"] == 4
    assert snap["turn_count"] == 1
    assert snap["interruption_count"] == 1
    assert snap["prewarm_count"] == 1
    assert snap["shell_v2_ready"] is True
    assert snap["provider_count"] == 7
    assert [event["event"] for event in snap["events"]][-2:] == [
        "interrupted",
        "assistant_speech_done",
    ]


# ---- Tests below required ShellHoloUI (PyQt6), removed during UI cleanup ----

@pytest.mark.skip(reason="ShellHoloUI removed during PyQt6 cleanup")
def test_voice_text_prefers_persistent_shell_v2_path(monkeypatch) -> None:
    pass


@pytest.mark.skip(reason="ShellHoloUI removed during PyQt6 cleanup")
def test_realtime_voice_prewarm_triggers_tts_intent(monkeypatch) -> None:
    pass


@pytest.mark.skip(reason="ShellHoloUI removed during PyQt6 cleanup")
def test_shell_v2_voice_reply_does_not_duplicate_stream_done(monkeypatch) -> None:
    pass


@pytest.mark.skip(reason="ShellHoloUI removed during PyQt6 cleanup")
def test_shell_v2_voice_reply_does_not_double_speak_streamed_turn(monkeypatch) -> None:
    pass


@pytest.mark.skip(reason="ShellHoloUI removed during PyQt6 cleanup")
def test_shell_v2_voice_error_falls_back_to_inprocess(monkeypatch) -> None:
    pass
