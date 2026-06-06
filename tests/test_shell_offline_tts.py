import sys
import types
from pathlib import Path

from PyQt6.QtCore import QCoreApplication


class FakeSpeechProcess:
    def __init__(self) -> None:
        self.stopped = False

    def poll(self):
        return None if not self.stopped else 0

    def terminate(self) -> None:
        self.stopped = True

    def wait(self, timeout=None):
        self.stopped = True
        return 0

    def kill(self) -> None:
        self.stopped = True


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self.callbacks):
            callback(*args)


def test_offline_tts_status_reports_disabled(monkeypatch):
    import shell_offline_tts

    monkeypatch.setenv("SHELL_OFFLINE_TTS", "0")

    status = shell_offline_tts.offline_tts_status()

    assert status["success"] is True
    assert status["available"] is False
    assert status["engine"] == "disabled"


def test_offline_tts_status_falls_back_without_packaged_model(monkeypatch, tmp_path):
    import shell_offline_tts

    monkeypatch.setattr(shell_offline_tts, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("SHELL_OFFLINE_TTS", "1")
    monkeypatch.setenv("SHELL_NATURAL_TTS_ENGINE", "auto")
    monkeypatch.setenv("SHELL_NATURAL_TTS_MODEL_DIR", str(tmp_path / "missing-model"))

    status = shell_offline_tts.offline_tts_status()

    assert status["success"] is True
    assert status["available"] is False
    assert status["engine"] == "fallback"
    assert "OS voice fallback" in status["reason"]
    assert {candidate["engine"] for candidate in status["candidates"]} == {"kokoro", "piper"}


def test_offline_tts_status_tracks_shell_language(monkeypatch, tmp_path):
    import shell_offline_tts

    monkeypatch.setattr(shell_offline_tts, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("SHELL_OFFLINE_TTS", "1")
    monkeypatch.setenv("SHELL_LANGUAGE", "hindi")
    monkeypatch.setenv("SHELL_NATURAL_TTS_ENGINE", "auto")

    status = shell_offline_tts.offline_tts_status()

    assert status["language"] == "hindi"
    assert status["locale"] == "hi"


def test_offline_tts_status_reports_kokoro_metadata(monkeypatch, tmp_path):
    import shell_offline_tts

    model_dir = tmp_path / "kokoro"
    model_dir.mkdir()
    (model_dir / "kokoro-v1.0.onnx").write_bytes(b"model")
    (model_dir / "voices-v1.0.bin").write_bytes(b"voices")
    fake_kokoro = types.ModuleType("kokoro_onnx")

    monkeypatch.setattr(shell_offline_tts, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(sys.modules, "kokoro_onnx", fake_kokoro)
    monkeypatch.setenv("SHELL_OFFLINE_TTS", "1")
    monkeypatch.setenv("SHELL_LANGUAGE", "hindi")
    monkeypatch.setenv("SHELL_NATURAL_TTS_ENGINE", "kokoro")
    monkeypatch.setenv("SHELL_NATURAL_TTS_MODEL_DIR", str(model_dir))

    status = shell_offline_tts.offline_tts_status()

    assert status["available"] is True
    assert status["engine"] == "kokoro"
    assert status["modelFamily"] == "Kokoro-82M"
    assert status["runtime"] == "kokoro_onnx"
    assert status["activeVoice"] == "hf_alpha"
    assert status["voices"]["english"] == "af_heart"
    assert status["voices"]["hindi"] == "hf_alpha"
    assert status["preferredVoiceProfile"] == "realistic-female"
    assert status["nativeHindiVoice"] == "hf_alpha"


def test_offline_tts_status_finds_kokoro_next_to_installed_pyinstaller_app(monkeypatch, tmp_path):
    import shell_offline_tts

    install_root = tmp_path / "ShellAI"
    app_dir = install_root / "ShellAIApp"
    internal_dir = app_dir / "_internal"
    model_dir = install_root / "models" / "tts" / "kokoro"
    model_dir.mkdir(parents=True)
    internal_dir.mkdir(parents=True)
    (model_dir / "kokoro-v1.0.int8.onnx").write_bytes(b"model")
    (model_dir / "voices-v1.0.bin").write_bytes(b"voices")
    fake_kokoro = types.ModuleType("kokoro_onnx")

    monkeypatch.setattr(shell_offline_tts, "PROJECT_ROOT", internal_dir)
    monkeypatch.setattr(shell_offline_tts.sys, "frozen", True, raising=False)
    monkeypatch.setattr(shell_offline_tts.sys, "executable", str(app_dir / "ShellAI.exe"))
    monkeypatch.setitem(sys.modules, "kokoro_onnx", fake_kokoro)
    monkeypatch.setenv("SHELL_OFFLINE_TTS", "1")
    monkeypatch.setenv("SHELL_NATURAL_TTS_ENGINE", "kokoro")
    monkeypatch.delenv("SHELL_NATURAL_TTS_MODEL_DIR", raising=False)
    monkeypatch.delenv("SHELL_OFFLINE_TTS_MODEL_DIR", raising=False)

    status = shell_offline_tts.offline_tts_status()

    assert status["available"] is True
    assert status["engine"] == "kokoro"
    assert status["modelDir"] == str(model_dir)


def test_kokoro_segments_route_hinglish_clauses(monkeypatch):
    import shell_offline_tts

    monkeypatch.setenv("SHELL_LANGUAGE", "hinglish")
    monkeypatch.delenv("SHELL_HINGLISH_TTS_ROUTING", raising=False)
    monkeypatch.delenv("SHELL_NATURAL_TTS_VOICE", raising=False)

    segments = shell_offline_tts._prepare_kokoro_segments("Open Chrome now. bhai kaise ho?")

    assert [segment.language for segment in segments] == ["english", "hindi"]
    assert [segment.locale for segment in segments] == ["en-us", "hi"]
    assert [segment.voice for segment in segments] == ["af_heart", "hf_alpha"]
    assert [segment.text for segment in segments] == ["Open Chrome now.", "bhai kaise ho?"]


def test_kokoro_balanced_routing_keeps_roman_hinglish_on_english_when_requested(monkeypatch):
    import shell_offline_tts

    monkeypatch.setenv("SHELL_LANGUAGE", "hinglish")
    monkeypatch.setenv("SHELL_HINGLISH_TTS_ROUTING", "balanced")
    monkeypatch.delenv("SHELL_NATURAL_TTS_VOICE", raising=False)

    segments = shell_offline_tts._prepare_kokoro_segments("Open Chrome now. bhai kaise ho?")

    assert [segment.language for segment in segments] == ["english"]
    assert [segment.locale for segment in segments] == ["en-us"]
    assert [segment.voice for segment in segments] == ["af_heart"]
    assert segments[0].text == "Open Chrome now. bhai kaise ho?"


def test_kokoro_bilingual_routing_keeps_pure_english_on_realistic_voice(monkeypatch):
    import shell_offline_tts

    monkeypatch.setenv("SHELL_LANGUAGE", "hinglish")
    monkeypatch.delenv("SHELL_HINGLISH_TTS_ROUTING", raising=False)
    monkeypatch.delenv("SHELL_NATURAL_TTS_VOICE", raising=False)

    segments = shell_offline_tts._prepare_kokoro_segments(
        "Shell AI is online. Offline voice is active. Your private command center is standing by."
    )

    assert [segment.language for segment in segments] == ["english"]
    assert segments[0].locale == "en-us"
    assert segments[0].voice == "af_heart"


def test_kokoro_roman_hindi_uses_native_pronunciation_text(monkeypatch):
    import shell_offline_tts

    monkeypatch.setenv("SHELL_LANGUAGE", "hinglish")
    monkeypatch.delenv("SHELL_HINGLISH_TTS_ROUTING", raising=False)

    segments = shell_offline_tts._prepare_kokoro_segments("bhai awaaz ab sahi hai?")

    assert [segment.language for segment in segments] == ["hindi"]
    assert segments[0].voice == "hf_alpha"
    assert shell_offline_tts._kokoro_synthesis_text_for(segments[0]) == "भाई आवाज अब सही है?"


def test_kokoro_devanagari_routes_to_native_hindi_voice(monkeypatch):
    import shell_offline_tts

    monkeypatch.setenv("SHELL_LANGUAGE", "hinglish")
    monkeypatch.delenv("SHELL_HINGLISH_TTS_ROUTING", raising=False)
    monkeypatch.delenv("SHELL_NATURAL_TTS_VOICE", raising=False)

    segments = shell_offline_tts._prepare_kokoro_segments("Namaste. आप कैसे हैं?")

    assert [segment.language for segment in segments] == ["english", "hindi"]
    assert [segment.locale for segment in segments] == ["en-us", "hi"]
    assert [segment.voice for segment in segments] == ["af_heart", "hf_alpha"]


def test_kokoro_espeak_patch_uses_relative_data_path_on_macos(monkeypatch, tmp_path):
    import shell_offline_tts

    captured = []
    data_path = tmp_path / "pkg" / "espeak-ng-data"
    data_path.mkdir(parents=True)
    (data_path / "phontab").write_text("phoneme table")

    class FakeEspeakAPI:
        def __init__(self, library, data_path_arg) -> None:
            captured.append((library, data_path_arg))

    fake_phonemizer = types.ModuleType("phonemizer")
    fake_backend = types.ModuleType("phonemizer.backend")
    fake_espeak = types.ModuleType("phonemizer.backend.espeak")
    fake_api = types.ModuleType("phonemizer.backend.espeak.api")
    fake_api.EspeakAPI = FakeEspeakAPI

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(shell_offline_tts.platform, "system", lambda: "Darwin")
    monkeypatch.setitem(sys.modules, "phonemizer", fake_phonemizer)
    monkeypatch.setitem(sys.modules, "phonemizer.backend", fake_backend)
    monkeypatch.setitem(sys.modules, "phonemizer.backend.espeak", fake_espeak)
    monkeypatch.setitem(sys.modules, "phonemizer.backend.espeak.api", fake_api)

    shell_offline_tts._patch_kokoro_espeak_absolute_data_path()
    FakeEspeakAPI("libespeak", str(data_path))

    assert captured == [("libespeak", str(Path("pkg") / "espeak-ng-data"))]


def test_play_wav_async_rejects_immediate_player_failure(monkeypatch, tmp_path):
    import shell_offline_tts

    class FailedProcess:
        def poll(self):
            return 1

    wav_path = tmp_path / "speech.wav"
    wav_path.write_bytes(b"wav")

    monkeypatch.setattr(shell_offline_tts, "_playback_command", lambda _path: ["fake-player", str(wav_path)])
    monkeypatch.setattr(shell_offline_tts.subprocess, "Popen", lambda *_args, **_kwargs: FailedProcess())
    monkeypatch.setattr(shell_offline_tts.time, "sleep", lambda _seconds: None)

    assert shell_offline_tts._play_wav_async(wav_path) is None


def test_play_wav_async_uses_winsound_on_windows(monkeypatch, tmp_path):
    import shell_offline_tts

    calls = []
    fake_winsound = types.ModuleType("winsound")
    fake_winsound.SND_FILENAME = 1
    fake_winsound.SND_ASYNC = 2
    fake_winsound.SND_PURGE = 4

    def fake_play_sound(path, flags):
        calls.append((path, flags))

    fake_winsound.PlaySound = fake_play_sound
    wav_path = tmp_path / "speech.wav"
    wav_path.write_bytes(b"wav")

    monkeypatch.setattr(shell_offline_tts.platform, "system", lambda: "Windows")
    monkeypatch.setitem(sys.modules, "winsound", fake_winsound)
    monkeypatch.setattr(
        shell_offline_tts.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("PowerShell fallback should not run")),
    )

    playback = shell_offline_tts._play_wav_async(wav_path)

    assert playback is not None
    assert calls == [(str(wav_path), fake_winsound.SND_FILENAME | fake_winsound.SND_ASYNC)]
    playback.terminate()
    assert calls[-1] == (None, fake_winsound.SND_PURGE)


def test_kokoro_speak_renders_routed_segments(monkeypatch, tmp_path):
    import shell_offline_tts

    model_dir = tmp_path / "kokoro"
    model_dir.mkdir()
    (model_dir / "kokoro-v1.0.onnx").write_bytes(b"model")
    (model_dir / "voices-v1.0.bin").write_bytes(b"voices")
    calls = []
    captured_audio = {}

    class FakeKokoro:
        def __init__(self, model, voices) -> None:
            self.model = model
            self.voices = voices

        def create(self, text, voice, speed, lang):
            calls.append({"text": text, "voice": voice, "speed": speed, "lang": lang})
            return ([0.1, 0.0] if lang == "en-us" else [0.2, 0.0]), 24000

    fake_kokoro = types.ModuleType("kokoro_onnx")
    fake_kokoro.Kokoro = FakeKokoro

    monkeypatch.setattr(shell_offline_tts, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(sys.modules, "kokoro_onnx", fake_kokoro)
    monkeypatch.setenv("SHELL_LANGUAGE", "hinglish")
    monkeypatch.setenv("SHELL_NATURAL_TTS_MODEL_DIR", str(model_dir))
    monkeypatch.setattr(
        shell_offline_tts,
        "_write_float_wav",
        lambda path, samples, sample_rate: captured_audio.update(
            {"path": path, "samples": samples, "sample_rate": sample_rate}
        ),
    )
    monkeypatch.setattr(shell_offline_tts, "_play_wav_async", lambda _path: FakeSpeechProcess())

    result = shell_offline_tts._speak_kokoro("Open Chrome now. bhai kaise ho?")

    assert result["success"] is True
    assert [call["lang"] for call in calls] == ["en-us", "hi"]
    assert [call["voice"] for call in calls] == ["af_heart", "hf_alpha"]
    assert calls[1]["text"] == "भाई कैसे हो?"
    assert result["voices"] == ["af_heart", "hf_alpha"]
    assert result["segments"][0]["language"] == "english"
    assert result["segments"][1]["language"] == "hindi"
    assert result["durationMs"] > 0
    assert result["amplitudeFrameMs"] > 0
    assert result["amplitudeFrames"]
    assert captured_audio["sample_rate"] == 24000


def test_backend_bridge_prefers_offline_tts(monkeypatch):
    import shell_web_ui.host as host

    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []
    fake_process = FakeSpeechProcess()

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(bridge, "_start_background_task", lambda _name, target: target())
    monkeypatch.setattr(
        host,
        "offline_tts_status",
        lambda: {"available": True, "engine": "kokoro", "label": "Offline natural voice"},
    )
    monkeypatch.setattr(
        host,
        "speak_offline_tts",
        lambda text: {
            "success": True,
            "available": True,
            "engine": "kokoro",
            "voice": "af_heart",
            "chars": len(text),
            "durationMs": 1400,
            "amplitudeFrameMs": 70,
            "amplitudeFrames": [0.2, 0.6, 0.3],
            "_process": fake_process,
        },
    )
    monkeypatch.setattr(
        bridge,
        "_tts_command",
        lambda _text: (_ for _ in ()).throw(AssertionError("OS TTS should not be used when offline TTS succeeds")),
    )

    result = bridge._speak_text(["Shell voice test"])

    assert result["success"] is True
    assert result["source"] == "offline-tts"
    assert "_process" not in result
    assert bridge._speech_process is fake_process
    assert emitted[-1][0] == "speech-status"
    assert emitted[-1][1]["engine"] == "kokoro"
    assert emitted[-1][1]["durationMs"] == 1400
    assert emitted[-1][1]["amplitudeFrames"] == [0.2, 0.6, 0.3]


def test_backend_bridge_uses_gemini_voice_when_cloud_key_configured(monkeypatch):
    import shell_web_ui.host as host

    class FakeCloudSpeaker:
        def __init__(self, parent=None) -> None:
            self.parent = parent
            self.speech_error = FakeSignal()
            self.speaking_finished = FakeSignal()
            self._engine = ""
            self.spoken = []
            self.started = False

        def start(self) -> None:
            self.started = True

        def stop_speaking(self) -> None:
            pass

        def set_voice(self, voice) -> None:
            self.voice = voice

        def speak(self, text, force=False) -> None:
            self.spoken.append((text, force))

        def voice_identity_snapshot(self):
            return {"gemini_voice": "Aoede"}

    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []

    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.setenv("GOOGLE_API_KEY", "g" * 32)
    monkeypatch.setattr(host, "TTSSpeaker", FakeCloudSpeaker)
    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(
        host,
        "speak_offline_tts",
        lambda _text: (_ for _ in ()).throw(AssertionError("offline TTS should not run before Gemini cloud voice")),
    )

    result = bridge._speak_text(["Cloud voice test"])

    assert result["success"] is True
    assert result["engine"] == "gemini"
    assert result["source"] == "gemini-live"
    assert result["voice"] == "Aoede"
    assert bridge._cloud_tts_speaker.started is True
    assert bridge._cloud_tts_speaker.spoken == [("Cloud voice test", True)]
    assert emitted[-1][1]["engine"] == "gemini"


def test_backend_bridge_falls_back_to_offline_tts_without_gemini_key(monkeypatch):
    import shell_web_ui.host as host

    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []
    fake_process = FakeSpeechProcess()

    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(
        host,
        "offline_tts_status",
        lambda: {"success": True, "available": True, "engine": "kokoro", "label": "Kokoro offline voice"},
    )
    monkeypatch.setattr(bridge, "_start_background_task", lambda _name, target: target())
    monkeypatch.setattr(
        host,
        "speak_offline_tts",
        lambda text: {
            "success": True,
            "available": True,
            "engine": "kokoro",
            "voice": "af_heart",
            "chars": len(text),
            "durationMs": 1200,
            "amplitudeFrameMs": 70,
            "amplitudeFrames": [0.15, 0.55],
            "_process": fake_process,
        },
    )

    result = bridge._speak_text(["No key local voice"])

    assert result["success"] is True
    assert result["queued"] is True
    assert result["source"] == "offline-tts"
    assert result["engine"] == "kokoro"
    assert bridge._speech_process is fake_process
    assert emitted[-1][1]["engine"] == "kokoro"
    assert emitted[-1][1]["durationMs"] == 1200


def test_backend_bridge_queues_offline_tts_without_blocking(monkeypatch):
    import shell_web_ui.host as host

    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []
    queued_targets = []

    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(
        host,
        "offline_tts_status",
        lambda: {"success": True, "available": True, "engine": "kokoro", "label": "Kokoro offline voice"},
    )
    monkeypatch.setattr(bridge, "_start_background_task", lambda _name, target: queued_targets.append(target))
    monkeypatch.setattr(
        host,
        "speak_offline_tts",
        lambda _text: (_ for _ in ()).throw(AssertionError("offline TTS must run after _speak_text returns")),
    )

    result = bridge._speak_text(["No hang local voice"])

    assert result["success"] is True
    assert result["queued"] is True
    assert result["source"] == "offline-tts"
    assert queued_targets
    assert emitted[-1][1]["state"] == "queued"


def test_backend_bridge_cloud_error_falls_back_to_offline_tts(monkeypatch):
    import shell_web_ui.host as host

    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []
    fake_process = FakeSpeechProcess()

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(
        host,
        "offline_tts_status",
        lambda: {"success": True, "available": True, "engine": "kokoro", "label": "Kokoro offline voice"},
    )
    monkeypatch.setattr(bridge, "_start_background_task", lambda _name, target: target())
    monkeypatch.setattr(
        host,
        "speak_offline_tts",
        lambda text: {
            "success": True,
            "available": True,
            "engine": "kokoro",
            "voice": "af_heart",
            "chars": len(text),
            "durationMs": 1300,
            "amplitudeFrameMs": 70,
            "amplitudeFrames": [0.25, 0.5],
            "_process": fake_process,
        },
    )

    bridge._cloud_tts_fallback_text = "Gemini network failed"
    bridge._on_cloud_tts_error("network offline")

    assert emitted[0][1]["state"] == "fallback"
    assert emitted[0][1]["engine"] == "gemini"
    assert emitted[-1][1]["engine"] == "kokoro"
    assert emitted[-1][1]["fallbackFrom"] == "gemini"
    assert emitted[-1][1]["durationMs"] == 1300
    assert emitted[-1][1]["amplitudeFrames"] == [0.25, 0.5]
    assert bridge._speech_process is fake_process


def test_backend_bridge_falls_back_to_os_tts_when_offline_model_missing(monkeypatch):
    import shell_web_ui.host as host

    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []
    popen_calls = []
    fake_process = FakeSpeechProcess()

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(
        host,
        "offline_tts_status",
        lambda: {
            "success": True,
            "available": False,
            "engine": "fallback",
            "reason": "No packaged model.",
        },
    )
    monkeypatch.setattr(
        host,
        "speak_offline_tts",
        lambda _text: {
            "success": False,
            "available": False,
            "engine": "fallback",
            "message": "No packaged model.",
        },
    )
    monkeypatch.setattr(bridge, "_tts_command", lambda text: ["fake-local-tts", text])
    monkeypatch.setattr(host.subprocess, "Popen", lambda command, **_kwargs: popen_calls.append(command) or fake_process)

    result = bridge._speak_text(["Fallback voice test"])

    assert result["success"] is True
    assert result["source"] == "os-tts"
    assert popen_calls == [["fake-local-tts", "Fallback voice test"]]
    assert emitted[-1][0] == "speech-status"
    assert emitted[-1][1]["engine"] == "os"
