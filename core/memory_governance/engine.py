from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class MemoryPolicy:
    owner: str
    namespace: str
    allowed_nodes: list[str] = field(default_factory=list)
    encrypted: bool = True
    private: bool = True
    ttl_s: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"owner": self.owner, "namespace": self.namespace, "allowed_nodes": list(self.allowed_nodes), "encrypted": self.encrypted, "private": self.private, "ttl_s": self.ttl_s}


@dataclass(frozen=True)
class MemoryAccessDecision:
    allowed: bool
    reason: str
    requires_encryption: bool

    def to_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason, "requires_encryption": self.requires_encryption}


class MemoryGovernanceEngine:
    def evaluate(self, policy: MemoryPolicy, *, node_id: str, operation: str, encrypted: bool = True) -> MemoryAccessDecision:
        if policy.encrypted and not encrypted:
            decision = MemoryAccessDecision(False, "memory namespace requires encryption", True)
        elif policy.private and node_id not in policy.allowed_nodes and node_id != policy.owner:
            decision = MemoryAccessDecision(False, "node is outside memory boundary", policy.encrypted)
        elif operation not in {"read", "write", "replicate", "delete"}:
            decision = MemoryAccessDecision(False, "unsupported memory operation", policy.encrypted)
        else:
            decision = MemoryAccessDecision(True, "memory access allowed by policy", policy.encrypted)
        publish_event(AIEventType.MEMORY_GOVERNANCE_DECISION, {"policy": policy.to_dict(), "node_id": node_id, "operation": operation, "decision": decision.to_dict()}, source="core.memory_governance")
        return decision

    def lifecycle_action(self, policy: MemoryPolicy) -> dict[str, Any]:
        action = "expire" if policy.ttl_s > 0 else "retain"
        return {"namespace": policy.namespace, "action": action, "owner": policy.owner}

