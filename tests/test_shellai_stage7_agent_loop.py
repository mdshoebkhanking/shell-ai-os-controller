from __future__ import annotations

import json


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


def _services(tmp_path, router):
    from shellai.config import ShellAIConfig, ShellAIPaths
    from shellai.memory import MemoryStore
    from shellai.skills import SkillManager
    from shellai.tools import ToolRegistry

    config_path = tmp_path / ".shellai" / "config.json"
    config = ShellAIConfig.load(config_path)
    config.paths = ShellAIPaths.from_config_path(config_path)
    memory = MemoryStore(tmp_path / "memory.sqlite3", config=config)
    skills = SkillManager(config=config, memory_store=memory, skills_dir=tmp_path / "skills")
    tools = ToolRegistry(config)
    return config, memory, skills, tools, router


def test_agent_loop_safe_shell_plan_executes_and_saves_conversation(tmp_path) -> None:
    import platform
    from shellai.agent_loop import create_user_request, run_agent_task

    cmd = "dir" if platform.system().lower() == "windows" else "pwd"
    plan = {
        "steps": [
            {
                "id": "pwd",
                "tool": "shell",
                "description": "Print working directory",
                "args": {"command": cmd},
            }
        ]
    }
    config, memory, skills, tools, router = _services(tmp_path, FakeRouter(plan))
    request = create_user_request("where am I?", context={"cwd": str(tmp_path)})
    result = run_agent_task(
        request,
        config=config,
        model_router=router,
        memory_store=memory,
        skill_manager=skills,
        tool_registry=tools,
    )

    assert result["status"] == "ok"
    assert result["steps"][0]["status"] == "ok"
    if cmd == "pwd":
        assert str(tmp_path) in result["steps"][0]["stdout"]
    else:
        assert str(tmp_path).lower().replace('/', '\\') in result["steps"][0]["stdout"].lower()
    assert [call["role"] for call in router.calls] == ["planning", "summarization"]

    rows = memory.search_memory("conversation", "Fake memory", limit=5)
    assert len(rows) == 1
    assert rows[0]["user_input"] == "where am I?"


def test_agent_loop_ask_command_requires_approval_without_execution(tmp_path) -> None:
    from shellai.agent_loop import create_user_request, run_agent_task

    plan = {
        "steps": [
            {
                "id": "ask",
                "tool": "shell",
                "description": "Remove a file",
                "args": {"command": "rm missing.txt"},
            }
        ]
    }
    config, memory, skills, tools, router = _services(tmp_path, FakeRouter(plan))
    request = create_user_request("remove missing file", context={"cwd": str(tmp_path)}, auto_approve_ask=False)
    result = run_agent_task(
        request,
        config=config,
        model_router=router,
        memory_store=memory,
        skill_manager=skills,
        tool_registry=tools,
    )

    assert result["status"] == "needs_confirmation"
    assert result["steps"][0]["status"] == "needs_confirmation"
    assert result["steps"][0]["metadata"]["risk"]["level"] == "ASK"


def test_agent_loop_file_tool_writes_file(tmp_path) -> None:
    from shellai.agent_loop import create_user_request, run_agent_task

    plan = {
        "steps": [
            {
                "id": "write",
                "tool": "file",
                "description": "Write a file",
                "args": {"operation": "write_file", "path": "hello.txt", "content": "namaste"},
            }
        ]
    }
    config, memory, skills, tools, router = _services(tmp_path, FakeRouter(plan))
    request = create_user_request("write a hello file", context={"cwd": str(tmp_path)})
    result = run_agent_task(
        request,
        config=config,
        model_router=router,
        memory_store=memory,
        skill_manager=skills,
        tool_registry=tools,
    )

    assert result["status"] == "ok"
    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "namaste"


def test_agent_loop_creates_auto_skill_for_reusable_multi_shell_plan(tmp_path) -> None:
    import platform
    from shellai.agent_loop import create_user_request, run_agent_task

    cmd = "dir" if platform.system().lower() == "windows" else "pwd"
    plan = {
        "mark_reusable": True,
        "steps": [
            {"id": "pwd", "tool": "shell", "description": "pwd", "args": {"command": cmd}},
            {"id": "whoami", "tool": "shell", "description": "whoami", "args": {"command": "whoami"}},
        ],
    }
    config, memory, skills, tools, router = _services(tmp_path, FakeRouter(plan))
    request = create_user_request("record my basic shell context", context={"cwd": str(tmp_path)})
    result = run_agent_task(
        request,
        config=config,
        model_router=router,
        memory_store=memory,
        skill_manager=skills,
        tool_registry=tools,
    )

    assert result["status"] == "ok"
    assert result["auto_skill"]["id"].startswith("auto_record_my_basic_shell_context_")
    assert len(skills.list_skills(query="basic shell")) == 1
    assert memory.get_skill(result["auto_skill"]["id"])["metadata"]["is_draft"] is True


def test_agent_loop_invalid_plan_returns_structured_error(tmp_path) -> None:
    from shellai.agent_loop import create_user_request, run_agent_task

    config, memory, skills, tools, router = _services(tmp_path, FakeRouter("not json"))
    request = create_user_request("bad plan please", context={"cwd": str(tmp_path)})
    result = run_agent_task(
        request,
        config=config,
        model_router=router,
        memory_store=memory,
        skill_manager=skills,
        tool_registry=tools,
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "planning_failed"
    assert "JSON" in result["error"]["message"]
