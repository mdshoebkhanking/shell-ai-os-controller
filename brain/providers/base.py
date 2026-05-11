from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator


class ModelProvider(ABC):
    """
    Abstract Base Class for all AI Model Providers.
    Provides default implementations for optional capabilities so that
    existing provider subclasses continue to work without modification.
    """

    @abstractmethod
    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generates a response from the model.

        Args:
            messages (List[Dict[str, str]]): List of message dicts (role, content).
            **kwargs: Additional arguments like temperature, max_tokens, etc.

        Returns:
            str: The text content of the response.
        """
        pass

    @abstractmethod
    async def generate_response_async(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Asynchronously generates a response from the model.
        """
        pass

    async def generate_response_stream(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> AsyncIterator[str]:
        """
        Async generator that streams response tokens.
        Default implementation calls generate_response_async and yields
        the complete result as a single chunk. Providers that support
        true streaming should override this method.
        """
        full_response = await self.generate_response_async(messages, **kwargs)
        yield full_response

    def get_cost_per_1k_tokens(self, model: str = "") -> Dict[str, float]:
        """
        Returns estimated cost per 1,000 tokens for the given model.
        Providers should override this with their actual pricing.
        """
        return {"input": 0.0, "output": 0.0}

    def supports_streaming(self) -> bool:
        """Whether this provider supports token-level streaming."""
        return False

    def supports_function_calling(self) -> bool:
        """Whether this provider supports function/tool calling."""
        return False

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the name of the provider (e.g., 'OpenAI', 'Claude')."""
        pass
