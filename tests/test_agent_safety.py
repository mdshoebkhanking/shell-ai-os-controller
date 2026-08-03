import asyncio


class FakeBrain:
    async def generate_response(self, *args, **kwargs):
        return "```python\nprint('hello from swarm')\n```"


def test_swarm_coder_file_write_blocked_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SHELL_ALLOW_SWARM_FILE_WRITE", raising=False)

    from swarm.agents.coder import CoderAgent
    from swarm.base import SwarmState

    state = SwarmState(task_id="test", original_request="write code")
    result = asyncio.run(CoderAgent(FakeBrain()).execute("write code", state))

    assert "File write blocked by policy" in result
    assert not (tmp_path / "swarm_output.py").exists()
    assert "code_preview" in state.artifacts


def test_swarm_coder_file_write_requires_explicit_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHELL_ALLOW_SWARM_FILE_WRITE", "1")

    from swarm.agents.coder import CoderAgent
    from swarm.base import SwarmState

    state = SwarmState(task_id="test", original_request="write code")
    result = asyncio.run(CoderAgent(FakeBrain()).execute("write code", state))

    assert "Code generated and saved to swarm_output.py" in result
    assert (tmp_path / "swarm_output.py").read_text(encoding="utf-8").strip() == "print('hello from swarm')"


def test_agent_provider_failure_is_human_readable(monkeypatch):
    from shell_agents import ShellAgent

    class BrokenBrain:
        async def generate_response(self, *args, **kwargs):
            return "All Brains Failed. Errors: provider quota raw details"

    class ProbeAgent(ShellAgent):
        pass

    ProbeAgent._brain = BrokenBrain()
    ProbeAgent._brain_unavailable_until = 0.0
    agent = ProbeAgent("ProbeAgent", "tester", "testing", [])

    result = asyncio.run(agent._ai_think("hello"))

    assert "All Brains Failed" not in result
    assert "degraded mode" in result


def test_shell_agent_missing_tool_uses_reasoning_fallback():
    from shell_agents import ShellAgent

    class ProbeAgent(ShellAgent):
        async def _ai_think(self, prompt, system_prompt=None, mode=None):
            if "Step 1:" in prompt:
                return '{"completed": true, "final_summary": "Check that the chat input sends a message and the reply bubble appears."}'
            if "Selenium" in prompt:
                return "Check that the chat input sends a message and the reply bubble appears."
            return '{"completed": false, "next_step": {"action": "Suggest one UI test idea", "tool": "Selenium", "params": {"prompt": "one idea"}}}'

    agent = ProbeAgent("ProbeAgent", "tester", "testing", [])
    result = asyncio.run(agent.execute("return one short UI test idea"))

    assert "Tool 'Selenium' not found" not in result
    assert "Check that the chat input sends a message" in result
    assert "(success | 1/" in result


def test_testing_agent_short_test_idea_stays_short():
    from shell_agents import TestingAgent

    result = asyncio.run(TestingAgent().execute("return one short UI test idea"))

    assert "layout shift" in result
    assert "Example Code" not in result
    assert "Selenium" not in result
    assert len(result) < 260


def test_shell_agents_ui_smoke_fast_path_avoids_provider():
    from shell_agents import WebsiteBuilderAgent

    result = asyncio.run(WebsiteBuilderAgent().execute("UI smoke test only: suggest one tiny homepage section in one sentence."))

    assert "compact hero status section" in result
    assert "degraded mode" not in result
    assert len(result) < 260


def test_extra_agents_ui_smoke_fast_path_avoids_provider():
    import shell_extra_agents

    result = asyncio.run(
        shell_extra_agents._ask_brain(
            "UI smoke test only: give one packing tip.",
            "You are TravelAgent.",
        )
    )

    assert "versatile outfit" in result
    assert "degraded mode" not in result


def test_extra_agent_provider_failure_is_human_readable(monkeypatch):
    import shell_extra_agents

    class BrokenBrain:
        async def generate_response(self, *args, **kwargs):
            return "All Brains Failed. Errors: provider quota raw details"

    class FakeMultiAIBrain:
        @staticmethod
        def get_instance():
            return BrokenBrain()

    monkeypatch.setattr(shell_extra_agents, "_BRAIN_UNAVAILABLE_UNTIL", 0.0)
    monkeypatch.setitem(__import__("sys").modules, "brain.core", type("M", (), {"MultiAIBrain": FakeMultiAIBrain}))

    result = asyncio.run(shell_extra_agents._ask_brain("hello", "system"))

    assert "All Brains Failed" not in result
    assert "degraded mode" in result


def test_swarm_smoke_and_no_write_requests_route_to_reviewer():
    from swarm.orchestrator import Orchestrator

    orch = object.__new__(Orchestrator)

    assert orch._route_step("UI smoke test only: produce a one-line readiness report") == "reviewer"
    assert orch._route_step("Do not create files; just inspect status") == "reviewer"


def test_deploy_swarm_ui_smoke_avoids_provider_calls():
    import shell_agent_tools

    result = asyncio.run(
        shell_agent_tools.deploy_swarm_tool(
            "UI smoke test only: produce a one-line readiness report. Do not create files."
        )
    )

    assert "Swarm is ready" in result
    assert "no files" in result.lower()


def test_swarm_agent_provider_failure_is_human_readable():
    from swarm.agents.reviewer import ReviewerAgent
    from swarm.base import BaseAgent, SwarmState

    class BrokenBrain:
        async def generate_response(self, *args, **kwargs):
            return "All Brains Failed. Errors: provider quota raw details"

    BaseAgent._provider_unavailable_until = 0.0
    state = SwarmState(task_id="test", original_request="review")
    result = asyncio.run(ReviewerAgent(BrokenBrain()).execute("review status", state))

    assert "All Brains Failed" not in result
    assert "degraded mode" in result
