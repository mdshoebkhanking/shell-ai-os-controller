from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class InterfaceEndpoint:
    endpoint_id: str
    interface_type: str
    name: str
    capabilities: list[str] = field(default_factory=list)
    active_context: dict[str, Any] = field(default_factory=dict)
    last_sync: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint_id": self.endpoint_id,
            "interface_type": self.interface_type,
            "name": self.name,
            "capabilities": list(self.capabilities),
            "active_context": dict(self.active_context),
            "last_sync": self.last_sync,
        }


class UniversalInterfaceLayer:
    def __init__(self):
        self._endpoints: dict[str, InterfaceEndpoint] = {}

    def register(self, interface_type: str, name: str, *, capabilities: list[str] | None = None) -> InterfaceEndpoint:
        endpoint = InterfaceEndpoint(uuid.uuid4().hex, interface_type, name, list(capabilities or []))
        self._endpoints[endpoint.endpoint_id] = endpoint
        publish_event(AIEventType.INTERFACE_LAYER_SYNCED, {"registered": endpoint.to_dict()}, source="core.interface_layer")
        return endpoint

    def sync_context(self, endpoint_id: str, context: dict[str, Any]) -> InterfaceEndpoint | None:
        current = self._endpoints.get(endpoint_id)
        if not current:
            return None
        updated = InterfaceEndpoint(current.endpoint_id, current.interface_type, current.name, list(current.capabilities), dict(context), time.time())
        self._endpoints[endpoint_id] = updated
        publish_event(AIEventType.INTERFACE_LAYER_SYNCED, {"context": updated.to_dict()}, source="core.interface_layer")
        return updated

    def compatible(self, capability: str) -> list[InterfaceEndpoint]:
        return [endpoint for endpoint in self._endpoints.values() if capability in endpoint.capabilities]

    def continuity_plan(self, source_id: str, target_id: str) -> dict[str, Any]:
        source = self._endpoints.get(source_id)
        target = self._endpoints.get(target_id)
        return {
            "status": "preview",
            "source": source.to_dict() if source else None,
            "target": target.to_dict() if target else None,
            "context": dict(source.active_context) if source else {},
            "requires_confirmation": True,
        }

