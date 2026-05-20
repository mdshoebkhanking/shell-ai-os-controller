from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shellai.observability import RequestTrace, get_logger


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    description: str
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": list(self.capabilities),
        }


@dataclass
class ToolRequest:
    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)
    working_dir: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    trace: RequestTrace | None = None
    risk_level_hint: str = ""
    dry_run: bool = False
    approved: bool = False
    timeout_s: float = 30.0


@dataclass
class ToolResult:
    tool_name: str
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status == "ok" and (self.exit_code in (0, None))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "metadata": dict(self.metadata),
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "ok": self.ok,
        }


class BaseTool(ABC):
    metadata: ToolMetadata

    def __init__(self) -> None:
        self.logger = get_logger(f"shellai.tools.{self.metadata.name}")

    def _record(self, request: ToolRequest, status: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        payload = {
            "tool": self.metadata.name,
            **dict(metadata or {}),
        }
        self.logger.info("tool.%s %s", self.metadata.name, status)
        if request.trace is not None:
            request.trace.add_step(f"Tool:{self.metadata.name}", status, message, payload)

    @staticmethod
    def resolve_path(path: str, working_dir: str | None = None) -> Path:
        raw = Path(str(path)).expanduser()
        if raw.is_absolute():
            return raw
        base = Path(working_dir).expanduser() if working_dir else Path.cwd()
        return (base / raw).resolve()

    @abstractmethod
    def run(self, request: ToolRequest) -> ToolResult:
        raise NotImplementedError
