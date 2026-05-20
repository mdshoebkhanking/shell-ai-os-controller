from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Union

from shellai.config import ProviderBackendConfig, ShellAIConfig
from shellai.protocol import AgentRole


ChatMessage = dict[str, str]
ModelRole = Union[str, AgentRole]


@dataclass(frozen=True)
class ModelDiagnostics:
    provider: str
    kind: str
    model: str
    model_role: str
    ok: bool
    message: str
    base_url: str = ""
    api_key_env: str = ""
    api_key_configured: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "kind": self.kind,
            "model": self.model,
            "model_role": self.model_role,
            "ok": self.ok,
            "message": self.message,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "api_key_configured": self.api_key_configured,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ModelResponse:
    text: str
    provider: str
    model: str
    model_role: str
    raw: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "model_role": self.model_role,
            "raw": dict(self.raw),
            "metadata": dict(self.metadata),
        }


class ModelCallError(RuntimeError):
    pass


class MissingProviderCredentialError(ModelCallError):
    def __init__(self, diagnostics: ModelDiagnostics) -> None:
        super().__init__(diagnostics.message)
        self.diagnostics = diagnostics


class ModelProvider(ABC):
    """Minimal sync model provider interface.

    This keeps Stage 3 simple while preserving the two future expansion points
    we need: agent-role model routing and embeddings for memory.
    """

    def __init__(self, config: ShellAIConfig, backend: ProviderBackendConfig) -> None:
        self.config = config
        self.backend = backend

    @property
    def name(self) -> str:
        return self.backend.name

    def resolve_model_role(self, model_role: ModelRole | None) -> str:
        if isinstance(model_role, AgentRole):
            mapped = self.config.agent_model_roles.get(model_role.value, "planning")
            return mapped if mapped in {"planning", "command", "summarization"} else "planning"
        text = str(model_role or "planning").strip()
        if text in {"planning", "command", "summarization"}:
            return text
        normalized = AgentRole.normalize(text)
        if normalized in self.config.agent_model_roles:
            mapped = self.config.agent_model_roles.get(normalized, "planning")
            return mapped if mapped in {"planning", "command", "summarization"} else "planning"
        return "planning"

    def resolve_model(self, model_role: ModelRole | None = None, model: str | None = None) -> tuple[str, str]:
        role = self.resolve_model_role(model_role)
        resolved_model = str(model or self.config.model_for_role(role) or self.backend.default_model)
        return role, resolved_model

    def diagnostics(self, model_role: ModelRole | None = None) -> ModelDiagnostics:
        role, model = self.resolve_model(model_role)
        if not self.backend.enabled:
            return ModelDiagnostics(
                provider=self.name,
                kind=self.backend.kind,
                model=model,
                model_role=role,
                ok=False,
                message=f"Provider '{self.name}' is disabled in config.",
                base_url=self.backend.base_url,
                api_key_env=self.backend.api_key_env,
                api_key_configured=self.backend.api_key_configured,
            )
        if self.backend.api_key_env and not self.backend.api_key_configured:
            return ModelDiagnostics(
                provider=self.name,
                kind=self.backend.kind,
                model=model,
                model_role=role,
                ok=False,
                message=f"Missing API key for provider '{self.name}'. Set {self.backend.api_key_env}.",
                base_url=self.backend.base_url,
                api_key_env=self.backend.api_key_env,
                api_key_configured=False,
            )
        return ModelDiagnostics(
            provider=self.name,
            kind=self.backend.kind,
            model=model,
            model_role=role,
            ok=True,
            message="Provider is configured.",
            base_url=self.backend.base_url,
            api_key_env=self.backend.api_key_env,
            api_key_configured=self.backend.api_key_configured,
        )

    def require_ready(self, model_role: ModelRole | None = None) -> ModelDiagnostics:
        diagnostics = self.diagnostics(model_role)
        if not diagnostics.ok:
            raise MissingProviderCredentialError(diagnostics)
        return diagnostics

    def complete(
        self,
        prompt: str,
        *,
        model_role: ModelRole = "planning",
        messages: list[ChatMessage] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        chat_messages = messages or [{"role": "user", "content": str(prompt or "")}]
        return self.chat(chat_messages, model_role=model_role, **kwargs)

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model_role: ModelRole = "planning",
        **kwargs: Any,
    ) -> ModelResponse:
        raise NotImplementedError

    def embed(
        self,
        texts: list[str] | str,
        *,
        model_role: ModelRole | None = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        raise NotImplementedError(f"{self.name} does not implement embeddings yet")
