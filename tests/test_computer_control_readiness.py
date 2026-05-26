from __future__ import annotations

import json


def test_computer_control_snapshot_is_redacted_and_policy_gated(monkeypatch):
    from core.computer_control import build_computer_control_snapshot

    monkeypatch.setenv("SHELL_ALLOW_AGENT_PATCH", "1")
    monkeypatch.setenv("SHELL_HUB_TOKEN", "secret-value-that-must-not-leak")

    snapshot = build_computer_control_snapshot(include_catalog=False)
    payload = json.dumps(snapshot, sort_keys=True)
    groups = {row["name"]: row for row in snapshot["groups"]}

    assert snapshot["profile"] == "computer_control_os"
    assert snapshot["status"] in {"ready", "attention", "blocked"}
    assert snapshot["platform"] in {"macos", "windows", "linux", "unknown"}
    assert snapshot["control_policy"]["default_mode"] == "observe_then_confirm"
    assert snapshot["control_policy"]["silent_fallback_allowed"] is False
    assert {"app_control", "input_control", "screen_understanding", "clipboard", "desktop_agent_loop", "safety"}.issubset(groups)
    assert groups["desktop_agent_loop"]["status"] == "ready"
    assert groups["safety"]["metadata"]["flags"]
    assert any(row["key"] == "SHELL_ALLOW_AGENT_PATCH" and row["enabled"] is True for row in groups["safety"]["metadata"]["flags"])
    assert "secret-value-that-must-not-leak" not in payload


def test_desktop_agent_loop_plans_click_from_observed_bounds(tmp_path):
    from core.computer_control import DesktopAgentLoop

    loop = DesktopAgentLoop(tmp_path / "automation.jsonl")
    plan = loop.plan(
        "click Start Voice",
        screenshot_id="screen-1",
        ocr_text="Start Voice",
        active_window="Shell",
        elements=[{"label": "Start Voice", "type": "button", "bounds": [10, 20, 100, 40]}],
    )
    data = plan.to_dict()
    step = data["steps"][0]

    assert data["status"] == "ready_for_confirmation"
    assert data["requires_confirmation"] is True
    assert data["one_step_at_a_time"] is True
    assert step["tool_id"] == "shell_desktop_tools:desktop_click_tool"
    assert step["args"] == {"x": 60, "y": 40, "button": "left"}
    assert step["verification"]["method"] == "fresh_screenshot_after_step"
    assert (tmp_path / "automation.jsonl").exists()


def test_desktop_agent_execute_step_requires_approval_and_dry_runs(tmp_path):
    from core.computer_control import DesktopAgentLoop

    loop = DesktopAgentLoop(tmp_path / "automation.jsonl")
    plan = loop.plan("open calculator")
    blocked = loop.execute_step(plan, approved=False)
    dry_run = loop.execute_step(plan, approved=True, dry_run=True)

    assert blocked["status"] == "blocked"
    assert "approval" in blocked["reason"]
    assert dry_run["status"] == "dry_run"
    assert dry_run["would_execute"] == {
        "tool_id": "shell_window_CTRL:open_app",
        "args": {"app_title": "calculator"},
    }


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
    assert rows["shell_computer_control:desktop_agent_plan_tool"]["category"] == "system"
    assert rows["shell_computer_control:desktop_agent_execute_step_tool"]["category"] == "system"


def test_natural_computer_control_route():
    from shell_nl_router import route_natural_command

    route = route_natural_command("show desktop control readiness")

    assert route["tool"] == "shell_computer_control:computer_control_status_tool"
    assert route["args"] == {"include_catalog": True}


def test_natural_desktop_agent_plan_route():
    from shell_nl_router import route_natural_command

    route = route_natural_command("desktop agent plan click Start Voice")

    assert route["tool"] == "shell_computer_control:desktop_agent_plan_tool"
    assert route["args"] == {"goal": "click Start Voice"}


def test_natural_ai_os_status_still_routes_to_platform_supervisor():
    from shell_nl_router import route_natural_command

    route = route_natural_command("show ai os status")

    assert route["tool"] == "shell_platform_supervisor:shell_platform_status_tool"
