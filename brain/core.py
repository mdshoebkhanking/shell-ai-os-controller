"""
MultiAIBrain — ULTRA CORTEX (V3)
==================================
Shell AI ka central brain. 8 AI providers, intelligent fallback, conversation memory,
response caching, provider health tracking, multi-turn chat, token estimation.

V3 additions:
- ResponseQualityScorer: detects refusals, stubs, repetition, incoherence
- ProviderCostTracker: per-model cost tracking with detailed reports
- Rate-limit tracking via ProviderHealth.calls_last_minute
- Streaming support (generate_response_stream)
- Consensus generation across multiple providers
- Chain-of-thought prompting (generate_with_cot)
- Prompt compression for oversized inputs
- Quality-aware fallback in generate_response
"""

import os
import asyncio
import time
import logging
import hashlib
import json
from typing import List, Dict, Optional, Any, AsyncGenerator
from collections import OrderedDict, Counter
from datetime import datetime
from .router import SmartRouter
from .providers.openai_p import OpenAIProvider
from .providers.mistral_p import MistralProvider
from .providers.blackbox_p import BlackboxProvider
from .providers.groq_p import GroqProvider
from .providers.sambanova_p import SambaNovaProvider
from .providers.gemini_p import GeminiProvider
from .providers.perplexity_p import PerplexityProvider
from .providers.deepseek_p import DeepSeekProvider
from .providers.openrouter_p import OpenRouterProvider

logger = logging.getLogger("MultiBrain")


def _provider_timeout_s(mode: str = "SMART") -> float:
    """Interactive provider timeout; bounded so one slow API cannot stall UI."""
    try:
        return max(3.0, min(60.0, float(os.environ.get("SHELL_AI_PROVIDER_TIMEOUT_S", "18"))))
    except Exception:
        return 18.0


# ---------------------------------------------------------------------------
# ResponseQualityScorer
# ---------------------------------------------------------------------------

class ResponseQualityScorer:
    """Scores an AI response on a 0.0–1.0 scale for quality, detecting
    refusals, stubs, repetition, truncation, and empty outputs."""

    REFUSAL_PATTERNS = [
        "i cannot", "i'm unable", "as an ai", "i don't have",
        "not possible for me", "i can't", "i am not able",
    ]
    STUB_PATTERNS = [
        "coming soon", "not yet implemented", "placeholder",
        "todo", "work in progress", "under construction",
    ]

    def score(self, response: str, prompt: str) -> float:
        """Return a quality score between 0.0 and 1.0."""
        # Empty / whitespace-only → immediate zero
        if not response or not response.strip():
            return 0.0

        score = 1.0
        resp_lower = response.lower()

        # Length check — suspiciously short answer for a long prompt
        if len(response) < 20 and len(prompt) > 50:
            score -= 0.3

        # Repetition — same sentence appears 3+ times
        sentences = [s.strip() for s in response.split('.') if s.strip()]
        if sentences:
            counts = Counter(sentences)
            if any(c >= 3 for c in counts.values()):
                score -= 0.4

        # Refusal detection
        if any(p in resp_lower for p in self.REFUSAL_PATTERNS):
            score -= 0.4

        # Stub detection
        if any(p in resp_lower for p in self.STUB_PATTERNS):
            score -= 0.5

        # Coherence — doesn't end mid-word (missing terminal punctuation)
        if response and response[-1] not in '.!?"\'})\n':
            score -= 0.1

        return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# ProviderCostTracker
# ---------------------------------------------------------------------------

