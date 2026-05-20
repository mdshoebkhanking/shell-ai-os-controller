from __future__ import annotations

import pytest


def test_model_router_resolves_provider_and_model_per_role() -> None:
    from shellai.config import ModelRoleConfig, ShellAIConfig
    from shellai.models import ModelRouter
    from shellai.protocol import AgentRole

    config = ShellAIConfig(
        provider="ollama",
        models=ModelRoleConfig(
            planning="planner",
            command="commander",
            summarization="summarizer",
        ),
    )
    router = ModelRouter(config)

    assert router.resolve_model("planning") == {
        "provider": "ollama",
        "provider_kind": "ollama",
        "model_role": "planning",
        "model": "planner",
    }
    assert router.model_for_agent(AgentRole.SHELL)["model"] == "commander"
    assert router.model_for_agent(AgentRole.MEMORY)["model"] == "summarizer"


def test_missing_key_diagnostics_refuses_real_calls(monkeypatch) -> None:
    from shellai.config import ShellAIConfig
    from shellai.models import MissingProviderCredentialError, ModelRouter

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = ShellAIConfig(provider="openai")
    router = ModelRouter(config)
    diagnostics = router.diagnostics("openai")["openai"]["planning"]

    assert diagnostics["ok"] is False
    assert diagnostics["api_key_env"] == "OPENAI_API_KEY"
    assert "Missing API key" in diagnostics["message"]

    with pytest.raises(MissingProviderCredentialError):
        router.complete("hello", provider_name="openai")


def test_fake_provider_can_be_injected_without_network() -> None:
    from shellai.config import ProviderBackendConfig, ShellAIConfig
    from shellai.models.base import ChatMessage, ModelProvider, ModelResponse, ModelRole
    from shellai.models.router import ModelRouter

    class FakeProvider(ModelProvider):
        def chat(
            self,
            messages: list[ChatMessage],
            *,
            model_role: ModelRole = "planning",
            **kwargs,
        ) -> ModelResponse:
            role, model = self.resolve_model(model_role, kwargs.get("model"))
            return ModelResponse(
                text=f"fake:{messages[-1]['content']}",
                provider=self.name,
                model=model,
                model_role=role,
            )

    config = ShellAIConfig(
        provider="fake",
        providers={
            "fake": ProviderBackendConfig(
                name="fake",
                kind="fake",
                base_url="memory://fake",
                api_key_env="",
                default_model="fake-model",
            )
        },
    )
    router = ModelRouter(config, provider_factories={"fake": FakeProvider})
    response = router.complete("ping", model_role="command")

    assert response.text == "fake:ping"
    assert response.provider == "fake"
    assert response.model_role == "command"
    assert response.model == config.models.command
