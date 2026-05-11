"""
SmartRouter - EXTREME Edition
==============================
Intelligent routing with 8 modes, context-aware detection, load balancing,
latency-based routing, cost optimization, composite modes, and AI-based detection.
"""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("SmartRouter")


class SmartRouter:
    """
    Decides which model provider and model to use based on the task type (mode).
    Updated model names for 2025/2026 compatibility.
    8 modes with intelligent keyword-based auto-detection.
    Extended with context-aware routing, load balancing, latency routing,
    cost optimization, composite modes, and AI-based detection.
    """

    MODE_CONFIG = {
        "FAST": {
            "groq": "llama-3.3-70b-versatile",
            "sambanova": "Meta-Llama-3.1-8B-Instruct",
            "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
            "gemini": "gemini-2.0-flash-lite",
            "deepseek": "deepseek-chat",
            "blackbox": "blackbox",
            "openai": "gpt-4o-mini",
            "priority": ["groq", "sambanova", "openrouter", "gemini", "deepseek", "blackbox", "openai"]
        },
        "SMART": {
            "groq": "llama-3.3-70b-versatile",
            "deepseek": "deepseek-chat",
            "gemini": "gemini-2.5-flash",
            "openrouter": "deepseek/deepseek-chat-v3-0324:free",
            "perplexity": "sonar-reasoning-pro",
            "openai": "gpt-4o",
            "mistral": "mistral-large-latest",
            "priority": ["groq", "deepseek", "gemini", "openrouter", "perplexity", "openai", "mistral"]
        },
        "CODING": {
            "groq": "llama-3.3-70b-versatile",
            "deepseek": "deepseek-chat",
            "openrouter": "deepseek/deepseek-chat-v3-0324:free",
            "blackbox": "blackbox-code",
            "sambanova": "Llama-3.3-70B-Instruct",
            "gemini": "gemini-2.5-flash",
            "openai": "gpt-4o",
            "priority": ["groq", "deepseek", "openrouter", "blackbox", "sambanova", "gemini", "openai"]
        },
        "REASONING": {
            "groq": "llama-3.3-70b-versatile",
            "deepseek": "deepseek-reasoner",
            "gemini": "gemini-2.5-flash",
            "openrouter": "qwen/qwen-2.5-72b-instruct:free",
            "perplexity": "sonar-reasoning-pro",
            "openai": "o3-mini",
            "priority": ["groq", "deepseek", "gemini", "openrouter", "perplexity", "openai"]
        },
        "CHEAP": {
            "groq": "llama-3.1-8b-instant",
            "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
            "sambanova": "Meta-Llama-3.1-8B-Instruct",
            "blackbox": "blackbox",
            "gemini": "gemini-2.0-flash-lite",
            "deepseek": "deepseek-chat",
            "priority": ["groq", "openrouter", "sambanova", "blackbox", "gemini", "deepseek"]
        },
        "CREATIVE": {
            "groq": "llama-3.3-70b-versatile",
            "deepseek": "deepseek-chat",
            "gemini": "gemini-2.5-flash",
            "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
            "openai": "gpt-4o",
            "priority": ["groq", "deepseek", "gemini", "openrouter", "openai"]
        },
        "RESEARCH": {
            "perplexity": "sonar-reasoning-pro",
            "deepseek": "deepseek-chat",
            "groq": "llama-3.3-70b-versatile",
            "gemini": "gemini-2.5-flash",
            "openrouter": "deepseek/deepseek-chat-v3-0324:free",
            "openai": "gpt-4o",
            "priority": ["perplexity", "deepseek", "groq", "gemini", "openrouter", "openai"]
        },
        "TRANSLATE": {
            "gemini": "gemini-2.5-flash",
            "groq": "llama-3.3-70b-versatile",
            "deepseek": "deepseek-chat",
            "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
            "openai": "gpt-4o",
            "priority": ["gemini", "groq", "deepseek", "openrouter", "openai"]
        },
    }

    # Keyword mappings for mode detection, ordered by specificity (most specific first)
    _MODE_KEYWORDS = {
        "TRANSLATE": [
            "translate", "translation", "convert to", "in hindi", "in english",
            "in spanish", "in french", "in german", "in japanese", "in chinese",
            "in arabic", "in korean", "in portuguese", "in russian", "in italian",
            "in urdu", "in bengali", "in tamil", "in telugu", "in marathi",
            "to english", "to hindi", "to spanish", "to french", "to german",
            "language", "transliterate", "localize",
        ],
        "CODING": [
            "code", "script", "function", "debug", "fix", "program", "app",
            "html", "python", "java", "javascript", "typescript", "react",
            "api", "database", "sql", "css", "backend", "frontend", "deploy",
            "compile", "runtime", "error", "bug", "refactor", "regex",
            "algorithm", "class", "method", "endpoint", "server", "docker",
            "git", "repository", "npm", "pip", "package", "framework",
        ],
        "REASONING": [
            "solve", "calculate", "logic", "math", "prove", "derive",
            "equation", "formula", "theorem", "probability", "statistics",
            "reasoning", "deduce", "infer", "puzzle", "riddle",
        ],
        "CREATIVE": [
            "write story", "poem", "creative", "imagine", "design", "compose",
            "lyrics", "novel", "blog", "fiction", "narrative", "character",
            "dialogue", "screenplay", "haiku", "sonnet", "limerick",
            "fairy tale", "fantasy", "sci-fi", "horror story", "romance",
            "blog post", "article", "content", "copywriting", "slogan",
            "tagline", "brainstorm", "ideate",
        ],
        "RESEARCH": [
            "research", "analyze", "detailed", "deep dive", "report",
            "history of", "explain complex", "compare", "pros and cons",
            "case study", "investigation", "survey", "literature review",
            "in-depth", "comprehensive", "thorough analysis", "white paper",
            "findings", "methodology", "systematic",
        ],
    }

    # ─── Free providers for cost-optimized routing ───
    FREE_PROVIDERS = {"groq", "sambanova", "gemini", "blackbox", "openrouter", "deepseek"}

    # ─── Composite mode definitions ───
    COMPOSITE_MODES = {
        "CODING+RESEARCH": {
            "primary": "CODING",
            "secondary": "RESEARCH",
            "strategy": "research_then_code",
        },
        "CREATIVE+RESEARCH": {
            "primary": "CREATIVE",
            "secondary": "RESEARCH",
            "strategy": "research_then_create",
        },
    }

    # ─── AI mode detection cache ───
    _ai_mode_cache: Dict[str, tuple] = {}  # query_hash -> (mode, timestamp)
    _AI_CACHE_TTL = 60  # seconds

    # ─── Original methods (preserved) ───

    @staticmethod
    def get_provider_sequence(mode: str = "SMART") -> List[str]:
        mode = mode.upper()
        if mode not in SmartRouter.MODE_CONFIG:
            mode = "SMART"
        return SmartRouter.MODE_CONFIG[mode]["priority"]

    @staticmethod
    def get_model_for_provider(mode: str, provider_name: str) -> Optional[str]:
        mode = mode.upper()
        if mode not in SmartRouter.MODE_CONFIG:
            mode = "SMART"
        config = SmartRouter.MODE_CONFIG[mode]
        return config.get(provider_name.lower())

    @staticmethod
    def detect_mode(query: str) -> str:
        """Auto-selects the best mode based on user query keywords with scoring."""
        q = query.lower()

        best_mode = "FAST"
        best_score = 0

        for mode, keywords in SmartRouter._MODE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q)
            if score > best_score:
                best_score = score
                best_mode = mode

        return best_mode

    # ─── NEW: Context-aware routing ───

    @staticmethod
    def detect_mode_with_context(
        query: str, conversation_history: List[Dict] = None
    ) -> str:
        """
        Detect mode using keywords + conversation context.
        If the last 3 user messages all triggered the same mode, boost that mode 2x.
        """
        q = query.lower()

        # Score each mode by keywords
        mode_scores: Dict[str, int] = {}
        for mode, keywords in SmartRouter._MODE_KEYWORDS.items():
            mode_scores[mode] = sum(1 for kw in keywords if kw in q)

        # Context boost: scan last 3 user messages
        if conversation_history:
            user_msgs = [
                m["content"]
                for m in conversation_history
                if m.get("role") == "user"
            ]
            recent = user_msgs[-3:] if len(user_msgs) >= 3 else []

            if len(recent) == 3:
                recent_modes = [SmartRouter.detect_mode(msg) for msg in recent]
                # If all 3 triggered the same non-FAST mode, boost it
                if len(set(recent_modes)) == 1 and recent_modes[0] != "FAST":
                    boosted = recent_modes[0]
                    mode_scores[boosted] = mode_scores.get(boosted, 0) * 2
                    # Ensure at least score of 2 for the boosted mode
                    if mode_scores[boosted] == 0:
                        mode_scores[boosted] = 2

        # Pick best
        best_mode = "FAST"
        best_score = 0
        for mode, score in mode_scores.items():
            if score > best_score:
                best_score = score
                best_mode = mode

        return best_mode

    # ─── NEW: Load balancing ───

    @staticmethod
    def get_provider_sequence_balanced(
        mode: str, health_data: Dict = None
    ) -> List[str]:
        """
        Get provider sequence reordered by health/load score.
        health_data format per provider:
            {"calls_in_last_min": int, "success_rate": float, "avg_latency": float}
        """
        base_sequence = SmartRouter.get_provider_sequence(mode)

        if not health_data:
            return base_sequence

        def _score(provider: str) -> float:
            data = health_data.get(provider)
            if not data:
                return 0.5  # neutral score for unknown providers
            calls = data.get("calls_in_last_min", 0)
            success_rate = data.get("success_rate", 1.0)
            avg_latency = data.get("avg_latency", 1.0)

            load_factor = 1.0 - min(calls / 10.0, 1.0)
            latency_factor = 1.0 / max(avg_latency, 0.01)

            score = load_factor * 0.4 + success_rate * 0.3 + latency_factor * 0.3
            return score

        scored = [(p, _score(p)) for p in base_sequence]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [p for p, _ in scored]

    # ─── NEW: Latency-based routing ───

    @staticmethod
    def get_providers_by_latency(
        provider_names: List[str], latency_data: Dict
    ) -> List[str]:
        """
        Sort providers by average latency ascending.
        latency_data: {provider_name: avg_latency_seconds}
        Providers missing from latency_data go to the end.
        """
        def _lat(name: str) -> float:
            return latency_data.get(name, 999.0)

        return sorted(provider_names, key=_lat)

    # ─── NEW: Cost-optimized routing ───

    @staticmethod
    def get_cheapest_sequence(mode: str) -> List[str]:
        """
        Get providers for mode with free providers first, then paid.
        Order within each group is preserved from MODE_CONFIG priority.
        """
        base_sequence = SmartRouter.get_provider_sequence(mode)
        free = [p for p in base_sequence if p in SmartRouter.FREE_PROVIDERS]
        paid = [p for p in base_sequence if p not in SmartRouter.FREE_PROVIDERS]
        return free + paid

    # ─── NEW: Composite modes ───

    @staticmethod
    def detect_composite_mode(query: str) -> Optional[Dict]:
        """
        Check if a query matches both primary and secondary mode keywords
        for any composite mode definition.
        Returns composite config dict if matched, None otherwise.
        """
        q = query.lower()

        for combo_name, config in SmartRouter.COMPOSITE_MODES.items():
            primary = config["primary"]
            secondary = config["secondary"]

            primary_kws = SmartRouter._MODE_KEYWORDS.get(primary, [])
            secondary_kws = SmartRouter._MODE_KEYWORDS.get(secondary, [])

            primary_hits = sum(1 for kw in primary_kws if kw in q)
            secondary_hits = sum(1 for kw in secondary_kws if kw in q)

            if primary_hits >= 1 and secondary_hits >= 1:
                return {
                    "name": combo_name,
                    "primary": primary,
                    "secondary": secondary,
                    "strategy": config["strategy"],
                    "primary_score": primary_hits,
                    "secondary_score": secondary_hits,
                }

        return None

    # ─── NEW: AI-based mode detection ───

    @staticmethod
    async def detect_mode_ai(query: str, brain) -> str:
        """
        Use AI to classify the query into a mode.
        Only called when keyword score is low (< 2).
        Caches results for 60 seconds. 5-second timeout.
        Falls back to keyword-based detection on failure.
        """
        # First check keyword score
        keyword_result = SmartRouter.detect_mode(query)
        q_lower = query.lower()
        keyword_score = 0
        for mode, keywords in SmartRouter._MODE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q_lower)
            if score > keyword_score:
                keyword_score = score

        # If keyword detection is confident enough, use it directly
        if keyword_score >= 2:
            return keyword_result

        # Check cache
        import hashlib
        cache_key = hashlib.md5(query.encode()).hexdigest()
        cached = SmartRouter._ai_mode_cache.get(cache_key)
        if cached:
            cached_mode, cached_time = cached
            if time.time() - cached_time < SmartRouter._AI_CACHE_TTL:
                return cached_mode

        # Ask AI to classify
        valid_modes = list(SmartRouter.MODE_CONFIG.keys())
        classification_prompt = (
            f"Classify this user query into exactly ONE of these modes: "
            f"{', '.join(valid_modes)}.\n\n"
            f"Query: {query}\n\n"
            f"Return ONLY the mode name, nothing else."
        )

        try:
            response = await asyncio.wait_for(
                brain.generate_response(
                    prompt=classification_prompt,
                    mode="FAST",
                    use_cache=False,
                    max_tokens=20,
                ),
                timeout=5.0,
            )

            detected = response.strip().upper()
            # Validate the response is a known mode
            if detected in SmartRouter.MODE_CONFIG:
                SmartRouter._ai_mode_cache[cache_key] = (detected, time.time())
                logger.info(f"[SmartRouter] AI detected mode: {detected}")
                return detected
            else:
                logger.warning(
                    f"[SmartRouter] AI returned invalid mode '{detected}', "
                    f"falling back to keyword: {keyword_result}"
                )
                return keyword_result

        except asyncio.TimeoutError:
            logger.warning("[SmartRouter] AI mode detection timed out")
            return keyword_result
        except Exception as e:
            logger.warning(f"[SmartRouter] AI mode detection failed: {e}")
            return keyword_result
