from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import ChatMessage, ModelCallError, ModelProvider, ModelResponse, ModelRole


class OllamaProvider(ModelProvider):
    """Local Ollama provider using `/api/chat`."""

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        model_role: ModelRole = "planning",
        **kwargs: Any,
    ) -> ModelResponse:
        diagnostics = self.require_ready(model_role)
        role, model = self.resolve_model(model_role, kwargs.pop("model", None))
        url = f"{self.backend.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": float(kwargs.pop("temperature", 0.2))},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
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
            raise ModelCallError(f"ollama HTTP {exc.code}: {body}") from exc
        except Exception as exc:
            raise ModelCallError(f"ollama call failed: {exc}") from exc

        text = ""
        try:
            text = str(raw["message"]["content"] or "")
        except Exception as exc:
            raise ModelCallError("ollama response did not include message.content") from exc

        return ModelResponse(
            text=text,
            provider=self.name,
            model=model,
            model_role=role,
            raw=raw if isinstance(raw, dict) else {},
            metadata={"diagnostics": diagnostics.to_dict()},
        )
