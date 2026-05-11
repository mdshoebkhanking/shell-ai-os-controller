from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class KnowledgeSourceType(str, Enum):
    DOCS = "docs"
    CODE = "code"
    WORKFLOW = "workflow"
    API = "api"
    LOG = "log"
    MEMORY = "memory"
    BROWSER = "browser"
    LOCAL = "local"


@dataclass(frozen=True)
class KnowledgeItem:
    item_id: str
    source_type: KnowledgeSourceType
    title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "source_type": self.source_type.value,
            "title": self.title,
            "text": self.text,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class KnowledgeEdge:
    source_id: str
    target_id: str
    relation: str
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "target_id": self.target_id, "relation": self.relation, "confidence": self.confidence}


class KnowledgeFabric:
    def __init__(self):
        self._items: dict[str, KnowledgeItem] = {}
        self._edges: list[KnowledgeEdge] = []

    def add_item(self, source_type: KnowledgeSourceType | str, title: str, text: str, metadata: dict[str, Any] | None = None) -> KnowledgeItem:
        source = source_type if isinstance(source_type, KnowledgeSourceType) else KnowledgeSourceType(str(source_type))
        item = KnowledgeItem(uuid.uuid4().hex, source, title, text, dict(metadata or {}))
        self._items[item.item_id] = item
        return item

    def link(self, source_id: str, target_id: str, relation: str, *, confidence: float = 0.5) -> KnowledgeEdge:
        edge = KnowledgeEdge(source_id, target_id, relation, max(0.0, min(1.0, float(confidence))))
        self._edges.append(edge)
        publish_event(AIEventType.KNOWLEDGE_LINKED, edge.to_dict(), source="core.knowledge")
        return edge

    def retrieve(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        tokens = {token.lower() for token in str(query or "").split() if token.strip()}
        rows: list[dict[str, Any]] = []
        for item in self._items.values():
            hay = f"{item.title} {item.text} {item.metadata}".lower()
            score = sum(1 for token in tokens if token in hay)
            if tokens and score <= 0:
                continue
            row = item.to_dict()
            row["score"] = score
            row["edges"] = [edge.to_dict() for edge in self._edges if edge.source_id == item.item_id or edge.target_id == item.item_id]
            rows.append(row)
        rows.sort(key=lambda row: (row["score"], row["created_at"]), reverse=True)
        return rows[: max(0, int(limit))]

    def summarize(self) -> dict[str, Any]:
        by_source: dict[str, int] = {}
        for item in self._items.values():
            by_source[item.source_type.value] = by_source.get(item.source_type.value, 0) + 1
        return {"items": len(self._items), "edges": len(self._edges), "by_source": by_source}

