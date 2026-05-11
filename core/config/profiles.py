from __future__ import annotations

import os
import platform
import time
from dataclasses import dataclass, field
from typing import Mapping, Any


class ConfigProfile:
    BEGINNER = "beginner"
    ADVANCED = "advanced"
    DEBUG = "debug"
    ENTERPRISE = "enterprise"

    ALL = {BEGINNER, ADVANCED, DEBUG, ENTERPRISE}


class ConfigIssueLevel:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


_TRUTHY = {"1", "true", "yes", "on", "enabled"}
_FALSY = {"0", "false", "no", "off", "disabled", ""}
_SECRET_HINTS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "WEBHOOK")

_SAFETY_FLAGS = {
    "SHELL_ALLOW_CODE_WRITE",
    "SHELL_ALLOW_AGENT_PATCH",
    "SHELL_ALLOW_TERMINAL_EXEC",
    "SHELL_ALLOW_WORKFLOW_COMMANDS",
    "SHELL_ALLOW_WORKFLOW_FILE_WRITE",
    "SHELL_ALLOW_AGENT_BROWSER_EXEC",
    "SHELL_ALLOW_OPENCLAW_SKILL_INSTALL",
    "SHELL_TELEGRAM_ALLOW_TERMINAL",
}

_PROFILE_DEFAULTS: dict[str, dict[str, str]] = {
    ConfigProfile.BEGINNER: {
        "SHELL_BEGINNER_MODE": "1",
        "SHELL_ADVANCED_MODE": "0",
        "SHELL_DEBUG_MODE": "0",
        "SHELL_LOG_LEVEL": "INFO",
        "SHELL_LOG_FORMAT": "text",
        "SHELL_AI_PROVIDER_MODE": "hybrid",
        "SHELL_LOCAL_MODELS_ENABLED": "0",
        "SHELL_CLOUD_PROVIDERS_ENABLED": "1",
        "SHELL_ENABLE_PLUGIN_LOADING": "0",
        "SHELL_PLUGIN_REQUIRE_SIGNATURES": "0",
        "SHELL_MAX_CONCURRENCY": "2",
        "SHELL_TOOL_CONFIRMATION_LEVEL": "high",
        "SHELL_OBSERVABILITY_MODE": "local",
    },
    ConfigProfile.ADVANCED: {
        "SHELL_BEGINNER_MODE": "0",
        "SHELL_ADVANCED_MODE": "1",
        "SHELL_DEBUG_MODE": "0",
        "SHELL_LOG_LEVEL": "INFO",
        "SHELL_LOG_FORMAT": "json",
        "SHELL_AI_PROVIDER_MODE": "hybrid",
        "SHELL_LOCAL_MODELS_ENABLED": "1",
        "SHELL_CLOUD_PROVIDERS_ENABLED": "1",
        "SHELL_ENABLE_PLUGIN_LOADING": "0",
        "SHELL_PLUGIN_REQUIRE_SIGNATURES": "0",
        "SHELL_MAX_CONCURRENCY": "4",
        "SHELL_TOOL_CONFIRMATION_LEVEL": "medium",
        "SHELL_OBSERVABILITY_MODE": "local",
    },
    ConfigProfile.DEBUG: {
        "SHELL_BEGINNER_MODE": "0",
        "SHELL_ADVANCED_MODE": "1",
        "SHELL_DEBUG_MODE": "1",
        "SHELL_LOG_LEVEL": "DEBUG",
        "SHELL_LOG_FORMAT": "json",
        "SHELL_AI_PROVIDER_MODE": "hybrid",
        "SHELL_LOCAL_MODELS_ENABLED": "1",
        "SHELL_CLOUD_PROVIDERS_ENABLED": "1",
        "SHELL_ENABLE_PLUGIN_LOADING": "0",
        "SHELL_PLUGIN_REQUIRE_SIGNATURES": "0",
        "SHELL_MAX_CONCURRENCY": "1",
        "SHELL_TOOL_CONFIRMATION_LEVEL": "high",
        "SHELL_OBSERVABILITY_MODE": "debug",
    },
    ConfigProfile.ENTERPRISE: {
        "SHELL_BEGINNER_MODE": "0",
        "SHELL_ADVANCED_MODE": "1",
        "SHELL_DEBUG_MODE": "0",
        "SHELL_LOG_LEVEL": "INFO",
        "SHELL_LOG_FORMAT": "json",
        "SHELL_AI_PROVIDER_MODE": "hybrid",
        "SHELL_LOCAL_MODELS_ENABLED": "1",
        "SHELL_CLOUD_PROVIDERS_ENABLED": "1",
        "SHELL_ENABLE_PLUGIN_LOADING": "0",
        "SHELL_PLUGIN_REQUIRE_SIGNATURES": "1",
        "SHELL_MAX_CONCURRENCY": "4",
        "SHELL_TOOL_CONFIRMATION_LEVEL": "high",
        "SHELL_OBSERVABILITY_MODE": "audit",
        "SHELL_ENTERPRISE_AUDIT_LOG": "1",
    },
}


