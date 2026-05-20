from __future__ import annotations

from typing import Any, Optional

from shellai.agents import CoordinatorAgent, SafetyAgent, ShellAgent
from shellai.agents_memory import MemoryAgent
from shellai.agents_optimizer import OptimizerAgent
from shellai.agents_ui import UIAgent
from shellai.config import ShellAIConfig
from shellai.memory import MemoryStore
from shellai.models import ModelRouter
from shellai.observability import RequestTrace, TRACE_STORE
from shellai.safety import ShellRiskPolicy
from shellai.skills import SkillManager
from shellai.tools import ToolRegistry


class AgentRuntime:
    """Small in-process runtime that wires the Phase-2 agent fabric."""

    def __init__(
        self,
        config: Optional[ShellAIConfig] = None,
        model_router: Optional[Any] = None,
        memory_store: Optional[MemoryStore] = None,
        skill_manager: Optional[SkillManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ) -> None:
        self.config = config or ShellAIConfig.load()
        self.model_router = model_router or ModelRouter(self.config)
        self.memory_store = memory_store or MemoryStore(self.config.paths.memory_db, config=self.config)
        self.skill_manager = skill_manager or SkillManager(config=self.config, memory_store=self.memory_store)
        self.tool_registry = tool_registry or ToolRegistry(self.config)
        self.trace: Optional[RequestTrace] = None
        self.coordinator: Optional[CoordinatorAgent] = None
        self.shell: Optional[ShellAgent] = None
        self.safety: Optional[SafetyAgent] = None
        self.memory_agent: Optional[MemoryAgent] = None
        self.ui_agent: Optional[UIAgent] = None
        self.optimizer_agent: Optional[OptimizerAgent] = None

    def bind_trace(self, trace: RequestTrace) -> "AgentRuntime":
        self.trace = trace
        self.coordinator = CoordinatorAgent(config=self.config, trace=trace)
        self.shell = ShellAgent(trace)
        self.safety = SafetyAgent(trace, ShellRiskPolicy(self.config.risk_policy), config=self.config)
        self.memory_agent = MemoryAgent(
            config=self.config,
            memory_store=self.memory_store,
            skill_manager=self.skill_manager,
            trace=trace,
        )
        self.ui_agent = UIAgent(config=self.config, model_router=self.model_router, trace=trace)
        self.optimizer_agent = OptimizerAgent(config=self.config, memory_store=self.memory_store, trace=trace)
        self.record_agent_boundary("AgentRuntime", "bound", "runtime bound to request trace")
        return self

    def record_agent_boundary(self, agent: str, status: str, message: str, metadata: Optional[dict[str, Any]] = None) -> None:
        if self.trace is not None:
            payload = {"agent": agent}
            payload.update(dict(metadata or {}))
            self.trace.add_step("AgentRuntime", status, message, payload)

    def run_single_task(
        self,
        user_text: str,
        context: Optional[dict[str, Any]] = None,
        auto_approve_ask: bool = False,
    ) -> dict[str, Any]:
        from shellai.agent_loop import create_user_request, run_agent_task

        trace = TRACE_STORE.start_trace(user_text)
        self.bind_trace(trace)
        request = create_user_request(user_text, context=dict(context or {}), auto_approve_ask=auto_approve_ask)
        return run_agent_task(
            request,
            trace=trace,
            config=self.config,
            model_router=self.model_router,
            memory_store=self.memory_store,
            skill_manager=self.skill_manager,
            tool_registry=self.tool_registry,
            agent_runtime=self,
        )


__all__ = ["AgentRuntime"]
