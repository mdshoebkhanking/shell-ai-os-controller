from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ManifestValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ExtensionManifest:
    name: str
    version: str
    shell_api: str
    kind: str
    entrypoint: str
    permissions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    sandbox: dict[str, Any] = field(default_factory=dict)

    VALID_KINDS = {"tool", "agent", "workflow", "ui_panel", "provider", "automation_pack"}
    VALID_PERMISSIONS = {
        "filesystem.read",
        "filesystem.write",
        "network",
        "desktop.control",
        "shell.execute",
        "api.keys",
        "api.external",
        "events.publish",
        "events.subscribe",
        "workflow.run",
        "memory.read",
        "memory.write",
        "cloud.sync",
        "cloud.execute",
        "profile.read",
        "profile.write",
        "workspace.sync",
        "agent.spawn",
        "agent.delegate",
        "automation.share",
        "marketplace.publish",
        "marketplace.install",
        "multimodal.capture",
    }

    @classmethod
    def from_file(cls, path: str | Path) -> "ExtensionManifest":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExtensionManifest":
        manifest = cls(
            name=str(data.get("name") or ""),
            version=str(data.get("version") or ""),
            shell_api=str(data.get("shell_api") or ""),
            kind=str(data.get("kind") or ""),
            entrypoint=str(data.get("entrypoint") or ""),
            permissions=list(data.get("permissions") or []),
            dependencies=list(data.get("dependencies") or []),
            sandbox=dict(data.get("sandbox") or {}),
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if not self.name or not self.version or not self.shell_api or not self.entrypoint:
            raise ManifestValidationError("manifest requires name, version, shell_api, and entrypoint")
        if self.kind not in self.VALID_KINDS:
            raise ManifestValidationError(f"invalid extension kind: {self.kind}")
        invalid = sorted(set(self.permissions) - self.VALID_PERMISSIONS)
        if invalid:
            raise ManifestValidationError(f"invalid permission(s): {', '.join(invalid)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "shell_api": self.shell_api,
            "kind": self.kind,
            "entrypoint": self.entrypoint,
            "permissions": list(self.permissions),
            "dependencies": list(self.dependencies),
            "sandbox": dict(self.sandbox),
        }
