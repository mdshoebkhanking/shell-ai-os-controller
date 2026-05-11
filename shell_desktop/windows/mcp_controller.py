from __future__ import annotations

from typing import Any

from shell_desktop.base_controller import ControllerResult, DesktopController


class WindowsMCPDesktopController(DesktopController):
    platform = "windows"

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ControllerResult:
        from shell_windows_mcp import call_windows_mcp_tool_sync

        result = call_windows_mcp_tool_sync(name, dict(arguments or {}))
        status = "success" if result.get("status") == "success" else "error"
        return ControllerResult(
            status=status,
            action=str(name),
            message=str(result.get("message") or ""),
            data=result,
        )

