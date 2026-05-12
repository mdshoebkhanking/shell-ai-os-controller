"""
DeepSeek AI Provider
--------------------
Very cheap, excellent for coding and general tasks.
API is OpenAI-compatible. Free trial credits on signup.
Models: deepseek-chat, deepseek-coder, deepseek-reasoner
Get key: https://platform.deepseek.com/
"""

import os
import asyncio
import json
import logging
from typing import List, Dict
from brain.provider_transport import get_aiohttp_session
from .base import ModelProvider

logger = logging.getLogger("deepseek_provider")


class DeepSeekProvider(ModelProvider):
    """DeepSeek AI — cheap & powerful, OpenAI-compatible API."""

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/chat/completions"

    @property
    def provider_name(self) -> str:
        return "DeepSeek"

    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        import urllib.request
        import urllib.error

        if not self.api_key:
            raise Exception("DeepSeek API Key missing (DEEPSEEK_API_KEY)")

        model = kwargs.get("model", "deepseek-chat")
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
            raise Exception(f"DeepSeek HTTP {e.code}: {body}")
        except Exception as e:
            raise Exception(f"DeepSeek Error: {e}")

    async def generate_response_async(self, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.api_key:
            raise Exception("DeepSeek API Key missing (DEEPSEEK_API_KEY)")

        model = kwargs.get("model", "deepseek-chat")
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
        }

        try:
            session = await get_aiohttp_session("deepseek", timeout_s=60)
            async with session.post(self.base_url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"DeepSeek HTTP {resp.status}: {text[:500]}")
                result = await resp.json()
                return result["choices"][0]["message"]["content"]
        except ImportError:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.generate_response, messages, **kwargs
            )
