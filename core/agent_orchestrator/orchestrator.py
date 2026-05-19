from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.agent_ecosystem import (
    AgentCapability,
    AgentEcosystemRegistry,
    AgentExecutionPolicy,
    AgentProfile,
    AgentRiskLevel,
    AgentRole,
    AgentTask,
    AutonomyLevel,
    MemoryScope,
)
from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class AgentRoutePlan:
    trace_id: str
    goal: str
    status: str
    selected_agent_id: str
    selected_agent_name: str
    role: str
    capability: str
    low_level_tool_id: str = ""
    low_level_kind: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    route_confidence: float = 0.0
    risk_level: str = AgentRiskLevel.SAFE.value
    memory_scopes: list[str] = field(default_factory=list)
    requires_approval: bool = False
    execution_allowed: bool = False
    reasons: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "goal": self.goal,
            "status": self.status,
            "selected_agent_id": self.selected_agent_id,
            "selected_agent_name": self.selected_agent_name,
            "role": self.role,
            "capability": self.capability,
            "low_level_tool_id": self.low_level_tool_id,
            "low_level_kind": self.low_level_kind,
            "args": dict(self.args),
            "route_confidence": self.route_confidence,
            "risk_level": self.risk_level,
            "memory_scopes": list(self.memory_scopes),
            "requires_approval": self.requires_approval,
            "execution_allowed": self.execution_allowed,
            "reasons": list(self.reasons),
            "created_at": self.created_at,
        }


_CAPABILITY_AGENT_MAP = {
    "agent": "planner_agent",
    "browser": "browser_agent",
    "coding": "coding_agent",
    "communication": "communication_agent",
    "desktop": "desktop_automation_agent",
    "file": "workflow_agent",
    "memory": "memory_agent",
    "multimodal": "multimodal_orchestrator_agent",
    "provider": "provider_routing_agent",
    "reasoning": "reasoning_agent",
    "research": "research_agent",
    "system": "system_monitoring_agent",
    "vision": "vision_agent",
    "voice": "voice_agent",
    "workflow": "workflow_agent",
}


def _capability(name: str, *, risk: AgentRiskLevel = AgentRiskLevel.SAFE) -> AgentCapability:
    return AgentCapability(name, risk_level=risk)


def default_agent_profiles() -> list[AgentProfile]:
    """Return Shell's bounded specialist agent directory.

    These are orchestration identities, not background workers. Existing tools
    remain low-level capabilities until a specific agent route elects to use
    them.
    """
    return [
        AgentProfile("realtime_conversation_agent", AgentRole.VOICE, "Realtime Conversation Agent", [_capability("capability.voice"), _capability("capability.agent")]),
        AgentProfile("planner_agent", AgentRole.PLANNER, "Planner Agent", [_capability("plan.goal"), _capability("capability.agent"), _capability("capability.workflow")]),
        AgentProfile("voice_agent", AgentRole.VOICE, "Voice Agent", [_capability("capability.voice")]),
        AgentProfile("workflow_agent", AgentRole.WORKFLOW, "Workflow Agent", [_capability("capability.workflow"), _capability("capability.file")]),
        AgentProfile("reasoning_agent", AgentRole.EXECUTOR, "Reasoning Agent", [_capability("capability.reasoning")]),
        AgentProfile("research_agent", AgentRole.RESEARCHER, "Research Agent", [_capability("capability.research")]),
        AgentProfile("browser_agent", AgentRole.EXECUTOR, "Browser Agent", [_capability("capability.browser", risk=AgentRiskLevel.CAUTION)], autonomy_level=AutonomyLevel.MANUAL),
        AgentProfile("desktop_automation_agent", AgentRole.EXECUTOR, "Desktop Automation Agent", [_capability("capability.desktop", risk=AgentRiskLevel.CAUTION)], autonomy_level=AutonomyLevel.MANUAL),
        AgentProfile("memory_agent", AgentRole.OBSERVER, "Memory Agent", [_capability("capability.memory")]),
        AgentProfile("vision_agent", AgentRole.OBSERVER, "Vision Agent", [_capability("capability.vision")]),
        AgentProfile("system_monitoring_agent", AgentRole.OBSERVER, "System Monitoring Agent", [_capability("capability.system", risk=AgentRiskLevel.CAUTION)]),
        AgentProfile("context_agent", AgentRole.OBSERVER, "Context Agent", [_capability("capability.workflow"), _capability("capability.memory")]),
        AgentProfile("retrieval_agent", AgentRole.RESEARCHER, "Retrieval Agent", [_capability("capability.research"), _capability("capability.memory")]),
        AgentProfile("coding_agent", AgentRole.EXECUTOR, "Coding Agent", [_capability("capability.coding", risk=AgentRiskLevel.CAUTION)], autonomy_level=AutonomyLevel.MANUAL),
        AgentProfile("task_execution_agent", AgentRole.EXECUTOR, "Task Execution Agent", [_capability("capability.workflow", risk=AgentRiskLevel.CAUTION)], autonomy_level=AutonomyLevel.MANUAL),
        AgentProfile("provider_routing_agent", AgentRole.OBSERVER, "Provider Routing Agent", [_capability("capability.provider")]),
        AgentProfile("multimodal_orchestrator_agent", AgentRole.WORKFLOW, "Multimodal Orchestrator Agent", [_capability("capability.multimodal"), _capability("capability.vision"), _capability("capability.voice")]),
        AgentProfile("communication_agent", AgentRole.EXECUTOR, "Communication Agent", [_capability("capability.communication", risk=AgentRiskLevel.CAUTION)], autonomy_level=AutonomyLevel.MANUAL),
        AgentProfile("validator_agent", AgentRole.VALIDATOR, "Validator Agent", [_capability("validate.result")]),
    ]


