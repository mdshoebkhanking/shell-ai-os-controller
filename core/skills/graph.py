from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class SkillNode:
    skill_id: str
    version: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    reliability_score: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "description": self.description,
            "dependencies": list(self.dependencies),
            "capabilities": list(self.capabilities),
            "reliability_score": self.reliability_score,
        }


@dataclass(frozen=True)
class SkillValidationResult:
    ok: bool
    missing_dependencies: list[str] = field(default_factory=list)
    cycle: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "missing_dependencies": list(self.missing_dependencies),
            "cycle": self.cycle,
        }


class SkillGraph:
    def __init__(self):
        self._skills: dict[str, SkillNode] = {}

    def add(self, node: SkillNode) -> None:
        self._skills[node.skill_id] = node

    def get(self, skill_id: str) -> SkillNode | None:
        return self._skills.get(skill_id)

    def validate(self, skill_id: str) -> SkillValidationResult:
        missing: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def walk(node_id: str) -> bool:
            if node_id in visiting:
                return True
            if node_id in visited:
                return False
            node = self._skills.get(node_id)
            if not node:
                missing.append(node_id)
                return False
            visiting.add(node_id)
            cycle = any(walk(dep) for dep in node.dependencies)
            visiting.remove(node_id)
            visited.add(node_id)
            return cycle

        cycle = walk(skill_id)
        result = SkillValidationResult(ok=not missing and not cycle, missing_dependencies=missing, cycle=cycle)
        publish_event(AIEventType.SKILL_VALIDATED, {"skill_id": skill_id, **result.to_dict()}, source="core.skills")
        return result

    def chain(self, target_skill: str) -> list[SkillNode]:
        ordered: list[SkillNode] = []
        seen: set[str] = set()

        def visit(skill_id: str) -> None:
            if skill_id in seen:
                return
            node = self._skills.get(skill_id)
            if not node:
                return
            for dep in node.dependencies:
                visit(dep)
            seen.add(skill_id)
            ordered.append(node)

        visit(target_skill)
        return ordered

    def score(self, skill_id: str) -> float:
        chain = self.chain(skill_id)
        if not chain:
            return 0.0
        dependency_penalty = max(0.0, 1.0 - (len(chain) - 1) * 0.05)
        reliability = sum(node.reliability_score for node in chain) / len(chain)
        return round(reliability * dependency_penalty, 3)

    def to_dict(self) -> dict[str, Any]:
        return {"skills": [node.to_dict() for node in self._skills.values()]}

