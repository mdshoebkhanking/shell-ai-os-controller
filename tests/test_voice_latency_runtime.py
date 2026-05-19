def test_voice_aliases_resolve_to_aoede(monkeypatch):
    monkeypatch.delenv("VOICE_NAME", raising=False)

    from shell_voice import describe_voice, resolve_voice

    assert resolve_voice("adreno") == "Aoede"
    assert resolve_voice("aode") == "Aoede"
    assert "Aoede" in describe_voice("adreno")


def test_tts_command_detection_is_non_throwing(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import TTSSpeaker, _system_tts_available

    speaker = TTSSpeaker()
    assert isinstance(speaker._detect_system_tts_command(), str)
    assert isinstance(_system_tts_available(), bool)


def test_tts_speak_reports_no_audio_output(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    speaker._engine = "system"
    monkeypatch.setattr(speaker, "_speak_system", lambda _text: False)

    assert speaker._do_speak("hello") is False


def test_cloud_voice_prioritizes_gemini_identity_even_instant_mode(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.setenv("SHELL_TTS_LATENCY_MODE", "instant")
    monkeypatch.setenv("GOOGLE_API_KEY", "g" * 32)

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    calls = []
    monkeypatch.setattr(
        speaker,
        "_speak_system",
        lambda _text: (_ for _ in ()).throw(AssertionError("system fallback used")),
    )
    monkeypatch.setattr(speaker, "_speak_gemini_live_tts", lambda _text: False)
    monkeypatch.setattr(speaker, "_speak_gemini_tts", lambda text: calls.append(text) or True)

    assert speaker._do_speak("hello") is True
    assert calls == ["hello"]


def test_cloud_voice_prefers_gemini_live_streaming(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.setenv("GOOGLE_API_KEY", "g" * 32)

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    calls = []
    monkeypatch.setattr(speaker, "_speak_gemini_live_tts", lambda text: calls.append(("live", text)) or True)
    monkeypatch.setattr(
        speaker,
        "_speak_gemini_tts",
        lambda _text: (_ for _ in ()).throw(AssertionError("batch Gemini used before live")),
    )
    monkeypatch.setattr(
        speaker,
        "_speak_system",
        lambda _text: (_ for _ in ()).throw(AssertionError("system fallback used")),
    )

    assert speaker._do_speak("hello") is True
    assert calls == [("live", "hello")]


def test_cloud_voice_fallback_is_logged_only_when_explicitly_allowed(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.setenv("SHELL_CLOUD_TTS_LOCAL_FALLBACK", "1")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    events = []
    speaker.latency_event.connect(lambda event, payload: events.append((event, dict(payload))))
    monkeypatch.setattr(speaker, "_speak_gemini_live_tts", lambda _text: False)
    monkeypatch.setattr(speaker, "_speak_system", lambda _text: True)

    assert speaker._do_speak("hello") is True
    fallback = [payload for event, payload in events if event == "tts_fallback_activated"]
    assert fallback
    assert fallback[0]["from_backend"] == "gemini"
    assert fallback[0]["to_backend"] == "system"
    assert fallback[0]["cloud_fallback_allowed"] is True


def test_cloud_voice_does_not_silently_use_local_fallback(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("SHELL_CLOUD_TTS_LOCAL_FALLBACK", raising=False)

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    monkeypatch.setattr(speaker, "_speak_system", lambda _text: (_ for _ in ()).throw(AssertionError("local fallback used")))
    monkeypatch.setattr(speaker, "_speak_pyttsx3", lambda _text: (_ for _ in ()).throw(AssertionError("local fallback used")))

    assert speaker._do_speak("hello") is False
    assert "Gemini voice is selected" in speaker._last_error


def test_cloud_voice_fallback_blocked_is_logged(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("SHELL_CLOUD_TTS_LOCAL_FALLBACK", raising=False)

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    events = []
    speaker.latency_event.connect(lambda event, payload: events.append((event, dict(payload))))
    monkeypatch.setattr(speaker, "_speak_gemini_live_tts", lambda _text: False)

    assert speaker._do_speak("hello") is False
    blocked = [payload for event, payload in events if event == "tts_fallback_blocked"]
    assert blocked
    assert blocked[0]["from_backend"] == "gemini"
    assert blocked[0]["to_backend"] == "system"
    assert blocked[0]["cloud_fallback_allowed"] is False
    assert blocked[0]["gemini_voice"] == "Aoede"


def test_cloud_voice_cancel_does_not_emit_fallback_failure(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.setenv("GOOGLE_API_KEY", "g" * 32)
    monkeypatch.delenv("SHELL_CLOUD_TTS_LOCAL_FALLBACK", raising=False)

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    events = []
    speaker.latency_event.connect(lambda event, payload: events.append((event, dict(payload))))
    speaker._stop_requested.set()
    monkeypatch.setattr(speaker, "_speak_gemini_live_tts", lambda _text: False)
    monkeypatch.setattr(speaker, "_speak_gemini_tts", lambda _text: False)
    monkeypatch.setattr(
        speaker,
        "_speak_system",
        lambda _text: (_ for _ in ()).throw(AssertionError("system fallback used")),
    )

    assert speaker._do_speak("hello") is True
    assert "tts_fallback_blocked" not in [event for event, _payload in events]


def test_mac_audio_output_probe_is_cached(monkeypatch):
    import shutil

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    speaker._audio_output_probe_ttl_s = 60.0
    probes = []
    monkeypatch.setattr(
        shutil, "which", lambda name: "/usr/bin/afplay" if name == "afplay" else None
    )
    monkeypatch.setattr(speaker, "_run_probe_command", lambda *_args, **_kwargs: probes.append(1) or True)

    assert speaker._mac_audio_output_available() is True
    assert speaker._mac_audio_output_available() is True
    assert len(probes) == 1


def test_openai_streaming_tts_uses_pcm_player(monkeypatch):
    import openai
    import openai.helpers

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-" + "x" * 40)
    monkeypatch.setenv("OPENAI_TTS_PCM_CHUNK_BYTES", "480")

    from shell_ui.shell_cinematic_full import TTSSpeaker

    consumed = []
    create_calls = []

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def iter_bytes(self, chunk_size=1024):
            yield b"\x00\x00" * 240
            yield b"\x01\x00" * 240

    class FakeCreate:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return FakeResponse()

    class FakeSpeech:
        def __init__(self):
            self.with_streaming_response = FakeCreate()

    class FakeAudio:
        def __init__(self):
            self.speech = FakeSpeech()

    class FakeAsyncOpenAI:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.audio = FakeAudio()

    class FakeLocalAudioPlayer:
        def __init__(self, should_stop=None):
            self.should_stop = should_stop

        async def play_stream(self, stream):
            async for buffer in stream:
                if buffer is None:
                    break
                consumed.append(buffer)

    monkeypatch.setattr(openai, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(openai.helpers, "LocalAudioPlayer", FakeLocalAudioPlayer)

    speaker = TTSSpeaker()
    speaker._engine = "openai-stream"
    events = []
    speaker.latency_event.connect(lambda event, payload: events.append((event, dict(payload))))

    assert speaker._speak_openai_streaming_tts("hello") is True
    assert len(consumed) == 2
    assert create_calls[0]["response_format"] == "pcm"
    assert create_calls[0]["model"] == "gpt-4o-mini-tts"
    event_names = [event for event, _payload in events]
    assert "tts_backend_selected" in event_names
    assert "openai_pcm_first_chunk" in event_names
    assert "playback_started" in event_names
    assert "openai_pcm_done" in event_names
    selected_payloads = [payload for event, payload in events if event == "tts_backend_selected"]
    assert selected_payloads[0]["backend"] == "openai_pcm"
    assert selected_payloads[0]["voice"] == "coral"


def test_gemini_live_streaming_tts_uses_aoede_pcm_player(monkeypatch):
    import google.genai
    import openai.helpers

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("GOOGLE_API_KEY", "g" * 32)

    from shell_ui.shell_cinematic_full import TTSSpeaker

    consumed = []
    connect_calls = []
    sent_turns = []

    class Inline:
        data = b"\x00\x00" * 240
        mime_type = "audio/pcm;rate=24000"

    class Part:
        inline_data = Inline()

    class ModelTurn:
        parts = [Part()]

    class ServerContent:
        model_turn = ModelTurn()
        turn_complete = False
        interrupted = False

    class DoneServerContent:
        model_turn = None
        turn_complete = True
        interrupted = False

    class Message:
        server_content = ServerContent()

    class DoneMessage:
        server_content = DoneServerContent()

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def send_client_content(self, **kwargs):
            sent_turns.append(kwargs)

        async def receive(self):
            yield Message()
            yield DoneMessage()

    class FakeLive:
        def connect(self, **kwargs):
            connect_calls.append(kwargs)
            return FakeSession()

    class FakeAio:
        def __init__(self):
            self.live = FakeLive()

        async def aclose(self):
            pass

    class FakeClient:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.aio = FakeAio()

    class FakeLocalAudioPlayer:
        def __init__(self, should_stop=None):
            self.should_stop = should_stop

        async def play_stream(self, stream):
            async for buffer in stream:
                if buffer is None:
                    break
                consumed.append(buffer)

    monkeypatch.setattr(google.genai, "Client", FakeClient)
    monkeypatch.setattr(openai.helpers, "LocalAudioPlayer", FakeLocalAudioPlayer)

    speaker = TTSSpeaker()
    events = []
    speaker.latency_event.connect(lambda event, payload: events.append((event, dict(payload))))

    assert speaker._speak_gemini_live_tts("hello") is True
    assert len(consumed) == 1
    assert connect_calls[0]["model"] == "gemini-3.1-flash-live-preview"
    assert sent_turns
    event_names = [event for event, _payload in events]
    assert "tts_backend_selected" in event_names
    assert "gemini_live_first_chunk" in event_names
    assert "playback_started" in event_names
    assert "gemini_live_done" in event_names
    selected_payloads = [payload for event, payload in events if event == "tts_backend_selected"]
    assert selected_payloads[0]["backend"] == "gemini_live_pcm"
    assert selected_payloads[0]["voice"] == "Aoede"


def test_set_voice_keeps_gemini_voice_name(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    speaker.set_voice("Charon")

    assert speaker._gemini_voice_name == "Charon"


def test_gemini_pcm_audio_is_wrapped_as_wav(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import TTSSpeaker

    path = tmp_path / "speech.wav"
    TTSSpeaker._write_gemini_audio_file(b"\x00\x00\x01\x00", "audio/l16;rate=24000", str(path))

    assert path.read_bytes().startswith(b"RIFF")


def test_speak_tool_cloud_mode_requires_gemini_not_local(monkeypatch):
    import asyncio

    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.delenv("SHELL_CLOUD_TTS_LOCAL_FALLBACK", raising=False)

    from shell_speech import speak_tool

    result = asyncio.run(speak_tool("hello"))

    assert "Gemini voice is selected" in result
    assert "Spoke" not in result


def test_voice_page_has_no_test_voice_button(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication
    from shell_ui.shell_cinematic_full import VoicePage
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    page = VoicePage()

    assert not hasattr(page, "test_voice_requested")
    assert not hasattr(page, "test_voice_btn")
    page.close()


def test_voice_listener_defaults_reduce_end_of_turn_latency(monkeypatch):
    monkeypatch.delenv("SHELL_VOICE_END_SILENCE_MS", raising=False)
    monkeypatch.delenv("SHELL_VOICE_CHUNK_MS", raising=False)

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()

    assert listener._speech_timeout <= 0.8
    assert listener._min_speech_duration <= 0.35
    assert listener._chunk_duration <= 0.05


def test_voice_listener_adaptive_endpointing_short_clean_turn_is_faster(monkeypatch):
    monkeypatch.setenv("SHELL_VOICE_ADAPTIVE_ENDPOINTING", "1")
    monkeypatch.delenv("SHELL_VOICE_END_SILENCE_MS", raising=False)
    monkeypatch.delenv("SHELL_VOICE_ENDPOINT_MIN_MS", raising=False)
    monkeypatch.delenv("SHELL_VOICE_ENDPOINT_MAX_MS", raising=False)

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()
    timeout = listener._adaptive_speech_timeout(0.8, noise_floor=0.0)

    assert timeout < listener._speech_timeout
    assert timeout >= listener._endpoint_min_s
    assert timeout <= 0.6


def test_voice_listener_adaptive_endpointing_waits_longer_for_noise(monkeypatch):
    monkeypatch.setenv("SHELL_VOICE_ADAPTIVE_ENDPOINTING", "1")
    monkeypatch.delenv("SHELL_VOICE_END_SILENCE_MS", raising=False)

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()
    clean = listener._adaptive_speech_timeout(0.8, noise_floor=0.0)
    noisy = listener._adaptive_speech_timeout(
        0.8,
        noise_floor=listener._silence_threshold * 0.8,
    )

    assert noisy > clean
    assert noisy <= listener._endpoint_max_s


def test_voice_listener_adaptive_endpointing_can_be_disabled(monkeypatch):
    monkeypatch.setenv("SHELL_VOICE_ADAPTIVE_ENDPOINTING", "0")

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()

    assert listener._adaptive_speech_timeout(0.8, noise_floor=0.0) == listener._speech_timeout


def test_voice_listener_semantic_pacing_waits_after_hesitation(monkeypatch):
    monkeypatch.setenv("SHELL_VOICE_ADAPTIVE_ENDPOINTING", "1")
    monkeypatch.setenv("SHELL_VOICE_SEMANTIC_PACING", "1")

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()
    clean = listener._adaptive_speech_timeout(0.8, noise_floor=0.0)
    semantic = listener._remember_semantic_turn("um let me think", duration_s=0.8)
    paced = listener._adaptive_speech_timeout(0.8, noise_floor=0.0)

    assert semantic["completion"] == "hesitation"
    assert paced > clean
    assert listener._last_semantic_endpoint["completion"] == "hesitation"


def test_voice_listener_semantic_pacing_speeds_after_short_command(monkeypatch):
    monkeypatch.setenv("SHELL_VOICE_ADAPTIVE_ENDPOINTING", "1")
    monkeypatch.setenv("SHELL_VOICE_SEMANTIC_PACING", "1")

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()
    clean = listener._adaptive_speech_timeout(1.8, noise_floor=0.0)
    semantic = listener._remember_semantic_turn("stop", duration_s=0.4)
    paced = listener._adaptive_speech_timeout(1.8, noise_floor=0.0)

    assert semantic["completion"] == "short_command"
    assert paced < clean
    assert paced >= listener._endpoint_min_s


def test_voice_listener_semantic_pacing_detects_continuation(monkeypatch):
    monkeypatch.setenv("SHELL_VOICE_SEMANTIC_PACING", "1")

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()
    semantic = listener._remember_semantic_turn("can you open the file and", duration_s=1.4)

    assert semantic["completion"] == "continuation"
    assert semantic["bias_ms"] > 0


def test_voice_listener_semantic_pacing_can_be_disabled(monkeypatch):
    monkeypatch.setenv("SHELL_VOICE_SEMANTIC_PACING", "0")

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()
    semantic = listener._remember_semantic_turn("um let me think", duration_s=0.8)

    assert semantic["completion"] == "hesitation"
    assert semantic["bias_ms"] == 0.0
    assert listener._adaptive_speech_timeout(0.8, noise_floor=0.0) <= 0.6


def test_voice_listener_semantic_rhythm_learns_patient_style(monkeypatch):
    monkeypatch.setenv("SHELL_VOICE_ADAPTIVE_ENDPOINTING", "1")
    monkeypatch.setenv("SHELL_VOICE_SEMANTIC_PACING", "1")

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()
    initial = listener._adaptive_speech_timeout(0.8, noise_floor=0.0)
    listener._remember_semantic_turn("um let me think", duration_s=0.8)
    listener._remember_semantic_turn("can you open the file and", duration_s=1.4)
    paced = listener._adaptive_speech_timeout(0.8, noise_floor=0.0)

    assert listener._semantic_rhythm_profile["style"] == "patient"
    assert listener._semantic_rhythm_profile["rhythm_bias_ms"] > 0
    assert paced > initial


def test_voice_listener_semantic_rhythm_learns_fast_style(monkeypatch):
    monkeypatch.setenv("SHELL_VOICE_ADAPTIVE_ENDPOINTING", "1")
    monkeypatch.setenv("SHELL_VOICE_SEMANTIC_PACING", "1")

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()
    initial = listener._adaptive_speech_timeout(1.8, noise_floor=0.0)
    listener._remember_semantic_turn("stop", duration_s=0.4)
    listener._remember_semantic_turn("yes", duration_s=0.4)
    paced = listener._adaptive_speech_timeout(1.8, noise_floor=0.0)

    assert listener._semantic_rhythm_profile["style"] == "fast"
    assert listener._semantic_rhythm_profile["rhythm_bias_ms"] < 0
    assert paced < initial


def test_voice_listener_emits_latency_payloads(monkeypatch):
    import time

    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()
    events = []
    listener.latency_event.connect(lambda event, payload: events.append((event, payload)))

    started = time.perf_counter()
    listener._emit_latency("probe", started, source="test")

    assert events
    assert events[0][0] == "probe"
    assert events[0][1]["source"] == "test"
    assert "elapsed_ms" in events[0][1]
    assert "ts" in events[0][1]


def test_voice_tts_first_segment_can_start_before_full_sentence(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SHELL_VOICE_TTS_FIRST_CHARS", "12")
    monkeypatch.setenv("SHELL_VOICE_TTS_FIRST_HARD_CHARS", "40")

    from shell_ui.shell_cinematic_full import ShellHoloUI

    segment, offset = ShellHoloUI._voice_tts_next_segment(
        "I can absolutely help, and I will keep going with details. More text.",
        0,
    )

    assert segment == "I can absolutely help,"
    assert offset > 0


def test_tool_gateway_awaits_async_tool_results(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_tool_gateway import execute_tool_sync

    result = execute_tool_sync("shell_speech:voice_status_tool", {})

    assert result["status"] == "success"
    assert "coroutine object" not in str(result["result"])
    assert "Shell Voice Status" in str(result["result"])


def test_active_context_import_is_cross_platform_safe():
    import active_context_engine

    assert hasattr(active_context_engine, "get_selected_file_context_tool")
    assert isinstance(active_context_engine.WINDOWS_CONTEXT_AVAILABLE, bool)
