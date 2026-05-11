from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExperiencePanel:
    panel_id: str
    title: str
    data_source: str
    priority: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"panel_id": self.panel_id, "title": self.title, "data_source": self.data_source, "priority": self.priority, "metadata": dict(self.metadata)}


class OperatingExperiencePlatform:
    def default_panels(self) -> list[ExperiencePanel]:
        return [
            ExperiencePanel("execution_topology", "Execution Topology", "core.execution_graph", 10),
            ExperiencePanel("workflow_timeline", "Workflow Timeline", "core.timeline", 9),
            ExperiencePanel("memory_graph", "Memory Graph", "core.semantic_graph", 8),
            ExperiencePanel("runtime_nodes", "Runtime Nodes", "core.ecosystem", 8),
            ExperiencePanel("trust_safety", "Trust And Safety", "core.governance", 10),
        ]

    def layout(self) -> dict[str, Any]:
        panels = sorted(self.default_panels(), key=lambda panel: panel.priority, reverse=True)
        return {"panels": [panel.to_dict() for panel in panels], "requires_operator_access": True}

