"""
Context Engine for Shell AI.
Manages context-window budget allocation, compression, relevance ranking,
and caching. Pure Python -- no external dependencies.
"""

import hashlib
import re
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple


class ContextEngine:
    """
    Builds, compresses, and selects context for LLM prompts while
    staying within a configurable token budget.
    """

    # Budget allocation ratios per source category
    DEFAULT_BUDGETS: Dict[str, float] = {
        "conversation": 0.40,
        "memory": 0.30,
        "working_memory": 0.15,
        "corrections": 0.10,
        "knowledge": 0.05,
    }

    def __init__(self, max_context_tokens: int = 4000) -> None:
        self.max_context_tokens = max_context_tokens

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 characters per token."""
        return len(text) // 4

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    def build_context(self, query: str, sources: Dict[str, str]) -> str:
        """
        Assemble a structured context block from *sources* (keyed by
        category name) while respecting per-category budgets.

        Args:
            query: the current user query (used for relevance trimming).
            sources: mapping of category -> raw text.
                     Recognised categories: conversation, memory,
                     working_memory, corrections, knowledge.
                     Unknown categories are appended under 'extra'.

        Returns:
            A single string ready to be prepended to the system prompt.
        """
        sections: List[str] = []

        for category, ratio in self.DEFAULT_BUDGETS.items():
            raw = sources.get(category, "")
            if not raw:
                continue
            budget_tokens = int(self.max_context_tokens * ratio)
            trimmed = self._trim_to_budget(raw, budget_tokens)
            header = category.replace("_", " ").upper()
            sections.append(f"=== {header} ===\n{trimmed}")

        # Handle any extra categories not in the default budgets
        extra_keys = set(sources.keys()) - set(self.DEFAULT_BUDGETS.keys())
        if extra_keys:
            extra_budget = int(self.max_context_tokens * 0.05)
            per_extra = max(extra_budget // len(extra_keys), 50)
            for key in sorted(extra_keys):
                raw = sources[key]
                if not raw:
                    continue
                trimmed = self._trim_to_budget(raw, per_extra)
                header = key.replace("_", " ").upper()
                sections.append(f"=== {header} ===\n{trimmed}")

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Compression strategies
    # ------------------------------------------------------------------

    def compress_context(self, text: str, target_tokens: int = 2000) -> str:
        """
        Progressively compress *text* until it fits within *target_tokens*.

        Strategies (applied in order):
            1. Collapse redundant whitespace.
            2. Keep only the first and last sentence of each paragraph.
            3. Keep only sentences containing query-relevant keywords
               (falls back to first sentence of input if nothing matches).
        """
        # Strategy 1 -- whitespace normalisation
        compressed = self._strip_whitespace(text)
        if self.estimate_tokens(compressed) <= target_tokens:
            return compressed

        # Strategy 2 -- first + last sentence per paragraph
        compressed = self._first_last_sentences(compressed)
        if self.estimate_tokens(compressed) <= target_tokens:
            return compressed

        # Strategy 3 -- keyword-only sentences (generic, no query)
        compressed = self._keyword_sentences(compressed, keywords=set())
        if self.estimate_tokens(compressed) <= target_tokens:
            return compressed

        # Last resort: hard truncate
        char_limit = target_tokens * 4
        return compressed[:char_limit]

    def compress_context_for_query(
        self, text: str, query: str, target_tokens: int = 2000
    ) -> str:
        """Like compress_context but uses *query* keywords in strategy 3."""
        compressed = self._strip_whitespace(text)
        if self.estimate_tokens(compressed) <= target_tokens:
            return compressed

        compressed = self._first_last_sentences(compressed)
        if self.estimate_tokens(compressed) <= target_tokens:
            return compressed

        keywords = set(re.findall(r"[a-z]{3,}", query.lower()))
        compressed = self._keyword_sentences(compressed, keywords)
        if self.estimate_tokens(compressed) <= target_tokens:
            return compressed

        char_limit = target_tokens * 4
        return compressed[:char_limit]

    # ------------------------------------------------------------------
    # Relevance selection
    # ------------------------------------------------------------------

    def select_relevant_context(
        self,
        query: str,
        context_chunks: List[str],
        top_k: int = 5,
    ) -> List[str]:
        """
        Rank *context_chunks* by Jaccard similarity to *query* and
        return the top-K chunks that fit within the token budget.
        """
        query_words = set(re.findall(r"[a-z]{3,}", query.lower()))
        if not query_words:
            return context_chunks[:top_k]

        scored: List[Tuple[float, int, str]] = []
        for idx, chunk in enumerate(context_chunks):
            chunk_words = set(re.findall(r"[a-z]{3,}", chunk.lower()))
            if not chunk_words:
                scored.append((0.0, idx, chunk))
                continue
            intersection = query_words & chunk_words
            union = query_words | chunk_words
            jaccard = len(intersection) / len(union)
            scored.append((jaccard, idx, chunk))

        scored.sort(key=lambda t: (-t[0], t[1]))

        selected: List[str] = []
        remaining_budget = self.max_context_tokens
        for _score, _idx, chunk in scored:
            tokens = self.estimate_tokens(chunk)
            if tokens > remaining_budget:
                continue
            selected.append(chunk)
            remaining_budget -= tokens
            if len(selected) >= top_k:
                break

        return selected

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim_to_budget(self, text: str, budget_tokens: int) -> str:
        """Truncate *text* to fit within *budget_tokens*."""
        if self.estimate_tokens(text) <= budget_tokens:
            return text
        char_limit = budget_tokens * 4
        truncated = text[:char_limit]
        # Try to break at last newline or sentence boundary
        last_nl = truncated.rfind("\n")
        if last_nl > char_limit * 0.5:
            truncated = truncated[:last_nl]
        return truncated

    @staticmethod
    def _strip_whitespace(text: str) -> str:
        """Collapse runs of whitespace and blank lines."""
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _first_last_sentences(text: str) -> str:
        """Keep the first and last sentence of every paragraph."""
        paragraphs = re.split(r"\n\s*\n", text)
        result_parts: List[str] = []
        for para in paragraphs:
            sentences = re.split(r"(?<=[.!?])\s+", para.strip())
            if len(sentences) <= 2:
                result_parts.append(para.strip())
            else:
                result_parts.append(f"{sentences[0]} {sentences[-1]}")
        return "\n\n".join(result_parts)

    @staticmethod
    def _keyword_sentences(text: str, keywords: set) -> str:
        """Keep only sentences containing at least one keyword."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if not keywords:
            # No keywords provided -- return first sentence as fallback
            return sentences[0] if sentences else text
        kept = [
            s for s in sentences
            if any(kw in s.lower() for kw in keywords)
        ]
        return " ".join(kept) if kept else (sentences[0] if sentences else text)


class ContextCache:
    """
    LRU + TTL cache for pre-built context strings.
    Uses an OrderedDict for efficient eviction.
    """

    def __init__(self, max_size: int = 50, ttl: int = 300) -> None:
        self.max_size = max_size
        self.ttl = ttl  # seconds
        self._cache: OrderedDict[str, Tuple[str, float]] = OrderedDict()

    @staticmethod
    def _hash(query: str) -> str:
        return hashlib.md5(query.encode("utf-8")).hexdigest()

    def get(self, query: str) -> Optional[str]:
        """Return cached context if it exists and has not expired."""
        key = self._hash(query)
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, ts = entry
        if time.time() - ts > self.ttl:
            del self._cache[key]
            return None
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return value

    def set(self, query: str, context: str) -> None:
        """Store context, evicting the oldest entry if over capacity."""
        key = self._hash(query)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (context, time.time())
        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


# Module-level singletons
context_engine = ContextEngine()
context_cache = ContextCache()
