from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class DistributedModuleSpec:
    name: str
    kind: str
    interfaces: list[str] = field(default_factory=list)
    governance_hooks: list[str] = field(default_factory=list)
    sandbox_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "interfaces": list(self.interfaces), "governance_hooks": list(self.governance_hooks), "sandbox_required": self.sandbox_required}


class DistributedDevPlatform:
    REQUIRED_INTERFACES = {"workflow": {"validate", "execute"}, "runtime_provider": {"health", "execute"}, "cognition_module": {"plan", "validate"}, "orchestration_pack": {"route", "recover"}}

    def validate(self, spec: DistributedModuleSpec) -> dict[str, Any]:
        required = self.REQUIRED_INTERFACES.get(spec.kind, {"activate"})
        missing = sorted(required - set(spec.interfaces))
        governance_ok = "approval" in spec.governance_hooks and "audit" in spec.governance_hooks
        ok = not missing and governance_ok and spec.sandbox_required
        result = {"ok": ok, "missing_interfaces": missing, "governance_ok": governance_ok, "sandbox_required": spec.sandbox_required, "spec": spec.to_dict()}
        publish_event(AIEventType.DISTRIBUTED_DEV_PLATFORM_VALIDATED, result, source="core.distributed_dev_platform")
        return result

    def api_contract(self, kind: str) -> dict[str, Any]:
        return {"kind": kind, "interfaces": sorted(self.REQUIRED_INTERFACES.get(kind, {"activate"})), "governance_hooks": ["approval", "audit"], "semantic_execution": True}

