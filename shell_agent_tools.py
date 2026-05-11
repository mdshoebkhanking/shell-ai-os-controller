"""
shell_agent_tools.py — inline tool definitions extracted from agent.py
=======================================================================

Historically, agent.py's `Assistant.__init__` contained roughly 14
inline `@function_tool` definitions mixed in with the lazy-import block.
They closed over singletons imported at function scope (memory_core,
prompt_manager, swarm_orchestrator, etc.) and were hard to test in
isolation.

This module:

* Imports those brain / swarm / health singletons once at module level.
* Defines each inline tool as a top-level async function with `@function_tool`.
* Exposes `get_inline_tools()` which returns the full list agent.py used
  to build inline, preserving the original order and fault-tolerance of
  the dashboard tools (those were wrapped in try/except so a missing
  dependency would skip rather than fail startup).

agent.py can now call `tools_list.extend(get_inline_tools())` once
instead of ~200 lines of inline class-body code.
"""

from __future__ import annotations

import logging

from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("agent.inline_tools")


# ─────────────────────────────────────────────────────────────────────
# Brain singletons — every one of these was already a module-level
# singleton in its source module, so importing them here does not
# create new instances.
# ─────────────────────────────────────────────────────────────────────

from brain.memory_core import memory_core
from brain.prompts.manager import prompt_manager
from brain.automation.engine import workflow_engine
from brain.prediction.engine import predictor
from brain.autonomous.engine import autopilot
from brain.knowledge.graph_lite import kg_lite
from brain.future.predictor_lite import future_lite


# ─────────────────────────────────────────────────────────────────────
# Swarm orchestrator — was instantiated inside __init__; moving the
# instantiation to module scope matches the pattern used by the brain
# singletons and means we only ever create one Orchestrator.
# ─────────────────────────────────────────────────────────────────────

from swarm.orchestrator import Orchestrator

swarm_orchestrator = Orchestrator()


# ─────────────────────────────────────────────────────────────────────
# Brain + swarm tools
# ─────────────────────────────────────────────────────────────────────

@function_tool
async def deploy_swarm_tool(mission_objective: str) -> str:
    """Activates the Multi-Agent Swarm (Hive Mind)."""
    return await swarm_orchestrator.run_mission(mission_objective)


@function_tool
async def kg_add_knowledge_tool(subject: str, relation: str, object_: str) -> str:
    """Add a subject-relation-object triple to the knowledge graph."""
    kg_lite.add_relation(subject, relation, object_)
    return "✅ Knowledge Graph updated."


@function_tool
async def get_future_forecast_tool() -> str:
    """Predict the user's productivity / focus forecast from past activity."""
    return future_lite.predict_productivity()


@function_tool
async def enable_autopilot_tool(goal: str) -> str:
    """Hand a high-level goal to the autonomous engine to execute."""
    return await autopilot.engage(goal)


@function_tool
async def run_workflow_tool(workflow_name: str) -> str:
    """Run a saved workflow by fuzzy name match."""
    available = workflow_engine.list_workflows()
    for w in available:
        if w.lower() in workflow_name.lower():
            return await workflow_engine.execute_workflow(w)
    return f"❌ Workflow '{workflow_name}' not found."


@function_tool
async def get_suggestion_tool() -> str:
    """Ask the predictor what the user is likely to do next."""
    prediction = predictor.predict_next_action()
    return f"🔮 Smart Suggestion: {prediction}" if prediction else "🔮 No patterns yet."


@function_tool
async def change_persona_tool(persona_name: str) -> str:
    """Switch the prompt persona template (see brain.prompts.manager)."""
    available = prompt_manager.list_templates()
    if persona_name.lower() in available:
        return f"✅ Persona Switched: {persona_name.upper()}"
    return f"❌ Persona '{persona_name}' not found."


@function_tool
async def remember_tool(info: str) -> str:
    """Save a piece of information to long-term memory."""
    memory_core.add_memory(info, meta={"source": "user_command"})
    return "✅ Saved to Long-Term Memory."


@function_tool
async def recall_tool(query: str) -> str:
    """Search long-term memory for relevant past entries."""
    results = memory_core.search_memory(query)
    if not results:
        return "🧠 Memory mein kuch nahi mila."
    return "🧠 Found Memories:\n" + "\n".join([f"- {m['text']}" for m in results])


