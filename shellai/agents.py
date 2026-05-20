from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import ShellAIConfig
from .observability import RequestTrace, TRACE_STORE, get_logger
from .policy import evaluate_command, record_audit
from .protocol import AgentRole
from .safety import CommandRisk, ShellRiskPolicy


@dataclass(frozen=True)
class AgentResult:
    agent: str
    status: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "status": self.status,
            "message": self.message,
            "data": dict(self.data),
        }


class BaseAgent:
    def __init__(self, role: AgentRole | str, trace: RequestTrace) -> None:
        self.role = AgentRole.normalize(role)
        self.name = self.role
        self.trace = trace
        self.logger = get_logger(f"shellai.{self.name}")

    def record(self, status: str, message: str = "", metadata: dict[str, Any] | None = None) -> None:
        self.trace.add_step(self.name, status, message, metadata)


class SafetyAgent(BaseAgent):
    """Owns policy decisions for potentially risky actions."""

    def __init__(
        self,
        trace: RequestTrace,
        policy: ShellRiskPolicy,
        config: ShellAIConfig | None = None,
    ) -> None:
        super().__init__(AgentRole.SAFETY, trace)
        self.config = config or ShellAIConfig.load()
        self.policy = policy

    def assess_shell_command(self, command: str) -> CommandRisk:
        risk = evaluate_command(command, config=self.config, trace=self.trace)
        try:
            record_audit(self.config, risk, trace=self.trace)
        except Exception as exc:
            self.record("audit_error", "failed to record audit entry", {"error": str(exc)})
        self.record("classified", risk.reason, risk.to_dict())
        return risk


class ShellAgent(BaseAgent):
    """Owns shell-action proposals and later command execution."""

    SHELL_PREFIXES = ("shell:", "$", "!")

    def __init__(self, trace: RequestTrace) -> None:
        super().__init__(AgentRole.SHELL, trace)

    def propose_shell_command(self, user_input: str) -> AgentResult:
        text = str(user_input or "").strip()
        for prefix in self.SHELL_PREFIXES:
            if text.startswith(prefix):
                command = text[len(prefix):].strip()
                if command:
                    self.record("proposed", "user supplied an explicit shell command", {"command": command})
                    return AgentResult(
                        agent=self.name,
                        status="command_proposed",
                        message="Explicit shell command detected.",
                        data={"command": command},
                    )
        self.record("no_command", "no explicit shell command prefix detected")
        return AgentResult(
            agent=self.name,
            status="no_command",
            message="No shell command was proposed in Stage 1.",
        )


class CoordinatorAgent(BaseAgent):
    """Single-process coordinator for the shellai agent loop."""

    def __init__(self, config: ShellAIConfig | None = None, trace: RequestTrace | None = None) -> None:
        self.config = config or ShellAIConfig.load()
        active_trace = trace or TRACE_STORE.start_trace("")
        super().__init__(AgentRole.COORDINATOR, active_trace)
        self.shell = ShellAgent(active_trace)
        self.safety = SafetyAgent(active_trace, ShellRiskPolicy(self.config.risk_policy), config=self.config)

    def handle(self, user_input: str) -> dict[str, Any]:
        self.trace.user_input = str(user_input or "")
        self.record("received", "request accepted by coordinator")

        shell_result = self.shell.propose_shell_command(user_input)
        payload: dict[str, Any] = {
            "status": "planned",
            "message": "Stage 1 coordinator initialized. Full LLM planning and execution land in later stages.",
            "trace_id": self.trace.request_id,
            "agents": ["CoordinatorAgent", "ShellAgent", "SafetyAgent"],
            "shell": shell_result.to_dict(),
        }

        command = shell_result.data.get("command")
        if command:
            risk = self.safety.assess_shell_command(str(command))
            payload["risk"] = risk.to_dict()
            if risk.level.value == "BLOCK":
                payload["status"] = "blocked"
                payload["message"] = "Command blocked by shell risk policy."
            elif risk.level.value == "ASK":
                payload["status"] = "needs_confirmation"
                payload["message"] = "Command requires explicit confirmation before execution."
            else:
                payload["status"] = "ready"
                payload["message"] = "Command is classified as SAFE. Execution is not enabled in Stage 1."

        self.record("completed", payload["message"], {"status": payload["status"]})
        payload["trace"] = self.trace.to_dict()
        return payload


__all__ = [
    "AgentResult",
    "BaseAgent",
    "CoordinatorAgent",
    "SafetyAgent",
    "ShellAgent",
]
