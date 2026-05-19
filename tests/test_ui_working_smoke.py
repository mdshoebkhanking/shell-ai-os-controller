import ast
import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_topbar_theme_button_emits_real_theme_request():
    app = _app()
    from shell_ui.shell_cinematic_full import ThemeEngine, TopBar

    topbar = TopBar()
    requested = []
    topbar.theme_requested.connect(requested.append)

    topbar.theme_btn.click()
    app.processEvents()

    assert requested
    assert requested[-1] in ThemeEngine.get().theme_names
    topbar.close()


def test_settings_language_picker_writes_backend_store(monkeypatch, tmp_path):
    app = _app()
    import shell_settings_manager
    import shell_ui.shell_cinematic_full as ui
    from shell_ui.shell_cinematic_full import SettingsPage

    settings_path = tmp_path / ".shell_settings.json"
    monkeypatch.setattr(shell_settings_manager, "_SETTINGS_PATH", settings_path)
    monkeypatch.setattr(ui, "_hub_base_url_candidates", lambda *args, **kwargs: [])
    monkeypatch.delenv("SHELL_LANGUAGE", raising=False)

    page = SettingsPage()
    page._on_language_changed(1)
    app.processEvents()

    assert os.environ["SHELL_LANGUAGE"] == "english"
    saved = settings_path.read_text(encoding="utf-8")
    assert '"language": "english"' in saved
    assert '"shell_language": "english"' in saved
    assert "Saved" in page._lang_status.text()
    page.close()


def test_system_page_shows_real_unavailable_state_when_psutil_missing(monkeypatch):
    app = _app()
    import shell_ui.shell_cinematic_full as ui
    from PyQt6.QtWidgets import QLabel
    from shell_ui.shell_cinematic_full import SystemPage

    monkeypatch.setattr(ui, "psutil", None)
    page = SystemPage()
    page._refresh_top_processes()
    app.processEvents()

    labels = [lbl.text() for lbl in page.findChildren(QLabel)]
    assert "psutil unavailable" in labels
    page._tick_timer.stop()
    page._proc_timer.stop()
    page.close()


def test_system_page_renders_ai_os_platform_status():
    app = _app()
    from PyQt6.QtWidgets import QLabel
    from shell_ui.shell_cinematic_full import SystemPage

    page = SystemPage()
    page._on_platform_status_ready({
        "score": 88,
        "status": "ready",
        "process": {"snapshot_ms": 4.5},
        "domains": [
            {"name": "realtime", "status": "ready", "score": 94, "risks": []},
            {
                "name": "voice",
                "status": "ready",
                "score": 96,
                "metrics": {"gemini_voice": "Aoede"},
                "risks": [],
            },
            {"name": "agents", "status": "ready", "score": 93, "risks": []},
            {
                "name": "capabilities",
                "status": "ready",
                "score": 90,
                "metrics": {
                    "total": 456,
                    "by_kind": {"tool": 399, "agent": 40},
                    "readiness": {"ready": 214},
                },
                "risks": [],
            },
        ],
    })
    app.processEvents()

    text = "\n".join(lbl.text() for lbl in page.findChildren(QLabel))
    assert "AI OS Status" in text
    assert "READY · 88" in text
    assert "456 capabilities" in text
    assert "Voice Aoede" in text
    assert "Capabilities" in text
    page._tick_timer.stop()
    page._proc_timer.stop()
    page.close()


def test_system_telemetry_does_not_fabricate_random_stats():
    src_path = Path(__file__).resolve().parents[1] / "shell_ui" / "shell_cinematic_full.py"
    src = src_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    poll = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_poll_system")
    poll_src = ast.get_source_segment(src, poll) or ""

    assert "random.uniform(15, 45)" not in poll_src
    assert "random.uniform(40, 70)" not in poll_src
    assert "psutil unavailable" in poll_src


def test_voice_orb_stays_embedded_by_default():
    src_path = Path(__file__).resolve().parents[1] / "shell_ui" / "shell_cinematic_full.py"
    src = src_path.read_text(encoding="utf-8")

    assert 'SHELL_ENABLE_WEBGL_ORB' in src
    assert 'class _VoiceOrbBridge' in src
    assert 'self.orb = _VoiceOrbBridge(self)' in src


def test_shell_start_page_env_hook_exists_for_ui_qa():
    src_path = Path(__file__).resolve().parents[1] / "shell_ui" / "shell_cinematic_full.py"
    src = src_path.read_text(encoding="utf-8")

    assert "SHELL_START_PAGE" in src
    assert '"voice": 1' in src


def test_chat_stream_scroll_is_coalesced_and_user_safe():
    app = _app()
    from shell_ui.shell_cinematic_full import ChatPage

    page = ChatPage()
    page.resize(900, 700)
    page.show()
    app.processEvents()

    assert page.is_scroll_near_bottom() is True

    page.request_stream_scroll(was_near_bottom=False)
    assert page._stream_scroll_timer.isActive() is False

    page.request_stream_scroll(was_near_bottom=True)
    assert page._stream_scroll_timer.isActive() is True

    page._stream_scroll_timer.stop()
    page.close()
