"""
Shell Config - Centralized Configuration Manager
--------------------------------------------------
Load .env once, provide typed access to all settings.
Validates on startup and warns about missing keys.

Usage:
    from shell_config import config
    api_key = config.get_str("GOOGLE_API_KEY")
    port = config.get_int("SHELL_HUB_PORT", 5000)
    email_cfg = config.email  # grouped access
"""

import os
import threading
from dotenv import load_dotenv


class ShellConfig:
    """Singleton configuration manager for Shell AI."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._data = {}
        self._load()
        self._initialized = True

    def _load(self):
        """Load .env file and populate internal data."""
        load_dotenv(encoding="utf-8")
        # Cache all env vars at load time for fast access
        for key in os.environ:
            self._data[key] = os.environ[key]

    def reload(self):
        """Force reload .env file. Useful for runtime config changes."""
        self._data.clear()
        load_dotenv(override=True, encoding="utf-8")
        for key in os.environ:
            self._data[key] = os.environ[key]

    # ── Typed Getters ──────────────────────────────────────────────

    def get_str(self, key: str, default: str = None) -> str:
        return os.getenv(key, default)

    def get_int(self, key: str, default: int = None) -> int:
        val = os.getenv(key)
        if val is None:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = os.getenv(key, "").lower().strip()
        if val in ("1", "true", "yes", "on"):
            return True
        if val in ("0", "false", "no", "off", ""):
            return default
        return default

    def get_float(self, key: str, default: float = None) -> float:
        val = os.getenv(key)
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def get_list(self, key: str, default: list = None, separator: str = ",") -> list:
        """Get a comma-separated (or custom separator) list from env var."""
        val = os.getenv(key)
        if val is None:
            return default or []
        return [item.strip() for item in val.split(separator) if item.strip()]

    # ── Grouped Access ─────────────────────────────────────────────

    _API_KEYS = [
        "GOOGLE_API_KEY", "GOOGLE_SEARCH_API_KEY", "SEARCH_ENGINE_ID",
        "OPENAI_API_KEY", "GROQ_API_KEY",
        "MISTRAL_API_KEY", "PERPLEXITY_API_KEY",
        "OPENWEATHER_API_KEY", "NEWS_API_KEY",
        "HF_API_KEY", "HUGGINGFACE_API_KEY", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
        "INSTAGRAM_USERNAME", "INSTAGRAM_PASSWORD",
        "TELEGRAM_BOT_TOKEN",
    ]

    _CRITICAL_KEYS = [
        "GOOGLE_API_KEY", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "LIVEKIT_URL",
    ]

    @property
    def api_keys(self) -> dict:
        return {k: self.get_str(k) for k in self._API_KEYS}

    @property
    def livekit(self) -> dict:
        return {
            "api_key": self.get_str("LIVEKIT_API_KEY"),
            "api_secret": self.get_str("LIVEKIT_API_SECRET"),
            "url": self.get_str("LIVEKIT_URL"),
        }

    @property
    def voice(self) -> dict:
        # Import lazily to avoid a circular import: shell_voice doesn't depend
        # on shell_config, but other modules might import both during startup.
        try:
            from shell_voice import resolve_voice, resolve_persona, DEFAULT_VOICE, DEFAULT_PERSONA
            voice_name = resolve_voice(self.get_str("VOICE_NAME"))
            persona = resolve_persona(self.get_str("VOICE_PERSONA")).name
        except Exception:
            voice_name = self.get_str("VOICE_NAME", "Aoede")
            persona = self.get_str("VOICE_PERSONA", "Hinglish")
        return {
            "model": self.get_str("GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest"),
            "api_version": self.get_str("GEMINI_API_VERSION", "v1alpha"),
            "temperature": self.get_float("GEMINI_TEMPERATURE", 0.8),
            "voice_name": voice_name,
            "persona": persona,
            "force_realtime": self.get_bool("FORCE_REALTIME_VOICE", True),
            "allow_local_fallback": self.get_bool("ALLOW_LOCAL_TTS", True),
            "local_mirror": self.get_bool("LOCAL_TTS_MIRROR", False),
        }

    @property
    def email(self) -> dict:
        return {
            "smtp_server": self.get_str("SHELL_SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": self.get_int("SHELL_SMTP_PORT", 587),
            "use_ssl": self.get_bool("SHELL_SMTP_USE_SSL", False),
            "sender_email": self.get_str("SHELL_SENDER_EMAIL", ""),
            "sender_name": self.get_str("SHELL_SENDER_NAME", ""),
            "sender_role": self.get_str("SHELL_SENDER_ROLE", ""),
            "sender_company": self.get_str("SHELL_SENDER_COMPANY", ""),
        }

    @property
    def audio(self) -> dict:
        return {
            "input_device": self.get_str("SHELL_INPUT_DEVICE"),
            "output_device": self.get_str("SHELL_OUTPUT_DEVICE"),
            "avoid_virtual_mic": self.get_bool("SHELL_AUTO_AVOID_VIRTUAL_MIC", True),
            "avoid_virtual_output": self.get_bool("SHELL_AUTO_AVOID_VIRTUAL_OUTPUT", True),
            "auto_text_on_no_input": self.get_bool("SHELL_AUTO_TEXT_ON_NO_INPUT", True),
            "console_text_mode": self.get_bool("SHELL_CONSOLE_TEXT_MODE", False),
        }

    @property
    def vad(self) -> dict:
        return {
            "activation_threshold": self.get_float("VAD_ACTIVATION_THRESHOLD", 0.58),
            "deactivation_threshold": self.get_float("VAD_DEACTIVATION_THRESHOLD", 0.46),
            "min_speech_sec": self.get_float("VAD_MIN_SPEECH_SEC", 0.12),
            "min_silence_sec": self.get_float("VAD_MIN_SILENCE_SEC", 0.75),
            "prefix_padding_sec": self.get_float("VAD_PREFIX_PADDING_SEC", 0.35),
            "max_buffer_sec": self.get_float("VAD_MAX_BUFFER_SEC", 45),
            "sample_rate": self.get_int("VAD_SAMPLE_RATE", 16000),
        }

    @property
    def infrastructure(self) -> dict:
        return {
            "log_level": self.get_str("LOG_LEVEL", "INFO"),
            "auto_discover": self.get_bool("SHELL_AUTO_DISCOVER", False),
            "hub_url": self.get_str("SHELL_HUB_URL", "http://127.0.0.1:5000"),
            "agent_mode": self.get_str("SHELL_AGENT_MODE", "console"),
        }

    @property
    def memory(self) -> dict:
        """Memory system configuration — previously hardcoded values."""
        return {
            "max_memories": self.get_int("SHELL_MAX_MEMORIES", 10000),
            "save_batch_size": self.get_int("SHELL_SAVE_BATCH_SIZE", 10),
            "similarity_threshold": self.get_float("SHELL_SIMILARITY_THRESHOLD", 0.55),
            "chunk_size": self.get_int("SHELL_CHUNK_SIZE", 1500),
            "chunk_overlap": self.get_int("SHELL_CHUNK_OVERLAP", 200),
        }

    @property
    def telegram(self) -> dict:
        """Telegram bot configuration — previously hardcoded values."""
        return {
            "bot_token": self.get_str("TELEGRAM_BOT_TOKEN", ""),
            "rate_limit_per_minute": self.get_int("TELEGRAM_RATE_LIMIT", 30),
            "max_history_per_user": self.get_int("TELEGRAM_MAX_HISTORY", 50),
        }

    @property
    def vision(self) -> dict:
        """Vision engine configuration."""
        return {
            "gemini_timeout": self.get_int("VISION_GEMINI_TIMEOUT", 30),
            "ocr_confidence": self.get_float("VISION_OCR_CONFIDENCE", 0.8),
        }

    @property
    def hub(self) -> dict:
        """Hub server configuration — previously hardcoded port list."""
        return {
            "ports": self.get_list("SHELL_HUB_PORTS", ["5000", "5001", "5002", "5003"]),
            "host": self.get_str("SHELL_HUB_HOST", "127.0.0.1"),
        }

    # ── Validation ─────────────────────────────────────────────────

    def validate(self) -> list:
        """Return list of warning messages for missing/empty keys."""
        warnings = []
        for key in self._CRITICAL_KEYS:
            if not self.get_str(key):
                warnings.append(f"CRITICAL: {key} is missing!")
        for key in self._API_KEYS:
            if key not in self._CRITICAL_KEYS and not self.get_str(key):
                warnings.append(f"Optional: {key} not set")
        return warnings

    def get_active_keys_count(self) -> tuple:
        """Returns (active_count, total_count) of API keys."""
        active = sum(1 for k in self._API_KEYS if self.get_str(k))
        return active, len(self._API_KEYS)

    def summary(self) -> str:
        """Human-readable config summary with redacted secrets."""
        lines = ["Shell AI Configuration:"]
        active, total = self.get_active_keys_count()
        lines.append(f"  API Keys: {active}/{total} configured")
        lines.append("")
        for key in self._API_KEYS:
            val = self.get_str(key, "")
            if val:
                redacted = val[:4] + "****" + val[-4:] if len(val) > 12 else "****"
                lines.append(f"  {key}: {redacted}")
            else:
                lines.append(f"  {key}: (not set)")
        return "\n".join(lines)


# Module-level singleton
config = ShellConfig()
