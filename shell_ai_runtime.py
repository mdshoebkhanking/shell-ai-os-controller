"""
Lazy AI brain runtime accessors.

The UI can render instantly without importing brain.core or hydrating provider
graphs. AI providers are loaded on first real AI fallback/use or when settings
explicitly refresh provider state.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path


logger = logging.getLogger("shell.ai_runtime")
_PROJECT_ROOT = Path(__file__).resolve().parent
_BRAIN = None
_BRAIN_LOAD_ERROR = ""
_BRAIN_LOAD_MS = None


def _provider_key_names() -> tuple[str, ...]:
    return (
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "DEEPSEEK_API_KEY",
        "PERPLEXITY_API_KEY",
        "SAMBANOVA_API_KEY",
        "BLACKBOX_API_KEY",
    )


def has_configured_ai_key() -> bool:
    return any(str(os.environ.get(name, "")).strip() for name in _provider_key_names())


def get_brain():
    global _BRAIN, _BRAIN_LOAD_ERROR, _BRAIN_LOAD_MS
    if _BRAIN is not None:
        return _BRAIN
    started = time.perf_counter()
    try:
        if str(_PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(_PROJECT_ROOT))
        from brain.core import MultiAIBrain

        _BRAIN = MultiAIBrain.get_instance()
        _BRAIN_LOAD_ERROR = ""
        _BRAIN_LOAD_MS = round((time.perf_counter() - started) * 1000.0, 3)
        logger.info("AI Brain loaded lazily in %sms", _BRAIN_LOAD_MS)
        return _BRAIN
    except Exception as exc:
        _BRAIN_LOAD_ERROR = str(exc)
        _BRAIN_LOAD_MS = round((time.perf_counter() - started) * 1000.0, 3)
        logger.warning("AI Brain unavailable after lazy load: %s", exc)
        return None


def is_brain_loaded() -> bool:
    return _BRAIN is not None


def brain_load_metrics() -> dict[str, object]:
    return {
        "loaded": is_brain_loaded(),
        "load_ms": _BRAIN_LOAD_MS,
        "error": _BRAIN_LOAD_ERROR,
        "provider_count": len(getattr(_BRAIN, "providers", {}) or {}) if _BRAIN is not None else 0,
    }


def brain_has_providers(*, load: bool = False) -> bool:
    brain = get_brain() if load else _BRAIN
    return bool(brain and getattr(brain, "providers", None))


def brain_provider_names(*, load: bool = False) -> list[str]:
    brain = get_brain() if load else _BRAIN
    return list((getattr(brain, "providers", {}) or {}).keys()) if brain is not None else []


def reload_brain_providers() -> bool:
    brain = get_brain()
    if brain is None or not hasattr(brain, "reload_providers"):
        return False
    brain.reload_providers()
    return True


__all__ = [
    "brain_has_providers",
    "brain_load_metrics",
    "brain_provider_names",
    "get_brain",
    "has_configured_ai_key",
    "is_brain_loaded",
    "reload_brain_providers",
]
