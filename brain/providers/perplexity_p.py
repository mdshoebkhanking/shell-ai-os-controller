
import os
import aiohttp
import asyncio
from typing import List, Dict
from .base import ModelProvider

class PerplexityProvider(ModelProvider):
    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY")
        self.base_url = "https://api.perplexity.ai/chat/completions"

    @property
    def provider_name(self) -> str:
        return "Perplexity"

    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Synchronous wrapper for generating a response.
        """
        return asyncio.run(self.generate_response_async(messages, **kwargs))

    async def generate_response_async(self, messages: List[Dict[str, str]], model="sonar-reasoning-pro", **kwargs) -> str:
        """
        Asynchronously generates a response from Perplexity API.
        """
        if not self.api_key:
            raise Exception("Perplexity API Key missing")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Ensure model is valid for Perplexity
        if not model.startswith("sonar"):
             model = "sonar-reasoning-pro"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2, 
            "max_tokens": 1024,
            "return_citations": True
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Perplexity Error {resp.status}: {text}")
                result = await resp.json()
                
                content = result['choices'][0]['message']['content']
                citations = result.get('citations', [])
                if citations:
                   content += "\n\nSources:\n" + "\n".join([f"- {c}" for c in citations])
                   
                return content
