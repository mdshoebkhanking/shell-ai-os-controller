from __future__ import annotations

import os
import subprocess
import time
from typing import Any

from shellai.config import ShellAIConfig
from shellai.policy import evaluate_command, record_audit
from shellai.safety import RiskLevel, ShellRiskPolicy

from .base import BaseTool, ToolMetadata, ToolRequest, ToolResult


class ShellTool(BaseTool):
    metadata = ToolMetadata(
        name="shell",
        description="Run shell commands through ShellAI risk policy.",
        capabilities=["command", "dry_run", "risk_policy"],
    )

    def __init__(self, config: ShellAIConfig | None = None) -> None:
        self.config = config or ShellAIConfig.load()
        self.policy = ShellRiskPolicy(self.config.risk_policy)
        super().__init__()

    @staticmethod
    def _command_from_args(args: dict[str, Any]) -> str | list[str]:
        command = args.get("command")
        if command is None:
            command = args.get("argv")
        if isinstance(command, list):
            return [str(part) for part in command]
        return str(command or "").strip()

    @staticmethod
    def _preview(command: str | list[str]) -> str:
        if isinstance(command, list):
            text = " ".join(command)
        else:
            text = command
        return text[:240]

    def run(self, request: ToolRequest) -> ToolResult:
        started = time.time()
        command = self._command_from_args(request.args)
        command_for_policy = self._preview(command)
        risk = evaluate_command(command_for_policy, config=self.config, trace=request.trace)
        try:
            record_audit(self.config, risk, source="ShellTool", trace=request.trace)
        except Exception as exc:
            if request.trace is not None:
                request.trace.add_step("AuditLog", "error", "audit write failed", {"error": str(exc)})
        metadata = {
            "command": command_for_policy,
            "risk": risk.to_dict(),
            "dry_run": request.dry_run,
            "approved": request.approved,
        }

        if request.dry_run:
            self._record(request, "dry_run", "shell command dry run", metadata)
            return ToolResult(
                tool_name=self.metadata.name,
                status="dry_run",
                stdout="",
                metadata=metadata,
                started_at=started,
                duration_ms=round((time.time() - started) * 1000.0, 3),
            )

        if risk.level is RiskLevel.BLOCK:
            self._record(request, "blocked", risk.reason, metadata)
            return ToolResult(
                tool_name=self.metadata.name,
                status="blocked",
                stderr=risk.reason,
                metadata=metadata,
                started_at=started,
                duration_ms=round((time.time() - started) * 1000.0, 3),
            )

        if risk.level is RiskLevel.ASK and not request.approved:
            self._record(request, "needs_confirmation", risk.reason, metadata)
            return ToolResult(
                tool_name=self.metadata.name,
                status="needs_confirmation",
                stderr=risk.reason,
                metadata=metadata,
                started_at=started,
                duration_ms=round((time.time() - started) * 1000.0, 3),
            )

        if not command:
            self._record(request, "error", "empty command", metadata)
            return ToolResult(
                tool_name=self.metadata.name,
                status="error",
                stderr="Command cannot be empty.",
                metadata=metadata,
                started_at=started,
                duration_ms=round((time.time() - started) * 1000.0, 3),
            )

        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in request.env.items()})
        try:
            completed = subprocess.run(
                command,
                cwd=request.working_dir or None,
                env=env,
                text=True,
                capture_output=True,
                timeout=max(0.1, float(request.timeout_s)),
                shell=not isinstance(command, list),
                check=False,
            )
            status = "ok" if completed.returncode == 0 else "error"
            metadata["exit_code"] = completed.returncode
            self._record(request, status, "shell command completed", metadata)
            return ToolResult(
                tool_name=self.metadata.name,
                status=status,
                stdout=completed.stdout,
                stderr=completed.stderr,
                exit_code=completed.returncode,
                metadata=metadata,
                started_at=started,
                duration_ms=round((time.time() - started) * 1000.0, 3),
            )
        except subprocess.TimeoutExpired as exc:
            metadata["timeout_s"] = request.timeout_s
            self._record(request, "timeout", "shell command timed out", metadata)
            return ToolResult(
                tool_name=self.metadata.name,
                status="timeout",
                stdout=exc.stdout or "",
                stderr=exc.stderr or "Command timed out.",
                metadata=metadata,
                started_at=started,
                duration_ms=round((time.time() - started) * 1000.0, 3),
            )