class ProviderCostTracker:
    """Tracks estimated API costs per model based on token usage."""

    COST_TABLE: Dict[str, Dict[str, float]] = {
        # --- FREE providers (Groq, SambaNova, Gemini, Blackbox, OpenRouter free) ---
        "llama-3.3-70b-versatile": {"input": 0.0, "output": 0.0},
        "llama-3.1-8b-instant": {"input": 0.0, "output": 0.0},
        "Meta-Llama-3.1-405B-Instruct": {"input": 0.0, "output": 0.0},
        "Meta-Llama-3.1-8B-Instruct": {"input": 0.0, "output": 0.0},
        "Llama-3.3-70B-Instruct": {"input": 0.0, "output": 0.0},
        "gemini-2.5-flash": {"input": 0.0, "output": 0.0},
        "gemini-2.0-flash-lite": {"input": 0.0, "output": 0.0},
        "blackbox-code": {"input": 0.0, "output": 0.0},
        "blackbox": {"input": 0.0, "output": 0.0},
        "meta-llama/llama-3.3-70b-instruct:free": {"input": 0.0, "output": 0.0},
        "deepseek/deepseek-chat-v3-0324:free": {"input": 0.0, "output": 0.0},
        "qwen/qwen-2.5-72b-instruct:free": {"input": 0.0, "output": 0.0},
        "google/gemma-2-9b-it:free": {"input": 0.0, "output": 0.0},
        "mistralai/mistral-small-3.1-24b-instruct:free": {"input": 0.0, "output": 0.0},
        # --- DeepSeek (very cheap) ---
        "deepseek-chat": {"input": 0.00014, "output": 0.00028},
        "deepseek-reasoner": {"input": 0.00055, "output": 0.002},
        # --- Paid providers (OpenAI, Mistral, Perplexity) ---
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "o3-mini": {"input": 0.0011, "output": 0.0044},
        "mistral-large-latest": {"input": 0.002, "output": 0.006},
        "open-mistral-nemo": {"input": 0.0003, "output": 0.0003},
        "sonar-reasoning-pro": {"input": 0.001, "output": 0.005},
        "sonar-pro": {"input": 0.001, "output": 0.005},
        "sonar": {"input": 0.0005, "output": 0.0005},
    }

    def __init__(self):
        self._usage: List[Dict[str, Any]] = []
        self._total_cost: float = 0.0

    def record(self, model: str, input_tokens: int, output_tokens: int):
        """Record a single API call's token usage and compute cost."""
        costs = self.COST_TABLE.get(model, {"input": 0.0, "output": 0.0})
        cost = (input_tokens / 1000) * costs["input"] + (output_tokens / 1000) * costs["output"]
        self._usage.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(cost, 6),
            "timestamp": datetime.now().isoformat(),
        })
        self._total_cost += cost
        # Keep at most 500 entries
        if len(self._usage) > 500:
            self._usage = self._usage[-500:]

    def get_total_cost(self) -> float:
        return round(self._total_cost, 4)

    def get_cost_report(self) -> str:
        if not self._usage:
            return "No API usage recorded."
        model_costs: Dict[str, float] = {}
        model_calls: Dict[str, int] = {}
        for u in self._usage:
            m = u["model"]
            model_costs[m] = model_costs.get(m, 0) + u["cost"]
            model_calls[m] = model_calls.get(m, 0) + 1
        lines = [
            "Provider Cost Report",
            "=" * 40,
            f"Total Cost: ${self.get_total_cost():.4f}",
            f"Total Requests: {len(self._usage)}",
            "",
        ]
        for m, c in sorted(model_costs.items(), key=lambda x: -x[1]):
            lines.append(f"  {m}: ${c:.4f} ({model_calls[m]} calls)")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ResponseCache
# ---------------------------------------------------------------------------

class ResponseCache:
    """LRU cache for AI responses — saves API calls and money."""

    def __init__(self, max_size: int = 200, ttl: int = 600):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl

    def _make_key(self, prompt: str, mode: str, system_prompt: str = None) -> str:
        raw = f"{mode}:{system_prompt or ''}:{prompt}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, prompt: str, mode: str, system_prompt: str = None) -> Optional[str]:
        key = self._make_key(prompt, mode, system_prompt)
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["time"] < self._ttl:
                self._cache.move_to_end(key)
                return entry["response"]
            else:
                del self._cache[key]
        return None

    def set(self, prompt: str, mode: str, response: str, system_prompt: str = None):
        key = self._make_key(prompt, mode, system_prompt)
        self._cache[key] = {"response": response, "time": time.time()}
        self._cache.move_to_end(key)
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self):
        self._cache.clear()

    @property
    def size(self):
        return len(self._cache)


