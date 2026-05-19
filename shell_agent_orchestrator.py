"""Agent-first Shell goal orchestration tools.

These tools are intentionally thin: they expose the agent supervisor boundary
while keeping low-level Shell tools as internal capabilities.
"""

from __future__ import annotations

import json
from typing import Any

from shell_safe_executor import god_tier_tool as function_tool


def orchestrate_shell_goal(goal: str, execute: bool = False, approved: bool = False) -> str:
    from core.agent_orchestrator import AgentFirstOrchestrator

    orchestrator = AgentFirstOrchestrator()
    plan = orchestrator.orchestrate(goal, approved=approved).to_dict()
    plan["execution_requested"] = bool(execute)
    if not execute:
        return json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True)
    if not plan.get("execution_allowed"):
        plan["execution_status"] = "blocked"
        plan["execution_reason"] = "agent policy did not allow capability execution"
        return json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True)

    from shell_tool_gateway import execute_tool_sync

    result: dict[str, Any]
    try:
        result = execute_tool_sync(plan["low_level_tool_id"], plan.get("args") or {})
    except Exception as exc:
        result = {"status": "error", "message": str(exc)[:240]}
    plan["execution_status"] = result.get("status", "unknown")
    plan["execution_result"] = result
    return json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True)


@function_tool
def orchestrate_shell_goal_tool(goal: str, execute: bool = False, approved: bool = False) -> str:
    """Route a user goal through Shell's agent orchestrator before any capability execution."""
    return orchestrate_shell_goal(goal, execute=execute, approved=approved)


def list_orchestration_agents() -> str:
    from core.agent_orchestrator import AgentFirstOrchestrator

    payload = {
        "architecture": "agent_first",
        "tools_are": "internal_capabilities",
        "agents": AgentFirstOrchestrator().agents(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


@function_tool
def list_orchestration_agents_tool() -> str:
    """List Shell's bounded specialist orchestration agents."""
    return list_orchestration_agents()


__all__ = [
    "list_orchestration_agents",
    "list_orchestration_agents_tool",
    "orchestrate_shell_goal",
    "orchestrate_shell_goal_tool",
]
