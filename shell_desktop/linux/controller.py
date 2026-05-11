from __future__ import annotations

from shell_desktop.base_controller import UnsupportedDesktopController


class LinuxDesktopController(UnsupportedDesktopController):
    def __init__(self):
        super().__init__("linux", "Linux desktop automation adapter is not implemented yet")

