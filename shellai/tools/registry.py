from __future__ import annotations

from typing import Any

from shellai.config import ShellAIConfig

from .base import BaseTool
from .file_tool import FileTool
from .os_tool import OSTool
from .shell_tool import ShellTool


class ToolRegistry:
    def __init__(self, config: ShellAIConfig | None = None) -> None:
        self.config = config or ShellAIConfig.load()
        self._tools: dict[str, BaseTool] = {}
        self.register(ShellTool(self.config))
        self.register(FileTool())
        self.register(OSTool())

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.metadata.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        key = str(name or "").strip()
        if key not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[key]

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.metadata.to_dict() for tool in self._tools.values()]

    def __contains__(self, name: str) -> bool:
        return str(name or "").strip() in self._tools
