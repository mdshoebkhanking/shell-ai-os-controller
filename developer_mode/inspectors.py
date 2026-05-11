from __future__ import annotations

from typing import Any


class DeveloperInspector:
    def execution_graph(self) -> dict[str, Any]:
        from core.observability.tracing import ExecutionTracer

        return {"traces": ExecutionTracer.get().recent_traces(100)}

    def memory(self) -> dict[str, Any]:
        from core.memory import LocalMemoryStore

        return {"summary": LocalMemoryStore().summarize(limit=50)}

    def events(self) -> dict[str, Any]:
        from core.events import replay_events

        return {"events": replay_events(limit=200)}

    def tool_routing(self, query: str) -> dict[str, Any]:
        from core.tools.registry import CapabilityRegistry
        from shell_tool_catalog import discover_capabilities

        registry = CapabilityRegistry.from_catalog(discover_capabilities()["catalog"])
        return {"query": query, "ranked": registry.rank(query, limit=10)}

    def operating_dashboard(self) -> dict[str, Any]:
        from core.operating_dashboard import OperatingDashboard

        return OperatingDashboard().snapshot()

    def experience_layout(self) -> dict[str, Any]:
        from core.experience import OperatingExperiencePlatform

        return OperatingExperiencePlatform().layout()

    def ai_operations_center(self) -> dict[str, Any]:
        from core.ops_center import AIOperationsCenter

        return AIOperationsCenter().snapshot()

    def distributed_command_center(self) -> dict[str, Any]:
        from core.command_center import DistributedCommandCenter

        return DistributedCommandCenter().snapshot()
