from __future__ import annotations

from typing import Any

from shellai.config import ProviderBackendConfig, ShellAIConfig
from shellai.protocol import AgentRole

from .base import ChatMessage, ModelDiagnostics, ModelProvider, ModelResponse, ModelRole
from .ollama import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider


class ModelRouter:
    """Resolve provider/model choices for agents and model roles."""

    def __init__(
        self,
        config: ShellAIConfig | None = None,
        provider_factories: dict[str, type[ModelProvider]] | None = None,
    ) -> None:
        self.config = config or ShellAIConfig.load()
        self.provider_factories = {
            "openai_compatible": OpenAICompatibleProvider,
            "ollama": OllamaProvider,
            **dict(provider_factories or {}),
        }

    def provider_for(self, provider_name: str | None = None) -> ModelProvider:
        backend = self.config.provider_config(provider_name)
        provider_cls = self.provider_factories.get(backend.kind)
        if provider_cls is None:
            fallback_backend = ProviderBackendConfig.from_dict(
                backend.name,
                {**backend.to_dict(), "kind": "openai_compatible"},
            )
            return OpenAICompatibleProvider(self.config, fallback_backend)
        return provider_cls(self.config, backend)

    def resolve_model(self, model_role: ModelRole = "planning", provider_name: str | None = None) -> dict[str, str]:
        provider = self.provider_for(provider_name)
        role, model = provider.resolve_model(model_role)
        return {
            "provider": provider.name,
            "provider_kind": provider.backend.kind,
            "model_role": role,
            "model": model,
        }

    def diagnostics(self, provider_name: str | None = None) -> dict[str, Any]:
        providers = [provider_name] if provider_name else sorted(self.config.providers)
        diagnostics: dict[str, Any] = {}
        for name in providers:
            provider = self.provider_for(name)
            diagnostics[name or provider.name] = {
                role: provider.diagnostics(role).to_dict()
                for role in ("planning", "command", "summarization")
            }
        return diagnostics

    def complete(
        self,
        prompt: str,
        *,
        model_role: ModelRole = "planning",
        provider_name: str | None = None,
        messages: list[ChatMessage] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        provider = self.provider_for(provider_name)
        return provider.complete(prompt, model_role=model_role, messages=messages, **kwargs)

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model_role: ModelRole = "planning",
        provider_name: str | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        provider = self.provider_for(provider_name)
        return provider.chat(messages, model_role=model_role, **kwargs)

    def embed(
        self,
        texts: list[str] | str,
        *,
        model_role: ModelRole | None = None,
        provider_name: str | None = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        provider = self.provider_for(provider_name)
        return provider.embed(texts, model_role=model_role, **kwargs)

    def model_for_agent(self, agent: AgentRole | str, provider_name: str | None = None) -> dict[str, str]:
        return self.resolve_model(agent, provider_name=provider_name)


__all__ = ["ModelRouter"]
