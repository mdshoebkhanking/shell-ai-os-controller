from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .base import ChatMessage, ModelCallError, ModelProvider, ModelResponse, ModelRole


class OpenAICompatibleProvider(ModelProvider):
    """HTTP provider for OpenAI-compatible chat-completions APIs."""

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model_role: ModelRole = "planning",
        **kwargs: Any,
    ) -> ModelResponse:
        diagnostics = self.require_ready(model_role)
        role, model = self.resolve_model(model_role, kwargs.pop("model", None))
        base_url = self.backend.base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": float(kwargs.pop("temperature", 0.2)),
        }
        if "max_tokens" in kwargs:
            payload["max_tokens"] = int(kwargs["max_tokens"])

        headers = {
            "Content-Type": "application/json",
        }
        if self.backend.api_key_env:
            headers["Authorization"] = f"Bearer {os.environ.get(self.backend.api_key_env, '')}"
        if self.name == "openrouter":
            headers.setdefault("HTTP-Referer", "https://shell-ai.local")
            headers.setdefault("X-Title", "ShellAI")

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=float(kwargs.pop("timeout", 60))) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            raise ModelCallError(f"{self.name} HTTP {exc.code}: {body}") from exc
        except Exception as exc:
            raise ModelCallError(f"{self.name} call failed: {exc}") from exc

        text = ""
        try:
            text = str(raw["choices"][0]["message"]["content"] or "")
        except Exception as exc:
            raise ModelCallError(f"{self.name} response did not include choices[0].message.content") from exc

        return ModelResponse(
            text=text,
            provider=self.name,
            model=model,
            model_role=role,
            raw=raw if isinstance(raw, dict) else {},
            metadata={"diagnostics": diagnostics.to_dict()},
        )