@dataclass(frozen=True)
class ConfigIssue:
    level: str
    key: str
    message: str
    recommendation: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "key": self.key,
            "message": self.message,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class EnterpriseConfig:
    profile: str
    generated_at: float
    values: dict[str, str] = field(default_factory=dict)
    platform: dict[str, str] = field(default_factory=dict)

    def get_bool(self, key: str, default: bool = False) -> bool:
        raw = str(self.values.get(key, "")).strip().lower()
        if raw in _TRUTHY:
            return True
        if raw in _FALSY:
            return False
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(str(self.values.get(key, "")).strip())
        except (TypeError, ValueError):
            return default

    def redacted(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "generated_at": self.generated_at,
            "platform": dict(self.platform),
            "values": {key: redact_value(key, value) for key, value in sorted(self.values.items())},
        }


@dataclass(frozen=True)
class ValidationReport:
    status: str
    profile: str
    generated_at: float
    issues: list[ConfigIssue]
    config: EnterpriseConfig

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "profile": self.profile,
            "generated_at": self.generated_at,
            "issues": [issue.to_dict() for issue in self.issues],
            "summary": {
                "errors": sum(1 for issue in self.issues if issue.level == ConfigIssueLevel.ERROR),
                "warnings": sum(1 for issue in self.issues if issue.level == ConfigIssueLevel.WARNING),
                "infos": sum(1 for issue in self.issues if issue.level == ConfigIssueLevel.INFO),
            },
            "config": self.config.redacted(),
        }


def normalize_profile(raw: str | None) -> str:
    profile = str(raw or ConfigProfile.BEGINNER).strip().lower()
    if profile in ConfigProfile.ALL:
        return profile
    return ConfigProfile.BEGINNER


def profile_defaults(profile: str | None = None) -> dict[str, str]:
    return dict(_PROFILE_DEFAULTS[normalize_profile(profile)])


def redact_value(key: str, value: object) -> str:
    text = "" if value is None else str(value)
    if any(hint in key.upper() for hint in _SECRET_HINTS):
        if not text:
            return ""
        if len(text) <= 8:
            return "****"
        return f"{text[:3]}****{text[-3:]}"
    return text


def _env_bool(env: Mapping[str, str], key: str, default: bool = False) -> bool:
    raw = str(env.get(key, "")).strip().lower()
    if raw in _TRUTHY:
        return True
    if raw in _FALSY:
        return False
    return default


