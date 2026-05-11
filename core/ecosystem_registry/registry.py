from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class RegistryItem:
    item_id: str
    item_type: str
    name: str
    capabilities: list[str] = field(default_factory=list)
    trust_score: float = 0.5
    compatibility: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"item_id": self.item_id, "item_type": self.item_type, "name": self.name, "capabilities": list(self.capabilities), "trust_score": self.trust_score, "compatibility": list(self.compatibility), "metadata": dict(self.metadata)}


class EcosystemRegistry:
    def __init__(self):
        self._items: dict[str, RegistryItem] = {}

    def register(self, item_type: str, name: str, *, capabilities: list[str] | None = None, trust_score: float = 0.5, compatibility: list[str] | None = None, metadata: dict[str, Any] | None = None) -> RegistryItem:
        item = RegistryItem(uuid.uuid4().hex, item_type, name, list(capabilities or []), max(0.0, min(1.0, float(trust_score))), list(compatibility or []), dict(metadata or {}))
        self._items[item.item_id] = item
        publish_event(AIEventType.ECOSYSTEM_REGISTRY_UPDATED, {"registered": item.to_dict()}, source="core.ecosystem_registry")
        return item

    def find_by_capability(self, capability: str, *, min_trust: float = 0.0) -> list[RegistryItem]:
        rows = [item for item in self._items.values() if capability in item.capabilities and item.trust_score >= min_trust]
        rows.sort(key=lambda item: item.trust_score, reverse=True)
        return rows

    def compatibility_report(self, item_id: str, target_version: str) -> dict[str, Any]:
        item = self._items.get(item_id)
        ok = bool(item and (not item.compatibility or target_version in item.compatibility))
        report = {"item_id": item_id, "target_version": target_version, "compatible": ok}
        publish_event(AIEventType.ECOSYSTEM_REGISTRY_UPDATED, {"compatibility": report}, source="core.ecosystem_registry")
        return report

