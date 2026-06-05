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
