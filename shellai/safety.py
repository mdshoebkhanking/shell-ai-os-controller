from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .config import DEFAULT_RISK_POLICY


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    ASK = "ASK"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class CommandRisk:
    command: str
    level: RiskLevel
    reason: str
    matched_pattern: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed_without_confirmation(self) -> bool:
        return self.level is RiskLevel.SAFE

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "level": self.level.value,
            "reason": self.reason,
            "matched_pattern": self.matched_pattern,
            "metadata": dict(self.metadata),
        }


class ShellRiskPolicy:
    """Configurable static risk classifier for shell commands."""

    def __init__(self, policy: dict[str, Any] | None = None) -> None:
        merged = dict(DEFAULT_RISK_POLICY)
        merged.update(dict(policy or {}))
        self.default = self._parse_level(merged.get("default"), RiskLevel.ASK)
        self.safe_patterns = [str(item) for item in merged.get("safe_patterns") or []]
        self.ask_patterns = [str(item) for item in merged.get("ask_patterns") or []]
        self.block_patterns = [str(item) for item in merged.get("block_patterns") or []]

    @staticmethod
    def _parse_level(value: Any, fallback: RiskLevel) -> RiskLevel:
        try:
            return RiskLevel(str(value).upper())
        except Exception:
            return fallback

    @staticmethod
    def _first_match(command: str, patterns: list[str]) -> str:
        for pattern in patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return pattern
        return ""

    def classify(self, command: str) -> CommandRisk:
        clean = str(command or "").strip()
        if not clean:
            return CommandRisk(clean, RiskLevel.BLOCK, "empty shell command")

        pattern = self._first_match(clean, self.block_patterns)
        if pattern:
            return CommandRisk(clean, RiskLevel.BLOCK, "matches blocked destructive command policy", pattern)

        pattern = self._first_match(clean, self.ask_patterns)
        if pattern:
            return CommandRisk(clean, RiskLevel.ASK, "requires explicit confirmation by policy", pattern)

        pattern = self._first_match(clean, self.safe_patterns)
        if pattern:
            return CommandRisk(clean, RiskLevel.SAFE, "matches read-only safe command policy", pattern)

        return CommandRisk(clean, self.default, f"default policy is {self.default.value}")


__all__ = ["CommandRisk", "RiskLevel", "ShellRiskPolicy"]
