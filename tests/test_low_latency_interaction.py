def test_shell_v2_prefers_streaming_and_short_interactive_timeout(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("SHELL_V2_STREAM", raising=False)

    from shell_ui.shell_cinematic_full import ShellV2Worker

    assert ShellV2Worker.stream_enabled() is True
    assert ShellV2Worker.TIMEOUT_S <= 15


def test_fast_local_reply_is_conservative(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import ShellHoloUI

    assert ShellHoloUI._fast_local_reply_candidate("hello")
    assert ShellHoloUI._fast_local_reply_candidate("what time is it")
    status_reply = ShellHoloUI._fast_local_reply_candidate("kya hua bolo")
    assert status_reply
    assert "Shell chal raha hai" in status_reply
    assert ShellHoloUI._fast_local_reply_candidate("/tool shell_calculator:calculate_tool {}") is None
    assert ShellHoloUI._fast_local_reply_candidate("write a python app for me") is None


def test_latency_recorder_summarizes_hot_paths():
    from core.performance import InteractionLatencyRecorder

    recorder = InteractionLatencyRecorder(maxlen=3)
    recorder.record("chat.first_chunk", 120)
    recorder.record("chat.first_chunk", 180)
    recorder.record("tts.playback_started", 40, engine="system")

    summary = recorder.summary()

    assert summary["count"] == 3
    assert summary["by_name"]["chat.first_chunk"]["avg_ms"] == 150
    assert recorder.recent(1)[0]["metadata"]["engine"] == "system"
