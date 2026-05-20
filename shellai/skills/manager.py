from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from shellai.config import ShellAIConfig
from shellai.memory import MemoryStore
from shellai.observability import RequestTrace, get_logger

from .schema import SkillDefinition, SkillValidationError


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "").strip().lower()).strip("_")
    return slug[:80] or "skill"


def _infer_tags(commands: list[str], task_description: str) -> list[str]:
    blob = "\n".join(commands + [task_description]).lower()
    tags: list[str] = []
    checks = {
        "git": ("git ", "git-", "git_"),
        "python": ("python", "pip ", "pytest", "venv"),
        "node": ("npm ", "node ", "pnpm ", "yarn "),
        "android_adb": ("adb ", "android", "gradle", "./gradlew"),
        "vscode": ("code ", "vscode"),
        "browser": ("http://", "https://", "browser"),
        "file": ("mkdir", "touch", "cp ", "mv "),
        "shell": ("",),
    }
    for tag, needles in checks.items():
        if tag == "shell" or any(needle in blob for needle in needles):
            tags.append(tag)
    return sorted(set(tags))


class SkillManager:
    """File-backed skill manager with SkillMemory integration."""

    def __init__(
        self,
        config: ShellAIConfig | None = None,
        memory_store: MemoryStore | None = None,
        skills_dir: str | Path | None = None,
    ) -> None:
        self.config = config or ShellAIConfig.load()
        self.skills_dir = Path(skills_dir).expanduser() if skills_dir else self.config.paths.skills_dir
        self.manual_dir = self.skills_dir / "manual"
        self.auto_dir = self.skills_dir / "auto"
        self.memory = memory_store or MemoryStore(self.config.paths.memory_db, config=self.config)
        self.logger = get_logger("shellai.skills")
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        self.manual_dir.mkdir(parents=True, exist_ok=True)
        self.auto_dir.mkdir(parents=True, exist_ok=True)

    def _skill_files(self) -> list[Path]:
        self.ensure_dirs()
        files = list(self.manual_dir.glob("*.json")) + list(self.auto_dir.glob("*.json"))
        return sorted(files)

    def load_all_skills(self, *, register: bool = True) -> list[SkillDefinition]:
        skills: list[SkillDefinition] = []
        for path in self._skill_files():
            skill = SkillDefinition.from_file(path)
            skills.append(skill)
            if register:
                self._register_skill_memory(skill)
        return skills

    def _register_skill_memory(self, skill: SkillDefinition) -> None:
        metadata = {
            **dict(skill.metadata),
            "version": skill.version,
            "tags": list(skill.tags),
            "tools": list(skill.tools),
            "inputs": dict(skill.inputs),
            "source_path": skill.source_path,
        }
        self.memory.save_memory(
            "skill",
            {
                "skill_id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "metadata": metadata,
            },
        )

    def get_skill_by_id(self, skill_id: str) -> SkillDefinition | None:
        key = str(skill_id or "").strip()
        for skill in self.load_all_skills(register=True):
            if skill.id == key or skill.name == key:
                return skill
        return None

    def list_skills(
        self,
        *,
        tag: str | None = None,
        query: str | None = None,
        register: bool = True,
    ) -> list[dict[str, Any]]:
        tag_value = str(tag or "").strip().lower()
        query_value = str(query or "").strip().lower()
        rows: list[dict[str, Any]] = []
        for skill in self.load_all_skills(register=register):
            if tag_value and tag_value not in {item.lower() for item in skill.tags}:
                continue
            if query_value:
                haystack = " ".join([skill.id, skill.name, skill.description, " ".join(skill.tags)]).lower()
                if query_value not in haystack:
                    continue
            memory_skill = self.memory.get_skill(skill.id) or {}
            rows.append(
                {
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "version": skill.version,
                    "tags": list(skill.tags),
                    "tools": list(skill.tools),
                    "usage_count": int(memory_skill.get("success_count") or 0) + int(memory_skill.get("failure_count") or 0),
                    "success_count": int(memory_skill.get("success_count") or 0),
                    "failure_count": int(memory_skill.get("failure_count") or 0),
                    "source_path": skill.source_path,
                }
            )
        return rows

    def create_skill_from_definition(
        self,
        definition: dict[str, Any],
        *,
        auto: bool = False,
        overwrite: bool = False,
        trace: RequestTrace | None = None,
    ) -> SkillDefinition:
        skill = SkillDefinition.from_dict(definition)
        target_dir = self.auto_dir if auto else self.manual_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{_slugify(skill.id)}.json"
        if path.exists() and not overwrite:
            raise FileExistsError(f"Skill already exists: {path}")
        data = skill.to_dict()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
        saved = SkillDefinition.from_file(path)
        self._register_skill_memory(saved)
        if trace is not None:
            trace.add_step(
                "SkillManager",
                "ok",
                "created skill",
                {"skill_id": saved.id, "auto": auto, "path": str(path)},
            )
        return saved

    def delete_skill(self, skill_id: str, *, trace: RequestTrace | None = None) -> bool:
        skill = self.get_skill_by_id(skill_id)
        if not skill or not skill.source_path:
            return False
        path = Path(skill.source_path)
        if path.exists():
            path.unlink()
        self.memory.save_memory(
            "skill",
            {
                "skill_id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "metadata": {**dict(skill.metadata), "deleted": True, "deleted_at": time.time()},
            },
        )
        if trace is not None:
            trace.add_step("SkillManager", "ok", "deleted skill", {"skill_id": skill.id})
        return True

    def create_auto_skill_draft(
        self,
        *,
        task_description: str,
        commands: list[str],
        final_summary: str = "",
        trace: RequestTrace | None = None,
    ) -> SkillDefinition:
        if not task_description.strip():
            raise ValueError("task_description is required")
        clean_commands = [str(command).strip() for command in commands if str(command).strip()]
        if not clean_commands:
            raise ValueError("At least one command is required")
        slug = _slugify(task_description)
        skill_id = f"auto_{slug}_{uuid.uuid4().hex[:8]}"
        tags = _infer_tags(clean_commands, task_description)
        tools = sorted({"shell", *("file" for command in clean_commands if any(token in command for token in ("mkdir", "touch", "cp ", "mv ")))})
        definition = {
            "id": skill_id,
            "name": slug.replace("_", " ").title(),
            "description": final_summary or task_description.strip(),
            "version": "0.1.0",
            "tags": tags,
            "inputs": {
                "working_dir": {
                    "type": "string",
                    "description": "Directory where the workflow should run.",
                    "optional": True,
                    "default": ".",
                }
            },
            "outputs": "A repeatable workflow result matching the original successful task.",
            "preconditions": ["Review generated commands before execution in a new project."],
            "postconditions": ["Workflow commands have completed or produced clear errors."],
            "tools": tools,
            "steps": [
                {
                    "description": f"Run command: {command}",
                    "command": command,
                }
                for command in clean_commands
            ],
            "safety": {
                "risk": "review_required",
                "requires_confirmation": True,
                "notes": "Auto-generated draft from a previous successful task.",
            },
            "metadata": {
                "is_draft": True,
                "generated_from": "task_and_commands",
                "task_description": task_description.strip(),
                "created_at": time.time(),
            },
        }
        return self.create_skill_from_definition(definition, auto=True, overwrite=False, trace=trace)

    def record_skill_usage(self, skill_id: str, success: bool, duration_ms: int | None = None) -> dict[str, Any]:
        return self.memory.record_skill_usage(skill_id, success=success, duration_ms=duration_ms)
