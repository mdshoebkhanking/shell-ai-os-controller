import pytest
import os
import json
from pathlib import Path


def test_capability_catalog_exposes_readiness_metadata():
    from shell_tool_catalog import discover_capabilities

    data = discover_capabilities()
    assert data["status"] == "success"
    assert data["summary"]["total"] >= 1
    assert "readiness_counts" in data["summary"]

    sample = next(item for item in data["catalog"] if item.get("id") == "windows-mcp:Click")
    assert sample["metadata"]["tool_id"] == "windows-mcp:Click"
    assert "platform_support" in sample["metadata"]
    assert "readiness" in sample
    if os.name != "nt":
        assert sample["readiness"]["state"] == "WINDOWS_ONLY"


def test_natural_router_uses_cross_platform_desktop_route():
    from shell_nl_router import route_natural_command

    route = route_natural_command("click 120 340")

    assert route["tool"] == "shell_desktop_tools:desktop_click_tool"
    assert route["args"] == {"x": 120, "y": 340, "button": "left"}
    assert "readiness" in route
    assert route["readiness"]["state"] == "READY"


def test_gateway_blocks_unready_dangerous_tool(monkeypatch):
    from shell_tool_gateway import execute_tool_sync

    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    result = execute_tool_sync("shell_evolution:create_capability_tool", {"name": "x", "description": "test"})

    assert result["status"] == "error"
    assert result["state"] == "BLOCKED_BY_SAFETY"
    assert "SHELL_ALLOW_CODE_WRITE" in " ".join(result["reasons"])


def test_startup_diagnostics_are_structured():
    from core.health.startup import run_startup_diagnostics

    data = run_startup_diagnostics()

    assert data["status"] == "success"
    assert "platform" in data
    assert "dependencies" in data
    assert "safety" in data
    assert "summary" in data


def test_desktop_controller_returns_structured_result():
    from shell_desktop import get_desktop_controller

    controller = get_desktop_controller()
    result = controller.screenshot().to_dict()

    assert result["status"] in {"success", "error"}
    assert result["action"] == "Screenshot"
    assert "data" in result


def test_planner_marks_unready_route():
    from core.planner import Planner

    plan = Planner().plan("click 120 340").to_dict()

    assert plan["steps"]
    assert plan["steps"][0]["tool_id"] == "shell_desktop_tools:desktop_click_tool"
    assert plan["steps"][0]["readiness"]["state"] == "READY"


@pytest.mark.skip(reason="shell_ui pages removed during PyQt6 cleanup")
def test_ui_modular_import_seams_exist(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.chat import ChatPage
    from shell_ui.settings import SettingsPage
    from shell_ui.voice import VoicePage

    assert ChatPage is not None
    assert SettingsPage is not None
    assert VoicePage is not None


def test_production_guard_blocks_dangerous_flags():
    from shell_production_guard import audit_production_environment

    report = audit_production_environment(
        {
            "SHELL_PRODUCTION_MODE": "1",
            "SHELL_ALLOW_AGENT_PATCH": "1",
        },
        root=Path.cwd(),
        check_assets=False,
    )

    assert report["status"] == "fail"
    assert any("SHELL_ALLOW_AGENT_PATCH" in item for item in report["blockers"])


def test_production_guard_redacts_secret_values():
    from shell_production_guard import audit_production_environment

    report = audit_production_environment(
        {
            "SHELL_PRODUCTION_MODE": "1",
            "GOOGLE_API_KEY": "secret-test-value",
            "SHELL_HUB_TOKEN": "another-secret-value",
        },
        root=Path.cwd(),
        check_assets=False,
    )

    dumped = json.dumps(report)
    assert "secret-test-value" not in dumped
    assert "another-secret-value" not in dumped


def test_env_example_is_safe_for_public_release():
    from shell_production_guard import audit_production_environment, read_env_file

    root = Path.cwd()
    env = read_env_file(root / ".env.example")
    report = audit_production_environment(env, root=root, check_assets=True)

    assert report["status"] == "pass", report["blockers"]
