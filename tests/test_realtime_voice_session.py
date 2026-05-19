from __future__ import annotations


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


def test_voice_text_prefers_persistent_shell_v2_path(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_realtime_voice_session import RealtimeVoiceSession
    from shell_ui.shell_cinematic_full import ShellHoloUI

    ui = ShellHoloUI.__new__(ShellHoloUI)
    ui._voice_turn_id = 0
    ui._voice_turn_query_started = 0.0
    ui._voice_turn_processing_ts = 0.0
    ui._voice_realtime_session = RealtimeVoiceSession(session_id="voice")
    ui._voice_realtime_session.start()
    ui._chat_history = []
    ui.voice_page = _VoicePage()
    ui.top_bar = _TopBar()
    ui.system_page = _SystemPage()

    ui._try_run_backend_command = lambda *args, **kwargs: False
    ui._fast_local_reply_candidate = lambda _text: None
    shell_v2_calls = []
    inprocess_calls = []
    ui._start_voice_shell_v2_worker = lambda text, tid: shell_v2_calls.append((text, tid)) or True
    ui._start_voice_inprocess_worker = lambda text, tid: inprocess_calls.append((text, tid)) or True

    ShellHoloUI._on_voice_text(ui, "hello there")

    assert shell_v2_calls == [("hello there", 1)]
    assert inprocess_calls == []
    assert ui._voice_realtime_session.turn_count == 1
    assert ui._voice_realtime_session.state == "thinking"


def test_realtime_voice_prewarm_triggers_tts_intent(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    import shell_ui.shell_cinematic_full as ui_module
    from shell_realtime_voice_session import RealtimeVoiceSession
    from shell_ui.shell_cinematic_full import ShellHoloUI

    class _Brain:
        providers = {"probe": object()}

    class _TTS:
        def __init__(self) -> None:
            self.calls = []

        def prewarm_for_voice_intent(self, *, reason: str, provider_modules: bool) -> bool:
            self.calls.append((reason, provider_modules))
            return True

    ui = ShellHoloUI.__new__(ShellHoloUI)
    ui._voice_realtime_session = RealtimeVoiceSession(session_id="voice")
    ui._voice_realtime_session.start()
    ui._voice_realtime_prewarm_thread = None
    ui._tts = _TTS()
    ui._voice_shell_v2_ready = lambda start_bridge=False: False
    monkeypatch.setattr(ui_module, "get_brain", lambda: _Brain())

    assert ShellHoloUI._prewarm_realtime_voice_path(ui, "speech_started") is True
    ui._voice_realtime_prewarm_thread.join(2.0)

    assert ui._tts.calls == [("speech_started", True)]
    snap = ui._voice_realtime_session.snapshot()
    assert snap["prewarm_count"] == 1
    assert snap["provider_count"] == 1


def test_shell_v2_voice_reply_does_not_duplicate_stream_done(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import ShellHoloUI

    ui = ShellHoloUI.__new__(ShellHoloUI)
    ui._voice_turn_id = 5
    ui._voice_stream_completed_turn_id = 5
    replies = []
    ui._on_voice_ai_reply = replies.append

    ShellHoloUI._on_voice_shell_v2_reply_for_turn(ui, 5, "already streamed")

    assert replies == []


def test_shell_v2_voice_reply_does_not_double_speak_streamed_turn(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import ShellHoloUI

    ui = ShellHoloUI.__new__(ShellHoloUI)
    ui._voice_turn_id = 7
    ui._voice_stream_completed_turn_id = 0
    ui._voice_streaming_text = "Hello, world."
    ui._voice_stream_spoken_upto = len("Hello, ")
    ui._voice_first_chunk_seen = True
    ui._chat_history = [("user", "say hello")]
    ui._tts = _TTSRecorder()
    ui.voice_page = _VoicePage()
    ui.chat_page = _ChatPage()
    ui.top_bar = _TopBar()
    ui.system_page = _SystemPage()
    ui._record_agent_message = lambda _text: None

    ShellHoloUI._on_voice_shell_v2_reply_for_turn(ui, 7, "Hello, world.")
    ShellHoloUI._on_voice_stream_done_for_turn(ui, 7)
    ShellHoloUI._on_voice_stream_chunk_for_turn(ui, 7, "Hello, world.")

    assert ui._tts.calls == [("world.", True)]
    assert all(call[0] != "Hello, world." for call in ui._tts.calls)
    assert ui._voice_stream_completed_turn_id == 7


def test_shell_v2_voice_error_falls_back_to_inprocess(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import ShellHoloUI

    ui = ShellHoloUI.__new__(ShellHoloUI)
    ui._voice_turn_id = 2
    ui._voice_streaming_text = ""
    ui.system_page = _SystemPage()
    calls = []
    ui._start_voice_inprocess_worker = lambda text, tid: calls.append((text, tid)) or True

    ShellHoloUI._on_voice_shell_v2_error_for_turn(ui, 2, "down", "hello")

    assert calls == [("hello", 2)]
    assert ui.system_page.logs
