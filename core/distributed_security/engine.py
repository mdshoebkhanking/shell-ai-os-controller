from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class RuntimeAttestation:
    node_id: str
    runtime_id: str
    signed: bool
    sandboxed: bool
    trust_score: float = 0.5
    issued_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "runtime_id": self.runtime_id, "signed": self.signed, "sandboxed": self.sandboxed, "trust_score": self.trust_score, "issued_at": self.issued_at}


class DistributedSecurityEngine:
    def attest(self, attestation: RuntimeAttestation) -> dict[str, Any]:
        ok = attestation.signed and attestation.sandboxed and attestation.trust_score >= 0.5
        result = {"ok": ok, "attestation": attestation.to_dict(), "reason": "valid signed sandboxed runtime" if ok else "runtime attestation failed"}
        publish_event(AIEventType.DISTRIBUTED_SECURITY_DECISION, result, source="core.distributed_security")
        return result

    def validate_channel(self, source: str, target: str, *, encrypted: bool, trust_score: float) -> dict[str, Any]:
        ok = encrypted and trust_score >= 0.5
        result = {"source": source, "target": target, "ok": ok, "encrypted": encrypted, "trust_score": trust_score}
        publish_event(AIEventType.DISTRIBUTED_SECURITY_DECISION, {"channel": result}, source="core.distributed_security")
        return result

    def anomaly_score(self, telemetry: dict[str, Any]) -> float:
        failures = float(telemetry.get("failures", 0.0) or 0.0)
        denied = float(telemetry.get("denied", 0.0) or 0.0)
        total = max(1.0, float(telemetry.get("total", 1.0) or 1.0))
        score = min(1.0, (failures + denied * 1.5) / total)
        publish_event(AIEventType.DISTRIBUTED_SECURITY_DECISION, {"anomaly_score": score}, source="core.distributed_security")
        return round(score, 3)

