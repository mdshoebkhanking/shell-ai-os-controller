import sys
import types

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


def test_kokoro_segments_route_hinglish_clauses(monkeypatch):
    import shell_offline_tts

    monkeypatch.setenv("SHELL_LANGUAGE", "hinglish")
    monkeypatch.delenv("SHELL_HINGLISH_TTS_ROUTING", raising=False)

    segments = shell_offline_tts._prepare_kokoro_segments("Open Chrome now. bhai kaise ho?")

    assert [segment.language for segment in segments] == ["english", "hindi"]
    assert [segment.locale for segment in segments] == ["en-us", "hi"]
    assert [segment.voice for segment in segments] == ["af_heart", "hf_alpha"]
    assert segments[0].text == "Open Chrome now."
    assert segments[1].text == "bhai kaise ho?"


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
    assert result["voices"] == ["af_heart", "hf_alpha"]
    assert result["segments"][1]["language"] == "hindi"
    assert captured_audio["sample_rate"] == 24000


def test_backend_bridge_prefers_offline_tts(monkeypatch):
    import shell_web_ui.host as host

    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []
    fake_process = FakeSpeechProcess()

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(
        host,
        "speak_offline_tts",
        lambda text: {
            "success": True,
            "available": True,
            "engine": "kokoro",
            "voice": "af_heart",
            "chars": len(text),
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
