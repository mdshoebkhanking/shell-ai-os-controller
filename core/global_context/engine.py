from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class GlobalContextRecord:
    context_id: str
    scope: str
    payload: dict[str, Any]
    version: int = 1
    encrypted: bool = True
    updated_at: float = field(default_factory=time.time)
    source_node: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"context_id": self.context_id, "scope": self.scope, "payload": dict(self.payload), "version": self.version, "encrypted": self.encrypted, "updated_at": self.updated_at, "source_node": self.source_node}


class GlobalContextEngine:
    def __init__(self):
        self._records: dict[str, GlobalContextRecord] = {}

    def update(self, scope: str, payload: dict[str, Any], *, source_node: str = "", version: int = 1, encrypted: bool = True) -> GlobalContextRecord:
        record = GlobalContextRecord(uuid.uuid4().hex, scope, dict(payload), version, encrypted, time.time(), source_node)
        self._records[scope] = record
        publish_event(AIEventType.GLOBAL_CONTEXT_SYNCED, {"record": record.to_dict()}, source="core.global_context")
        return record

    def reconcile(self, local: GlobalContextRecord | None, remote: GlobalContextRecord) -> dict[str, Any]:
        if not remote.encrypted:
            result = {"accepted": local.to_dict() if local else None, "conflict": True, "reason": "remote context not encrypted"}
        elif not local or remote.version >= local.version:
            result = {"accepted": remote.to_dict(), "conflict": bool(local and local.payload != remote.payload), "reason": "accepted encrypted newer context"}
            self._records[remote.scope] = remote
        else:
            result = {"accepted": local.to_dict(), "conflict": False, "reason": "kept local context"}
        publish_event(AIEventType.GLOBAL_CONTEXT_SYNCED, {"reconcile": result}, source="core.global_context")
        return result

    def checkpoint(self, workflow_id: str) -> dict[str, Any]:
        snapshot = {"workflow_id": workflow_id, "records": {scope: record.to_dict() for scope, record in self._records.items()}, "encrypted": True}
        publish_event(AIEventType.GLOBAL_CONTEXT_SYNCED, {"checkpoint": snapshot}, source="core.global_context")
        return snapshot

