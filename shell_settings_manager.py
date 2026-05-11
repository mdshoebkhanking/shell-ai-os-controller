"""
Backend-backed settings store for Shell UI.

The desktop UI writes here through the hub's /settings endpoint. Values are
persisted to .shell_settings.json and mirrored into process environment where a
backend component can consume them immediately.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
_SETTINGS_PATH = PROJECT_ROOT / ".shell_settings.json"
_write_lock = threading.Lock()

_ALLOWED_SETTINGS = {
    "accent_intensity",
    "font_scale",
    "voice_persona",
    "tts_enabled",
    "tts_rate",
    "tts_volume",
    "tts_voice",
    "voice_output",
    "speech_rate",
    "speech_volume",
    "voice_sensitivity",
    "voice_mode",
    "brain_mode",
    "max_tokens",
    "temperature_pct",
    "hotkey_show",
    "hotkey_palette",
    "hotkey_voice",
    "shortcut_label_show",
    "shortcut_label_palette",
    "shortcut_label_voice",
    "python_path",
    "workspace_path",
    "log_level",
    "auto_venv",
    "gpu_accel",
    "shell_allow_code_write",
    "prompt_injection_level",
    "telemetry_enabled",
    "theme",
    "language",
    "shell_language",
    "telegram_allowed_chat_ids",
    "telegram_remote_control_enabled",
    "telegram_auto_start",
    "telegram_allow_terminal",
}

_ALIASES = {
    "tts_enabled": ("voice_output",),
    "voice_output": ("tts_enabled",),
    "speech_rate": ("tts_rate",),
    "speech_volume": ("tts_volume",),
    "voice_persona": ("tts_voice",),
    "language": ("shell_language",),
    "shell_language": ("language",),
}

_ENV_MAP = {
    "voice_persona": "VOICE_PERSONA",
    "tts_enabled": "SHELL_TTS_ENABLED",
    "voice_output": "SHELL_TTS_ENABLED",
    "speech_rate": "SHELL_SPEECH_RATE",
    "speech_volume": "SHELL_SPEECH_VOLUME",
    "tts_rate": "SHELL_SPEECH_RATE",
    "tts_volume": "SHELL_SPEECH_VOLUME",
    "tts_voice": "VOICE_PERSONA",
    "voice_sensitivity": "SHELL_VOICE_SENSITIVITY",
    "voice_mode": "SHELL_VOICE_MODE",
    "brain_mode": "SHELL_BRAIN_MODE",
    "max_tokens": "SHELL_MAX_TOKENS",
    "temperature_pct": "SHELL_TEMPERATURE",
    "python_path": "SHELL_PYTHON_PATH",
    "workspace_path": "SHELL_WORKSPACE_PATH",
    "log_level": "LOG_LEVEL",
    "auto_venv": "SHELL_AUTO_VENV",
    "gpu_accel": "SHELL_GPU_ACCEL",
    "shell_allow_code_write": "SHELL_ALLOW_CODE_WRITE",
    "prompt_injection_level": "SHELL_PROMPT_INJECTION_LEVEL",
    "telemetry_enabled": "SHELL_TELEMETRY_ENABLED",
    "theme": "SHELL_THEME",
    "language": "SHELL_LANGUAGE",
    "shell_language": "SHELL_LANGUAGE",
    "telegram_allowed_chat_ids": "SHELL_TELEGRAM_ALLOWED_CHAT_IDS",
    "telegram_remote_control_enabled": "SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED",
    "telegram_auto_start": "AUTO_START_TELEGRAM_BOT",
    "telegram_allow_terminal": "SHELL_TELEGRAM_ALLOW_TERMINAL",
}


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(name or "").strip().lower()).strip("_")


def _load() -> dict[str, Any]:
    if not _SETTINGS_PATH.exists():
        return {}
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write(data: dict[str, Any]) -> None:
    tmp_fd, tmp_name = tempfile.mkstemp(prefix=".shell_settings.", dir=str(_SETTINGS_PATH.parent))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, _SETTINGS_PATH)
    finally:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass


def _env_value(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if key == "temperature_pct":
        try:
            return f"{int(value) / 100:.2f}"
        except Exception:
            return str(value)
    return str(value)


def _apply_env(key: str, value: Any) -> None:
    env_name = _ENV_MAP.get(key)
    if env_name:
        os.environ[env_name] = _env_value(key, value)


def get_settings() -> dict[str, Any]:
    data = _load()
    allowed = _ALLOWED_SETTINGS | set(_ALIASES)
    return {k: data.get(k) for k in sorted(allowed) if k in data}


def set_settings(values: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    if not isinstance(values, dict):
        return False, "settings must be a JSON object", {}

    normalized: dict[str, Any] = {}
    for raw_key, value in values.items():
        key = _key(raw_key)
        if key not in _ALLOWED_SETTINGS:
            return False, f"setting {raw_key!r} is not allowlisted", {}
        if value is None:
            continue
        normalized[key] = value
        for alias in _ALIASES.get(key, ()):
            normalized[alias] = value

    with _write_lock:
        data = _load()
        data.update(normalized)
        _write(data)
        for key, value in normalized.items():
            _apply_env(key, value)

    return True, f"{len(normalized)} setting(s) updated", normalized


__all__ = ["get_settings", "set_settings"]
