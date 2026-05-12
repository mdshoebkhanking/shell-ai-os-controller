import os
from typing import List, Dict, Any
from .base import ModelProvider


class OpenAIProvider(ModelProvider):
    def __init__(self):
        # Fail-fast so MultiBrain skips cleanly if SDK is missing or
        # the key isn't set, instead of constructing an `OpenAI()` with
        # None key (which raises a confusing OpenAIError deep inside).
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found or empty in environment")
        try:
            from openai import OpenAI, AsyncOpenAI
        except ImportError:
            raise ImportError("openai SDK not installed. pip install openai")
        self.client = OpenAI(api_key=self.api_key)
        self.async_client = AsyncOpenAI(api_key=self.api_key)

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.client:
            return "Error: OpenAI library not installed or API key missing."
        
        model = kwargs.get("model", "gpt-4o") # Default to 4o
        temperature = kwargs.get("temperature", 0.7)

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"OpenAI Error: {str(e)}"

    async def generate_response_async(self, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.async_client:
            return "Error: OpenAI library not installed or API key missing."
        
        model = kwargs.get("model", "gpt-4o")
        temperature = kwargs.get("temperature", 0.7)

        try:
            response = await self.async_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"OpenAI Error: {str(e)}"
