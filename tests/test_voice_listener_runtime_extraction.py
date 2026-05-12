import subprocess
import sys
import time


def test_voice_listener_runtime_import_does_not_load_full_ui_or_audio_libs():
    code = (
        "import sys; "
        "import shell_voice_listener_runtime; "
        "print('shell_ui.shell_cinematic_full' in sys.modules); "
        "print('sounddevice' in sys.modules); "
        "print('speech_recognition' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    assert result.stdout.strip().splitlines() == ["False", "False", "False"]


def test_ui_reexports_voice_listener_runtime_for_backward_compatibility(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import VoiceListenerThread as UiVoiceListenerThread
    from shell_voice_listener_runtime import VoiceListenerThread as RuntimeVoiceListenerThread

    assert UiVoiceListenerThread is RuntimeVoiceListenerThread


def test_voice_listener_reports_dependency_failure_and_exits(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtCore import QCoreApplication
    from shell_voice_listener_runtime import VoiceListenerThread

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    listener = VoiceListenerThread()
    errors: list[str] = []
    listener.error_occurred.connect(errors.append)
    monkeypatch.setattr(
        listener,
        "_load_audio_modules",
        lambda: (None, None, None, None, "sounddevice not installed"),
    )

    listener.start()
    deadline = time.time() + 2.0
    while time.time() < deadline and not errors:
        app.processEvents()
        time.sleep(0.01)
    listener.wait(1000)
    app.processEvents()

    assert errors == ["sounddevice not installed"]
    assert not listener.isRunning()


def test_voice_listener_thread_stops_cleanly_with_silent_audio(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    import numpy as np
    from PyQt6.QtCore import QCoreApplication
    from shell_voice_listener_runtime import VoiceListenerThread

    class FakeSoundDevice:
        @staticmethod
        def rec(frames, samplerate, channels, dtype, blocking):
            return np.zeros((frames, channels), dtype=dtype)

    class FakeSpeechRecognition:
        class Recognizer:
            pass

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    listener = VoiceListenerThread()
    stopped: list[bool] = []
    amplitudes: list[float] = []
    listener.listening_stopped.connect(lambda: stopped.append(True))
    listener.amplitude_changed.connect(amplitudes.append)
    monkeypatch.setattr(
        listener,
        "_load_audio_modules",
        lambda: (
            FakeSoundDevice,
            FakeSpeechRecognition,
            np,
            (__import__("io"), __import__("wave")),
            "",
        ),
    )

    listener.start()
    time.sleep(0.25)
    listener.stop_listening()
    listener.wait(1500)
    app.processEvents()

    assert stopped == [True]
    assert amplitudes and amplitudes[-1] == 0.0
    assert not listener.isRunning()
