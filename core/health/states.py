from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeState(str, Enum):
    READY = "READY"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    NEEDS_API_KEY = "NEEDS_API_KEY"
    WINDOWS_ONLY = "WINDOWS_ONLY"
    BLOCKED_BY_SAFETY = "BLOCKED_BY_SAFETY"
    OFFLINE_ONLY = "OFFLINE_ONLY"
    EXPERIMENTAL = "EXPERIMENTAL"


class SafetyLevel(str, Enum):
    SAFE = "safe"
    GUARDED = "guarded"
    DANGEROUS = "dangerous"
    EXPERIMENTAL = "experimental"


@dataclass(frozen=True)
class RequirementStatus:
    name: str
    ok: bool
    state: RuntimeState
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "state": self.state.value,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ToolReadiness:
    state: RuntimeState
    ok: bool
    reasons: list[str] = field(default_factory=list)
    requirements: list[RequirementStatus] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "ok": self.ok,
            "reasons": list(self.reasons),
            "requirements": [r.to_dict() for r in self.requirements],
        }


_STATE_PRIORITY = {
    RuntimeState.BLOCKED_BY_SAFETY: 100,
    RuntimeState.WINDOWS_ONLY: 90,
    RuntimeState.MISSING_DEPENDENCY: 80,
    RuntimeState.NEEDS_API_KEY: 70,
    RuntimeState.EXPERIMENTAL: 30,
    RuntimeState.OFFLINE_ONLY: 10,
    RuntimeState.READY: 0,
}


def worst_state(states: list[RuntimeState]) -> RuntimeState:
    if not states:
        return RuntimeState.READY
    return max(states, key=lambda s: _STATE_PRIORITY.get(s, 0))

