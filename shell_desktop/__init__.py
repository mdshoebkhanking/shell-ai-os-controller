"""Cross-platform desktop controller abstraction.

Named `shell_desktop` to avoid colliding with the existing `Desktop/` asset
directory on case-insensitive macOS filesystems.
"""

from __future__ import annotations

from core.health.checks import current_platform
from shell_desktop.base_controller import ControllerResult, DesktopController, UnsupportedDesktopController


def get_desktop_controller() -> DesktopController:
    platform_name = current_platform()
    if platform_name == "windows":
        try:
            from shell_desktop.windows.mcp_controller import WindowsMCPDesktopController

            return WindowsMCPDesktopController()
        except Exception as exc:
            return UnsupportedDesktopController(platform_name, str(exc))
    if platform_name == "mac":
        try:
            from shell_desktop.mac.controller import MacDesktopController

            return MacDesktopController()
        except Exception as exc:
            return UnsupportedDesktopController(platform_name, str(exc))
    if platform_name == "linux":
        try:
            from shell_desktop.linux.controller import LinuxDesktopController

            return LinuxDesktopController()
        except Exception as exc:
            return UnsupportedDesktopController(platform_name, str(exc))
    return UnsupportedDesktopController(platform_name, "unknown platform")


__all__ = [
    "ControllerResult",
    "DesktopController",
    "UnsupportedDesktopController",
    "get_desktop_controller",
]

