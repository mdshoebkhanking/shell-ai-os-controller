"""User-visible computer-control readiness tools."""

from __future__ import annotations

import json

from shell_safe_executor import god_tier_tool as function_tool


def computer_control_status(include_catalog: bool = True) -> str:
    """Return a redacted snapshot of Shell's desktop-control readiness."""
    from core.computer_control import build_computer_control_snapshot

    snapshot = build_computer_control_snapshot(include_catalog=bool(include_catalog))
    return json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)


@function_tool(category="system")
def computer_control_status_tool(include_catalog: bool = True) -> str:
    """Show Shell computer-control readiness, OS support, permissions, and safety gates."""
    return computer_control_status(include_catalog=include_catalog)


__all__ = ["computer_control_status", "computer_control_status_tool"]
