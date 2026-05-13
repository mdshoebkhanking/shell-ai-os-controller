"""
Lazy AI provider runtime.

`brain.core` should be cheap to import and cheap to initialize. Provider SDKs
such as OpenAI, Gemini, Mistral, and aiohttp-backed providers are loaded only
when the selected provider is actually used for inference.
"""

from __future__ import annotations

import importlib
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, List, Dict

from .providers.base import ModelProvider


def _is_placeholder_api_key(value: str | None) -> bool:
    key = str(value or "").strip()
    if not key:
        return True
    low = key.lower()
    return (
        low.startswith("your_")
        or low.startswith("replace_")
        or low in {"changeme", "change_me", "paste_key_here", "api_key", "none", "null"}
        or "your_google_api_key" in low
    )


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    module: str
    class_name: str
    key_env: tuple[str, ...] = ()
    require_valid_key_for_registration: bool = False
    enabled_env: str | None = None
    enabled_value: str = "1"

    def is_enabled(self) -> bool:
        if self.enabled_env:
            if os.getenv(self.enabled_env, "0").strip() != self.enabled_value:
                return False
        if not self.require_valid_key_for_registration:
            return True
        return any(not _is_placeholder_api_key(os.getenv(key)) for key in self.key_env)


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec("groq", "brain.providers.groq_p", "GroqProvider"),
    ProviderSpec(
        "gemini",
        "brain.providers.gemini_p",
        "GeminiProvider",
        key_env=("GOOGLE_API_KEY",),
        require_valid_key_for_registration=True,
    ),
    ProviderSpec("deepseek", "brain.providers.deepseek_p", "DeepSeekProvider"),
    ProviderSpec("openrouter", "brain.providers.openrouter_p", "OpenRouterProvider"),
    ProviderSpec("sambanova", "brain.providers.sambanova_p", "SambaNovaProvider"),
    ProviderSpec(
        "blackbox",
        "brain.providers.blackbox_p",
        "BlackboxProvider",
        enabled_env="BLACKBOX_ENABLED",
    ),
    ProviderSpec(
        "openai",
        "brain.providers.openai_p",
        "OpenAIProvider",
        key_env=("OPENAI_API_KEY",),
        require_valid_key_for_registration=True,
    ),
    ProviderSpec("mistral", "brain.providers.mistral_p", "MistralProvider"),
    ProviderSpec("perplexity", "brain.providers.perplexity_p", "PerplexityProvider"),
)


class LazyProviderProxy(ModelProvider):
    """Provider placeholder that loads the concrete provider on first use."""

    def __init__(self, spec: ProviderSpec):
        self.spec = spec
        self._provider: ModelProvider | None = None
        self._load_error = ""
        self._load_ms: float | None = None
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return self.spec.name

    @property
    def loaded(self) -> bool:
        return self._provider is not None

    @property
    def load_ms(self) -> float | None:
        return self._load_ms

    @property
    def load_error(self) -> str:
        return self._load_error

    def _load_provider(self) -> ModelProvider:
        if self._provider is not None:
            return self._provider
        with self._lock:
            if self._provider is not None:
                return self._provider
            started = time.perf_counter()
            try:
                module = importlib.import_module(self.spec.module)
                provider_cls = getattr(module, self.spec.class_name)
                provider = provider_cls()
                self._provider = provider
                self._load_error = ""
                return provider
            except Exception as exc:
                self._load_error = str(exc)
                raise
            finally:
                self._load_ms = round((time.perf_counter() - started) * 1000.0, 3)

    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        return self._load_provider().generate_response(messages, **kwargs)

    async def generate_response_async(self, messages: List[Dict[str, str]], **kwargs) -> str:
        return await self._load_provider().generate_response_async(messages, **kwargs)

    async def generate_response_stream_async(self, messages: List[Dict[str, str]], **kwargs):
        provider = self._load_provider()
        method = getattr(provider, "generate_response_stream_async", None)
        if not method or not provider.supports_streaming():
            raise NotImplementedError(f"{self.spec.name} does not support token streaming")
        async for chunk in method(messages, **kwargs):
            yield chunk

    def get_cost_per_1k_tokens(self, model: str = "") -> Dict[str, float]:
        return self._load_provider().get_cost_per_1k_tokens(model)

    def supports_streaming(self) -> bool:
        try:
            return bool(self._load_provider().supports_streaming())
        except Exception:
            return False

    def supports_function_calling(self) -> bool:
        provider = self._provider
        return bool(provider and provider.supports_function_calling())

    def diagnostics(self) -> dict[str, Any]:
        return {
            "name": self.spec.name,
            "module": self.spec.module,
            "class_name": self.spec.class_name,
            "loaded": self.loaded,
            "load_ms": self.load_ms,
            "load_error": self.load_error,
        }


def build_lazy_providers() -> dict[str, LazyProviderProxy]:
    return {
        spec.name: LazyProviderProxy(spec)
        for spec in PROVIDER_SPECS
        if spec.is_enabled()
    }


def provider_runtime_diagnostics(providers: dict[str, Any]) -> dict[str, Any]:
    items: dict[str, Any] = {}
    for name, provider in providers.items():
        if hasattr(provider, "diagnostics"):
            items[name] = provider.diagnostics()
        else:
            items[name] = {
                "name": name,
                "loaded": True,
                "class_name": provider.__class__.__name__,
                "module": provider.__class__.__module__,
            }
    return items


__all__ = [
    "LazyProviderProxy",
    "PROVIDER_SPECS",
    "ProviderSpec",
    "build_lazy_providers",
    "provider_runtime_diagnostics",
]
