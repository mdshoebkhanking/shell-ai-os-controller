import os
import json
import logging
import asyncio
import urllib.request
import urllib.error
from typing import List, Dict
from .base import ModelProvider

logger = logging.getLogger("blackbox_provider")


class BlackboxProvider(ModelProvider):
    """Real Blackbox AI provider using the free API endpoint."""

    def __init__(self):
        self.api_url = "https://api.blackbox.ai/api/chat"
        self.api_key = os.getenv("BLACKBOX_API_KEY", "")

    @property
    def provider_name(self) -> str:
        return "Blackbox"

    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Synchronous response using urllib.request (stdlib)."""
        model = kwargs.get("model", "blackboxai")
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)

        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "maxTokens": max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.api_url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")

            # Try to parse as JSON first
            try:
                parsed = json.loads(raw)
                # Handle various response formats
                if isinstance(parsed, dict):
                    if "choices" in parsed:
                        return parsed["choices"][0]["message"]["content"]
                    if "message" in parsed:
                        content = parsed["message"]
                        if isinstance(content, dict):
                            return content.get("content", str(content))
                        return str(content)
                    if "text" in parsed:
                        return parsed["text"]
                    if "response" in parsed:
                        return parsed["response"]
                    if "content" in parsed:
                        return parsed["content"]
                # If parsed but no known key, return as string
                return str(parsed)
            except json.JSONDecodeError:
                # Response is plain text
                if raw.strip():
                    return raw.strip()
                return "Blackbox AI returned an empty response."

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")[:500]
            except Exception:
                pass
            logger.error(f"Blackbox HTTP error {e.code}: {body}")
            # RAISE so MultiBrain's fallback chain triggers — returning a
            # string was leaking the error into the user's chat bubble.
            raise RuntimeError(f"Blackbox HTTP {e.code}: {body or e.reason}")

        except urllib.error.URLError as e:
            logger.error(f"Blackbox connection error: {e.reason}")
            raise RuntimeError(f"Blackbox connection error: {e.reason}")

        except Exception as e:
            logger.error(f"Blackbox unexpected error: {e}")
            raise

    async def generate_response_async(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Async response. Uses aiohttp if available, otherwise runs sync in executor."""
        try:
            import aiohttp
            return await self._async_aiohttp(messages, **kwargs)
        except ImportError:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.generate_response, messages, **kwargs)

    async def _async_aiohttp(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Async implementation using aiohttp."""
        import aiohttp

        model = kwargs.get("model", "blackboxai")
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)

        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "maxTokens": max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    raw = await resp.text()

                    if resp.status != 200:
                        logger.error(f"Blackbox HTTP error {resp.status}: {raw[:500]}")
                        # RAISE so MultiBrain falls through. Returning the
                        # error string was leaking into user chat.
                        raise RuntimeError(
                            f"Blackbox HTTP {resp.status}: {raw[:200]}")

                    # Try JSON parse
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            if "choices" in parsed:
                                return parsed["choices"][0]["message"]["content"]
                            if "message" in parsed:
                                content = parsed["message"]
                                if isinstance(content, dict):
                                    return content.get("content", str(content))
                                return str(content)
                            if "text" in parsed:
                                return parsed["text"]
                            if "response" in parsed:
                                return parsed["response"]
                            if "content" in parsed:
                                return parsed["content"]
                        return str(parsed)
                    except json.JSONDecodeError:
                        if raw.strip():
                            return raw.strip()
                        return "Blackbox AI returned an empty response."

        except aiohttp.ClientError as e:
            logger.error(f"Blackbox aiohttp error: {e}")
            raise RuntimeError(f"Blackbox connection error: {e}")

        except asyncio.TimeoutError:
            logger.error("Blackbox request timed out")
            raise RuntimeError("Blackbox timeout")

        except Exception as e:
            logger.error(f"Blackbox unexpected async error: {e}")
            raise
