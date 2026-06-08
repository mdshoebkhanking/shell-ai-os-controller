"""Offline/online task-mode policy for Shell user requests."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


CLOUD_PROVIDER_KEY_GROUPS: tuple[tuple[str, ...], ...] = (
    ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    ("OPENAI_API_KEY",),
    ("ANTHROPIC_API_KEY",),
    ("OPENROUTER_API_KEY",),
    ("GROQ_API_KEY",),
    ("MISTRAL_API_KEY",),
    ("TOGETHER_API_KEY",),
    ("HF_API_KEY", "HUGGINGFACE_API_KEY"),
)

_HARD_BUILD_RE = re.compile(
    r"\b("
    r"full\s*stack|full-stack|full\s+app|complete\s+app|complex\s+(?:website|site|web\s*app|app)|"
    r"big\s+codebase|large\s+codebase|production\s+(?:app|website|site|system)|"
    r"saas|e-?commerce|marketplace|multi\s*page|multi-page|admin\s+panel|"
    r"authentication\s+system|auth\s+system|backend\s+(?:api|server)|database\s+(?:app|schema)|"
    r"deployment|deployable|enterprise|real\s+app"
    r")\b",
    re.I,
)

_BASIC_CREATION_RE = re.compile(
    r"\b("
    r"single\s+html|standalone\s+html|login\s+page|landing\s+page|simple\s+(?:website|site|page|app)|"
    r"one\s+page|pdf|document|script|notes?|resume|calculator|snake|tetris"
    r")\b",
    re.I,
)


def _looks_configured_secret(value: str | None) -> bool:
    low = str(value or "").strip().lower()
    return bool(low) and len(low) >= 12 and low not in {
        "your_api_key_here",
        "your_openai_api_key_here",
        "your_google_api_key_here",
        "your_gemini_api_key_here",
        "your_anthropic_api_key_here",
    } and not low.startswith(("your_", "replace_"))


@dataclass(frozen=True)
class TaskModeDecision:
    mode: str
    requires_online: bool
    reason: str
    level: int = 1
    capability: str = "local"

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "requires_online": self.requires_online,
            "reason": self.reason,
            "level": self.level,
            "capability": self.capability,
        }


def configured_cloud_key_names() -> list[str]:
    """Return configured provider key names without exposing secret values."""
    configured: list[str] = []
    for group in CLOUD_PROVIDER_KEY_GROUPS:
        if any(_looks_configured_secret(os.environ.get(key)) for key in group):
            configured.append(group[0])
    return configured


def has_cloud_api_key() -> bool:
    return bool(configured_cloud_key_names())


def online_mode_setting() -> str:
    return os.environ.get("SHELL_CHAT_PROVIDER_MODE", os.environ.get("SHELL_WEB_CHAT_PROVIDER_MODE", "auto")).strip().lower()


def online_mode_enabled() -> bool:
    return online_mode_setting() in {"online", "cloud", "provider"}


def online_full_version_ready() -> bool:
    return has_cloud_api_key() and online_mode_enabled()


def classify_task_mode(request: str, *, route_tool: str = "") -> TaskModeDecision:
    """Classify whether Shell can handle a task offline or should require cloud mode."""
    text = " ".join(str(request or "").split()).strip()
    lower = text.lower()
    tool = str(route_tool or "").lower()

    if not text:
        return TaskModeDecision("offline", False, "empty request", level=1, capability="local")

    if any(
        marker in tool
        for marker in (
            "shell_workspace_tools:create_user_file_tool",
            "shell_workspace_tools:read_user_file_tool",
        )
    ):
        return TaskModeDecision("offline", False, "Level 1 document/file task", level=1, capability="document")

    if re.search(r"\b(powershell|python|javascript|js|html|css|batch|bat)\b", lower) and re.search(
        r"\b(script|helper|small|simple|snippet|glue|automation|file\s+operation|files?)\b",
        lower,
    ):
        return TaskModeDecision("offline", False, "Level 1 small code task", level=1, capability="local-code")

    if _BASIC_CREATION_RE.search(lower) and not _HARD_BUILD_RE.search(lower):
        return TaskModeDecision("offline", False, "Level 1 basic creation task", level=1, capability="template")

    if re.search(r"\b(portfolio|personal\s+site|profile\s+site|static\s+(?:website|site|page))\b", lower):
        return TaskModeDecision("offline", False, "Level 1 static website task", level=1, capability="template")

    if _HARD_BUILD_RE.search(lower):
        return TaskModeDecision(
            "online",
            True,
            "Level 2 hard creative/build task needs the full cloud model",
            level=2,
            capability="cloud-llm",
        )

    if "shell_code_engine:create_fullstack_app_tool" in tool:
        if re.search(r"\b(app|application|software|dashboard|crm|manager)\b", lower) and re.search(
            r"\b(auth|login|database|api|backend|full|production|complex)\b",
            lower,
        ):
            return TaskModeDecision(
                "online",
                True,
                "Level 2 app build includes backend/auth/database complexity",
                level=2,
                capability="cloud-llm",
            )
        return TaskModeDecision("offline", False, "Level 1 basic managed scaffold", level=1, capability="template")

    return TaskModeDecision("offline", False, "Level 1 normal local task", level=1, capability="local")


def requires_online_full_version(request: str, *, route_tool: str = "") -> bool:
    return classify_task_mode(request, route_tool=route_tool).requires_online


def online_full_version_message(reason: str = "") -> str:
    key_names = configured_cloud_key_names()
    if key_names and not online_mode_enabled():
        key_note = (
            "API key configured hai, lekin online mode enabled nahi hai. "
            "Settings mein Shell Chat Provider Mode ko Online/Cloud par set karo for the pro version."
        )
    elif key_names:
        key_note = (
            "API key configured hai, lekin cloud model abhi reachable/ready nahi lag raha. "
            "Internet/provider status check karo for the pro version."
        )
    else:
        key_note = (
            "Settings > API Keys mein OpenAI, Gemini/Google, Anthropic, OpenRouter, Groq, Mistral, "
            "Together, ya HuggingFace key add karoge to advanced version milega."
        )
    reason_text = f" Reason: {reason}." if reason else ""
    return (
        "I can make a basic version offline, or you can add an API key to get a more advanced version. "
        "Level 1 local mode reliable basic PDFs/docs, simple static websites, small code, aur normal desktop automation karta hai. "
        "Level 2 pro mode full apps, complex websites, big codebases, aur polished long documents ke liye cloud LLM use karta hai. "
        f"{key_note}{reason_text}"
    ).strip()


__all__ = [
    "CLOUD_PROVIDER_KEY_GROUPS",
    "TaskModeDecision",
    "classify_task_mode",
    "configured_cloud_key_names",
    "has_cloud_api_key",
    "online_full_version_ready",
    "online_full_version_message",
    "online_mode_enabled",
    "online_mode_setting",
    "requires_online_full_version",
]
