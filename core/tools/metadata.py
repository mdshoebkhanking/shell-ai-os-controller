from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from core.health.checks import current_platform, env_present, import_available, truthy
from core.health.states import RequirementStatus, RuntimeState, SafetyLevel, ToolReadiness, worst_state


@dataclass(frozen=True)
class ToolMetadata:
    tool_id: str
    category: str
    platform_support: list[str] = field(default_factory=lambda: ["all"])
    dependency_requirements: list[str] = field(default_factory=list)
    permissions_required: list[str] = field(default_factory=list)
    safety_level: SafetyLevel = SafetyLevel.SAFE
    latency_score: float = 0.3
    reliability_score: float = 0.75
    fallback_available: bool = False
    online_state: str = "offline"
    api_requirements: list[str] = field(default_factory=list)
    enabled: bool = True
    readiness: ToolReadiness = field(default_factory=lambda: ToolReadiness(RuntimeState.READY, True))
    duplicate_group: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "category": self.category,
            "platform_support": list(self.platform_support),
            "dependency_requirements": list(self.dependency_requirements),
            "permissions_required": list(self.permissions_required),
            "safety_level": self.safety_level.value,
            "latency_score": self.latency_score,
            "reliability_score": self.reliability_score,
            "fallback_available": self.fallback_available,
            "online_state": self.online_state,
            "api_requirements": list(self.api_requirements),
            "enabled": self.enabled,
            "readiness": self.readiness.to_dict(),
            "duplicate_group": self.duplicate_group,
        }


def _module(item: dict[str, Any]) -> str:
    return str(item.get("module") or item.get("id", "").split(":", 1)[0])


def _name_blob(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(k, ""))
        for k in ("id", "name", "title", "module", "category", "description")
    ).lower()


def re_search_word(word: str, text: str) -> bool:
    return bool(re.search(rf"\b{re.escape(word)}\b", text))


def _safety(item: dict[str, Any], permissions: list[str]) -> SafetyLevel:
    blob = _name_blob(item)
    risk = str(item.get("risk") or "").lower()
    if "evolution" in blob or "sentinel" in blob or "self_heal" in blob:
        return SafetyLevel.EXPERIMENTAL
    if permissions:
        return SafetyLevel.DANGEROUS
    if risk == "guarded" or any(word in blob for word in ("delete", "registry", "kill", "terminal", "powershell", "command")):
        return SafetyLevel.GUARDED
    return SafetyLevel.SAFE


