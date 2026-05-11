from __future__ import annotations

import os
import asyncio
from .base import ModelProvider
from typing import List, Dict


# Default model if caller does not override. Kept as a class-level constant
# so tests + other providers can see what we dispatch to by default.
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


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


def _humanize_gemini_error(exc: Exception) -> str:
    raw = str(exc)
    low = raw.lower()
    if (
        "api_key_invalid" in low
        or "api key not valid" in low
        or "invalid api key" in low
        or "google.rpc.errorinfo" in low and "generativelanguage.googleapis.com" in low
    ):
        return (
            "Gemini Error: Invalid GOOGLE_API_KEY. Open Shell Settings > API Keys, "
            "edit Gemini/GOOGLE_API_KEY, paste a valid Google AI Studio API key, "
            "then save and restart Shell if this process was already running."
        )
    if "quota" in low or "resource_exhausted" in low or "429" in low:
        return "Gemini Error: quota or rate limit reached. Try again later or configure another provider."
    if "permission" in low or "403" in low:
        return "Gemini Error: this key does not have permission for the Gemini API/model."
    if "not_found" in low or "404" in low:
        return "Gemini Error: configured Gemini model was not found or is not enabled for this key."
    return f"Gemini Error: {raw[:500]}"


def _normalize_gemini_model(name: str | None) -> str:
    """Normalise a Gemini model name across SDK versions.

    The new `google.genai` Client API expects bare names (`gemini-2.5-flash`)
    while the legacy `google.generativeai` GenerativeModel historically
    accepted either form. We strip the `models/` prefix to land on the
    shape both SDKs accept.
    """
    if not name:
        return DEFAULT_GEMINI_MODEL
    cleaned = str(name).strip()
    if cleaned.startswith("models/"):
        cleaned = cleaned[len("models/"):]
    return cleaned or DEFAULT_GEMINI_MODEL


class GeminiProvider(ModelProvider):
    def __init__(self):
        self.api_key = (os.getenv("GOOGLE_API_KEY") or "").strip()
        if _is_placeholder_api_key(self.api_key):
            raise ValueError(
                "GOOGLE_API_KEY is missing or still a placeholder. "
                "Open Settings > API Keys and save a valid Google AI Studio key."
            )

        # Preferred SDK: google.genai (new)
        self._client_mode = None
        self._new_client = None
        self._legacy_genai = None

        try:
            from google import genai

            self._new_client = genai.Client(api_key=self.api_key)
            self._client_mode = "new"
        except Exception:
            # Fallback SDK: google.generativeai (legacy/deprecated)
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self._legacy_genai = genai
                self._client_mode = "legacy"
            except ImportError:
                raise ImportError(
                    "Neither 'google.genai' nor 'google.generativeai' is available. "
                    "Install a Gemini SDK package."
                )

    @property
    def provider_name(self) -> str:
        return "Gemini"

    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt += f"System: {content}\n"
            elif role == "user":
                prompt += f"User: {content}\n"
            else:
                prompt += f"{role}: {content}\n"
        
        # Normalise the model name so both SDKs see the same shape.
        model_name = _normalize_gemini_model(kwargs.get("model"))

        try:
            if self._client_mode == "new":
                response = self._new_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return getattr(response, "text", "") or str(response)

            model = self._legacy_genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return _humanize_gemini_error(e)

    async def generate_response_async(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # Run sync call in thread since google.genai client is sync
        return await asyncio.to_thread(self.generate_response, messages, **kwargs)
