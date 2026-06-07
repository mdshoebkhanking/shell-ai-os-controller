import subprocess
import sys
import time


def test_voice_runtime_import_does_not_load_full_ui():
    code = (
        "import sys; "
        "import shell_voice_runtime; "
        "print('shell_ui.shell_cinematic_full' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_voice_runtime_preserves_tts_helpers(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_voice_runtime import TTSSpeaker, _system_tts_available

    speaker = TTSSpeaker()
    assert isinstance(speaker._detect_system_tts_command(), str)
    assert isinstance(_system_tts_available(), bool)
    speaker.shutdown()


def test_ui_reexports_tts_runtime_for_backward_compatibility(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import TTSSpeaker as UiTTSSpeaker
    from shell_voice_runtime import TTSSpeaker as RuntimeTTSSpeaker

    assert UiTTSSpeaker is RuntimeTTSSpeaker


def test_voice_runtime_thread_handles_repeated_requests(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from shell_voice_runtime import TTSSpeaker
    speaker = TTSSpeaker()
    calls: list[str] = []
    finished: list[bool] = []

    def fake_speak(text):
        calls.append(text)
        return True

    monkeypatch.setattr(speaker, "_do_speak", fake_speak)
    speaker.speaking_finished.connect(lambda: finished.append(True))
    speaker.start()

    for index in range(3):
        speaker.speak(f"hello {index}", force=True)

    deadline = time.time() + 2.0
    while time.time() < deadline and len(finished) < 3:
        time.sleep(0.01)

    speaker.shutdown()
    speaker.wait(1000)

    assert calls == ["hello 0", "hello 1", "hello 2"]
    assert len(finished) == 3
    assert not speaker.isRunning()