def _requirements_for(item: dict[str, Any]) -> tuple[list[str], list[str], list[str], list[str], bool, str]:
    blob = _name_blob(item)
    module = _module(item)
    platforms = ["all"]
    dependencies: list[str] = []
    apis: list[str] = []
    permissions: list[str] = []
    fallback_available = False
    online_state = "offline"

    if module == "shell_external_integrations":
        return platforms, dependencies, apis, permissions, fallback_available, online_state
    if module == "shell_desktop_tools":
        return platforms, dependencies, apis, permissions, fallback_available, online_state
    if module == "shell_browser_CTRL" and str(item.get("name") or "").lower() in {
        "play_youtube_video",
        "search_youtube_video",
        "open_browser_url",
    }:
        # These functions use urllib/webbrowser and have graceful fallback
        # behavior. They do not need Selenium, ffmpeg, or a YouTube API key.
        online_state = "online"
        fallback_available = True
        return platforms, dependencies, apis, permissions, fallback_available, online_state
    if module == "shell_email_tool" and str(item.get("name") or "").lower() in {
        "email_setup_status_tool",
        "email_smtp_login_test_tool",
    }:
        return platforms, dependencies, apis, permissions, fallback_available, online_state
    if module == "shell_telegram" and str(item.get("name") or "").lower() in {
        "telegram_bot_status",
        "stop_telegram_bot",
        "set_telegram_remote_config_tool",
    }:
        return platforms, dependencies, apis, permissions, fallback_available, "online"
    if item.get("kind") == "agent":
        # Agent wrappers can answer text-only requests and choose their own
        # fallback path. Do not block the whole agent because its label or
        # description mentions "browser", "voice", or "Socratic".
        apis.append("GOOGLE_API_KEY|OPENAI_API_KEY|GROQ_API_KEY|MISTRAL_API_KEY|PERPLEXITY_API_KEY|OPENROUTER_API_KEY")
        online_state = "online"
        fallback_available = True
        return platforms, dependencies, apis, permissions, fallback_available, online_state

    if item.get("kind") == "windows_mcp_tool" or module in {"windows-mcp", "keyboard_mouse_CTRL"}:
        platforms = ["windows"]
    if module == "active_context_engine":
        platforms = ["windows"]
        dependencies.extend(["win32com", "win32gui", "win32clipboard"])
    if module == "shell_window_CTRL" and str(item.get("name") or "").lower() not in {"open_app", "close_app"}:
        platforms = ["windows"]
    if module in {"shell_system_god"}:
        platforms = ["windows"]
    if module == "shell_file_converter":
        dependencies.append("PIL")
    if module == "shell_file_opner":
        dependencies.append("fuzzywuzzy")
    if module == "shell_ppt_god":
        dependencies.append("pptx")

    if "browser" in blob:
        dependencies.append("selenium")
    if module == "shell_web_god":
        dependencies.append("playwright")
    if re_search_word("ocr", blob) or module in {"vision_engine", "shell_ocr"}:
        dependencies.extend(["pytesseract", "PIL"])
    if "video" in blob or "music" in blob or "audio" in blob:
        dependencies.append("ffmpeg")
    if "voice" in blob or "speech" in blob:
        dependencies.append("sounddevice")
        dependencies.append("speech_recognition")
    if "livekit" in blob:
        dependencies.append("livekit")
    if module == "shell_image_ai":
        apis.append("GOOGLE_API_KEY|OPENAI_API_KEY|HF_API_KEY|HUGGINGFACE_API_KEY|REPLICATE_API_KEY|STABILITY_API_KEY")
        fallback_available = True
        online_state = "online"
    if "google_search" in blob:
        apis.append("GOOGLE_SEARCH_API_KEY|GOOGLE_API_KEY")
        online_state = "online"
    if "weather" in blob or "whether" in blob:
        apis.append("OPENWEATHER_API_KEY")
        online_state = "online"
    if "news" in blob:
        apis.append("NEWS_API_KEY")
        online_state = "online"
    if "stock" in blob:
        apis.append("ALPHA_VANTAGE_API_KEY")
        online_state = "online"
    if "youtube" in blob:
        apis.append("YOUTUBE_API_KEY|GOOGLE_API_KEY")
        online_state = "online"
    if "telegram" in blob:
        apis.append("TELEGRAM_BOT_TOKEN")
        online_state = "online"
    if "email" in blob or "smtp" in blob:
        apis.append("SHELL_SMTP_SERVER|SHELL_SENDER_EMAIL")
        online_state = "online"
    if "instagram" in blob:
        apis.append("INSTAGRAM_USERNAME|INSTAGRAM_PASSWORD")
        online_state = "online"
    if any(word in blob for word in ("terminal", "powershell", "execute_code", "run_command", "shell command")):
        permissions.append("SHELL_ALLOW_TERMINAL_EXEC")
    if any(word in blob for word in ("write_code", "create_capability", "clone_module")):
        permissions.append("SHELL_ALLOW_CODE_WRITE")
    if any(word in blob for word in ("hotpatch", "rollback_evolution", "agent_patch")):
        permissions.append("SHELL_ALLOW_AGENT_PATCH")
    if "workflow" in blob and "command" in blob:
        permissions.append("SHELL_ALLOW_WORKFLOW_COMMANDS")
    if "workflow" in blob and "write" in blob:
        permissions.append("SHELL_ALLOW_WORKFLOW_FILE_WRITE")
    if "workflow" in blob and "read" in blob:
        permissions.append("SHELL_ALLOW_WORKFLOW_FILE_READ")

    return platforms, sorted(set(dependencies)), sorted(set(apis)), sorted(set(permissions)), fallback_available, online_state