def build_effective_config(env: Mapping[str, str] | None = None) -> EnterpriseConfig:
    source = dict(os.environ if env is None else env)
    profile = normalize_profile(source.get("SHELL_CONFIG_PROFILE") or source.get("SHELL_PROFILE"))
    values = profile_defaults(profile)
    tracked_keys = set(values) | _SAFETY_FLAGS | {
        "SHELL_CONFIG_PROFILE",
        "SHELL_PROFILE",
        "SHELL_HUB_HOST",
        "SHELL_HUB_PORTS",
        "SHELL_HUB_URL",
        "SHELL_PLUGIN_DIR",
        "SHELL_EXTENSION_DIR",
        "SHELL_RUNTIME_DIR",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "LIVEKIT_URL",
        "TELEGRAM_BOT_TOKEN",
        "SHELL_TELEGRAM_ALLOWED_CHAT_IDS",
        "SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED",
    }
    for key in tracked_keys:
        if key in source:
            values[key] = str(source[key])
    values["SHELL_CONFIG_PROFILE"] = profile
    return EnterpriseConfig(
        profile=profile,
        generated_at=time.time(),
        values=values,
        platform={
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
    )


def validate_environment(env: Mapping[str, str] | None = None) -> ValidationReport:
    source = dict(os.environ if env is None else env)
    config = build_effective_config(source)
    issues: list[ConfigIssue] = []

    requested_profile = source.get("SHELL_CONFIG_PROFILE") or source.get("SHELL_PROFILE")
    if requested_profile and normalize_profile(requested_profile) != str(requested_profile).strip().lower():
        issues.append(ConfigIssue(
            ConfigIssueLevel.WARNING,
            "SHELL_CONFIG_PROFILE",
            f"Unknown profile {requested_profile!r}; using beginner defaults.",
            "Use beginner, advanced, debug, or enterprise.",
        ))

    for flag in sorted(_SAFETY_FLAGS):
        if _env_bool(source, flag):
            level = ConfigIssueLevel.ERROR if config.profile in {ConfigProfile.BEGINNER, ConfigProfile.ENTERPRISE} else ConfigIssueLevel.WARNING
            issues.append(ConfigIssue(
                level,
                flag,
                "Risky execution flag is enabled.",
                "Keep disabled by default; enable only for an explicit, audited task.",
            ))

    provider_mode = config.values.get("SHELL_AI_PROVIDER_MODE", "hybrid").lower()
    if provider_mode not in {"auto", "local", "cloud", "hybrid"}:
        issues.append(ConfigIssue(
            ConfigIssueLevel.WARNING,
            "SHELL_AI_PROVIDER_MODE",
            f"Unsupported provider mode {provider_mode!r}.",
            "Use auto, local, cloud, or hybrid.",
        ))

    max_concurrency = config.get_int("SHELL_MAX_CONCURRENCY", 2)
    if max_concurrency < 1 or max_concurrency > 16:
        issues.append(ConfigIssue(
            ConfigIssueLevel.WARNING,
            "SHELL_MAX_CONCURRENCY",
            "Concurrency is outside the recommended desktop range.",
            "Use 1-8 for local desktop, 9-16 only for controlled worker nodes.",
        ))

    if config.profile == ConfigProfile.ENTERPRISE and not config.get_bool("SHELL_PLUGIN_REQUIRE_SIGNATURES"):
        issues.append(ConfigIssue(
            ConfigIssueLevel.ERROR,
            "SHELL_PLUGIN_REQUIRE_SIGNATURES",
            "Enterprise profile requires signed plugins.",
            "Set SHELL_PLUGIN_REQUIRE_SIGNATURES=1.",
        ))

    if config.get_bool("SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED") and not source.get("SHELL_TELEGRAM_ALLOWED_CHAT_IDS"):
        issues.append(ConfigIssue(
            ConfigIssueLevel.ERROR,
            "SHELL_TELEGRAM_ALLOWED_CHAT_IDS",
            "Telegram remote control is enabled without an allowlist.",
            "Set explicit chat IDs before enabling remote control.",
        ))

    status = "fail" if any(issue.level == ConfigIssueLevel.ERROR for issue in issues) else "pass"
    return ValidationReport(status, config.profile, time.time(), issues, config)
