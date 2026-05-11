from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class Suggestion:
    suggestion_id: str
    title: str
    reason: str
    command: str = ""
    confidence: float = 0.5
    category: str = "general"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "title": self.title,
            "reason": self.reason,
            "command": self.command,
            "confidence": self.confidence,
            "category": self.category,
            "created_at": self.created_at,
        }


class PredictiveEngine:
    """Non-intrusive suggestion generator."""

    def suggest(self, *, context: dict[str, Any] | None = None, health: dict[str, Any] | None = None, limit: int = 5) -> list[Suggestion]:
        context = dict(context or {})
        health = dict(health or {})
        suggestions: list[Suggestion] = []
        workspace = context.get("workspace") or context
        signals = workspace.get("signals") or {}

        if workspace.get("mode") == "coding" and "python" in set(workspace.get("languages") or []):
            if signals.get("has_requirements") or signals.get("has_pyproject"):
                suggestions.append(self._make(
                    "Python environment detected",
                    "You are in a Python project; environment setup checks may prevent dependency failures.",
                    "check dependency health",
                    0.74,
                    "workspace",
                ))
        if workspace.get("dirty_git"):
            suggestions.append(self._make(
                "Git changes detected",
                "A commit summary can help preserve session continuity.",
                "generate commit summary",
                0.72,
                "workflow",
            ))
        missing = set((health.get("summary") or {}).get("dependencies_missing") or [])
        if "ffmpeg" in missing:
            suggestions.append(self._make(
                "Video/audio tools need ffmpeg",
                "ffmpeg is missing, so media workflows may fail until installed.",
                "",
                0.86,
                "dependency",
            ))
        if "sounddevice" in missing:
            suggestions.append(self._make(
                "Voice input dependency missing",
                "The voice page can render, but microphone capture needs sounddevice.",
                "",
                0.82,
                "dependency",
            ))
        platform_info = health.get("platform") or {}
        if platform_info.get("os") and platform_info.get("os") != "windows":
            suggestions.append(self._make(
                "Windows-MCP desktop tools unavailable here",
                "Click, Type, App, Registry, and PowerShell actions require a Windows runtime.",
                "",
                0.9,
                "platform",
            ))
        out = suggestions[: max(0, int(limit))]
        for suggestion in out:
            publish_event(AIEventType.SUGGESTION_CREATED, suggestion.to_dict(), source="core.predictive")
        return out

    def _make(self, title: str, reason: str, command: str, confidence: float, category: str) -> Suggestion:
        return Suggestion(uuid.uuid4().hex, title, reason, command, confidence, category)