def _registry() -> AgentEcosystemRegistry:
    registry = AgentEcosystemRegistry(
        AgentExecutionPolicy(
            max_agents=24,
            max_chain_depth=3,
            max_parallel_tasks=1,
            require_validator_for_risky=True,
            allow_background_agents=False,
            default_timeout_s=45,
        )
    )
    for profile in default_agent_profiles():
        registry.register(profile)
    return registry


def _tool_blob(tool_id: str) -> str:
    return str(tool_id or "").lower().replace(":", ".")


def _capability_for_route(route: dict[str, Any]) -> str:
    tool_id = str(route.get("tool") or "")
    blob = _tool_blob(tool_id)
    kind = str(route.get("kind") or "")

    if kind == "agent" or ".agent" in blob:
        if any(word in blob for word in ("developer", "code", "coding")):
            return "coding"
        if "research" in blob:
            return "research"
        if any(word in blob for word in ("browser", "automation")):
            return "desktop"
        if any(word in blob for word in ("communication", "social")):
            return "communication"
        return "agent"
    if any(word in blob for word in ("calculator", "math", "text_tools", "json_tools", "hash", "crypto", "regex")):
        return "reasoning"
    if any(word in blob for word in ("workspace", "file", "pdf", "zip", "downloader", "converter")):
        return "file"
    if any(word in blob for word in ("email", "telegram", "whatsapp", "social", "instagram")):
        return "communication"
    if any(word in blob for word in ("browser", "youtube", "google", "open_url", "news", "stock")):
        return "browser" if any(word in blob for word in ("browser", "youtube", "open_url")) else "research"
    if any(word in blob for word in ("screenshot", "ocr", "vision", "screen")):
        return "vision"
    if any(word in blob for word in ("window", "desktop", "keyboard", "mouse", "click", "open_app", "close_app")):
        return "desktop"
    if any(word in blob for word in ("system", "battery", "process", "network", "diagnostic")):
        return "system"
    if any(word in blob for word in ("voice", "speech", "tts", "audio")):
        return "voice"
    if any(word in blob for word in ("image", "video", "multimodal")):
        return "multimodal"
    if any(word in blob for word in ("provider", "brain", "router")):
        return "provider"
    if any(word in blob for word in ("memory", "knowledge", "recall", "remember")):
        return "memory"
    if any(word in blob for word in ("code", "terminal", "powershell", "command")):
        return "coding"
    return "workflow"


def _risk_for_route(route: dict[str, Any]) -> AgentRiskLevel:
    tool_id = str(route.get("tool") or "")
    blob = _tool_blob(tool_id)
    metadata = route.get("metadata") if isinstance(route.get("metadata"), dict) else {}
    safety = str(metadata.get("safety_level") or "").lower()
    readiness = route.get("readiness") if isinstance(route.get("readiness"), dict) else {}
    reasons = " ".join(str(item) for item in readiness.get("reasons", [])).lower()

    if any(word in blob for word in ("hotpatch", "rollback", "registry_hack", "kill_process", "delete", "remove")):
        return AgentRiskLevel.CRITICAL
    if any(word in blob for word in ("terminal", "powershell", "run_command", "execute_code", "write_code", "send_email", "whatsapp_web_send", "telegram")):
        return AgentRiskLevel.DANGEROUS
    if safety in {"guarded", "dangerous", "experimental"} or "blocked by safety flag" in reasons:
        return AgentRiskLevel.DANGEROUS
    if _capability_for_route(route) in {"desktop", "communication", "coding", "system"}:
        return AgentRiskLevel.CAUTION
    return AgentRiskLevel.SAFE


