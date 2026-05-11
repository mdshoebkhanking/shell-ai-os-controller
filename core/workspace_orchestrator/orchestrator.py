from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class WorkspaceApp:
    name: str
    role: str
    target: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "role": self.role, "target": self.target}


@dataclass(frozen=True)
class WorkspacePlan:
    plan_id: str
    mode: str
    project_root: str
    apps: list[WorkspaceApp] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    browser_tabs: list[str] = field(default_factory=list)
    terminal_commands: list[str] = field(default_factory=list)
    requires_confirmation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "mode": self.mode,
            "project_root": self.project_root,
            "apps": [app.to_dict() for app in self.apps],
            "files": list(self.files),
            "browser_tabs": list(self.browser_tabs),
            "terminal_commands": list(self.terminal_commands),
            "requires_confirmation": self.requires_confirmation,
        }


class WorkspaceOrchestrator:
    def plan_restore(
        self,
        mode: str,
        *,
        project_root: str = "",
        recent_files: list[str] | None = None,
        docs: list[str] | None = None,
    ) -> WorkspacePlan:
        apps = [WorkspaceApp("Shell", "control_surface")]
        terminal_commands: list[str] = []
        if mode == "coding":
            apps.extend([WorkspaceApp("VS Code", "editor", project_root), WorkspaceApp("Terminal", "shell", project_root)])
            terminal_commands.append("git status")
        if docs:
            apps.append(WorkspaceApp("Browser", "reference"))
        plan = WorkspacePlan(
            uuid.uuid4().hex,
            mode,
            project_root,
            apps,
            list(recent_files or [])[:10],
            list(docs or [])[:10],
            terminal_commands,
            True,
        )
        publish_event(AIEventType.WORKSPACE_RESTORED, {"preview": plan.to_dict()}, source="core.workspace_orchestrator")
        return plan

    def dry_run_restore(self, plan: WorkspacePlan) -> dict[str, Any]:
        return {
            "status": "preview",
            "requires_confirmation": plan.requires_confirmation,
            "actions": [
                *[{"type": "open_app", **app.to_dict()} for app in plan.apps],
                *[{"type": "open_file", "path": path} for path in plan.files],
                *[{"type": "open_tab", "url": url} for url in plan.browser_tabs],
                *[{"type": "terminal_suggestion", "command": cmd} for cmd in plan.terminal_commands],
            ],
        }