# ---------------------------------------------------------------------------
# ProviderHealth
# ---------------------------------------------------------------------------

class ProviderHealth:
    """Tracks provider health — success rate, latency, failures, call rate."""

    def __init__(self):
        self._stats: Dict[str, Dict[str, Any]] = {}
        self._call_times: Dict[str, List[float]] = {}

    def _ensure(self, name: str):
        if name not in self._stats:
            self._stats[name] = {
                "calls": 0, "successes": 0, "failures": 0,
                "total_latency": 0.0, "last_failure": 0,
                "consecutive_failures": 0,
            }
        if name not in self._call_times:
            self._call_times[name] = []

    def record_call(self, name: str):
        """Record that a call was made (for rate tracking)."""
        self._ensure(name)
        now = time.time()
        self._call_times[name].append(now)
        # Keep only last 120 seconds of timestamps
        cutoff = now - 120
        self._call_times[name] = [t for t in self._call_times[name] if t > cutoff]

    def get_calls_last_minute(self, name: str) -> int:
        """Count calls made to this provider in the last 60 seconds."""
        self._ensure(name)
        now = time.time()
        cutoff = now - 60
        return sum(1 for t in self._call_times.get(name, []) if t > cutoff)

    def record_success(self, name: str, latency: float):
        self._ensure(name)
        s = self._stats[name]
        s["calls"] += 1
        s["successes"] += 1
        s["total_latency"] += latency
        s["consecutive_failures"] = 0

    def record_failure(self, name: str):
        self._ensure(name)
        s = self._stats[name]
        s["calls"] += 1
        s["failures"] += 1
        s["last_failure"] = time.time()
        s["consecutive_failures"] += 1

    def is_healthy(self, name: str) -> bool:
        self._ensure(name)
        s = self._stats[name]
        # Skip provider if 3+ consecutive failures in last 5 minutes
        if s["consecutive_failures"] >= 3 and (time.time() - s["last_failure"]) < 300:
            return False
        return True

    def get_avg_latency(self, name: str) -> float:
        self._ensure(name)
        s = self._stats[name]
        if s["successes"] == 0:
            return 999.0
        return s["total_latency"] / s["successes"]

    def get_success_rate(self, name: str) -> float:
        self._ensure(name)
        s = self._stats[name]
        if s["calls"] == 0:
            return 1.0
        return s["successes"] / s["calls"]

    def get_report(self) -> str:
        lines = ["Provider Health Report", "=" * 50]
        for name, s in sorted(self._stats.items()):
            rate = f"{self.get_success_rate(name)*100:.0f}%"
            avg_lat = f"{self.get_avg_latency(name):.2f}s"
            status = "HEALTHY" if self.is_healthy(name) else "UNHEALTHY"
            rpm = self.get_calls_last_minute(name)
            lines.append(
                f"  {name:15s} | {s['calls']:3d} calls | {rate:5s} success | "
                f"{avg_lat:7s} avg | {rpm:2d} rpm | {status}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ConversationMemory
# ---------------------------------------------------------------------------

class ConversationMemory:
    """Maintains conversation history for multi-turn chat."""

    def __init__(self, max_turns: int = 20):
        self._history: List[Dict[str, str]] = []
        self._max_turns = max_turns

    def add_user(self, message: str):
        self._history.append({"role": "user", "content": message})
        self._trim()

    def add_assistant(self, message: str):
        self._history.append({"role": "assistant", "content": message})
        self._trim()

    def _trim(self):
        # Keep max_turns * 2 messages (user + assistant pairs)
        max_messages = self._max_turns * 2
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]

    def get_messages(self, system_prompt: str = None) -> List[Dict[str, str]]:
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(self._history)
        return msgs

    def clear(self):
        self._history.clear()

    @property
    def turn_count(self):
        return len([m for m in self._history if m["role"] == "user"])


