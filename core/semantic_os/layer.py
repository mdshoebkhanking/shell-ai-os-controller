from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class SemanticEntity:
    entity_id: str
    entity_type: str
    name: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "name": self.name,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SemanticWorkspace:
    workspace_id: str
    intent: str
    entities: list[SemanticEntity] = field(default_factory=list)
    workflow_state: str = "unknown"
    temporal_context: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "intent": self.intent,
            "entities": [entity.to_dict() for entity in self.entities],
            "workflow_state": self.workflow_state,
            "temporal_context": self.temporal_context,
            "created_at": self.created_at,
        }


class SemanticOperatingLayer:
    def __init__(self):
        self._workspaces: dict[str, SemanticWorkspace] = {}

    def create_workspace(
        self,
        intent: str,
        *,
        entities: list[dict[str, Any]] | None = None,
        workflow_state: str = "active",
        temporal_context: str = "",
    ) -> SemanticWorkspace:
        parsed = [
            SemanticEntity(
                entity_id=str(row.get("entity_id") or uuid.uuid4().hex),
                entity_type=str(row.get("entity_type") or row.get("type") or "unknown"),
                name=str(row.get("name") or ""),
                tags=list(row.get("tags") or []),
                metadata=dict(row.get("metadata") or {}),
            )
            for row in entities or []
        ]
        workspace = SemanticWorkspace(uuid.uuid4().hex, intent, parsed, workflow_state, temporal_context)
        self._workspaces[workspace.workspace_id] = workspace
        publish_event(AIEventType.SEMANTIC_OS_UPDATED, workspace.to_dict(), source="core.semantic_os")
        return workspace

    def group_files(self, workspace: SemanticWorkspace) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for entity in workspace.entities:
            if entity.entity_type != "file":
                continue
            key = entity.tags[0] if entity.tags else "general"
            groups.setdefault(key, []).append(entity.name)
        return groups

    def route_intent(self, intent: str, workspaces: list[SemanticWorkspace] | None = None) -> dict[str, Any]:
        candidates = workspaces or list(self._workspaces.values())
        tokens = {token.lower() for token in str(intent or "").split() if token.strip()}
        scored = []
        for workspace in candidates:
            hay = f"{workspace.intent} {workspace.workflow_state} {workspace.temporal_context} " + " ".join(
                f"{entity.name} {' '.join(entity.tags)}" for entity in workspace.entities
            )
            score = sum(1 for token in tokens if token in hay.lower())
            if "yesterday" in tokens and "yesterday" in workspace.temporal_context.lower():
                score += 2
            scored.append((score, workspace))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[0][1] if scored and scored[0][0] > 0 else None
        result = {
            "intent": intent,
            "selected_workspace": selected.to_dict() if selected else None,
            "confidence": round((scored[0][0] / max(1, len(tokens))) if scored else 0.0, 3),
        }
        publish_event(AIEventType.SEMANTIC_OS_UPDATED, {"route": result}, source="core.semantic_os")
        return result

    def reconstruction_plan(self, workspace: SemanticWorkspace) -> dict[str, Any]:
        return {
            "workspace_id": workspace.workspace_id,
            "intent": workspace.intent,
            "requires_confirmation": True,
            "restore": [
                {"type": entity.entity_type, "name": entity.name, "metadata": dict(entity.metadata)}
                for entity in workspace.entities
            ],
        }

