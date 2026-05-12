
import os
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
        import aiohttp

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
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Groq Error {resp.status}: {text}")
                result = await resp.json()
                return result['choices'][0]['message']['content']
