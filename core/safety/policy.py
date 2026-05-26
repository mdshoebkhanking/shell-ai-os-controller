from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ActionClass(str, Enum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    DANGEROUS = "DANGEROUS"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class SafetyDecision:
    action_class: ActionClass
    allowed: bool
    requires_confirmation: bool
    reasons: list[str] = field(default_factory=list)
    required_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_class": self.action_class.value,
            "allowed": self.allowed,
            "requires_confirmation": self.requires_confirmation,
            "reasons": list(self.reasons),
            "required_flags": list(self.required_flags),
        }


class SafetyPolicy:
    def __init__(self, audit_path: str | Path = ".shell_safety_phase2_audit.log"):
        self.audit_path = Path(audit_path)

    def classify(self, action: str, metadata: dict[str, Any] | None = None) -> SafetyDecision:
        text = f"{action} {json.dumps(metadata or {}, default=str)}".lower()
        reasons: list[str] = []
        flags: list[str] = []
        action_class = ActionClass.SAFE

        if any(word in text for word in ("registry", "format disk", "delete system", "rm -rf", "wipe", "shutdown")):
            action_class = ActionClass.CRITICAL
            reasons.append("critical system mutation")
        elif any(word in text for word in ("terminal", "powershell", "shell", "execute", "command")):
            action_class = ActionClass.DANGEROUS
            reasons.append("command execution; destructive patterns remain blocked at runtime")
        elif any(word in text for word in ("hotpatch", "self_patch", "agent_patch")):
            action_class = ActionClass.DANGEROUS
            flags.append("SHELL_ALLOW_CODE_WRITE")
            reasons.append("core/runtime mutation")
        elif any(word in text for word in ("write_code", "workflow")):
            action_class = ActionClass.CAUTION
            reasons.append("managed workspace mutation")
        elif any(word in text for word in ("send_email", "whatsapp", "telegram", "post", "upload")):
            action_class = ActionClass.CAUTION
            reasons.append("external communication")

        missing = [flag for flag in flags if str(os.environ.get(flag, "")).lower() not in {"1", "true", "yes", "on"}]
        allowed = action_class in {ActionClass.SAFE, ActionClass.CAUTION, ActionClass.DANGEROUS} and not missing
        requires_confirmation = action_class in {ActionClass.CAUTION, ActionClass.DANGEROUS, ActionClass.CRITICAL}
        if missing:
            reasons.append(f"missing safety flag(s): {', '.join(missing)}")
        if action_class == ActionClass.CRITICAL:
            allowed = False
        return SafetyDecision(action_class, allowed, requires_confirmation, reasons, flags)

    def audit(self, action: str, decision: SafetyDecision, metadata: dict[str, Any] | None = None) -> None:
        row = {
            "ts": time.time(),
            "action": action,
            "decision": decision.to_dict(),
            "metadata": dict(metadata or {}),
        }
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