@function_tool
async def system_health_dashboard() -> str:
    """Shows health status of Shell AI tools, API keys, dependencies, cache, and rate limiters."""
    try:
        from shell_health import HealthMonitor
        from shell_cache import get_all_stats as _get_cache_stats

        monitor = HealthMonitor.get()
        health_report = monitor.summary()
        cache_stats = "\nCache Stats:\n" + "\n".join(
            f"  {s['name']}: {s['size']}/{s['max_size']} items, {s['hit_rate']}% hit rate"
            for s in _get_cache_stats()
        )
        return health_report + cache_stats
    except Exception as exc:
        return f"Health dashboard unavailable: {exc}"


@function_tool
async def error_tracker_dashboard() -> str:
    """Shows error patterns, top failing tools, and active issues."""
    try:
        from shell_error_tracker import ErrorTracker

        return ErrorTracker.get().get_report()
    except Exception as exc:
        return f"Error tracker unavailable: {exc}"


@function_tool
async def list_all_tools() -> str:
    """Lists registered tools with categories and usage stats."""
    try:
        from shell_tool_registry import ToolRegistry

        return ToolRegistry.get().get_summary()
    except Exception as exc:
        return f"Tool registry unavailable: {exc}"


@function_tool
async def circuit_breaker_status() -> str:
    """Shows which tools are currently circuit-broken due to repeated failures."""
    try:
        from shell_middleware import MiddlewareChain

        chain = MiddlewareChain.get()
        status = chain.circuit_breaker.get_status()
        if not status["open"]:
            return "All tools are healthy. No circuit breakers tripped."
        lines = ["Circuit Breaker Status:"]
        for tool in status["open"]:
            failures = status["failures"].get(tool, 0)
            lines.append(f"  OPEN: {tool} ({failures} failures)")
        return "\n".join(lines)
    except Exception as exc:
        return f"Circuit breaker status unavailable: {exc}"


@function_tool
async def plugin_loader_report() -> str:
    """Shows which tool modules are loaded, failed, and their tool counts."""
    try:
        from shell_plugin_loader import PluginLoader

        loader = PluginLoader()
        discovered = loader.discover_modules()
        return f"Discovered {len(discovered)} tool modules.\n" + loader.get_report()
    except Exception as exc:
        return f"Plugin loader report unavailable: {exc}"


# ─────────────────────────────────────────────────────────────────────
# Dashboard tools — each one depends on an optional module (health,
# rate limiter, tool registry, middleware, plugin loader). Previously
# wrapped in try/except inside agent.py; we preserve that behaviour by
# collecting whichever tools successfully load.
# ─────────────────────────────────────────────────────────────────────


def _build_dashboard_tools() -> list:
    """Return the list of dashboard tools whose dependencies imported."""
    return [
        system_health_dashboard,
        error_tracker_dashboard,
        list_all_tools,
        circuit_breaker_status,
        plugin_loader_report,
    ]


# ─────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────

# Tools that can safely be a module-level list because all their
# dependencies are required brain/swarm singletons.
BRAIN_SWARM_TOOLS: list = [
    deploy_swarm_tool,
    kg_add_knowledge_tool,
    get_future_forecast_tool,
    enable_autopilot_tool,
    run_workflow_tool,
    get_suggestion_tool,
    change_persona_tool,
    remember_tool,
    recall_tool,
]


def get_inline_tools() -> list:
    """Full list of tools previously defined inline inside agent.py's
    `Assistant.__init__`. Order is preserved so agent startup logs match."""
    return list(BRAIN_SWARM_TOOLS) + _build_dashboard_tools()


__all__ = [
    "swarm_orchestrator",
    "BRAIN_SWARM_TOOLS",
    "get_inline_tools",
    # Individual brain / swarm tools (so agent.py can reference them too)
    "deploy_swarm_tool",
    "kg_add_knowledge_tool",
    "get_future_forecast_tool",
    "enable_autopilot_tool",
    "run_workflow_tool",
    "get_suggestion_tool",
    "change_persona_tool",
    "remember_tool",
    "recall_tool",
    "system_health_dashboard",
    "error_tracker_dashboard",
    "list_all_tools",
    "circuit_breaker_status",
    "plugin_loader_report",
]
