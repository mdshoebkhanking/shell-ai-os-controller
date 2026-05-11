"""
OpenRouter Provider
-------------------
Access 100+ models through one API. Many FREE models available.
OpenAI-compatible API. Free tier has no cost models like:
  - meta-llama/llama-3.3-70b-instruct:free
  - google/gemma-2-9b-it:free
  - qwen/qwen-2.5-72b-instruct:free
  - deepseek/deepseek-chat-v3-0324:free
  - mistralai/mistral-small-3.1-24b-instruct:free

Get key: https://openrouter.ai/keys (free signup)
"""

import os
import asyncio
import json
import logging
from typing import List, Dict
from .base import ModelProvider

logger = logging.getLogger("openrouter_provider")


class OpenRouterProvider(ModelProvider):
    """OpenRouter — one API, 100+ models, many free."""

    # Best free models on OpenRouter (no cost)
    FREE_MODELS = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
    ]

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "OpenRouter"

    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        import urllib.request
        import urllib.error

        if not self.api_key:
            raise Exception("OpenRouter API Key missing (OPENROUTER_API_KEY)")

        model = kwargs.get("model", self.FREE_MODELS[0])
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2048)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://shell-ai.local",
            "X-Title": "Shell AI",
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url, data=data, headers=headers, method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")[:500]
            except Exception:
                pass
            raise Exception(f"OpenRouter HTTP {e.code}: {body}")
        except Exception as e:
            raise Exception(f"OpenRouter Error: {e}")

    async def generate_response_async(self, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.api_key:
            raise Exception("OpenRouter API Key missing (OPENROUTER_API_KEY)")

        model = kwargs.get("model", self.FREE_MODELS[0])
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2048)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://shell-ai.local",
            "X-Title": "Shell AI",
        }

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url, json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise Exception(f"OpenRouter HTTP {resp.status}: {text[:500]}")
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
        except ImportError:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.generate_response, messages, **kwargs
            )
