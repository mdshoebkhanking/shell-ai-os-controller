"""
shell_llm_client
================

Unified, SDK-agnostic LLM client for the shell project.

This module provides a single :class:`LLMClient` that internally routes between
the modern ``google.genai`` Client API (preferred) and the legacy
``google.generativeai`` module (fallback), mirroring the dual-SDK pattern used
in ``vision_engine.py`` after the Phase 9 cutover.

The client exposes three high-level async entry points:

* :meth:`LLMClient.generate`            - plain text completion.
* :meth:`LLMClient.generate_with_image` - multimodal (text + image) completion.
* :meth:`LLMClient.embed`               - embedding generation.

It also provides:

* Built-in retry with exponential backoff, using ``tenacity`` if available and
  a small hand-rolled helper otherwise. ``tenacity`` is never hard-required.
* Token usage accounting on :attr:`LLMClient.stats`.
* A thread-safe singleton accessor :meth:`LLMClient.get`.
* Default model names pulled from ``shell_config.config.voice["model"]``.

Environment
-----------
Reads ``GOOGLE_API_KEY`` from the process environment at initialisation time,
matching the behaviour of the existing ``VisionEngine``.

Logger
------
All log output goes through the logger named ``shell_llm_client``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import threading
from typing import Any, Iterable, List, Optional, Sequence, Union

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("shell_llm_client")

# ---------------------------------------------------------------------------
# Dual-SDK import (prefer google-genai, fall back to google-generativeai)
# ---------------------------------------------------------------------------
# The legacy ``google.generativeai`` package is deprecated. We try the new
# ``google.genai`` Client API first and only fall back to legacy if the new
# SDK isn't installed. Both paths end up driving the same public surface.
_NEW_GENAI_AVAILABLE = False
_LEGACY_GENAI_AVAILABLE = False
try:  # pragma: no cover - import side effect
    from google import genai as _new_genai_mod  # type: ignore
    _NEW_GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _new_genai_mod = None  # type: ignore[assignment]

_legacy_genai_mod = None  # type: ignore[assignment]


def _load_legacy_genai() -> bool:
    """Load deprecated google-generativeai only when the modern SDK is absent.

    Importing the legacy package emits deprecation warnings and pulls a heavier
    dependency chain, so the default production path avoids it entirely.
    """
    global _LEGACY_GENAI_AVAILABLE, _legacy_genai_mod
    if _LEGACY_GENAI_AVAILABLE:
        return True
    try:  # pragma: no cover - optional fallback
        import google.generativeai as legacy_genai_mod  # type: ignore
    except ImportError:  # pragma: no cover
        _legacy_genai_mod = None  # type: ignore[assignment]
        return False
    _legacy_genai_mod = legacy_genai_mod
    _LEGACY_GENAI_AVAILABLE = True
    return True


if not _NEW_GENAI_AVAILABLE:  # pragma: no cover - legacy-only installs
    _load_legacy_genai()

# ---------------------------------------------------------------------------
# Optional tenacity for retry. We never hard-require it.
# ---------------------------------------------------------------------------
try:  # pragma: no cover - optional
    import tenacity as _tenacity  # type: ignore
    _TENACITY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _tenacity = None  # type: ignore[assignment]
    _TENACITY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Default model fallback constants
# ---------------------------------------------------------------------------
_FALLBACK_TEXT_MODEL = "gemini-2.5-flash"
_FALLBACK_EMBED_MODEL = "text-embedding-004"


def _is_non_retryable_provider_error(exc: BaseException) -> bool:
    raw = str(exc).lower()
    return (
        "api_key_invalid" in raw
        or "api key not valid" in raw
        or "invalid api key" in raw
        or "unauthorized" in raw
        or "permission_denied" in raw
        or "billing" in raw
    )


def _resolve_default_model() -> str:
    """Return the project-configured default model, or a hard-coded fallback.

    The resolution order is:

    1. ``shell_config.config.voice["model"]`` - the user-facing setting used
       elsewhere in the project (Gemini voice session model).
    2. ``_FALLBACK_TEXT_MODEL`` - a safe text-capable Gemini default.

    Import of ``shell_config`` is lazy so that this module can be imported in
    contexts where the full config stack is unavailable (e.g. early boot,
    unit tests).
    """
    try:
        from shell_config import config as _cfg  # type: ignore
        model = _cfg.voice.get("model")
        if isinstance(model, str) and model:
            # Realtime-audio models (native-audio / live-audio) don't support
            # generateContent. Fall through to the text-capable fallback so
            # text-only callers don't hit 404 NOT_FOUND.
            low = model.lower()
            if "native-audio" in low or "live-audio" in low or "realtime" in low:
                return _FALLBACK_TEXT_MODEL
            return model
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("shell_config.voice['model'] lookup failed: %s", exc)
    return _FALLBACK_TEXT_MODEL


# ---------------------------------------------------------------------------
# Retry helper (inline fallback when tenacity isn't installed)
# ---------------------------------------------------------------------------
async def _retry_async(
    func,
    *,
    attempts: int = 4,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    exceptions: tuple = (Exception,),
):
    """Run ``func`` (a zero-arg coroutine factory) with exponential backoff.

    Used when ``tenacity`` is not installed. Retries up to ``attempts`` times,
    sleeping ``min(base_delay * 2**n, max_delay)`` (plus jitter) between
    attempts. On final failure the last exception is re-raised.

    Parameters
    ----------
    func:
        A callable returning a fresh coroutine on each call.
    attempts:
        Total number of attempts (including the first). Must be >= 1.
    base_delay:
        Initial delay in seconds.
    max_delay:
        Upper bound on the per-attempt delay.
    exceptions:
        Tuple of exception classes that should trigger a retry. Anything else
        is raised immediately.
    """
    last_exc: Optional[BaseException] = None
    for n in range(max(1, attempts)):
        try:
            return await func()
        except exceptions as e:  # noqa: PERF203 - clarity wins here
            if _is_non_retryable_provider_error(e):
                raise
            last_exc = e
            if n == attempts - 1:
                break
            delay = min(base_delay * (2 ** n), max_delay)
            # Full jitter to avoid thundering-herd retries.
            delay = delay * (0.5 + random.random() * 0.5)
            logger.warning(
                "LLMClient retry %d/%d in %.2fs after error: %s",
                n + 1, attempts, delay, e,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


def _with_retry(attempts: int = 4, base_delay: float = 0.5, max_delay: float = 8.0):
    """Decorator factory returning either a tenacity- or inline-backed retry.

    The decorator wraps async callables. It intentionally keeps the retry
    policy identical whichever backend is used, so callers see deterministic
    behaviour regardless of the environment.
    """
    if _TENACITY_AVAILABLE:
        return _tenacity.retry(  # type: ignore[attr-defined]
            reraise=True,
            retry=_tenacity.retry_if_exception(lambda e: not _is_non_retryable_provider_error(e)),  # type: ignore[attr-defined]
            stop=_tenacity.stop_after_attempt(attempts),  # type: ignore[attr-defined]
            wait=_tenacity.wait_exponential_jitter(  # type: ignore[attr-defined]
                initial=base_delay, max=max_delay,
            ),
            before_sleep=_tenacity.before_sleep_log(logger, logging.WARNING),  # type: ignore[attr-defined]
        )

    def _decorator(fn):
        async def _wrapper(*args, **kwargs):
            return await _retry_async(
                lambda: fn(*args, **kwargs),
                attempts=attempts,
                base_delay=base_delay,
                max_delay=max_delay,
            )
        _wrapper.__name__ = getattr(fn, "__name__", "wrapped")
        _wrapper.__doc__ = fn.__doc__
        return _wrapper

    return _decorator


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------
class LLMClient:
    """SDK-agnostic async client for text, multimodal, and embedding calls.

    The client is intentionally thin: it does not cache responses, does not
    do prompt templating, and does not enforce content policies beyond what
    the upstream SDKs do. It exists to centralise three concerns:

    1. **SDK routing** - prefer ``google.genai`` (new), fall back to
       ``google.generativeai`` (legacy) without the caller knowing.
    2. **Retries** - transient network/5xx/429 failures are retried with
       exponential backoff; permanent errors are propagated.
    3. **Accounting** - every call updates :attr:`stats` so that callers can
       measure token spend without instrumenting each call site.

    Use :meth:`get` to acquire a process-wide singleton. Direct construction
    is still supported for tests or when multiple isolated clients are needed.

    Attributes
    ----------
    stats: dict
        Mutable dict with keys ``total_prompt_tokens``,
        ``total_completion_tokens``, and ``calls``. Updated after each
        successful request. Callers may read these freely; mutating them
        from outside is discouraged.
    """

    # Class-level singleton state.
    _instance: "Optional[LLMClient]" = None
    _singleton_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Construction / setup
    # ------------------------------------------------------------------
    def __init__(self) -> None:
        """Initialise the client and pick an SDK backend.

        The constructor is side-effecting: it reads ``GOOGLE_API_KEY`` from
        the environment and tries to build either a ``google.genai.Client``
        or configure the legacy module. If neither SDK is available, the
        client is still constructed but every call will raise
        :class:`RuntimeError` until the environment is fixed.
        """
        self._client_mode: Optional[str] = None   # "new" | "legacy" | None
        self._new_client: Any = None              # google.genai.Client
        self._ready: bool = False
        self._call_lock = threading.Lock()        # guards stats updates
        self.stats: dict = {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "calls": 0,
        }
        self._setup()

    def _setup(self) -> None:
        """Configure whichever SDK we can reach.

        Side effects:

        * Sets :attr:`_client_mode` to ``"new"`` or ``"legacy"`` on success.
        * Sets :attr:`_new_client` when the new SDK is active.
        * Sets :attr:`_ready` to ``True`` on success.
        * Logs a warning and leaves the client un-ready on failure; no
          exception is raised so that import-time construction stays safe.
        """
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            logger.warning("GOOGLE_API_KEY not set; LLMClient will be inert.")
            return

        if _NEW_GENAI_AVAILABLE:
            try:
                self._new_client = _new_genai_mod.Client(api_key=key)  # type: ignore[union-attr]
                self._client_mode = "new"
                self._ready = True
                logger.info("LLMClient ready (google-genai, new SDK).")
                return
            except Exception as e:
                logger.debug("google-genai Client init failed, trying legacy: %s", e)

        if not _LEGACY_GENAI_AVAILABLE:
            _load_legacy_genai()

        if _LEGACY_GENAI_AVAILABLE:
            try:
                _legacy_genai_mod.configure(api_key=key)  # type: ignore[union-attr]
                self._client_mode = "legacy"
                self._ready = True
                logger.info("LLMClient ready (google-generativeai, legacy SDK).")
                return
            except Exception as e:
                logger.error("Legacy google-generativeai init failed: %s", e)

        logger.warning(
            "No Gemini SDK available. "
            "pip install google-genai (preferred) or google-generativeai."
        )

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------
    @classmethod
    def get(cls) -> "LLMClient":
        """Return the process-wide singleton, constructing it on first call.

        Thread-safe: uses a double-checked lock so only one instance is
        constructed even under concurrent access. Subsequent callers get the
        same instance, which means they also share :attr:`stats`.
        """
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _require_ready(self) -> None:
        """Raise ``RuntimeError`` if no SDK backend is usable."""
        if not self._ready:
            raise RuntimeError(
                "LLMClient is not initialised. Ensure GOOGLE_API_KEY is set "
                "and either google-genai or google-generativeai is installed."
            )

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Best-effort text extraction from either SDK's response object.

        The new SDK exposes ``response.text``; the legacy SDK does as well
        but may return ``None`` for blocked responses. We fall back to
        walking ``candidates -> content -> parts -> text`` when the direct
        attribute is missing or empty.
        """
        text = getattr(response, "text", None)
        if text:
            return str(text).strip()

        # Fallback: try to stitch parts together.
        try:
            candidates = getattr(response, "candidates", None) or []
            chunks: List[str] = []
            for cand in candidates:
                content = getattr(cand, "content", None)
                parts = getattr(content, "parts", None) or []
                for p in parts:
                    t = getattr(p, "text", None)
                    if t:
                        chunks.append(str(t))
            if chunks:
                return "".join(chunks).strip()
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Response part-walk failed: %s", e)

        return ""

    def _record_usage(self, response: Any) -> None:
        """Pull usage metadata off a response and fold it into :attr:`stats`.

        Both SDKs expose a ``usage_metadata`` object with
        ``prompt_token_count`` and ``candidates_token_count`` (the new SDK
        sometimes calls the latter ``response_token_count``). Missing fields
        are treated as zero; we never let accounting raise.
        """
        try:
            usage = getattr(response, "usage_metadata", None)
            prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
            completion_tokens = 0
            if usage is not None:
                completion_tokens = int(
                    getattr(usage, "candidates_token_count", 0)
                    or getattr(usage, "response_token_count", 0)
                    or 0
                )
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Usage extraction failed: %s", e)
            prompt_tokens = completion_tokens = 0

        with self._call_lock:
            self.stats["total_prompt_tokens"] += prompt_tokens
            self.stats["total_completion_tokens"] += completion_tokens
            self.stats["calls"] += 1

    # --- sync SDK-routing primitives (called from thread executor) ---
    def _generate_content_sync(
        self,
        model_name: str,
        contents: Any,
        *,
        temperature: Optional[float] = None,
    ) -> Any:
        """Call ``generate_content`` on whichever SDK is live.

        This runs synchronously; async entry points dispatch it onto a
        thread via :func:`asyncio.to_thread` so the caller's event loop
        stays responsive.
        """
        if self._client_mode == "new":
            config: Any = None
            if temperature is not None:
                try:
                    config = _new_genai_mod.types.GenerateContentConfig(  # type: ignore[union-attr]
                        temperature=temperature,
                    )
                except Exception:  # pragma: no cover - SDK shape drift
                    config = {"temperature": temperature}
            kwargs = {"model": model_name, "contents": contents}
            if config is not None:
                kwargs["config"] = config
            return self._new_client.models.generate_content(**kwargs)

        if self._client_mode == "legacy":
            gen_cfg = None
            if temperature is not None:
                gen_cfg = {"temperature": temperature}
            model = _legacy_genai_mod.GenerativeModel(model_name=model_name)  # type: ignore[union-attr]
            if gen_cfg is not None:
                return model.generate_content(contents, generation_config=gen_cfg)
            return model.generate_content(contents)

        raise RuntimeError("LLMClient has no active SDK backend.")

    def _embed_sync(self, model_name: str, text: Union[str, Sequence[str]]) -> List[List[float]]:
        """Call the embeddings endpoint on whichever SDK is live.

        Returns a list of vectors, one per input string. A single-string
        input still returns a list of length 1 so the return type is stable.
        """
        if self._client_mode == "new":
            # New SDK: client.models.embed_content(model=, contents=)
            resp = self._new_client.models.embed_content(
                model=model_name,
                contents=text,
            )
            # Response has `.embeddings` (list) each with `.values` (list[float])
            embeds = getattr(resp, "embeddings", None)
            if embeds is not None:
                return [list(getattr(e, "values", []) or []) for e in embeds]
            # Fallback shape: `.embedding.values`
            single = getattr(resp, "embedding", None)
            if single is not None:
                return [list(getattr(single, "values", []) or [])]
            return []

        if self._client_mode == "legacy":
            # Legacy SDK: genai.embed_content(model=, content=)
            if isinstance(text, (list, tuple)):
                out: List[List[float]] = []
                for t in text:
                    r = _legacy_genai_mod.embed_content(  # type: ignore[union-attr]
                        model=model_name, content=t,
                    )
                    out.append(list(r.get("embedding", []) or []))
                return out
            r = _legacy_genai_mod.embed_content(  # type: ignore[union-attr]
                model=model_name, content=text,
            )
            return [list(r.get("embedding", []) or [])]

        raise RuntimeError("LLMClient has no active SDK backend.")

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------
    @_with_retry(attempts=4, base_delay=0.5, max_delay=8.0)
    async def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        timeout: float = 30,
    ) -> str:
        """Generate text for ``prompt`` and return the model's reply.

        Parameters
        ----------
        prompt:
            The user prompt. Passed through to the SDK unchanged.
        model:
            Model name override. When ``None``, the default is pulled from
            ``shell_config.config.voice["model"]`` (with a hard-coded
            ``gemini-2.5-flash`` fallback).
        temperature:
            Sampling temperature. ``0.0`` is deterministic; higher values
            increase diversity. Forwarded to both SDK backends via their
            respective generation-config shapes.
        timeout:
            Hard ceiling on a single attempt, in seconds. Retries each get
            their own ``timeout``; total wall time can therefore exceed it.

        Returns
        -------
        str
            The stripped response text. Empty string if the SDK produced no
            usable text (e.g. safety block); callers should treat empty as
            a soft failure.

        Raises
        ------
        RuntimeError
            If no SDK backend is configured.
        asyncio.TimeoutError
            If a single attempt exceeds ``timeout``. Still wrapped by the
            retry decorator, so transient timeouts will be retried.
        Exception
            The last exception from the underlying SDK, after retries are
            exhausted.
        """
        self._require_ready()
        model_name = model or _resolve_default_model()

        async def _call() -> Any:
            return await asyncio.to_thread(
                self._generate_content_sync,
                model_name,
                prompt,
                temperature=temperature,
            )

        response = await asyncio.wait_for(_call(), timeout=timeout)
        self._record_usage(response)
        return self._extract_text(response)

    @_with_retry(attempts=4, base_delay=0.5, max_delay=8.0)
    async def generate_with_image(
        self,
        prompt: str,
        image: Any,
        *,
        model: Optional[str] = None,
        timeout: float = 30,
    ) -> str:
        """Generate text given a prompt plus an image (multimodal).

        Parameters
        ----------
        prompt:
            Text prompt describing what to do with the image.
        image:
            A PIL ``Image.Image`` or anything the active SDK accepts as a
            content part (e.g. a ``types.Part`` for the new SDK). No
            conversion is performed here; we rely on the SDK's own handling.
        model:
            Model name override. Defaults to
            ``shell_config.config.voice["model"]`` (falls back to
            ``gemini-2.5-flash``).
        timeout:
            Per-attempt timeout in seconds. Retries are independent.

        Returns
        -------
        str
            Stripped response text, or empty string if the model produced
            no text.

        Raises
        ------
        RuntimeError
            If no SDK backend is configured.
        asyncio.TimeoutError
            On per-attempt timeout, subject to the retry decorator.
        """
        self._require_ready()
        model_name = model or _resolve_default_model()

        async def _call() -> Any:
            return await asyncio.to_thread(
                self._generate_content_sync,
                model_name,
                [prompt, image],
            )

        response = await asyncio.wait_for(_call(), timeout=timeout)
        self._record_usage(response)
        return self._extract_text(response)

    @_with_retry(attempts=4, base_delay=0.5, max_delay=8.0)
    async def embed(
        self,
        text: Union[str, List[str]],
        *,
        model: str = "text-embedding-004",
    ) -> List[List[float]]:
        """Embed one or more texts and return a list of vectors.

        Parameters
        ----------
        text:
            A single string or a list of strings to embed. A single string
            still returns a list-of-lists of length 1 so downstream code
            can treat the output uniformly.
        model:
            Embedding model name. Defaults to ``text-embedding-004``, which
            is the current Google-hosted general-purpose embedding model.

        Returns
        -------
        list[list[float]]
            One embedding vector per input string, in input order.

        Raises
        ------
        RuntimeError
            If no SDK backend is configured.

        Notes
        -----
        Embeddings calls are counted in :attr:`stats["calls"]` but do not
        contribute to ``total_prompt_tokens``/``total_completion_tokens``
        because the embedding endpoints don't report token usage in a
        stable cross-SDK shape.
        """
        self._require_ready()
        # Normalise single-string input so the sync helper sees a consistent type.
        payload: Union[str, List[str]]
        if isinstance(text, str):
            payload = text
        else:
            payload = list(text)

        vectors = await asyncio.to_thread(self._embed_sync, model, payload)
        with self._call_lock:
            self.stats["calls"] += 1
        return vectors


__all__ = ["LLMClient", "logger"]
