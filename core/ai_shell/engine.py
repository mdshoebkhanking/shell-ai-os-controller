from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class ShellIntentPlan:
    plan_id: str
    intent: str
    commands: list[str] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)
    dry_run: bool = True
    requires_confirmation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "intent": self.intent,
            "commands": list(self.commands),
            "explanations": list(self.explanations),
            "dry_run": self.dry_run,
            "requires_confirmation": self.requires_confirmation,
        }


class AIShellEngine:
    def plan(self, command: str, *, project_summary: dict[str, Any] | None = None) -> ShellIntentPlan:
        text = str(command or "").lower()
        commands: list[str] = []
        explanations: list[str] = []
        if "clean" in text and "project" in text:
            commands.extend(["git status", "find . -name '__pycache__' -type d", "find . -name '.pytest_cache' -type d"])
            explanations.append("inspect cache/build artifacts before any removal")
        elif "test" in text:
            commands.append("pytest -q")
            explanations.append("run the configured test suite")
        elif "status" in text:
            commands.append("git status")
            explanations.append("inspect repository state")
        else:
            commands.append("# no shell command selected")
            explanations.append("intent needs clarification before shell execution")
        plan = ShellIntentPlan(uuid.uuid4().hex, command, commands, explanations, True, True)
        publish_event(AIEventType.AI_SHELL_PLAN_CREATED, {"plan": plan.to_dict(), "project_summary": project_summary or {}}, source="core.ai_shell")
        return plan

