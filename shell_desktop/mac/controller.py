from __future__ import annotations

from shell_desktop.base_controller import UnsupportedDesktopController


class MacDesktopController(UnsupportedDesktopController):
    def __init__(self):
        super().__init__("mac", "Mac desktop automation adapter is not implemented yet")

