import asyncio

from core.tools.metadata import infer_tool_metadata
from shell_agents import DeveloperAgent


AGENT_ITEM = {
    "id": "shell_agents:developer_agent_tool",
    "name": "developer_agent_tool",
    "module": "shell_agents",
    "kind": "agent",
    "category": "agents",
    "description": "Full-stack coding agent.",
    "risk": "normal",
}


def test_developer_agent_handles_simple_code_request_without_provider():
    reply = asyncio.run(DeveloperAgent().execute("python code likho fibonacci function"))

    assert "DeveloperAgent" in reply
    assert "def fibonacci" in reply
    assert "AI providers are temporarily unavailable" not in reply
    assert "No tools available" not in reply


def test_developer_agent_handles_javascript_sort_request_without_provider():
    reply = asyncio.run(DeveloperAgent().execute("write code for sorting a list in javascript"))

    assert "function sortNumbers" in reply
    assert "javascript" in reply.lower()


def test_agent_readiness_allows_offline_fallback_when_api_keys_missing(monkeypatch):
    for key in ("GOOGLE_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "PERPLEXITY_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    metadata = infer_tool_metadata(AGENT_ITEM).to_dict()

    assert metadata["fallback_available"] is True
    assert metadata["readiness"]["ok"] is True
    assert metadata["readiness"]["state"] == "OFFLINE_ONLY"


def test_developer_agent_gateway_executes_local_code_fallback(monkeypatch):
    for key in ("GOOGLE_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "PERPLEXITY_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    from shell_tool_gateway import execute_tool_sync

    result = execute_tool_sync("shell_agents:developer_agent_tool", {"task": "python code likho fibonacci function"})

    assert result["status"] == "success"
    assert "def fibonacci" in result["result"]


def test_developer_agent_uses_offline_coding_brain_when_provider_missing(monkeypatch):
    import shell_agents
    import shell_offline_llm

    class FakeOfflineCodingResult:
        success = True
        reply = "```python\ndef parse_csv_upload(stream):\n    return stream.read().decode('utf-8')\n```"

    monkeypatch.setattr(shell_agents.ShellAgent, "_get_brain", classmethod(lambda cls: None))
    monkeypatch.setattr(shell_offline_llm, "generate_offline_coding_reply", lambda *_args, **_kwargs: FakeOfflineCodingResult())

    reply = asyncio.run(DeveloperAgent().execute("write python code for csv upload parsing"))

    assert "parse_csv_upload" in reply
    assert "AI providers are temporarily unavailable" not in reply


def test_developer_agent_requires_online_for_hard_full_app_when_provider_missing(monkeypatch):
    import shell_agents
    import shell_offline_llm
    from shell_task_mode import CLOUD_PROVIDER_KEY_GROUPS

    for group in CLOUD_PROVIDER_KEY_GROUPS:
        for key in group:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(shell_agents.ShellAgent, "_get_brain", classmethod(lambda cls: None))
    monkeypatch.setattr(
        shell_offline_llm,
        "generate_offline_coding_reply",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("hard app task should not use offline coding brain")),
    )

    reply = asyncio.run(DeveloperAgent().execute("Build a full app with authentication, backend API, and database"))

    assert "basic version offline" in reply
    assert "API Keys" in reply
