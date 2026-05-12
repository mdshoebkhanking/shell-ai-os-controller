import os
from typing import List, Dict
from .base import ModelProvider

class MistralProvider(ModelProvider):
    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self._chat_message_cls = None
        if self.api_key:
            try:
                from mistralai.client import MistralClient
                from mistralai.async_client import MistralAsyncClient
                from mistralai.models.chat_completion import ChatMessage
            except ImportError:
                MistralClient = None
                MistralAsyncClient = None
                ChatMessage = None
            self._chat_message_cls = ChatMessage
        else:
            MistralClient = None
            MistralAsyncClient = None
        if MistralClient and MistralAsyncClient and self.api_key:
            self.client = MistralClient(api_key=self.api_key)
            self.async_client = MistralAsyncClient(api_key=self.api_key)
        else:
            self.client = None
            self.async_client = None

    @property
    def provider_name(self) -> str:
        return "Mistral"

    def _convert_messages(self, messages: List[Dict[str, str]]):
        if not self._chat_message_cls:
            return []
        return [self._chat_message_cls(role=m["role"], content=m["content"]) for m in messages]

    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.client:
            return "Error: Mistral library missing or API Key invalid."
        
        model = kwargs.get("model", "mistral-large-latest")
        
        try:
            chat_response = self.client.chat(
                model=model,
                messages=self._convert_messages(messages)
            )
            return chat_response.choices[0].message.content
        except Exception as e:
            return f"Mistral Error: {str(e)}"

    async def generate_response_async(self, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.async_client:
            return "Error: Mistral library missing or API Key invalid."
        
        model = kwargs.get("model", "mistral-large-latest")
        
        try:
            chat_response = await self.async_client.chat(
                model=model,
                messages=self._convert_messages(messages)
            )
            return chat_response.choices[0].message.content
        except Exception as e:
            return f"Mistral Error: {str(e)}"
