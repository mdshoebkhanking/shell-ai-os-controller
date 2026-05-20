from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class SkillValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: str | dict[str, Any] | None = None
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    safety: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""

    REQUIRED_FIELDS = ("id", "name", "description", "steps")

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, source_path: str = "") -> "SkillDefinition":
        if not isinstance(data, dict):
            raise SkillValidationError("Skill definition must be a JSON object")
        for field_name in cls.REQUIRED_FIELDS:
            if field_name not in data:
                raise SkillValidationError(f"Skill missing required field: {field_name}")
        if not isinstance(data.get("steps"), list) or not data.get("steps"):
            raise SkillValidationError("Skill field 'steps' must be a non-empty list")
        if not isinstance(data.get("id"), str) or not data["id"].strip():
            raise SkillValidationError("Skill field 'id' must be a non-empty string")
        if not isinstance(data.get("name"), str) or not data["name"].strip():
            raise SkillValidationError("Skill field 'name' must be a non-empty string")

        return cls(
            id=str(data["id"]).strip(),
            name=str(data["name"]).strip(),
            description=str(data.get("description") or "").strip(),
            version=str(data.get("version") or "1.0.0").strip(),
            tags=[str(item).strip() for item in data.get("tags", []) if str(item).strip()],
            inputs=dict(data.get("inputs") or {}),
            outputs=data.get("outputs"),
            preconditions=[str(item) for item in data.get("preconditions", [])],
            postconditions=[str(item) for item in data.get("postconditions", [])],
            tools=[str(item).strip() for item in data.get("tools", []) if str(item).strip()],
            steps=[dict(step) if isinstance(step, dict) else {"description": str(step)} for step in data.get("steps", [])],
            safety=dict(data.get("safety") or {}),
            metadata=dict(data.get("metadata") or {}),
            source_path=str(source_path or ""),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "SkillDefinition":
        skill_path = Path(path)
        data = json.loads(skill_path.read_text(encoding="utf-8"))
        return cls.from_dict(data, source_path=str(skill_path))

    def to_dict(self, *, include_source_path: bool = False) -> dict[str, Any]:
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tags": list(self.tags),
            "inputs": dict(self.inputs),
            "outputs": self.outputs,
            "preconditions": list(self.preconditions),
            "postconditions": list(self.postconditions),
            "tools": list(self.tools),
            "steps": [dict(step) for step in self.steps],
            "safety": dict(self.safety),
            "metadata": dict(self.metadata),
        }
        if include_source_path:
            data["source_path"] = self.source_path
        return data
