"""
shell_voice.py — Central voice management for Shell AI
=======================================================
Single source of truth for:
  * Gemini 2.5 Native Audio voice catalog (30 prebuilt voices)
  * Voice persona presets (Hinglish, English formal/casual, Hindi, etc.)
  * Runtime voice switching via Live API session.update()
  * Local TTS fallback (pyttsx3 / gTTS / Windows SAPI)

This replaces scattered VOICE_NAME lookups in agent.py, shell_config.py,
and shell_speech.py. Old code should import from here instead of reading
os.environ directly.

Reference: https://ai.google.dev/gemini-api/docs/speech-generation
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("shell_voice")


# ─────────────────────────────────────────────────────────────────────
# Gemini 2.5 Native Audio — prebuilt voice catalog (30 voices)
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VoiceProfile:
    name: str
    gender: str          # "F" | "M"
    style: str           # short descriptor — "bright", "firm", "breezy", ...
    description: str     # human-readable blurb for tool responses


_VOICES: tuple[VoiceProfile, ...] = (
    VoiceProfile("Achernar",       "F", "soft",          "Soft, airy tone — calm and gentle delivery."),
    VoiceProfile("Achird",         "M", "friendly",      "Friendly, approachable male voice."),
    VoiceProfile("Algenib",        "M", "gravelly",      "Gravelly, textured male voice with character."),
    VoiceProfile("Algieba",        "M", "smooth",        "Smooth, polished male voice — great for narration."),
    VoiceProfile("Alnilam",        "M", "firm",          "Firm, confident male voice."),
    VoiceProfile("Aoede",          "F", "breezy",        "Breezy, light female voice — warm and conversational. (Shell default)"),
    VoiceProfile("Autonoe",        "F", "bright",        "Bright, energetic female voice."),
    VoiceProfile("Callirrhoe",     "F", "easy-going",    "Easy-going, relaxed female voice."),
    VoiceProfile("Charon",         "M", "informative",   "Deep informative male voice — authoritative feel."),
    VoiceProfile("Despina",        "F", "smooth",        "Smooth, flowing female voice."),
    VoiceProfile("Enceladus",      "M", "breathy",       "Breathy, soft male voice."),
    VoiceProfile("Erinome",        "F", "clear",         "Clear, precise female voice."),
    VoiceProfile("Fenrir",         "M", "excitable",     "Excitable, energetic male voice."),
    VoiceProfile("Gacrux",         "F", "mature",        "Mature, seasoned female voice."),
    VoiceProfile("Iapetus",        "M", "clear",         "Clear, well-articulated male voice."),
    VoiceProfile("Kore",           "F", "firm",          "Firm, assertive female voice."),
    VoiceProfile("Laomedeia",      "F", "upbeat",        "Upbeat, cheerful female voice."),
    VoiceProfile("Leda",           "F", "youthful",      "Youthful, fresh female voice."),
    VoiceProfile("Orus",           "M", "firm",          "Firm, grounded male voice."),
    VoiceProfile("Puck",           "M", "upbeat",        "Upbeat, playful male voice."),
    VoiceProfile("Pulcherrima",    "F", "forward",       "Forward, confident female voice."),
    VoiceProfile("Rasalgethi",     "M", "informative",   "Informative, steady male voice."),
    VoiceProfile("Sadachbia",      "M", "lively",        "Lively, animated male voice."),
    VoiceProfile("Sadaltager",     "M", "knowledgeable", "Knowledgeable, measured male voice."),
    VoiceProfile("Schedar",        "M", "even",          "Even, neutral male voice."),
    VoiceProfile("Sulafat",        "F", "warm",          "Warm, caring female voice."),
    VoiceProfile("Umbriel",        "M", "easy-going",    "Easy-going, mellow male voice."),
    VoiceProfile("Vindemiatrix",   "F", "gentle",        "Gentle, soft-spoken female voice."),
    VoiceProfile("Zephyr",         "F", "bright",        "Bright, crisp female voice."),
    VoiceProfile("Zubenelgenubi",  "M", "casual",        "Casual, laid-back male voice."),
)

VOICE_CATALOG: dict[str, VoiceProfile] = {v.name: v for v in _VOICES}
VOICE_NAMES: list[str] = [v.name for v in _VOICES]

# Hardcoded fallback if nothing else is configured.
DEFAULT_VOICE = "Aoede"

# Common user-facing aliases and typos. Gemini only accepts the canonical
# catalog names, but the UI/chat should be forgiving.
_VOICE_ALIASES: dict[str, str] = {
    "adreno": "Aoede",
    "adeno": "Aoede",
    "aode": "Aoede",
    "aede": "Aoede",
    "aoede voice": "Aoede",
    "shell": "Aoede",
    "default": "Aoede",
}


# ─────────────────────────────────────────────────────────────────────
# Voice personas — prompt fragments that tune speaking style
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VoicePersona:
    name: str
    language_hint: str            # ISO-ish tag for developer reference
    style_instructions: str       # prompt fragment injected into generate_reply


_PERSONAS: tuple[VoicePersona, ...] = (
    VoicePersona(
        name="Hinglish",
        language_hint="hi-IN + en-IN",
        style_instructions=(
            "Speak in natural Hinglish — a fluid mix of Hindi and English as spoken "
            "casually in India. Do not force a ratio. Common English tech/noun words "
            "stay in English (phone, file, system, internet, browser), verbs and "
            "connectors use Hindi (karo, hai, tha, kyun, kaise). "
            "Pronounce Hindi words with correct native sounds (e.g. 'kyun' not 'kiyun', "
            "'achha' not 'ak-ha'). Keep pacing conversational — not robotic, not over-dramatic. "
            "Use 'aap' (respectful) when addressing the user directly. Avoid Sanskrit-heavy "
            "formal Hindi. Default addressing: 'boss' or 'boss'."
        ),
    ),
    VoicePersona(
        name="English",
        language_hint="en-US",
        style_instructions=(
            "Speak in clear, neutral American English. Conversational, friendly, not stiff. "
            "Avoid filler words. Short sentences preferred."
        ),
    ),
    VoicePersona(
        name="English-Indian",
        language_hint="en-IN",
        style_instructions=(
            "Speak in Indian English with natural Indian accent and rhythm. "
            "Keep sentences short and clear. Avoid over-formal phrasing."
        ),
    ),
    VoicePersona(
        name="Hindi",
        language_hint="hi-IN",
        style_instructions=(
            "Shuddh Hindi mein bolen, lekin natural aur conversational rakhen — "
            "bahut formal Sanskrit-heavy mat karen. Common tech words (phone, file, internet) "
            "English mein hi rakh sakte hain kyunki aam log aise hi bolte hain. "
            "User ko 'aap' se sambodhit karen."
        ),
    ),
    VoicePersona(
        name="Formal",
        language_hint="en-US",
        style_instructions=(
            "Speak in formal, professional English. Precise word choice, full sentences, "
            "no contractions. Address the user as 'sir' or 'ma'am' unless told otherwise."
        ),
    ),
    VoicePersona(
        name="Casual",
        language_hint="en-US",
        style_instructions=(
            "Speak casually — contractions, short punchy lines, light wit when appropriate. "
            "Think: helpful friend, not customer service."
        ),
    ),
)

PERSONA_CATALOG: dict[str, VoicePersona] = {p.name.lower(): p for p in _PERSONAS}
PERSONA_NAMES: list[str] = [p.name for p in _PERSONAS]

DEFAULT_PERSONA = "Hinglish"


# ─────────────────────────────────────────────────────────────────────
# Resolution — read VOICE_NAME / VOICE_PERSONA with correct fallback chain
# ─────────────────────────────────────────────────────────────────────

def _is_truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _canonical_voice_name(candidate: str | None) -> str | None:
    if not candidate:
        return None
    cleaned = str(candidate).strip()
    if not cleaned:
        return None
    alias = _VOICE_ALIASES.get(cleaned.lower())
    if alias:
        return alias
    return next((v for v in VOICE_NAMES if v.lower() == cleaned.lower()), None)


def resolve_voice(requested: str | None = None) -> str:
    """Return a validated Gemini voice name.

    Precedence:
      1. explicit `requested` argument (if valid)
      2. $VOICE_NAME env var (if valid)
      3. DEFAULT_VOICE

    Unknown names log a warning and fall back to DEFAULT_VOICE rather than
    letting the Realtime API reject the connection with a cryptic error.
    """
    for candidate in (requested, os.environ.get("VOICE_NAME")):
        if candidate:
            cleaned = candidate.strip()
            match = _canonical_voice_name(cleaned)
            if match:
                return match
            logger.warning(
                "Requested voice %r is not in Gemini 2.5 catalog; falling back to %s.",
                cleaned, DEFAULT_VOICE,
            )
    return DEFAULT_VOICE


def resolve_persona(requested: str | None = None) -> VoicePersona:
    """Return a VoicePersona — explicit arg > $VOICE_PERSONA > default."""
    for candidate in (requested, os.environ.get("VOICE_PERSONA")):
        if candidate:
            key = str(candidate).strip().lower()
            persona = PERSONA_CATALOG.get(key)
            if persona:
                return persona
            logger.warning(
                "Requested persona %r unknown; falling back to %s.",
                candidate, DEFAULT_PERSONA,
            )
    return PERSONA_CATALOG[DEFAULT_PERSONA.lower()]


def describe_voice(name: str) -> str:
    """Return a short human-readable description of a voice, or an error."""
    canonical = _canonical_voice_name(name)
    match = next((v for v in _VOICES if v.name == canonical), None)
    if not match:
        return f"Unknown voice: {name!r}. Use list_shell_voices() to see options."
    return f"{match.name} ({match.gender}, {match.style}): {match.description}"


def list_voices(gender: str | None = None, style: str | None = None) -> list[VoiceProfile]:
    """Filter the catalog by gender ('F'|'M') and/or style keyword."""
    result = list(_VOICES)
    if gender:
        g = gender.strip().upper()[:1]
        result = [v for v in result if v.gender == g]
    if style:
        s = style.strip().lower()
        result = [v for v in result if s in v.style.lower()]
    return result


# ─────────────────────────────────────────────────────────────────────
# Runtime session state — tracks the active LiveKit/Gemini session
# ─────────────────────────────────────────────────────────────────────

@dataclass
class _SessionState:
    session: Any = None
    current_voice: str = DEFAULT_VOICE
    current_persona: str = DEFAULT_PERSONA
    extras: dict[str, Any] = field(default_factory=dict)


_state = _SessionState()


def register_session(session: Any, voice: str | None = None, persona: str | None = None) -> None:
    """Called by agent.py once the AgentSession has started successfully."""
    _state.session = session
    _state.current_voice = resolve_voice(voice)
    _state.current_persona = resolve_persona(persona).name
    logger.info(
        "Voice session registered: voice=%s persona=%s",
        _state.current_voice, _state.current_persona,
    )


def unregister_session() -> None:
    """Clear cached session — call on shutdown."""
    _state.session = None


def current_voice() -> str:
    return _state.current_voice


def current_persona() -> str:
    return _state.current_persona


async def switch_voice_runtime(new_voice: str) -> tuple[bool, str]:
    """Switch the active Gemini voice on a running session.

    Returns (success, message). LiveKit's google.beta.realtime.RealtimeModel
    exposes a few possible update paths depending on version; we try them
    in order. If none succeed, we record the preferred voice so the next
    session start will pick it up.
    """
    requested = resolve_voice(new_voice)
    if requested == _state.current_voice:
        return True, f"Already using {requested}."

    session = _state.session
    if session is None:
        _state.current_voice = requested
        os.environ["VOICE_NAME"] = requested
        return True, f"No active session — queued {requested} for next startup."

    llm_obj = getattr(session, "llm", None)

    candidates: list[tuple[str, Any, tuple]] = []
    if llm_obj is not None:
        for attr in ("update_options", "update", "set_voice"):
            fn = getattr(llm_obj, attr, None)
            if callable(fn):
                if attr == "set_voice":
                    candidates.append((f"llm.{attr}(voice)", fn, (requested,)))
                else:
                    candidates.append((f"llm.{attr}(voice=...)", fn, ()))
    for attr in ("update_options", "update"):
        fn = getattr(session, attr, None)
        if callable(fn):
            candidates.append((f"session.{attr}(voice=...)", fn, ()))

    last_error: Optional[Exception] = None
    for label, fn, args in candidates:
        try:
            if args:
                result = fn(*args)
            else:
                result = fn(voice=requested)
            if asyncio.iscoroutine(result):
                await result
            _state.current_voice = requested
            os.environ["VOICE_NAME"] = requested
            logger.info("Voice switched via %s to %s.", label, requested)
            return True, f"Voice switched to {requested}."
        except TypeError:
            # Wrong signature — try next candidate.
            continue
        except Exception as e:
            last_error = e
            logger.debug("Voice switch via %s failed: %s", label, e)
            continue

    _state.current_voice = requested
    os.environ["VOICE_NAME"] = requested
    msg = (
        f"Could not hot-swap voice on this LiveKit version; "
        f"{requested} will be used from the next restart."
    )
    if last_error:
        msg += f" (last error: {last_error})"
    logger.warning(msg)
    return False, msg


def set_persona_runtime(new_persona: str) -> tuple[bool, str]:
    """Persona is prompt-level, so we just update state + env. agent.py's
    _announce_text reads VOICE_PERSONA live, so next utterance uses it."""
    persona = resolve_persona(new_persona)
    _state.current_persona = persona.name
    os.environ["VOICE_PERSONA"] = persona.name
    logger.info("Persona switched to %s.", persona.name)
    return True, f"Persona set to {persona.name}."


# ─────────────────────────────────────────────────────────────────────
# Prompt helpers — reused by agent.py _announce_text and startup banner
# ─────────────────────────────────────────────────────────────────────

def build_persona_instruction(text: str, persona_name: str | None = None) -> str:
    """Wrap raw `text` with persona-specific delivery instructions so that
    Gemini speaks it in the requested style without bleeding prompt text
    into the spoken audio."""
    persona = resolve_persona(persona_name)
    clean = (text or "").strip()
    return (
        f"{persona.style_instructions}\n\n"
        f"Now say exactly this content clearly, without repeating these instructions: {clean}"
    )


def persona_system_suffix(persona_name: str | None = None) -> str:
    """Short suffix appendable to realtime_prompts so the base voice style
    stays consistent across the whole session."""
    persona = resolve_persona(persona_name)
    return (
        f"\n\n[VOICE PERSONA: {persona.name} — {persona.language_hint}]\n"
        f"{persona.style_instructions}\n"
    )


# ─────────────────────────────────────────────────────────────────────
# Diagnostics
# ─────────────────────────────────────────────────────────────────────

def diagnostics() -> dict[str, Any]:
    return {
        "default_voice": DEFAULT_VOICE,
        "default_persona": DEFAULT_PERSONA,
        "env_voice": os.environ.get("VOICE_NAME"),
        "env_persona": os.environ.get("VOICE_PERSONA"),
        "resolved_voice": resolve_voice(),
        "resolved_persona": resolve_persona().name,
        "session_active": _state.session is not None,
        "current_voice": _state.current_voice,
        "current_persona": _state.current_persona,
        "catalog_size": len(VOICE_NAMES),
        "personas": PERSONA_NAMES,
    }


__all__ = [
    "VoiceProfile", "VoicePersona",
    "VOICE_CATALOG", "VOICE_NAMES", "DEFAULT_VOICE",
    "PERSONA_CATALOG", "PERSONA_NAMES", "DEFAULT_PERSONA",
    "resolve_voice", "resolve_persona",
    "describe_voice", "list_voices",
    "register_session", "unregister_session",
    "current_voice", "current_persona",
    "switch_voice_runtime", "set_persona_runtime",
    "build_persona_instruction", "persona_system_suffix",
    "diagnostics",
]
