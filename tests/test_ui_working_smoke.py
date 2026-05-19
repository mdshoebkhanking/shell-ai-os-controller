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


def test_agents_page_renders_real_orchestration_state():
    app = _app()
    from PyQt6.QtWidgets import QLabel
    from shell_ui.shell_cinematic_full import AgentsPage

    page = AgentsPage()
    page._on_agents_ready({
        "orchestration_agents": [
            {
                "agent_id": "reasoning_agent",
                "name": "Reasoning Agent",
                "role": "executor",
                "autonomy_level": "assisted",
                "capabilities": [{"name": "capability.reasoning", "risk_level": "safe"}],
            },
            {
                "agent_id": "coding_agent",
                "name": "Coding Agent",
                "role": "executor",
                "autonomy_level": "manual",
                "capabilities": [{"name": "capability.coding", "risk_level": "caution"}],
            },
        ],
        "agent_tools": 40,
        "readiness": {"READY": 37, "BLOCKED_BY_SAFETY": 3},
        "safety": {"normal": 30, "guarded": 10},
        "routes": [
            {
                "goal": "what is 2 + 3 * 4",
                "selected_agent_name": "Reasoning Agent",
                "selected_agent_id": "reasoning_agent",
                "capability": "capability.reasoning",
                "requires_approval": False,
                "execution_allowed": True,
                "risk_level": "safe",
            },
            {
                "goal": "terminal echo hello",
                "selected_agent_name": "Coding Agent",
                "selected_agent_id": "coding_agent",
                "capability": "capability.coding",
                "requires_approval": True,
                "execution_allowed": False,
                "risk_level": "dangerous",
            },
        ],
    })
    app.processEvents()

    text = "\n".join(lbl.text() for lbl in page.findChildren(QLabel))
    assert "Agents" in text
    assert "2 orchestration agents" in text
    assert "40 agent tools" in text
    assert "Reasoning Agent" in text
    assert "terminal echo hello" in text
    assert "Approval" in text
    page.close()


def test_tools_page_surfaces_readiness_filters_and_safe_run_state():
    app = _app()
    from PyQt6.QtWidgets import QLabel
    from shell_ui.shell_cinematic_full import BackendToolsPage

    catalog = [
        {
            "id": "safe_math:add",
            "name": "add",
            "title": "Add",
            "kind": "tool",
            "category": "productivity",
            "module": "safe_math",
            "description": "Safe local math.",
            "params": [],
            "readiness": {"state": "READY", "ok": True, "reasons": []},
            "metadata": {"safety_level": "safe", "platform_support": ["all"]},
        },
        {
            "id": "weather:get",
            "name": "get_weather",
            "title": "Weather",
            "kind": "tool",
            "category": "browser",
            "module": "weather",
            "description": "Needs an API key.",
            "params": [],
            "readiness": {
                "state": "NEEDS_API_KEY",
                "ok": False,
                "reasons": ["missing API key: OPENWEATHER_API_KEY"],
            },
            "metadata": {
                "safety_level": "safe",
                "platform_support": ["all"],
                "api_requirements": ["OPENWEATHER_API_KEY"],
            },
        },
        {
            "id": "terminal:run",
            "name": "run_command",
            "title": "Run Command",
            "kind": "tool",
            "category": "system",
            "module": "terminal",
            "description": "Safety-gated terminal command.",
            "params": [],
            "readiness": {
                "state": "BLOCKED_BY_SAFETY",
                "ok": False,
                "reasons": ["blocked by safety flag: SHELL_ALLOW_TERMINAL_EXEC"],
            },
            "metadata": {
                "safety_level": "guarded",
                "platform_support": ["all"],
                "permissions_required": ["SHELL_ALLOW_TERMINAL_EXEC"],
            },
        },
    ]

    page = BackendToolsPage()
    page._on_catalog_ready({
        "catalog": catalog,
        "summary": {
            "total": 3,
            "tools": 3,
            "agents": 0,
            "actions": 0,
            "readiness_counts": {
                "READY": 1,
                "NEEDS_API_KEY": 1,
                "BLOCKED_BY_SAFETY": 1,
            },
        },
        "source": "local",
    })

    labels = "\n".join(lbl.text() for lbl in page.findChildren(QLabel))
    assert "Ready 1" in labels
    assert "Needs API 1" in labels
    assert "Safety 1" in labels

    page._state_filter.setCurrentIndex(page._state_filter.findData("NEEDS_API_KEY"))
    assert [item["id"] for item in page._filtered_items()] == ["weather:get"]

    page._select_item(catalog[1])
    assert page._run_btn.isEnabled() is False
    assert page._chat_btn.isEnabled() is True
    assert "missing API key" in page._readiness.text()

    page._select_item(catalog[0])
    assert page._run_btn.isEnabled() is True
    page.stop_workers()
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
    assert '"agents": 3' in src


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