def _api_group_ok(group: str) -> bool:
    names = [part.strip() for part in str(group).split("|") if part.strip()]
    return any(env_present(name) for name in names)


def _evaluate(
    platforms: list[str],
    dependencies: list[str],
    apis: list[str],
    permissions: list[str],
    safety_level: SafetyLevel,
) -> ToolReadiness:
    statuses: list[RequirementStatus] = []
    states: list[RuntimeState] = []
    reasons: list[str] = []
    platform_name = current_platform()

    if "all" not in platforms and platform_name not in platforms:
        state = RuntimeState.WINDOWS_ONLY if platforms == ["windows"] else RuntimeState.MISSING_DEPENDENCY
        states.append(state)
        reasons.append(f"platform {platform_name} is not supported")
        statuses.append(RequirementStatus("platform", False, state, f"requires {', '.join(platforms)}"))

    for dep in dependencies:
        if dep == "ffmpeg":
            ok = bool(__import__("shutil").which("ffmpeg"))
        else:
            ok = import_available(dep)
        if not ok:
            states.append(RuntimeState.MISSING_DEPENDENCY)
            reasons.append(f"missing dependency: {dep}")
        statuses.append(RequirementStatus(dep, ok, RuntimeState.READY if ok else RuntimeState.MISSING_DEPENDENCY))

    for group in apis:
        ok = _api_group_ok(group)
        if not ok:
            states.append(RuntimeState.NEEDS_API_KEY)
            reasons.append(f"missing API key: {group}")
        statuses.append(RequirementStatus(group, ok, RuntimeState.READY if ok else RuntimeState.NEEDS_API_KEY))

    for flag in permissions:
        ok = truthy(os.environ.get(flag))
        if not ok:
            states.append(RuntimeState.BLOCKED_BY_SAFETY)
            reasons.append(f"blocked by safety flag: {flag}")
        statuses.append(RequirementStatus(flag, ok, RuntimeState.READY if ok else RuntimeState.BLOCKED_BY_SAFETY))

    if safety_level == SafetyLevel.EXPERIMENTAL and not states:
        states.append(RuntimeState.EXPERIMENTAL)
        reasons.append("experimental capability")

    state = worst_state(states)
    ok = state in {RuntimeState.READY, RuntimeState.OFFLINE_ONLY}
    return ToolReadiness(state=state, ok=ok, reasons=reasons, requirements=statuses)


def infer_tool_metadata(item: dict[str, Any]) -> ToolMetadata:
    tool_id = str(item.get("id") or item.get("name") or "")
    category = str(item.get("category") or "general")
    platforms, deps, apis, permissions, fallback, online_state = _requirements_for(item)
    safety_level = _safety(item, permissions)

    latency = 0.25
    reliability = 0.78
    if item.get("kind") == "agent":
        latency, reliability = 0.82, 0.55
    elif item.get("kind") == "windows_mcp_tool" or platforms == ["windows"]:
        latency, reliability = 0.62, 0.65
    elif online_state == "online":
        latency, reliability = 0.68, 0.62
    elif safety_level in {SafetyLevel.DANGEROUS, SafetyLevel.EXPERIMENTAL}:
        latency, reliability = 0.55, 0.45
    elif category in {"developer", "files", "productivity", "general"}:
        latency, reliability = 0.25, 0.82

    readiness = _evaluate(platforms, deps, apis, permissions, safety_level)
    return ToolMetadata(
        tool_id=tool_id,
        category=category,
        platform_support=platforms,
        dependency_requirements=deps,
        permissions_required=permissions,
        safety_level=safety_level,
        latency_score=round(latency, 2),
        reliability_score=round(reliability, 2),
        fallback_available=fallback,
        online_state=online_state,
        api_requirements=apis,
        enabled=True,
        readiness=readiness,
    )
