from __future__ import annotations

import json


def test_config_load_uses_env_fallback_for_provider_and_models(tmp_path, monkeypatch) -> None:
    from shellai.config import ShellAIConfig

    config_file = tmp_path / "config.json"
    monkeypatch.setenv("SHELLAI_PROVIDER", "openrouter")
    monkeypatch.setenv("SHELLAI_MODEL_PLANNING", "planner-model")
    monkeypatch.setenv("SHELLAI_MODEL_COMMAND", "command-model")
    monkeypatch.setenv("SHELLAI_MODEL_SUMMARIZATION", "summary-model")

    config = ShellAIConfig.load(config_file)

    assert config.provider == "openrouter"
    assert config.model_for_role("planning") == "planner-model"
    assert config.model_for_role("command") == "command-model"
    assert config.model_for_role("summarization") == "summary-model"


def test_config_save_and_reload_preserves_provider_backends(tmp_path) -> None:
    from shellai.config import ShellAIConfig

    config_file = tmp_path / ".shellai" / "config.json"
    config = ShellAIConfig.load(config_file)
    config.set_value("provider", "ollama")
    config.set_value("providers.ollama.base_url", "http://localhost:11434")
    config.set_value("providers.ollama.default_model", "qwen2.5-coder")
    config.save()

    raw = json.loads(config_file.read_text(encoding="utf-8"))
    assert raw["provider"] == "ollama"
    assert raw["providers"]["ollama"]["default_model"] == "qwen2.5-coder"

    reloaded = ShellAIConfig.load(config_file)
    assert reloaded.provider_config().name == "ollama"
    assert reloaded.provider_config().base_url == "http://localhost:11434"
    assert reloaded.provider_config().default_model == "qwen2.5-coder"


def test_future_agent_model_roles_are_configurable() -> None:
    from shellai.config import ShellAIConfig
    from shellai.protocol import AgentRole

    config = ShellAIConfig()

    assert config.model_for_agent(AgentRole.MEMORY) == config.models.summarization
    assert config.model_for_agent("OptimizerAgent") == config.models.planning

    config.set_value("agent_model_roles.MemoryAgent", "planning")
    assert config.model_for_agent("MemoryAgent") == config.models.planning


def test_agent_message_protocol_is_trace_ready() -> None:
    from shellai.protocol import AgentMessage, AgentRole, MessageKind

    message = AgentMessage.create(
        sender=AgentRole.COORDINATOR,
        recipient=AgentRole.SAFETY,
        kind=MessageKind.POLICY_DECISION,
        content="classify command",
        trace_id="trace-1",
        metadata={"command": "git status"},
    )

    payload = message.to_dict()
    assert payload["sender"] == "CoordinatorAgent"
    assert payload["recipient"] == "SafetyAgent"
    assert payload["kind"] == "policy_decision"
    assert payload["trace_id"] == "trace-1"
    assert payload["metadata"] == {"command": "git status"}
