from __future__ import annotations

import json


def _config(tmp_path):
    from shellai.config import ShellAIConfig, ShellAIPaths

    path = tmp_path / ".shellai" / "config.json"
    config = ShellAIConfig.load(path)
    config.paths = ShellAIPaths.from_config_path(path)
    return config


def _memory_stack(tmp_path):
    from shellai.memory import MemoryStore
    from shellai.skills import SkillManager

    config = _config(tmp_path)
    memory = MemoryStore(tmp_path / "memory.sqlite3", config=config)
    skills = SkillManager(config=config, memory_store=memory, skills_dir=tmp_path / "skills")
    return config, memory, skills


def test_memory_agent_context_profile_save_and_skill_lookup(tmp_path) -> None:
    from shellai.agents_memory import MemoryAgent
    from shellai.observability import TRACE_STORE

    config, memory, skills = _memory_stack(tmp_path)
    trace = TRACE_STORE.start_trace("git status")
    skills.create_skill_from_definition(
        {
            "id": "git_status_check",
            "name": "Git Status Check",
            "description": "Check git repository status",
            "version": "1.0.0",
            "tags": ["git"],
            "inputs": {},
            "tools": ["shell"],
            "steps": [{"description": "Run git status", "command": "git status"}],
        },
        overwrite=True,
    )
    agent = MemoryAgent(config=config, memory_store=memory, skill_manager=skills, trace=trace)

    profile = agent.update_profile({"preferences": {"editor": "VS Code"}, "language_style": "Hinglish"})
    assert profile["preferences"]["editor"] == "VS Code"
    assert profile["preferences"]["language_style"] == "Hinglish"

    saved = agent.save_task_result(
        {"user_input": "git status please"},
        [{"tool": "shell", "status": "ok"}],
        {"user_summary": "Git status checked.", "memory_summary": "Checked git status."},
        "ok",
    )
    assert saved["conversation_id"] == trace.request_id

    bundle = agent.get_context_bundle("git status", {"cwd": str(tmp_path)})
    assert bundle["user_profile"]["preferences"]["editor"] == "VS Code"
    assert len(bundle["recent_tasks"]) == 1
    assert bundle["relevant_skills"][0]["id"] == "git_status_check"
    assert any(step.name == "MemoryAgent" for step in trace.steps)


class FakeRouter:
    def __init__(self, plan, summary=None):
        from shellai.models.base import ModelResponse

        self.plan = plan
        self.summary = summary or {
            "user_summary": "Fake summary for user.",
            "memory_summary": "Fake memory summary.",
        }
        self.calls = []
        self._response_cls = ModelResponse

    def complete(self, prompt, *, model_role="planning", **kwargs):
        self.calls.append({"role": model_role, "prompt": prompt})
        payload = self.plan if model_role == "planning" else self.summary
        return self._response_cls(
            text=json.dumps(payload),
            provider="fake",
            model="fake-model",
            model_role=model_role,
        )


def test_agent_runtime_single_task_keeps_old_shape_and_agent_boundaries(tmp_path) -> None:
    import platform
    from shellai.fabric import AgentRuntime

    config, memory, skills = _memory_stack(tmp_path)
    cmd = "dir" if platform.system().lower() == "windows" else "pwd"
    runtime = AgentRuntime(
        config=config,
        model_router=FakeRouter({"steps": [{"id": "pwd", "tool": "shell", "description": "pwd", "args": {"command": cmd}}]}),
        memory_store=memory,
        skill_manager=skills,
    )
    result = runtime.run_single_task("where am I?", context={"cwd": str(tmp_path)})

    assert result["status"] == "ok"
    assert result["steps"][0]["tool"] == "shell"
    assert result["cli_summary"]
    assert result["desktop_summary"]
    names = [step["name"] for step in result["trace"]["steps"]]
    assert "AgentRuntime" in names
    assert "MemoryAgent" in names
    assert "UIAgent" in names


def test_ui_agent_deterministic_language_style_formatting(tmp_path) -> None:
    from shellai.agents_ui import UIAgent

    config = _config(tmp_path)
    agent = UIAgent(config=config, model_router=FakeRouter({}))
    shaped = agent.shape_response(
        {"status": "ok", "summary": "Completed task with step statuses: shell=ok.", "steps": [{"tool": "shell", "status": "ok"}]},
        user_text="folder dikhao",
        user_profile={"preferences": {"language_style": "Hinglish Hindi + English"}},
    )

    assert "shell=ok" in shaped["cli_summary"]
    assert shaped["desktop_summary"].startswith("Ho gaya:")
    assert "Hinglish" in shaped["language_style"]
