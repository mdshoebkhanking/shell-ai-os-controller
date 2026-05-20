from __future__ import annotations

import json

import pytest


def _manager(tmp_path):
    from shellai.memory import MemoryStore
    from shellai.skills import SkillManager

    memory = MemoryStore(tmp_path / "memory.sqlite3")
    return SkillManager(memory_store=memory, skills_dir=tmp_path / "skills")


def test_skill_schema_validation_failure_modes() -> None:
    from shellai.skills import SkillDefinition, SkillValidationError

    with pytest.raises(SkillValidationError):
        SkillDefinition.from_dict({"id": "missing_steps", "name": "Bad", "description": "Bad"})

    with pytest.raises(SkillValidationError):
        SkillDefinition.from_dict({"id": "", "name": "Bad", "description": "Bad", "steps": ["one"]})


def test_skill_create_list_and_fetch_registers_memory(tmp_path) -> None:
    manager = _manager(tmp_path)
    skill = manager.create_skill_from_definition(
        {
            "id": "git_status_review",
            "name": "Git Status Review",
            "description": "Review repo changes.",
            "version": "1.0.0",
            "tags": ["git"],
            "inputs": {"repo": {"type": "string"}},
            "tools": ["shell"],
            "steps": [{"description": "Check status", "command": "git status"}],
        }
    )

    assert skill.id == "git_status_review"
    listed = manager.list_skills(tag="git")
    assert listed[0]["id"] == "git_status_review"

    loaded = manager.get_skill_by_id("git_status_review")
    assert loaded is not None
    assert loaded.name == "Git Status Review"

    memory_skill = manager.memory.get_skill("git_status_review")
    assert memory_skill is not None
    assert memory_skill["metadata"]["tags"] == ["git"]


def test_auto_skill_draft_creation_from_task_and_commands(tmp_path) -> None:
    manager = _manager(tmp_path)
    draft = manager.create_auto_skill_draft(
        task_description="Check git status before committing",
        commands=["git status", "git diff --stat"],
        final_summary="Review git state before commit.",
    )

    assert draft.id.startswith("auto_check_git_status_before_committing_")
    assert "git" in draft.tags
    assert draft.metadata["is_draft"] is True
    assert (tmp_path / "skills" / "auto").exists()

    raw = json.loads((tmp_path / "skills" / "auto" / f"{draft.id}.json").read_text(encoding="utf-8"))
    assert raw["steps"][0]["command"] == "git status"

    memory_skill = manager.memory.get_skill(draft.id)
    assert memory_skill is not None
    assert memory_skill["metadata"]["is_draft"] is True


def test_skill_usage_tracking_via_manager(tmp_path) -> None:
    manager = _manager(tmp_path)
    skill = manager.create_skill_from_definition(
        {
            "id": "python_test",
            "name": "Python Test",
            "description": "Run tests.",
            "tags": ["python"],
            "tools": ["shell"],
            "steps": [{"description": "Run pytest", "command": "pytest"}],
        }
    )

    updated = manager.record_skill_usage(skill.id, success=True, duration_ms=50)

    assert updated["success_count"] == 1
    assert updated["failure_count"] == 0
    assert manager.list_skills(query="python")[0]["usage_count"] == 1


def test_cli_skills_list_and_show(tmp_path, monkeypatch, capsys) -> None:
    from shellai.cli import main
    from shellai.memory import MemoryStore
    from shellai.skills import SkillManager

    config_file = tmp_path / ".shellai" / "config.json"
    monkeypatch.setenv("SHELLAI_CONFIG", str(config_file))
    memory = MemoryStore(tmp_path / ".shellai" / "data" / "memory.sqlite3")
    manager = SkillManager(memory_store=memory, skills_dir=tmp_path / ".shellai" / "skills")
    manager.create_skill_from_definition(
        {
            "id": "browser_open_docs",
            "name": "Browser Open Docs",
            "description": "Open documentation.",
            "tags": ["browser"],
            "tools": ["browser"],
            "steps": [{"description": "Open docs"}],
        }
    )

    assert main(["skills", "list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["skills"][0]["id"] == "browser_open_docs"

    assert main(["skills", "show", "browser_open_docs"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["name"] == "Browser Open Docs"