# ---------------------------------------------------------------------------
# MultiAIBrain
# ---------------------------------------------------------------------------

class MultiAIBrain:
    """
    The Ultra Cortex of Shell AI — V3.
    Multi-provider AI with caching, health tracking, conversation memory,
    intelligent fallback, token estimation, quality scoring, cost tracking,
    streaming, consensus generation, and chain-of-thought support.
    """

    _instance = None
    _instance_lock = None  # threading.Lock created lazily in get_instance

    def __init__(self):
        self.providers = {}
        self.cache = ResponseCache(max_size=200, ttl=600)
        self.health = ProviderHealth()
        self.conversation = ConversationMemory(max_turns=20)
        self.quality_scorer = ResponseQualityScorer()
        self.cost_tracker = ProviderCostTracker()
        self._total_calls = 0
        self._total_tokens_est = 0
        self._initialize_providers()

    @classmethod
    def get_instance(cls) -> "MultiAIBrain":
        """Thread-safe singleton access. The lock prevents concurrent
        async tasks from each instantiating the heavy provider chain
        (10 providers × HTTP-client construction) on first access."""
        if cls._instance is None:
            import threading
            if cls._instance_lock is None:
                cls._instance_lock = threading.Lock()
            with cls._instance_lock:
                # Re-check inside the lock — classic double-checked locking.
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _initialize_providers(self):
        provider_map = {
            "groq": GroqProvider,
            "gemini": GeminiProvider,
            "deepseek": DeepSeekProvider,
            "openrouter": OpenRouterProvider,
            "sambanova": SambaNovaProvider,
            # Blackbox public endpoint (api.blackbox.ai/api/chat) returns
            # 404 since their API was restructured. Disabled by default —
            # set BLACKBOX_ENABLED=1 in .env if you have a working URL.
            **({"blackbox": BlackboxProvider}
               if os.getenv("BLACKBOX_ENABLED", "0").strip() == "1" else {}),
            "openai": OpenAIProvider,
            "mistral": MistralProvider,
            "perplexity": PerplexityProvider,
        }
        for name, cls in provider_map.items():
            try:
                self.providers[name] = cls()
                logger.info(f"Provider '{name}' initialized.")
            except Exception as e:
                logger.warning(f"Provider '{name}' unavailable: {e}")

        if not self.providers:
            logger.error("CRITICAL: No AI providers initialized! Check API keys in .env")

    def reload_providers(self) -> list[str]:
        """Rebuild provider instances after API keys change at runtime."""
        self.providers.clear()
        self.health = ProviderHealth()
        self._initialize_providers()
        return sorted(self.providers.keys())

    # ------------------------------------------------------------------
    # Token estimation & prompt compression
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimation (1 token ~ 4 chars for English)."""
        return max(1, len(text) // 4)

    def _compress_prompt(self, prompt: str, max_tokens: int = 3000) -> str:
        """Compress a prompt if it exceeds *max_tokens* estimated tokens.

        Steps:
        1. If already under budget, return unchanged.
        2. Collapse excessive whitespace (runs of 3+ spaces/newlines).
        3. If still over budget, hard-truncate from the front so the most
           recent context is preserved, with a ``[...truncated...]`` marker.
        """
        if self.estimate_tokens(prompt) <= max_tokens:
            return prompt

        # Step 2 — collapse whitespace
        import re
        compressed = re.sub(r'[ \t]{3,}', '  ', prompt)
        compressed = re.sub(r'\n{3,}', '\n\n', compressed)

        if self.estimate_tokens(compressed) <= max_tokens:
            return compressed

        # Step 3 — hard truncate (keep the tail, which is usually the question)
        char_budget = max_tokens * 4  # reverse of estimate_tokens
        if len(compressed) > char_budget:
            compressed = "[...truncated...] " + compressed[-(char_budget - 20):]

        return compressed

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    async def generate_response(self, prompt: str, system_prompt: str = None,
                                 mode: str = "SMART", use_cache: bool = True,
                                 temperature: float = None,
                                 max_tokens: int = None) -> str:
        """
        Generate AI response with caching, health-aware routing, quality
        scoring, cost tracking, prompt compression, and fallback.
        """
        self._total_calls += 1

        # Check cache first
        if use_cache:
            cached = self.cache.get(prompt, mode, system_prompt)
            if cached:
                logger.info(f"[MultiBrain] Cache HIT for mode={mode}")
                return cached

        # Compress prompt if oversized
        compressed_prompt = self._compress_prompt(prompt, max_tokens=3000)

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": compressed_prompt})

        # Get provider sequence and filter unhealthy ones
        provider_sequence = SmartRouter.get_provider_sequence(mode)
        provider_timeout = _provider_timeout_s(mode)
        errors = []

        for provider_name in provider_sequence:
            provider = self.providers.get(provider_name)
            if not provider:
                continue

            # Skip unhealthy providers
            if not self.health.is_healthy(provider_name):
                logger.info(f"[MultiBrain] Skipping unhealthy provider: {provider_name}")
                continue

            model_name = SmartRouter.get_model_for_provider(mode, provider_name)

            try:
                start = time.time()
                logger.info(f"[MultiBrain] Trying {provider_name} [{model_name}]...")

                # Track call rate
                self.health.record_call(provider_name)

                kwargs = {"messages": messages, "model": model_name}
                if temperature is not None:
                    kwargs["temperature"] = temperature
                if max_tokens is not None:
                    kwargs["max_tokens"] = max_tokens

                response = await asyncio.wait_for(
                    provider.generate_response_async(**kwargs),
                    timeout=provider_timeout
                )

                latency = time.time() - start

                if not response:
                    raise Exception(f"{provider_name} returned empty response")
                if isinstance(response, str):
                    rs = response.strip()
                    # Providers historically return their failures as
                    # strings prefixed with "Error:", "<Provider> Error:",
                    # "<Provider> AI error:", etc., instead of raising.
                    # Normalise: any of those = treat as failure so the
                    # fallback chain gets to try the next provider.
                    rs_low = rs.lower()
                    bad_prefixes = (
                        "error:", "openai error", "mistral error",
                        "gemini error", "groq error", "blackbox error",
                        "blackbox ai error",
                        "deepseek error", "openrouter error",
                        "perplexity error", "sambanova error",
                    )
                    if any(rs_low.startswith(p) for p in bad_prefixes):
                        raise Exception(response)
                # Skip stub/placeholder responses
                if "integration via unofficial API is pending" in str(response):
                    raise Exception(f"{provider_name} is a stub provider")

                # Quality gate — reject low-quality responses and try next provider
                quality = self.quality_scorer.score(str(response), prompt)
                if quality < 0.4:
                    logger.warning(
                        f"[MultiBrain] {provider_name} response quality too low "
                        f"({quality:.2f}), trying next provider"
                    )
                    self.health.record_failure(provider_name)
                    errors.append(f"{provider_name} quality={quality:.2f}")
                    continue

                # Record success
                self.health.record_success(provider_name, latency)
                input_tok = self.estimate_tokens(compressed_prompt)
                output_tok = self.estimate_tokens(str(response))
                self._total_tokens_est += input_tok + output_tok

                # Cost tracking
                if model_name:
                    self.cost_tracker.record(model_name, input_tok, output_tok)

                # Cache the response
                if use_cache:
                    self.cache.set(prompt, mode, response, system_prompt)

                return response

            except asyncio.TimeoutError:
                error_msg = f"{provider_name} Timeout ({provider_timeout:g}s)"
                logger.warning(f"{error_msg}")
                self.health.record_failure(provider_name)
                errors.append(error_msg)
            except Exception as e:
                error_msg = f"{provider_name} Failed: {str(e)[:150]}"
                logger.warning(f"{error_msg}")
                self.health.record_failure(provider_name)
                errors.append(error_msg)
                continue

        return f"All Brains Failed. Errors: {'; '.join(errors)}"

    # ------------------------------------------------------------------
    # Streaming generation
    # ------------------------------------------------------------------

    async def generate_response_stream(
        self,
        prompt: str,
        system_prompt: str = None,
        mode: str = "SMART",
    ) -> AsyncGenerator[str, None]:
        """Async generator that yields response chunks as they arrive.

        If the chosen provider supports ``generate_response_stream_async``,
        chunks are yielded in real time.  Otherwise, falls back to
        ``generate_response`` and yields the full response as a single chunk.

        The concatenated result is cached once streaming completes.
        """
        compressed_prompt = self._compress_prompt(prompt, max_tokens=3000)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": compressed_prompt})

        provider_sequence = SmartRouter.get_provider_sequence(mode)
        provider_timeout = _provider_timeout_s(mode)

        for provider_name in provider_sequence:
            provider = self.providers.get(provider_name)
            if not provider or not self.health.is_healthy(provider_name):
                continue

            model_name = SmartRouter.get_model_for_provider(mode, provider_name)
            self.health.record_call(provider_name)
            start = time.time()

            # Attempt streaming if the provider exposes the method
            if hasattr(provider, "generate_response_stream_async"):
                try:
                    collected: List[str] = []
                    async for chunk in provider.generate_response_stream_async(
                        messages=messages, model=model_name
                    ):
                        collected.append(chunk)
                        yield chunk

                    full_response = "".join(collected)
                    latency = time.time() - start

                    if not full_response.strip():
                        raise Exception(f"{provider_name} stream returned empty")

                    self.health.record_success(provider_name, latency)
                    input_tok = self.estimate_tokens(compressed_prompt)
                    output_tok = self.estimate_tokens(full_response)
                    self._total_tokens_est += input_tok + output_tok
                    if model_name:
                        self.cost_tracker.record(model_name, input_tok, output_tok)
                    self.cache.set(prompt, mode, full_response, system_prompt)
                    return  # successfully streamed

                except Exception as e:
                    logger.warning(f"[MultiBrain] Streaming failed for {provider_name}: {e}")
                    self.health.record_failure(provider_name)
                    continue

            # Fallback — non-streaming provider
            try:
                response = await asyncio.wait_for(
                    provider.generate_response_async(messages=messages, model=model_name),
                    timeout=provider_timeout,
                )
                latency = time.time() - start

                if not response or "integration via unofficial API is pending" in str(response):
                    raise Exception(f"{provider_name} returned invalid response")

                self.health.record_success(provider_name, latency)
                input_tok = self.estimate_tokens(compressed_prompt)
                output_tok = self.estimate_tokens(str(response))
                self._total_tokens_est += input_tok + output_tok
                if model_name:
                    self.cost_tracker.record(model_name, input_tok, output_tok)
                self.cache.set(prompt, mode, response, system_prompt)
                yield response
                return

            except Exception as e:
                logger.warning(f"[MultiBrain] Fallback failed for {provider_name}: {e}")
                self.health.record_failure(provider_name)
                continue

        # Every provider failed. Do NOT yield an error string — that would
        # appear in the user's chat as a chunk. Instead, log loudly and
        # return without yielding. The caller treats the empty stream as
        # a failure and falls back to its non-streaming chat() path.
        logger.error("[MultiBrain] All providers failed for streaming. "
                     "Caller should fall back to generate_response().")
        return

    # ------------------------------------------------------------------
    # Consensus generation
    # ------------------------------------------------------------------

    async def consensus_generate(
        self,
        prompt: str,
        system_prompt: str = None,
        n_providers: int = 3,
        mode: str = "SMART",
    ) -> str:
        """Query up to *n_providers* in parallel and return the best response.

        Selection strategy:
        - Score each response with ResponseQualityScorer.
        - If two or more responses share >60 % of their unique words (they
          largely agree), return the shorter of them (conciseness wins).
        - Otherwise, return the highest-scoring response.
        """
        provider_sequence = SmartRouter.get_provider_sequence(mode)
        # Pick healthy providers up to n_providers
        chosen: List[str] = []
        for pname in provider_sequence:
            if pname in self.providers and self.health.is_healthy(pname):
                chosen.append(pname)
            if len(chosen) >= n_providers:
                break

        if not chosen:
            return "All Brains Failed. No healthy providers available."

        compressed_prompt = self._compress_prompt(prompt, max_tokens=3000)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": compressed_prompt})

        async def _call(pname: str) -> Optional[str]:
            provider = self.providers[pname]
            model_name = SmartRouter.get_model_for_provider(mode, pname)
            self.health.record_call(pname)
            try:
                start = time.time()
                resp = await asyncio.wait_for(
                    provider.generate_response_async(messages=messages, model=model_name),
                    timeout=provider_timeout,
                )
                latency = time.time() - start
                if not resp or "integration via unofficial API is pending" in str(resp):
                    raise Exception("invalid")
                self.health.record_success(pname, latency)
                input_tok = self.estimate_tokens(compressed_prompt)
                output_tok = self.estimate_tokens(str(resp))
                self._total_tokens_est += input_tok + output_tok
                if model_name:
                    self.cost_tracker.record(model_name, input_tok, output_tok)
                return str(resp)
            except Exception as e:
                self.health.record_failure(pname)
                logger.warning(f"[Consensus] {pname} failed: {e}")
                return None

        results = await asyncio.gather(*[_call(p) for p in chosen])
        valid = [(r, self.quality_scorer.score(r, prompt)) for r in results if r]

        if not valid:
            return "All Brains Failed. No valid responses from consensus providers."

        # Check for agreement (>60 % word overlap between any two)
        def _word_set(text: str):
            return set(text.lower().split())

        for i in range(len(valid)):
            for j in range(i + 1, len(valid)):
                words_i = _word_set(valid[i][0])
                words_j = _word_set(valid[j][0])
                if not words_i or not words_j:
                    continue
                overlap = len(words_i & words_j) / min(len(words_i), len(words_j))
                if overlap > 0.6:
                    # They agree — return the shorter (more concise) one
                    agreed = min(valid[i][0], valid[j][0], key=len)
                    self.cache.set(prompt, mode, agreed, system_prompt)
                    return agreed

        # No strong agreement — return highest quality score
        best = max(valid, key=lambda x: x[1])[0]
        self.cache.set(prompt, mode, best, system_prompt)
        return best

    # ------------------------------------------------------------------
    # Chain-of-thought generation
    # ------------------------------------------------------------------

    async def generate_with_cot(
        self,
        prompt: str,
        system_prompt: str = None,
        mode: str = "REASONING",
    ) -> str:
        """Generate a response using explicit chain-of-thought prompting.

        Prepends structured COT instructions to the system prompt so the
        model is encouraged to show its reasoning step-by-step.
        """
        cot_prefix = (
            "You are an expert reasoning assistant. For every question:\n"
            "1. Break the problem down into clear steps.\n"
            "2. Think through each step carefully, showing your work.\n"
            "3. After reasoning, give a clear final answer prefixed with "
            "'**Answer:**'.\n\n"
        )
        if system_prompt:
            enriched_system = cot_prefix + system_prompt
        else:
            enriched_system = cot_prefix

        return await self.generate_response(
            prompt, system_prompt=enriched_system, mode=mode, use_cache=True
        )

    # ------------------------------------------------------------------
    # Multi-turn chat
    # ------------------------------------------------------------------

    async def chat(self, user_message: str, system_prompt: str = None,
                   mode: str = "SMART") -> str:
        """Multi-turn conversation with history."""
        self.conversation.add_user(user_message)
        messages = self.conversation.get_messages(system_prompt)

        provider_sequence = SmartRouter.get_provider_sequence(mode)
        provider_timeout = _provider_timeout_s(mode)
        errors = []

        for provider_name in provider_sequence:
            provider = self.providers.get(provider_name)
            if not provider or not self.health.is_healthy(provider_name):
                continue

            model_name = SmartRouter.get_model_for_provider(mode, provider_name)
            self.health.record_call(provider_name)
            try:
                start = time.time()
                response = await asyncio.wait_for(
                    provider.generate_response_async(messages=messages, model=model_name),
                    timeout=provider_timeout
                )
                latency = time.time() - start

                if not response or "integration via unofficial API is pending" in str(response):
                    raise Exception(f"{provider_name} returned invalid response")

                self.health.record_success(provider_name, latency)
                input_tok = self.estimate_tokens(user_message)
                output_tok = self.estimate_tokens(str(response))
                self._total_tokens_est += input_tok + output_tok
                if model_name:
                    self.cost_tracker.record(model_name, input_tok, output_tok)
                self.conversation.add_assistant(response)
                return response

            except Exception as e:
                self.health.record_failure(provider_name)
                errors.append(f"{provider_name}: {str(e)[:100]}")
                continue

        return f"All Brains Failed. Errors: {'; '.join(errors)}"

    # ------------------------------------------------------------------
    # Context-enriched (RAG-style) generation
    # ------------------------------------------------------------------

    async def generate_with_context(self, prompt: str, context: str,
                                     mode: str = "SMART") -> str:
        """Generate response with additional context (RAG-style)."""
        enriched_prompt = f"""Context Information:
{context[:3000]}

