from __future__ import annotations

from typing import Any

from core.events import AIEventType, publish_event, replay_events


class AIOperationsCenter:
    def snapshot(self, *, topology: dict[str, Any] | None = None, governance: dict[str, Any] | None = None, analytics: dict[str, Any] | None = None) -> dict[str, Any]:
        snapshot = {
            "orchestration_topology": dict(topology or {}),
            "runtime_graphs": {},
            "memory_fabric": {},
            "workflow_intelligence": {},
            "governance": dict(governance or {}),
            "analytics": dict(analytics or {}),
            "trust_risk": {},
            "distributed_nodes": {},
            "recent_events": replay_events(limit=50),
            "operator_visible": True,
        }
        publish_event(AIEventType.OPS_CENTER_SNAPSHOT_CREATED, snapshot, source="core.ops_center")
        return snapshot

    def panel_manifest(self) -> list[dict[str, Any]]:
        return [
            {"id": "topology", "title": "Orchestration Topology", "source": "core.topology"},
            {"id": "runtime_graphs", "title": "Runtime Graphs", "source": "core.runtime_virtualization"},
            {"id": "memory_fabric", "title": "Memory Fabric", "source": "core.distributed_memory"},
            {"id": "governance", "title": "Governance", "source": "core.human_governance"},
            {"id": "analytics", "title": "Execution Analytics", "source": "core.semantic_analytics"},
            {"id": "trust", "title": "Trust And Risk", "source": "core.security_fabric"},
        ]

