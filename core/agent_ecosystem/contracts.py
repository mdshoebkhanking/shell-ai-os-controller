from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class AgentRole(str, Enum):
    PLANNER = "planner"
    EXECUTOR = "executor"
    VALIDATOR = "validator"
    RESEARCHER = "researcher"
    SUMMARIZER = "summarizer"
    DEBUGGER = "debugger"
    OBSERVER = "observer"
    RECOVERY = "recovery"
    WORKFLOW = "workflow"
    VOICE = "voice"


class AutonomyLevel(str, Enum):
    MANUAL = "manual"
    ASSISTED = "assisted"
    APPROVED_AUTOMATION = "approved_automation"
    BACKGROUND_SAFE = "background_safe"
    BLOCKED = "blocked"


class AgentRiskLevel(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    DANGEROUS = "dangerous"
    CRITICAL = "critical"


class MemoryScope(str, Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    CONTEXTUAL = "contextual"
    WORKSPACE = "workspace"
    CONVERSATION = "conversation"
    SEMANTIC = "semantic"
    FAILURE = "failure"


class MessageIntent(str, Enum):
    DELEGATE = "delegate"
    RESULT = "result"
    HANDOFF = "handoff"
    CLARIFY = "clarify"
    OBSERVE = "observe"
    VALIDATE = "validate"


class AgentTaskStatus(str, Enum):
    PLANNED = "planned"
    BLOCKED = "blocked"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class AgentCapability:
    name: str
    tools: list[str] = field(default_factory=list)
    memory_scopes: list[MemoryScope] = field(default_factory=list)
    risk_level: AgentRiskLevel = AgentRiskLevel.SAFE
    requires_confirmation: bool = False
    platform_support: list[str] = field(default_factory=lambda: ["windows", "macos", "linux"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tools": list(self.tools),
            "memory_scopes": [scope.value for scope in self.memory_scopes],
            "risk_level": self.risk_level.value,
            "requires_confirmation": self.requires_confirmation,
            "platform_support": list(self.platform_support),
        }


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    role: AgentRole
    name: str
    capabilities: list[AgentCapability] = field(default_factory=list)
    autonomy_level: AutonomyLevel = AutonomyLevel.ASSISTED
    max_concurrency: int = 1
    enabled: bool = True
    version: str = "1.0.0"
    system_boundary: str = "local_shell"

    def capability_names(self) -> set[str]:
        return {capability.name for capability in self.capabilities}

    def max_risk(self) -> AgentRiskLevel:
        order = {
            AgentRiskLevel.SAFE: 0,
            AgentRiskLevel.CAUTION: 1,
            AgentRiskLevel.DANGEROUS: 2,
            AgentRiskLevel.CRITICAL: 3,
        }
        return max((capability.risk_level for capability in self.capabilities), key=lambda value: order[value], default=AgentRiskLevel.SAFE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "name": self.name,
            "capabilities": [capability.to_dict() for capability in self.capabilities],
            "autonomy_level": self.autonomy_level.value,
            "max_concurrency": self.max_concurrency,
            "enabled": self.enabled,
            "version": self.version,
            "system_boundary": self.system_boundary,
        }


@dataclass(frozen=True)
class AgentTask:
    goal: str
    required_capabilities: list[str]
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    requested_by: str = "user"
    priority: int = 5
    risk_level: AgentRiskLevel = AgentRiskLevel.SAFE
    memory_scopes: list[MemoryScope] = field(default_factory=list)
    timeout_s: int = 60
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "required_capabilities": list(self.required_capabilities),
            "requested_by": self.requested_by,
            "priority": self.priority,
            "risk_level": self.risk_level.value,
            "memory_scopes": [scope.value for scope in self.memory_scopes],
            "timeout_s": self.timeout_s,
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True)
class AgentExecutionPolicy:
    max_agents: int = 8
    max_chain_depth: int = 4
    max_parallel_tasks: int = 3
    require_validator_for_risky: bool = True
    allow_background_agents: bool = False
    default_timeout_s: int = 60


@dataclass(frozen=True)
class AgentTaskAssignment:
    task_id: str
    agent_id: str
    role: AgentRole
    capability_match: list[str]
    allowed: bool
    status: AgentTaskStatus
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "role": self.role.value,
            "capability_match": list(self.capability_match),
            "allowed": self.allowed,
            "status": self.status.value,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class AgentOrchestrationPlan:
    task_id: str
    assignments: list[AgentTaskAssignment]
    blocked: list[str] = field(default_factory=list)
    requires_approval: bool = False
    trace_id: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "assignments": [assignment.to_dict() for assignment in self.assignments],
            "blocked": list(self.blocked),
            "requires_approval": self.requires_approval,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AgentMessage:
    sender: str
    receiver: str
    intent: MessageIntent
    payload: dict[str, Any]
    task_id: str = ""
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "intent": self.intent.value,
            "payload": dict(self.payload),
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
        }


class AgentEcosystemRegistry:
    def __init__(self, policy: AgentExecutionPolicy | None = None):
        self.policy = policy or AgentExecutionPolicy()
        self._agents: dict[str, AgentProfile] = {}

    def register(self, profile: AgentProfile) -> AgentProfile:
        self._agents[profile.agent_id] = profile
        publish_event(AIEventType.AGENT_ECOSYSTEM_VALIDATED, {"agent": profile.to_dict()}, source="core.agent_ecosystem")
        return profile

    def agents(self, *, enabled_only: bool = True) -> list[AgentProfile]:
        rows = list(self._agents.values())
        if enabled_only:
            rows = [agent for agent in rows if agent.enabled]
        return rows

    def eligible(self, task: AgentTask) -> list[AgentProfile]:
        required = set(task.required_capabilities)
        candidates = []
        for agent in self.agents():
            if required.issubset(agent.capability_names()):
                candidates.append(agent)
        candidates.sort(key=lambda agent: (agent.role != AgentRole.PLANNER, agent.max_risk().value, agent.name))
        return candidates

    def plan(self, task: AgentTask, *, approved: bool = False) -> AgentOrchestrationPlan:
        assignments: list[AgentTaskAssignment] = []
        blocked: list[str] = []
        candidates = self.eligible(task)
        risky = task.risk_level in {AgentRiskLevel.DANGEROUS, AgentRiskLevel.CRITICAL}
        requires_approval = risky and not approved

        if not candidates:
            blocked.append("no agent covers all required capabilities")
        if risky and self.policy.require_validator_for_risky and not self._has_enabled_role(AgentRole.VALIDATOR):
            blocked.append("risky task requires an enabled validator agent")
        if requires_approval:
            blocked.append("risky task requires explicit approval before execution")
        if not self.policy.allow_background_agents and task.requested_by == "background":
            blocked.append("background agents are disabled by policy")

        allowed = not blocked
        for agent in candidates[: self.policy.max_parallel_tasks]:
            assignments.append(
                AgentTaskAssignment(
                    task_id=task.task_id,
                    agent_id=agent.agent_id,
                    role=agent.role,
                    capability_match=list(task.required_capabilities),
                    allowed=allowed,
                    status=AgentTaskStatus.WAITING_APPROVAL if requires_approval else (AgentTaskStatus.PLANNED if allowed else AgentTaskStatus.BLOCKED),
                    reasons=list(blocked),
                )
            )

        plan = AgentOrchestrationPlan(
            task_id=task.task_id,
            assignments=assignments,
            blocked=blocked,
            requires_approval=requires_approval,
            trace_id=task.trace_id,
        )
        publish_event(AIEventType.AGENT_ORCHESTRATION_PLANNED, plan.to_dict(), source="core.agent_ecosystem", trace_id=task.trace_id)
        return plan

    def bind_memory(self, task: AgentTask, available_scopes: list[MemoryScope]) -> dict[str, Any]:
        available = set(available_scopes)
        requested = set(task.memory_scopes)
        granted = sorted((requested & available), key=lambda item: item.value)
        denied = sorted((requested - available), key=lambda item: item.value)
        out = {
            "task_id": task.task_id,
            "granted": [scope.value for scope in granted],
            "denied": [scope.value for scope in denied],
            "privacy_safe": not denied,
        }
        publish_event(AIEventType.AGENT_MEMORY_BOUND, out, source="core.agent_ecosystem", trace_id=task.trace_id)
        return out

    def message(self, sender: str, receiver: str, intent: MessageIntent, payload: dict[str, Any], *, task_id: str = "", trace_id: str = "") -> AgentMessage:
        message = AgentMessage(sender, receiver, intent, dict(payload), task_id=task_id, trace_id=trace_id or uuid.uuid4().hex)
        publish_event(AIEventType.REALTIME_UPDATE, {"agent_message": message.to_dict()}, source="core.agent_ecosystem", trace_id=message.trace_id)
        return message

    def validate(self) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        if len(self._agents) > self.policy.max_agents:
            findings.append({"severity": "high", "message": "registered agents exceed policy max_agents"})
        for agent in self._agents.values():
            if not agent.capabilities:
                findings.append({"severity": "medium", "agent_id": agent.agent_id, "message": "agent has no capabilities"})
            if agent.autonomy_level == AutonomyLevel.BACKGROUND_SAFE and agent.max_risk() in {AgentRiskLevel.DANGEROUS, AgentRiskLevel.CRITICAL}:
                findings.append({"severity": "high", "agent_id": agent.agent_id, "message": "risky background agent is not allowed"})
            if agent.max_concurrency < 1:
                findings.append({"severity": "medium", "agent_id": agent.agent_id, "message": "agent max_concurrency must be at least 1"})
        publish_event(AIEventType.AGENT_ECOSYSTEM_VALIDATED, {"agent_count": len(self._agents), "finding_count": len(findings)}, source="core.agent_ecosystem")
        return findings

    def _has_enabled_role(self, role: AgentRole) -> bool:
        return any(agent.enabled and agent.role == role for agent in self._agents.values())
