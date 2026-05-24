import importlib
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_neural_dashboard_accepts_shell_chat_contract():
    app = _app()
    from shell_ui.neural_dashboard import NeuralDashboardPage

    page = NeuralDashboardPage()
    sent = []
    page.message_sent.connect(sent.append)
    bubble = page.add_message("shell", "stream online")
    page._input.setPlainText("scan project")
    page._send()
    app.processEvents()

    assert sent == ["scan project"]
    assert bubble._stream_label.text() == "stream online"
    assert page.is_scroll_near_bottom() is True
    page.close()


def test_shell_voice_coordinator_records_first_partial_latency():
    import shell_neural_voice

    snap = shell_neural_voice.VOICE_COORDINATOR.start("test-session")
    assert snap["active"] is True
    snap = shell_neural_voice.VOICE_COORDINATOR.partial("hello")
    assert snap["partial_transcript"] == "hello"
    assert snap["first_partial_ms"] is not None


def test_shell_memory_store_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_CORE_MEMORY_PATH", str(tmp_path / "memory.json"))
    import shell_core_memory

    shell_core_memory = importlib.reload(shell_core_memory)
    save = shell_core_memory.shell_save_core_memory_tool.__wrapped__
    recall = shell_core_memory.shell_recall_core_memory_tool.__wrapped__

    import asyncio

    result = asyncio.run(save("User prefers emerald UI", tags="ui,preference"))
    assert result["ok"] is True
    found = asyncio.run(recall("emerald", limit=3))
    assert found["count"] == 1
    assert found["memories"][0]["fact"] == "User prefers emerald UI"


def test_shell_project_scan_and_coding_context(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text("def run_voice_stream():\n    return 'ok'\n", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")

    import asyncio
    import shell_coding_assist

    scan = asyncio.run(shell_coding_assist.shell_scan_project_folder_tool.__wrapped__(str(root)))
    assert scan["ok"] is True
    assert scan["files_scanned"] == 1

    assist = asyncio.run(
        shell_coding_assist.shell_automated_coding_assist_tool.__wrapped__(
            str(root), "voice stream", max_files=20
        )
    )
    assert assist["ok"] is True
    assert assist["matches"]
    assert assist["matches"][0]["relative_path"] == "app.py"


def test_tool_catalog_discovers_shell_neural_modules():
    from shell_tool_catalog import discover_tool_catalog

    ids = {item["id"] for item in discover_tool_catalog()}
    assert "shell_neural_voice:shell_streaming_voice_status_tool" in ids
    assert "shell_coding_assist:shell_scan_project_folder_tool" in ids
    assert "shell_focus_mode:shell_deep_focus_mode_tool" in ids
