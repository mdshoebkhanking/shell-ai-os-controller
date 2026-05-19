"""Computer-control readiness surfaces for Shell AI OS."""

from .agent_loop import DesktopAgentLoop
from .readiness import build_computer_control_snapshot

__all__ = ["DesktopAgentLoop", "build_computer_control_snapshot"]
