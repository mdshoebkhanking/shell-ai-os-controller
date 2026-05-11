from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class MeshService:
    service_id: str
    name: str
    service_type: str
    capabilities: list[str] = field(default_factory=list)
    endpoint: str = ""
    trust_score: float = 0.5
    healthy: bool = True
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"service_id": self.service_id, "name": self.name, "service_type": self.service_type, "capabilities": list(self.capabilities), "endpoint": self.endpoint, "trust_score": self.trust_score, "healthy": self.healthy, "latency_ms": self.latency_ms}


class ServiceMesh:
    def __init__(self):
        self._services: dict[str, MeshService] = {}
        self._trace: list[dict[str, Any]] = []

    def register(self, name: str, service_type: str, *, capabilities: list[str] | None = None, endpoint: str = "", trust_score: float = 0.5, latency_ms: float = 0.0) -> MeshService:
        service = MeshService(uuid.uuid4().hex, name, service_type, list(capabilities or []), endpoint, max(0.0, min(1.0, float(trust_score))), True, max(0.0, float(latency_ms)))
        self._services[service.service_id] = service
        publish_event(AIEventType.SERVICE_MESH_ROUTED, {"registered": service.to_dict()}, source="core.service_mesh")
        return service

    def route(self, capability: str) -> dict[str, Any]:
        candidates = [svc for svc in self._services.values() if svc.healthy and capability in svc.capabilities and svc.trust_score >= 0.5]
        candidates.sort(key=lambda svc: (svc.latency_ms, -svc.trust_score))
        service = candidates[0] if candidates else None
        trace = {"capability": capability, "service": service.to_dict() if service else None, "ts": time.time()}
        self._trace.append(trace)
        publish_event(AIEventType.SERVICE_MESH_ROUTED, {"route": trace}, source="core.service_mesh")
        return trace

    def failover(self, failed_service: str, capability: str) -> dict[str, Any]:
        if failed_service in self._services:
            svc = self._services[failed_service]
            self._services[failed_service] = MeshService(svc.service_id, svc.name, svc.service_type, list(svc.capabilities), svc.endpoint, svc.trust_score, False, svc.latency_ms)
        result = self.route(capability)
        result["failed_service"] = failed_service
        return result

    def trace(self) -> list[dict[str, Any]]:
        return list(self._trace)

