from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event


class ContextLayer(str, Enum):
    ACTIVE_CONTEXT = "ACTIVE_CONTEXT"
    WORKING_CONTEXT = "WORKING_CONTEXT"
    LONG_TERM_CONTEXT = "LONG_TERM_CONTEXT"
    SESSION_CONTEXT = "SESSION_CONTEXT"


@dataclass(frozen=True)
class ContextItem:
    item_id: str
    layer: ContextLayer
    key: str
    value: Any
    priority: float = 0.5
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    source: str = "unknown"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "layer": self.layer.value,
            "key": self.key,
            "value": self.value,
            "priority": self.priority,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "source": self.source,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class ContextSnapshot:
    snapshot_id: str
    generated_at: float
    items: list[ContextItem]
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items],
        }


class ContextEngine:
    """Local-first context store with expiration, priority, and compression."""

    def __init__(self, path: str | Path = ".shell_context.json"):
        self.path = Path(path)
        self._items: dict[str, ContextItem] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for row in data.get("items", []):
                layer = ContextLayer(row.get("layer", ContextLayer.SESSION_CONTEXT.value))
                item = ContextItem(
                    item_id=str(row.get("item_id") or uuid.uuid4().hex),
                    layer=layer,
                    key=str(row.get("key") or ""),
                    value=row.get("value"),
                    priority=float(row.get("priority", 0.5)),
                    created_at=float(row.get("created_at", time.time())),
                    expires_at=float(row.get("expires_at", 0.0)),
                    source=str(row.get("source") or "unknown"),
                    tags=list(row.get("tags") or []),
                )
                self._items[item.item_id] = item
        except Exception:
            self._items = {}

    def _write(self) -> None:
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        data = {"items": [item.to_dict() for item in self._items.values()]}
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def update(
        self,
        layer: ContextLayer | str,
        key: str,
        value: Any,
        *,
        priority: float = 0.5,
        ttl_s: float = 0.0,
        source: str = "runtime",
        tags: list[str] | None = None,
    ) -> ContextItem:
        layer_enum = layer if isinstance(layer, ContextLayer) else ContextLayer(str(layer))
        now = time.time()
        existing_id = ""
        for item in self._items.values():
            if item.layer == layer_enum and item.key == key:
                existing_id = item.item_id
                break
        item = ContextItem(
            item_id=existing_id or uuid.uuid4().hex,
            layer=layer_enum,
            key=str(key),
            value=value,
            priority=max(0.0, min(1.0, float(priority))),
            created_at=now,
            expires_at=now + float(ttl_s) if ttl_s else 0.0,
            source=source,
            tags=list(tags or []),
        )
        self._items[item.item_id] = item
        self._write()
        publish_event(AIEventType.CONTEXT_UPDATED, item.to_dict(), source="core.context")
        return item

    def expire(self, now: float | None = None) -> int:
        current = time.time() if now is None else float(now)
        expired = [
            item_id for item_id, item in self._items.items()
            if item.expires_at and item.expires_at <= current
        ]
        for item_id in expired:
            self._items.pop(item_id, None)
        if expired:
            self._write()
        return len(expired)

    def snapshot(self, *, max_items: int = 40) -> ContextSnapshot:
        self.expire()
        items = sorted(
            self._items.values(),
            key=lambda item: (item.priority, item.created_at),
            reverse=True,
        )[: max(0, int(max_items))]
        summary = self.compress(items)
        return ContextSnapshot(uuid.uuid4().hex, time.time(), items, summary)

    def compress(self, items: list[ContextItem] | None = None, *, max_chars: int = 1400) -> str:
        rows = items if items is not None else list(self._items.values())
        parts: list[str] = []
        for item in sorted(rows, key=lambda i: (i.layer.value, -i.priority, -i.created_at)):
            value = item.value
            if isinstance(value, (dict, list)):
                value_text = json.dumps(value, ensure_ascii=False, default=str)
            else:
                value_text = str(value)
            parts.append(f"{item.layer.value}:{item.key}={value_text}")
        text = "\n".join(parts)
        return text[:max_chars]

    def get(self, key: str, *, layer: ContextLayer | str | None = None) -> ContextItem | None:
        layer_enum = layer if isinstance(layer, ContextLayer) else (ContextLayer(str(layer)) if layer else None)
        self.expire()
        matches = [
            item for item in self._items.values()
            if item.key == key and (layer_enum is None or item.layer == layer_enum)
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: (item.priority, item.created_at))

    def collect_environment(self, cwd: str | Path | None = None) -> ContextSnapshot:
        try:
            from core.workspace import WorkspaceDetector

            workspace = WorkspaceDetector().detect(cwd or Path.cwd())
            self.update(ContextLayer.ACTIVE_CONTEXT, "workspace", workspace.to_dict(), priority=0.9, source="workspace")
        except Exception as exc:
            self.update(ContextLayer.SESSION_CONTEXT, "workspace_error", str(exc), priority=0.3, ttl_s=300, source="workspace")
        return self.snapshot()

