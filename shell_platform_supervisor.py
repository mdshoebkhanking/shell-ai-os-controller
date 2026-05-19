"""User-visible Shell AI OS platform status tools."""

from __future__ import annotations

import json

from shell_safe_executor import god_tier_tool as function_tool


def shell_platform_status(include_catalog: bool = True, deep_packaging: bool = False) -> str:
    """Return a redacted AI OS readiness snapshot."""
    from core.platform_supervisor import build_platform_snapshot

    snapshot = build_platform_snapshot(
        include_catalog=bool(include_catalog),
        deep_packaging=bool(deep_packaging),
    )
    return json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)


@function_tool
def shell_platform_status_tool(include_catalog: bool = True, deep_packaging: bool = False) -> str:
    """Show Shell AI OS realtime, voice, agent, memory, packaging, and hybrid readiness."""
    return shell_platform_status(
        include_catalog=include_catalog,
        deep_packaging=deep_packaging,
    )


__all__ = ["shell_platform_status", "shell_platform_status_tool"]
