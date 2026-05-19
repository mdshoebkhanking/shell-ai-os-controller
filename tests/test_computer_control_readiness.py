from __future__ import annotations

import json


def test_computer_control_snapshot_is_redacted_and_policy_gated(monkeypatch):
    from core.computer_control import build_computer_control_snapshot

    monkeypatch.setenv("SHELL_ALLOW_TERMINAL_EXEC", "1")
    monkeypatch.setenv("SHELL_HUB_TOKEN", "secret-value-that-must-not-leak")

    snapshot = build_computer_control_snapshot(include_catalog=False)
    payload = json.dumps(snapshot, sort_keys=True)
    groups = {row["name"]: row for row in snapshot["groups"]}

    assert snapshot["profile"] == "computer_control_os"
    assert snapshot["status"] in {"ready", "attention", "blocked"}
    assert snapshot["platform"] in {"macos", "windows", "linux", "unknown"}
    assert snapshot["control_policy"]["default_mode"] == "observe_then_confirm"
    assert snapshot["control_policy"]["silent_fallback_allowed"] is False
    assert {"app_control", "input_control", "screen_understanding", "clipboard", "safety"}.issubset(groups)
    assert groups["safety"]["metadata"]["flags"]
    assert any(row["key"] == "SHELL_ALLOW_TERMINAL_EXEC" and row["enabled"] is True for row in groups["safety"]["metadata"]["flags"])
    assert "secret-value-that-must-not-leak" not in payload


def test_computer_control_tool_is_cataloged_as_system_capability():
    from shell_tool_catalog import discover_tool_catalog

    rows = {
        row["id"]: row
        for row in discover_tool_catalog()
        if row["id"].startswith("shell_computer_control:")
    }

    tool = rows["shell_computer_control:computer_control_status_tool"]
    assert tool["kind"] == "tool"
    assert tool["category"] == "system"
    assert tool["risk"] == "normal"


def test_natural_computer_control_route():
    from shell_nl_router import route_natural_command

    route = route_natural_command("show desktop control readiness")

    assert route["tool"] == "shell_computer_control:computer_control_status_tool"
    assert route["args"] == {"include_catalog": True}


def test_natural_ai_os_status_still_routes_to_platform_supervisor():
    from shell_nl_router import route_natural_command

    route = route_natural_command("show ai os status")

    assert route["tool"] == "shell_platform_supervisor:shell_platform_status_tool"
