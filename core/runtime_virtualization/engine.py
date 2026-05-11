from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class RuntimeUniverse:
    universe_id: str
    provider: str
    model: str
    context: dict[str, Any] = field(default_factory=dict)
    isolated: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"universe_id": self.universe_id, "provider": self.provider, "model": self.model, "context": dict(self.context), "isolated": self.isolated, "created_at": self.created_at}


@dataclass(frozen=True)
class RuntimeSandbox:
    sandbox_id: str
    universe_id: str
    permissions: list[str] = field(default_factory=list)
    snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"sandbox_id": self.sandbox_id, "universe_id": self.universe_id, "permissions": list(self.permissions), "snapshot": dict(self.snapshot)}


class RuntimeVirtualizationEngine:
    def create_universe(self, provider: str, model: str, *, context: dict[str, Any] | None = None, isolated: bool = True) -> RuntimeUniverse:
        universe = RuntimeUniverse(uuid.uuid4().hex, provider, model, dict(context or {}), isolated)
        publish_event(AIEventType.RUNTIME_VIRTUALIZED, {"universe": universe.to_dict()}, source="core.runtime_virtualization")
        return universe

    def snapshot(self, universe: RuntimeUniverse, *, permissions: list[str] | None = None) -> RuntimeSandbox:
        sandbox = RuntimeSandbox(uuid.uuid4().hex, universe.universe_id, list(permissions or []), universe.to_dict())
        publish_event(AIEventType.RUNTIME_VIRTUALIZED, {"snapshot": sandbox.to_dict()}, source="core.runtime_virtualization")
        return sandbox

    def clone(self, universe: RuntimeUniverse, *, context_updates: dict[str, Any] | None = None) -> RuntimeUniverse:
        clone = RuntimeUniverse(uuid.uuid4().hex, universe.provider, universe.model, {**universe.context, **dict(context_updates or {})}, universe.isolated)
        publish_event(AIEventType.RUNTIME_VIRTUALIZED, {"clone": clone.to_dict(), "source": universe.universe_id}, source="core.runtime_virtualization")
        return clone

