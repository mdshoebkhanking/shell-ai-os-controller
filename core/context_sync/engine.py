from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class SyncEnvelope:
    envelope_id: str
    device_id: str
    key: str
    payload: dict[str, Any]
    version: int = 1
    encrypted: bool = True
    trust_score: float = 0.5
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "device_id": self.device_id,
            "key": self.key,
            "payload": dict(self.payload),
            "version": self.version,
            "encrypted": self.encrypted,
            "trust_score": self.trust_score,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class SyncResolution:
    accepted: SyncEnvelope | None
    conflict: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"accepted": self.accepted.to_dict() if self.accepted else None, "conflict": self.conflict, "reason": self.reason}


class ContextSyncEngine:
    def package(self, device_id: str, key: str, payload: dict[str, Any], *, version: int = 1, trust_score: float = 0.5, encrypted: bool = True) -> SyncEnvelope:
        envelope = SyncEnvelope(uuid.uuid4().hex, device_id, key, dict(payload), version, encrypted, max(0.0, min(1.0, float(trust_score))))
        publish_event(AIEventType.CONTEXT_SYNC_DECISION, {"package": envelope.to_dict()}, source="core.context_sync")
        return envelope

    def reconcile(self, local: SyncEnvelope | None, remote: SyncEnvelope) -> SyncResolution:
        if remote.trust_score < 0.5:
            result = SyncResolution(local, True, "remote trust below threshold")
        elif not remote.encrypted:
            result = SyncResolution(local, True, "remote payload is not encrypted")
        elif not local or remote.version > local.version or remote.updated_at > local.updated_at:
            result = SyncResolution(remote, bool(local and local.payload != remote.payload), "accepted newer trusted envelope")
        else:
            result = SyncResolution(local, False, "kept local envelope")
        publish_event(AIEventType.CONTEXT_SYNC_DECISION, result.to_dict(), source="core.context_sync")
        return result

