
import os
from .base import ModelProvider

class SambaNovaProvider(ModelProvider):
    def __init__(self):
        self.api_key = os.getenv("SAMBANOVA_API_KEY")
        # Assuming SambaNova follows OpenAI compatible endpoint structure generally
        # or specific SambaNova endpoint. 
        # For now, using a standard compatible endpoint if available, or placeholder.
        # User defined SAMBANOVA_API_KEY implies access.
        # Check docs: Usually https://api.sambanova.ai/v1/chat/completions or similar.
        self.base_url = "https://api.sambanova.ai/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "SambaNova"

    def generate_response(self, messages, **kwargs) -> str:
        import asyncio
        return asyncio.run(self.generate_response_async(messages, **kwargs))

    async def generate_response_async(self, messages, model="Meta-Llama-3.1-405B-Instruct", **kwargs):
        if not self.api_key:
            raise Exception("SambaNova API Key missing")
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Default model if generic passed
        if "gemini" in model: model = "Meta-Llama-3.1-8B-Instruct"
        
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
                    raise Exception(f"SambaNova Error {resp.status}: {text}")
                result = await resp.json()
                return result['choices'][0]['message']['content']
