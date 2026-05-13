
import json
import os
from brain.provider_transport import get_aiohttp_session
from .base import ModelProvider

class GroqProvider(ModelProvider):
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "Groq"

    def generate_response(self, messages, **kwargs) -> str:
        import asyncio
        return asyncio.run(self.generate_response_async(messages, **kwargs))

    async def generate_response_async(self, messages, model="llama-3.3-70b-versatile", **kwargs):
        if not self.api_key:
            raise Exception("Groq API Key missing")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Default models if not specified correctly
        if "gemini" in model: model = "llama-3.3-70b-versatile" 
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        
        session = await get_aiohttp_session("groq", timeout_s=60)
        async with session.post(self.base_url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Groq Error {resp.status}: {text}")
            result = await resp.json()
            return result['choices'][0]['message']['content']

    async def generate_response_stream_async(self, messages, model="llama-3.3-70b-versatile", **kwargs):
        if not self.api_key:
            raise Exception("Groq API Key missing")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        if "gemini" in model:
            model = "llama-3.3-70b-versatile"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1024),
            "stream": True,
        }

        session = await get_aiohttp_session("groq", timeout_s=60)
        async with session.post(self.base_url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Groq Stream Error {resp.status}: {text}")
            async for raw in resp.content:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text = delta.get("content") or choices[0].get("text") or ""
                if text:
                    yield str(text)

    def supports_streaming(self) -> bool:
        return True
