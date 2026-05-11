from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ControllerResult:
    status: str
    action: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "action": self.action,
            "message": self.message,
            "data": dict(self.data),
        }


class DesktopController:
    platform: str = "unknown"

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ControllerResult:
        return ControllerResult("error", str(name), "desktop controller does not implement tool calls")

    def screenshot(self) -> ControllerResult:
        return self.call_tool("Screenshot", {})

    def click(self, x: int, y: int, button: str = "left") -> ControllerResult:
        return self.call_tool("Click", {"x": int(x), "y": int(y), "button": button})

    def type_text(self, text: str, clear: bool = False) -> ControllerResult:
        return self.call_tool("Type", {"text": text, "clear": bool(clear)})


class UnsupportedDesktopController(DesktopController):
    def __init__(self, platform: str, reason: str = ""):
        self.platform = platform
        self.reason = reason

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ControllerResult:
        return ControllerResult(
            "error",
            str(name),
            f"desktop automation is not available for platform {self.platform}",
            {"supported": False, "reason": self.reason, "arguments": dict(arguments or {})},
        )