def _memory_scopes_for_capability(capability: str) -> list[MemoryScope]:
    mapping = {
        "agent": [MemoryScope.CONTEXTUAL, MemoryScope.CONVERSATION],
        "browser": [MemoryScope.CONTEXTUAL],
        "coding": [MemoryScope.WORKSPACE, MemoryScope.FAILURE],
        "communication": [MemoryScope.CONVERSATION],
        "desktop": [MemoryScope.CONTEXTUAL],
        "file": [MemoryScope.WORKSPACE],
        "memory": [MemoryScope.LONG_TERM, MemoryScope.SEMANTIC],
        "multimodal": [MemoryScope.CONTEXTUAL, MemoryScope.CONVERSATION],
        "provider": [MemoryScope.FAILURE],
        "reasoning": [MemoryScope.SHORT_TERM],
        "research": [MemoryScope.SEMANTIC, MemoryScope.CONTEXTUAL],
        "system": [MemoryScope.CONTEXTUAL],
        "vision": [MemoryScope.CONTEXTUAL],
        "voice": [MemoryScope.CONVERSATION],
        "workflow": [MemoryScope.CONTEXTUAL, MemoryScope.WORKSPACE],
    }
    return list(mapping.get(capability, [MemoryScope.CONTEXTUAL]))


class AgentFirstOrchestrator:
    """Lightweight supervisor that turns goals into agent-owned capabilities."""

    def __init__(self, registry: AgentEcosystemRegistry | None = None):
        self.registry = registry or _registry()

    def agents(self) -> list[dict[str, Any]]:
        return [profile.to_dict() for profile in default_agent_profiles()]

    def orchestrate(self, goal: str, *, approved: bool = False) -> AgentRoutePlan:
        started = time.perf_counter()
        trace_id = uuid.uuid4().hex
        cleaned_goal = str(goal or "").strip()
        reasons: list[str] = []

        try:
            from shell_nl_router import route_natural_command

            route = route_natural_command(cleaned_goal)
        except Exception as exc:
            route = None
            reasons.append(f"deterministic router unavailable: {exc}")

        if not route:
            task = AgentTask(
                cleaned_goal,
                ["plan.goal"],
                risk_level=AgentRiskLevel.SAFE,
                memory_scopes=[MemoryScope.CONTEXTUAL],
                trace_id=trace_id,
                timeout_s=20,
            )
            ecosystem_plan = self.registry.plan(task, approved=approved)
            assignment = ecosystem_plan.assignments[0] if ecosystem_plan.assignments else None
            plan = AgentRoutePlan(
                trace_id=trace_id,
                goal=cleaned_goal,
                status="needs_planning",
                selected_agent_id=assignment.agent_id if assignment else "planner_agent",
                selected_agent_name="Planner Agent",
                role=assignment.role.value if assignment else AgentRole.PLANNER.value,
                capability="plan.goal",
                risk_level=AgentRiskLevel.SAFE.value,
                memory_scopes=[MemoryScope.CONTEXTUAL.value],
                requires_approval=False,
                execution_allowed=False,
                reasons=reasons + ["no safe deterministic capability route found"],
            )
            publish_event(AIEventType.AGENT_ORCHESTRATION_PLANNED, plan.to_dict(), source="core.agent_orchestrator", trace_id=trace_id)
            return plan

        capability = _capability_for_route(route)
        risk = _risk_for_route(route)
        memory_scopes = _memory_scopes_for_capability(capability)
        task = AgentTask(
            cleaned_goal,
            [f"capability.{capability}"],
            risk_level=risk,
            memory_scopes=memory_scopes,
            trace_id=trace_id,
            timeout_s=20,
        )
        ecosystem_plan = self.registry.plan(task, approved=approved)
        assignment = ecosystem_plan.assignments[0] if ecosystem_plan.assignments else None
        selected_agent_id = assignment.agent_id if assignment else _CAPABILITY_AGENT_MAP.get(capability, "workflow_agent")
        profile = next((item for item in default_agent_profiles() if item.agent_id == selected_agent_id), None)
        route_reasons = list(ecosystem_plan.blocked)
        if not route_reasons:
            route_reasons.append("tool selected as internal capability, not user-facing architecture")
        route_reasons.extend(reasons)
        execution_allowed = bool(assignment and assignment.allowed and not ecosystem_plan.requires_approval)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        plan = AgentRoutePlan(
            trace_id=trace_id,
            goal=cleaned_goal,
            status="planned" if assignment and assignment.allowed else "blocked",
            selected_agent_id=selected_agent_id,
            selected_agent_name=profile.name if profile else selected_agent_id.replace("_", " ").title(),
            role=assignment.role.value if assignment else "",
            capability=f"capability.{capability}",
            low_level_tool_id=str(route.get("tool") or ""),
            low_level_kind=str(route.get("kind") or "tool"),
            args=dict(route.get("args") or {}),
            route_confidence=float(route.get("confidence") or 0.0),
            risk_level=risk.value,
            memory_scopes=[scope.value for scope in memory_scopes],
            requires_approval=bool(ecosystem_plan.requires_approval),
            execution_allowed=execution_allowed,
            reasons=route_reasons,
        )
        payload = plan.to_dict()
        payload["orchestration_latency_ms"] = elapsed_ms
        publish_event(AIEventType.AGENT_ORCHESTRATION_PLANNED, payload, source="core.agent_orchestrator", trace_id=trace_id)
        return plan