Based on the above context, answer this:
{prompt}"""
        return await self.generate_response(enriched_prompt, mode=mode)

    # ------------------------------------------------------------------
    # Parallel multi-mode generation
    # ------------------------------------------------------------------

    async def parallel_generate(self, prompt: str, modes: List[str] = None) -> Dict[str, str]:
        """Generate responses from multiple modes in parallel for comparison."""
        if modes is None:
            modes = ["FAST", "SMART", "REASONING"]

        tasks = {
            mode: self.generate_response(prompt, mode=mode, use_cache=False)
            for mode in modes
        }

        results = {}
        for mode, task in tasks.items():
            try:
                results[mode] = await asyncio.wait_for(task, timeout=30.0)
            except Exception as e:
                results[mode] = f"Error: {e}"

        return results

    # ------------------------------------------------------------------
    # Synchronous wrapper
    # ------------------------------------------------------------------

    def generate_response_sync(self, prompt: str, system_prompt: str = None,
                                mode: str = "SMART") -> str:
        """Synchronous wrapper — safe for both async and non-async contexts."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            def _run_in_new_loop():
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(
                        self.generate_response(prompt, system_prompt, mode)
                    )
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_run_in_new_loop)
                return future.result(timeout=60)
        else:
            return asyncio.run(self.generate_response(prompt, system_prompt, mode))

    # ------------------------------------------------------------------
    # Statistics & reports
    # ------------------------------------------------------------------

    def get_brain_stats(self) -> Dict[str, Any]:
        """Full brain statistics."""
        return {
            "total_calls": self._total_calls,
            "estimated_tokens": self._total_tokens_est,
            "cache_size": self.cache.size,
            "conversation_turns": self.conversation.turn_count,
            "active_providers": list(self.providers.keys()),
            "healthy_providers": [
                name for name in self.providers
                if self.health.is_healthy(name)
            ],
            "total_cost": self.cost_tracker.get_total_cost(),
        }

    def get_health_report(self) -> str:
        """Provider health dashboard."""
        stats = self.get_brain_stats()
        report = [
            "Shell AI Brain — Ultra Cortex V3",
            "=" * 50,
            f"Total API Calls: {stats['total_calls']}",
            f"Estimated Tokens Used: {stats['estimated_tokens']:,}",
            f"Estimated Cost: ${stats['total_cost']:.4f}",
            f"Cache Size: {stats['cache_size']}/200",
            f"Conversation Turns: {stats['conversation_turns']}",
            f"Active Providers: {len(stats['active_providers'])}",
            f"Healthy Providers: {len(stats['healthy_providers'])}",
            "",
            self.health.get_report(),
            "",
            self.cost_tracker.get_cost_report(),
        ]
        return "\n".join(report)
