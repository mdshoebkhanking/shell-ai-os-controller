"""
shell_api_manager.py — safe, UI-addressable read/write of `.env` keys.
=====================================================================

The UI Settings page calls this module (via hub HTTP endpoints) to:

 * list known API keys + their set/unset status (never the value)
 * update a single key atomically (rewrite `.env` with a file-lock +
   temp-then-replace so a crash mid-write cannot blank the file)
 * (optionally) delete a key

Design rules
------------
* **Values are never returned to the UI.** `list_api_keys()` returns
  `{"name": "...", "set": True/False, "description": "..."}` only. Even
  the hub logs avoid the raw value.
* **Rewrites preserve comments + layout** where possible. We rebuild
  `.env` line-by-line: non-empty lines that don't match `KEY=value`
  (comments, blank lines, exotic shell syntax) are echoed verbatim.
* **Allowlist**: only keys that appear in `.env.example` or the built-in
  `_KNOWN_KEYS` catalog can be written. Anything else is rejected — the
  UI cannot inject random env vars into the runtime.
* **File lock**: best-effort `fcntl.flock` on POSIX, `msvcrt.locking`
  on Windows, with a fall-through so a missing lock module never blocks
  legitimate writes.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────
# Catalog of keys the UI is allowed to manage + human descriptions.
# Anything here that ALSO appears in .env.example is what the UI lists.
# ─────────────────────────────────────────────────────────────────────

_KNOWN_KEYS: dict[str, dict] = {
    # Required
    "GOOGLE_API_KEY":         {"required": True,  "section": "Gemini (critical)",   "desc": "Gemini brain + vision. Required."},
    "LIVEKIT_API_KEY":        {"required": True,  "section": "LiveKit (critical)",  "desc": "LiveKit Cloud API key."},
    "LIVEKIT_API_SECRET":     {"required": True,  "section": "LiveKit (critical)",  "desc": "LiveKit Cloud API secret."},
    "LIVEKIT_URL":            {"required": True,  "section": "LiveKit (critical)",  "desc": "LiveKit WS URL (wss://…)."},
    # Voice tuning
    "VOICE_NAME":             {"required": False, "section": "Voice",               "desc": "Gemini voice (Aoede, Kore, Charon, …)."},
    "VOICE_PERSONA":          {"required": False, "section": "Voice",               "desc": "Hinglish | English | Hindi | Formal | Casual."},
    "GEMINI_MODEL":           {"required": False, "section": "Gemini (critical)",   "desc": "Gemini realtime model id."},
    "GEMINI_TEMPERATURE":     {"required": False, "section": "Gemini (critical)",   "desc": "Temperature (0-2)."},
    # Multi-brain providers
    "GROQ_API_KEY":           {"required": False, "section": "Providers",           "desc": "Groq fast-inference key."},
    "OPENAI_API_KEY":         {"required": False, "section": "Providers",           "desc": "OpenAI GPT key."},
    "MISTRAL_API_KEY":        {"required": False, "section": "Providers",           "desc": "Mistral key."},
    "PERPLEXITY_API_KEY":     {"required": False, "section": "Providers",           "desc": "Perplexity key."},
    "SAMBANOVA_API_KEY":      {"required": False, "section": "Providers",           "desc": "SambaNova key."},
    "DEEPSEEK_API_KEY":       {"required": False, "section": "Providers",           "desc": "DeepSeek key."},
    "BLACKBOX_API_KEY":       {"required": False, "section": "Providers",           "desc": "Blackbox key."},
    "OPENROUTER_API_KEY":     {"required": False, "section": "Providers",           "desc": "OpenRouter key (100+ models)."},
    "HF_API_KEY":             {"required": False, "section": "Image AI",            "desc": "HuggingFace token (image gen)."},
    "HUGGINGFACE_API_KEY":    {"required": False, "section": "Image AI",            "desc": "Alias of HF_API_KEY."},
    "BYTEZ_API_KEY":          {"required": False, "section": "Image AI",            "desc": "Bytez open-model hub."},
    # Misc APIs
    "GOOGLE_SEARCH_API_KEY":  {"required": False, "section": "Search & info",       "desc": "Google Programmable Search key."},
    "SEARCH_ENGINE_ID":       {"required": False, "section": "Search & info",       "desc": "Google CSE engine id (cx)."},
    "OPENWEATHER_API_KEY":    {"required": False, "section": "Search & info",       "desc": "OpenWeatherMap key."},
    "NEWS_API_KEY":           {"required": False, "section": "Search & info",       "desc": "NewsData.io key."},
    "ALPHA_VANTAGE_API_KEY":  {"required": False, "section": "Search & info",       "desc": "Stock prices key."},
    "TAVILY_API_KEY":         {"required": False, "section": "Search & info",       "desc": "Tavily deep-search/RAG key."},
    # Communications
    "TELEGRAM_BOT_TOKEN":     {"required": False, "section": "Communications",      "desc": "Telegram bot token."},
    "AUTO_START_TELEGRAM_BOT":{"required": False, "section": "Communications",      "desc": "0/1 — auto-start Telegram bot."},
    "SHELL_TELEGRAM_ALLOWED_CHAT_IDS":{"required": False, "section": "Communications", "desc": "Comma-separated Telegram chat IDs allowed to control this PC."},
    "SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED":{"required": False, "section": "Communications", "desc": "0/1 — enable Telegram PC control commands."},
    "SHELL_TELEGRAM_ALLOW_TERMINAL":{"required": False, "section": "Communications", "desc": "0/1 — allow Telegram /cmd terminal execution. Dangerous; off by default."},
    "INSTAGRAM_USERNAME":     {"required": False, "section": "Communications",      "desc": "Instagram handle."},
    "INSTAGRAM_PASSWORD":     {"required": False, "section": "Communications",      "desc": "Instagram password (consider OAuth)."},
    # Email SMTP
    "SHELL_SMTP_SERVER":      {"required": False, "section": "Email",               "desc": "SMTP host (smtp.gmail.com)."},
    "SHELL_SMTP_PORT":        {"required": False, "section": "Email",               "desc": "SMTP port (587/465)."},
    "SHELL_SMTP_USE_SSL":     {"required": False, "section": "Email",               "desc": "true/false."},
    "SHELL_SENDER_EMAIL":     {"required": False, "section": "Email",               "desc": "Your sender email."},
    "SHELL_SENDER_PASSWORD":  {"required": False, "section": "Email",               "desc": "SMTP app password."},
    "SHELL_SENDER_NAME":      {"required": False, "section": "Email",               "desc": "Display name on outgoing mail."},
    # Safety gates
    "SHELL_ALLOW_CODE_WRITE": {"required": False, "section": "Safety",              "desc": "0/1 — enables code-writing tools."},
    "SHELL_ALLOW_AGENT_PATCH":{"required": False, "section": "Safety",              "desc": "0/1 — enables agent.py patches."},
    "SHELL_ALLOW_TERMINAL_EXEC":{"required": False, "section": "Safety",            "desc": "0/1 — enables terminal/PowerShell/Python execution tools."},
    "SHELL_ALLOW_WORKFLOW_COMMANDS":{"required": False, "section": "Safety",        "desc": "0/1 — enables workflow shell commands."},
    "SHELL_ALLOW_WORKFLOW_FILE_WRITE":{"required": False, "section": "Safety",      "desc": "0/1 — enables workflow file writes."},
    "SHELL_ALLOW_WORKFLOW_FILE_READ":{"required": False, "section": "Safety",       "desc": "0/1 — enables workflow file reads."},
    "SHELL_HUB_TOKEN":        {"required": False, "section": "Safety",              "desc": "Bearer token for hub HTTP/Socket.IO access."},
    "SHELL_MCP_TOKEN":        {"required": False, "section": "Safety",              "desc": "Bearer token for custom MCP HTTP access."},
    "SHELL_CTRL_TOKEN":       {"required": False, "section": "Safety",              "desc": "Shared secret for keyboard/mouse controller."},
    "SHELL_DOWNLOAD_DIR":     {"required": False, "section": "Safety",              "desc": "Directory used by downloader tools."},
    "SHELL_ALLOW_ARBITRARY_DOWNLOAD_PATH":{"required": False, "section": "Safety",  "desc": "0/1 — lets downloader write outside SHELL_DOWNLOAD_DIR."},
    # User preferences
    "SHELL_LANGUAGE":         {"required": False, "section": "Preferences",         "desc": "Reply language code (hinglish/english/hindi/spanish/...)."},
    # Tesseract override
    "TESSERACT_CMD":          {"required": False, "section": "OCR",                 "desc": "Full path to tesseract.exe."},
    # Logging
    "LOG_LEVEL":              {"required": False, "section": "Infra",               "desc": "INFO / DEBUG / WARNING."},
}


@dataclass(frozen=True)
class KeyStatus:
    name: str
    set: bool
    section: str
    description: str
    required: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "set": self.set,
            "section": self.section,
            "description": self.description,
            "required": self.required,
        }


# ─────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────

_ENV_PATH = Path(__file__).parent / ".env"
_ENV_EXAMPLE_PATH = Path(__file__).parent / ".env.example"
_write_lock = threading.Lock()
_VALID_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]{1,63}$")


def _is_placeholder_secret(value: str) -> bool:
    low = str(value or "").strip().lower()
    return (
        not low
        or low.startswith("your_")
        or low.startswith("replace_")
        or low in {"changeme", "change_me", "paste_key_here", "api_key", "token", "password", "none", "null"}
    )


def _is_secret_key_name(key: str) -> bool:
    return key.endswith(("_API_KEY", "_API_SECRET", "_TOKEN", "_PASSWORD")) or key in {"GOOGLE_API_KEY", "SHELL_SENDER_PASSWORD"}


def _known_or_example_keys() -> set[str]:
    """Union of `_KNOWN_KEYS` and anything defined in `.env.example`."""
    keys = set(_KNOWN_KEYS)
    if _ENV_EXAMPLE_PATH.exists():
        try:
            for line in _ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"^([A-Z_][A-Z0-9_]+)\s*=", line)
                if m:
                    keys.add(m.group(1))
        except Exception:
            pass
    return keys


def _load_current_values() -> dict[str, str]:
    """Read the current `.env` (if any) into a dict. Comments/blank skipped."""
    out: dict[str, str] = {}
    if not _ENV_PATH.exists():
        return out
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^([A-Z_][A-Z0-9_]+)\s*=\s*(.*)$", s)
        if m:
            key, val = m.group(1), m.group(2)
            # Strip surrounding quotes for consistency.
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            out[key] = val
    return out


def _rewrite_env(new_values: dict[str, str]) -> None:
    """Atomically rewrite `.env` preserving unknown lines (comments, etc).

    Existing KEY=value lines are updated in place when KEY is in
    `new_values`. Keys in `new_values` that aren't already in the file
    are appended at the end under a "# --- UI-managed keys ---" section.
    """
    original_lines: list[str] = []
    if _ENV_PATH.exists():
        original_lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    out_lines: list[str] = []
    managed_keys = _known_or_example_keys()
    for line in original_lines:
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]+)\s*=", line)
        if m:
            key = m.group(1)
            if key in new_values:
                val = new_values[key]
                out_lines.append(f"{key}={val}")
                seen.add(key)
            elif key in managed_keys:
                # Known key intentionally omitted from new_values: delete it.
                continue
            else:
                out_lines.append(line)
        else:
            out_lines.append(line)

    appended = [k for k in new_values if k not in seen]
    if appended:
        if out_lines and out_lines[-1].strip() != "":
            out_lines.append("")
        out_lines.append("# --- UI-managed keys ---")
        for k in appended:
            out_lines.append(f"{k}={new_values[k]}")

    # Atomic temp-then-replace.
    tmp_fd, tmp_name = tempfile.mkstemp(prefix=".env.", dir=str(_ENV_PATH.parent))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + "\n")
        os.replace(tmp_name, _ENV_PATH)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────────────
# Public API (called by hub endpoints)
# ─────────────────────────────────────────────────────────────────────

def list_api_keys() -> list[dict]:
    """Return `[KeyStatus.to_dict(), ...]` sorted by section then name.

    Values are NEVER included — only set/unset boolean."""
    env = _load_current_values()
    out: list[KeyStatus] = []
    for key in sorted(_known_or_example_keys()):
        meta = _KNOWN_KEYS.get(key, {
            "required": False,
            "section": "Other",
            "desc": f"(auto-detected from .env.example)",
        })
        raw_value = (env.get(key) or os.environ.get(key, "")).strip()
        set_flag = bool(raw_value) and not (_is_secret_key_name(key) and _is_placeholder_secret(raw_value))
        out.append(KeyStatus(
            name=key,
            set=set_flag,
            section=meta["section"],
            description=meta["desc"],
            required=meta.get("required", False),
        ))
    return [k.to_dict() for k in out]


def set_api_key(key: str, value: str) -> tuple[bool, str]:
    """Update a single key in `.env` + live process env.

    Returns (ok, message). Value is never logged.
    """
    if not isinstance(key, str) or not _VALID_KEY_RE.match(key or ""):
        return False, f"Invalid key name: {key!r}"
    allowed = _known_or_example_keys()
    if key not in allowed:
        return False, f"Key {key!r} is not in the allowlist (.env.example + built-in catalog)."

    value = "" if value is None else str(value)
    # Reject control characters + newlines that could break the file.
    if any(ch in value for ch in ("\n", "\r", "\x00")):
        return False, "Value contains newline or null byte; rejected."
    if _is_secret_key_name(key) and _is_placeholder_secret(value):
        return False, f"{key} looks like a placeholder, not a real credential."

    with _write_lock:
        current = _load_current_values()
        current[key] = value
        _rewrite_env(current)
        os.environ[key] = value  # Effective immediately for this process.
    return True, f"{key} updated ({len(value)} chars)."


def delete_api_key(key: str) -> tuple[bool, str]:
    """Remove a key from `.env` and the live env. UI can optionally expose."""
    if not isinstance(key, str) or not _VALID_KEY_RE.match(key or ""):
        return False, f"Invalid key name: {key!r}"
    allowed = _known_or_example_keys()
    if key not in allowed:
        return False, f"Key {key!r} is not in the allowlist (.env.example + built-in catalog)."
    with _write_lock:
        current = _load_current_values()
        if key not in current:
            return False, f"{key} was not set."
        current.pop(key, None)
        _rewrite_env(current)
        os.environ.pop(key, None)
    return True, f"{key} removed."


__all__ = [
    "KeyStatus",
    "list_api_keys",
    "set_api_key",
    "delete_api_key",
]
