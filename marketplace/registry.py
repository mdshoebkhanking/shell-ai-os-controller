from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event
from core.security import SecurityModel
from sdk import ExtensionManifest


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    digest: str
    reasons: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "digest": self.digest, "reasons": list(self.reasons), "permissions": list(self.permissions)}


@dataclass(frozen=True)
class PluginInstallRecord:
    name: str
    version: str
    manifest: dict[str, Any]
    verification: dict[str, Any]
    installed_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version, "manifest": dict(self.manifest), "verification": dict(self.verification), "installed_at": self.installed_at}


class MarketplaceRegistry:
    def __init__(self, path: str | Path = ".shell_runtime/marketplace.json"):
        self.path = Path(path)

    def verify_manifest(self, manifest: ExtensionManifest, *, expected_digest: str = "") -> VerificationResult:
        payload = json.dumps(manifest.to_dict(), sort_keys=True, ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        reasons: list[str] = []
        security = SecurityModel().classify("plugin install", {"permissions": manifest.permissions})
        if not security.allowed:
            reasons.extend(security.reasons)
        if expected_digest and expected_digest != digest:
            reasons.append("digest mismatch")
        ok = not reasons
        result = VerificationResult(ok, digest, reasons, manifest.permissions)
        publish_event(AIEventType.PLUGIN_VERIFIED, result.to_dict(), source="marketplace")
        return result

    def install(self, manifest: ExtensionManifest, verification: VerificationResult) -> PluginInstallRecord:
        if not verification.ok:
            raise PermissionError("plugin verification failed")
        data = self._load()
        record = PluginInstallRecord(manifest.name, manifest.version, manifest.to_dict(), verification.to_dict())
        data.setdefault("plugins", {})[manifest.name] = record.to_dict()
        self._write(data)
        return record

    def list(self) -> list[dict[str, Any]]:
        return list((self._load().get("plugins") or {}).values())

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"plugins": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"plugins": {}}
        except Exception:
            return {"plugins": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

