"""User-visible computer-control readiness tools."""

from __future__ import annotations

import json

from shell_safe_executor import god_tier_tool as function_tool


def desktop_agent_plan(
    goal: str,
    screenshot_id: str = "",
    ocr_text: str = "",
    active_window: str = "",
    elements_json: str = "",
) -> str:
    """Plan a desktop-control action through the safe Desktop Agent loop."""
    from core.computer_control import DesktopAgentLoop

    plan = DesktopAgentLoop().plan(
        goal,
        screenshot_id=screenshot_id,
        ocr_text=ocr_text,
        active_window=active_window,
        elements=elements_json,
    )
    return json.dumps(plan.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)


def desktop_agent_execute_step(
    plan_json: str,
    step_id: str = "",
    approved: bool = False,
    dry_run: bool = True,
    verify_after: bool = False,
) -> str:
    """Execute one approved Desktop Agent step, dry-run by default."""
    from core.computer_control import DesktopAgentLoop

    result = DesktopAgentLoop().execute_step(
        plan_json,
        step_id=step_id,
        approved=approved,
        dry_run=dry_run,
        verify_after=verify_after,
    )
    return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)


def computer_control_status(include_catalog: bool = True) -> str:
    """Return a redacted snapshot of Shell's desktop-control readiness."""
    from core.computer_control import build_computer_control_snapshot

    snapshot = build_computer_control_snapshot(include_catalog=bool(include_catalog))
    return json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)


@function_tool(category="system")
def computer_control_status_tool(include_catalog: bool = True) -> str:
    """Show Shell computer-control readiness, OS support, permissions, and safety gates."""
    return computer_control_status(include_catalog=include_catalog)


@function_tool(category="system")
def desktop_agent_plan_tool(
    goal: str,
    screenshot_id: str = "",
    ocr_text: str = "",
    active_window: str = "",
    elements_json: str = "",
) -> str:
    """Plan a one-step-at-a-time desktop action with confirmation and verification gates."""
    return desktop_agent_plan(
        goal,
        screenshot_id=screenshot_id,
        ocr_text=ocr_text,
        active_window=active_window,
        elements_json=elements_json,
    )


@function_tool(category="system")
def desktop_agent_execute_step_tool(
    plan_json: str,
    step_id: str = "",
    approved: bool = False,
    dry_run: bool = True,
    verify_after: bool = False,
) -> str:
    """Dry-run or execute one approved Desktop Agent step; never runs without approval."""
    return desktop_agent_execute_step(
        plan_json,
        step_id=step_id,
        approved=approved,
        dry_run=dry_run,
        verify_after=verify_after,
    )


__all__ = [
    "computer_control_status",
    "computer_control_status_tool",
    "desktop_agent_execute_step",
    "desktop_agent_execute_step_tool",
    "desktop_agent_plan",
    "desktop_agent_plan_tool",
]
