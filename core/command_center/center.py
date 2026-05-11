from __future__ import annotations

from typing import Any

from core.events import AIEventType, publish_event, replay_events


class DistributedCommandCenter:
    def snapshot(self, *, cluster: dict[str, Any] | None = None, governance: dict[str, Any] | None = None, observability: dict[str, Any] | None = None) -> dict[str, Any]:
        snapshot = {
            "cluster_topology": dict(cluster or {}),
            "orchestration_graphs": {},
            "runtime_federation": {},
            "cognition_heatmaps": {},
            "workflow_intelligence": {},
            "distributed_tracing": dict(observability or {}),
            "governance": dict(governance or {}),
            "recent_events": replay_events(limit=50),
            "operator_visible": True,
        }
        publish_event(AIEventType.COMMAND_CENTER_SNAPSHOT_CREATED, snapshot, source="core.command_center")
        return snapshot

    def panels(self) -> list[dict[str, str]]:
        return [
            {"id": "cluster_topology", "title": "Cluster Topology"},
            {"id": "orchestration_graphs", "title": "Orchestration Graphs"},
            {"id": "runtime_federation", "title": "Runtime Federation"},
            {"id": "cognition_heatmaps", "title": "Cognition Heatmaps"},
            {"id": "distributed_tracing", "title": "Distributed Tracing"},
            {"id": "governance", "title": "Governance"},
        ]

