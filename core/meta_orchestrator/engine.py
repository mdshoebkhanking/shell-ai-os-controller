from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class OrchestratorUnit:
    unit_id: str
    name: str
    layer: str
    capabilities: list[str] = field(default_factory=list)
    policy: str = "standard"
    load: float = 0.0
    healthy: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "name": self.name,
            "layer": self.layer,
            "capabilities": list(self.capabilities),
            "policy": self.policy,
            "load": self.load,
            "healthy": self.healthy,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class OrchestratorLink:
    source_id: str
    target_id: str
    relation: str = "coordinates"

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "target_id": self.target_id, "relation": self.relation}


class MetaOrchestrator:
    def __init__(self):
        self._units: dict[str, OrchestratorUnit] = {}
        self._links: list[OrchestratorLink] = []

    def register(self, name: str, layer: str, *, capabilities: list[str] | None = None, policy: str = "standard", load: float = 0.0, metadata: dict[str, Any] | None = None) -> OrchestratorUnit:
        unit = OrchestratorUnit(uuid.uuid4().hex, name, layer, list(capabilities or []), policy, max(0.0, min(1.0, float(load))), True, dict(metadata or {}))
        self._units[unit.unit_id] = unit
        self._emit("registered", unit.to_dict())
        return unit

    def link(self, source_id: str, target_id: str, relation: str = "coordinates") -> OrchestratorLink:
        link = OrchestratorLink(source_id, target_id, relation)
        self._links.append(link)
        self._emit("linked", link.to_dict())
        return link

    def route(self, capability: str, *, policy: str = "") -> dict[str, Any]:
        candidates = [
            unit for unit in self._units.values()
            if unit.healthy and capability in unit.capabilities and (not policy or unit.policy == policy)
        ]
        candidates.sort(key=lambda unit: (unit.load, unit.layer))
        selected = candidates[0] if candidates else None
        result = {"capability": capability, "selected": selected.to_dict() if selected else None, "reason": "lowest-load matching orchestrator" if selected else "no matching orchestrator"}
        self._emit("route", result)
        return result

    def adapt_topology(self, unit_id: str, *, healthy: bool, load: float | None = None) -> OrchestratorUnit | None:
        current = self._units.get(unit_id)
        if not current:
            return None
        updated = OrchestratorUnit(
            current.unit_id,
            current.name,
            current.layer,
            list(current.capabilities),
            current.policy,
            current.load if load is None else max(0.0, min(1.0, float(load))),
            bool(healthy),
            dict(current.metadata),
        )
        self._units[unit_id] = updated
        self._emit("adapted", updated.to_dict())
        return updated

    def hierarchy(self) -> dict[str, Any]:
        return {"units": [unit.to_dict() for unit in self._units.values()], "links": [link.to_dict() for link in self._links]}

    def _emit(self, action: str, payload: dict[str, Any]) -> None:
        publish_event(AIEventType.META_ORCHESTRATION_UPDATED, {"action": action, **payload}, source="core.meta_orchestrator")

