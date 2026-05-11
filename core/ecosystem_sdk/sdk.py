from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event
from sdk import ExtensionManifest


@dataclass(frozen=True)
class EcosystemSDKValidation:
    ok: bool
    kind: str
    lifecycle_hooks: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "kind": self.kind, "lifecycle_hooks": list(self.lifecycle_hooks), "reasons": list(self.reasons)}


class EcosystemSDK:
    REQUIRED_HOOKS = {
        "tool": {"activate"},
        "provider": {"activate", "health"},
        "workflow": {"activate", "validate"},
        "agent": {"activate", "shutdown"},
        "automation_pack": {"activate", "validate", "shutdown"},
        "ui_panel": {"activate"},
    }

    def validate_manifest(self, manifest: ExtensionManifest, *, hooks: list[str] | None = None) -> EcosystemSDKValidation:
        present = set(hooks or [])
        required = self.REQUIRED_HOOKS.get(manifest.kind, {"activate"})
        missing = sorted(required - present)
        reasons = [f"missing hook: {hook}" for hook in missing]
        if "shell.execute" in manifest.permissions:
            reasons.append("shell.execute requires sandbox integration")
        result = EcosystemSDKValidation(not reasons, manifest.kind, sorted(present), reasons)
        publish_event(AIEventType.ECOSYSTEM_SDK_VALIDATED, {"manifest": manifest.to_dict(), "validation": result.to_dict()}, source="core.ecosystem_sdk")
        return result

    def scaffold_contract(self, kind: str) -> dict[str, Any]:
        hooks = sorted(self.REQUIRED_HOOKS.get(kind, {"activate"}))
        return {"kind": kind, "required_hooks": hooks, "governance_required": True, "sandbox_required": kind in {"tool", "automation_pack", "provider"}}

