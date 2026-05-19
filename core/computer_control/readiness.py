from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

SAFETY_FLAGS: dict[str, str] = {
    "SHELL_ALLOW_TERMINAL_EXEC": "terminal or PowerShell execution",
    "SHELL_ALLOW_CODE_WRITE": "LLM-generated code and file writes",
    "SHELL_ALLOW_AGENT_PATCH": "runtime agent/core patching",
    "SHELL_ALLOW_WORKFLOW_COMMANDS": "workflow shell commands",
    "SHELL_ALLOW_WORKFLOW_FILE_WRITE": "workflow file writes",
    "SHELL_ALLOW_AGENT_BROWSER_EXEC": "real browser automation",
    "SHELL_TELEGRAM_ALLOW_TERMINAL": "Telegram-triggered terminal execution",
    "SHELL_HUB_ALLOW_UNAUTH_REMOTE": "unauthenticated remote hub access",
    "SHELL_MCP_ALLOW_UNAUTH_REMOTE": "unauthenticated remote MCP access",
}

OBSERVATION_ACTIONS = ("screenshot", "snapshot", "ocr", "window list", "clipboard read")
DIRECT_CONTROL_ACTIONS = ("click", "type", "shortcut", "open app", "switch app", "close app")
HIGH_IMPACT_ACTIONS = (
    "terminal execution",
    "file deletion",
    "registry edits",
    "purchases",
    "credential handling",
    "external messages",
)


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _platform_key() -> str:
    name = platform.system().lower()
    if name == "darwin":
        return "macos"
    if name.startswith("win"):
        return "windows"
    if name == "linux":
        return "linux"
    return name or "unknown"


def _which(name: str) -> bool:
    return shutil.which(name) is not None


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _file_available(*parts: str) -> bool:
    return (ROOT / Path(*parts)).exists()


def _status(score: int) -> str:
    if score >= 88:
        return "ready"
    if score >= 62:
        return "attention"
    return "blocked"


def _score_from_checks(checks: dict[str, bool], *, penalty: int = 0) -> int:
    if not checks:
        return max(0, 100 - penalty)
    passed = sum(1 for ok in checks.values() if ok)
    return max(0, min(100, round((passed / len(checks)) * 100) - penalty))


def _group(
    name: str,
    *,
    summary: str,
    checks: dict[str, bool],
    status: str | None = None,
    score: int | None = None,
    signals: list[str] | None = None,
    risks: list[str] | None = None,
    permissions: list[str] | None = None,
    next_actions: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    final_score = int(score if score is not None else _score_from_checks(checks))
    return {
        "name": name,
        "status": status or _status(final_score),
        "score": final_score,
        "summary": summary,
        "checks": dict(checks),
        "signals": list(signals or []),
        "risks": list(risks or []),
        "permissions_required": list(permissions or []),
        "next_actions": list(next_actions or []),
        "metadata": dict(metadata or {}),
    }


def _app_control_group(system: str) -> dict[str, Any]:
    checks = {
        "shell_window_open_app_tool": _file_available("shell_window_CTRL.py"),
        "shell_window_close_app_tool": _file_available("shell_window_CTRL.py"),
    }
    signals: list[str] = ["cross-platform open/close app tools are present"]
    risks: list[str] = []
    if system == "macos":
        checks.update({"macos_open_cli": _which("open"), "macos_osascript": _which("osascript")})
        if not checks["macos_open_cli"]:
            risks.append("macOS open command is unavailable")
    elif system == "windows":
        checks.update({"windows_mcp_catalog": _file_available("shell_windows_mcp.py")})
    elif system == "linux":
        checks.update({"linux_xdg_open": _which("xdg-open"), "linux_gtk_launch": _which("gtk-launch")})
        if not checks["linux_xdg_open"] and not checks["linux_gtk_launch"]:
            risks.append("Linux app launching needs xdg-open or gtk-launch")
    return _group(
        "app_control",
        summary="Launch and close applications through platform-specific adapters.",
        checks=checks,
        signals=signals,
        risks=risks,
        next_actions=["Promote app launch/close into the desktop agent plan executor with per-action confirmation."],
    )


def _input_control_group(system: str) -> dict[str, Any]:
    checks = {
        "desktop_click_tool": _file_available("shell_desktop_tools.py"),
        "desktop_type_tool": _file_available("shell_desktop_tools.py"),
        "desktop_shortcut_tool": _file_available("shell_desktop_tools.py"),
        "pyautogui_optional": _module_available("pyautogui"),
    }
    permissions: list[str] = []
    risks: list[str] = []
    signals = ["mouse and keyboard primitives are cataloged as guarded system capabilities"]
    score_penalty = 0
    if system == "macos":
        checks.update({"macos_system_events": _which("osascript"), "macos_cliclick": _which("cliclick")})
        permissions.extend(["macOS Accessibility permission", "macOS Screen Recording permission for screenshot/OCR workflows"])
        risks.append("macOS input control cannot be trusted until Accessibility permission is granted by the user")
        score_penalty = 16
    elif system == "windows":
        checks.update({"windows_mcp_static_actions": _file_available("shell_windows_mcp.py")})
        signals.append("Windows-MCP provides the native mouse/keyboard action surface on Windows")
    elif system == "linux":
        checks.update({"linux_xdotool": _which("xdotool"), "linux_wtype": _which("wtype")})
        permissions.append("Wayland/X11 automation permission or compositor support")
        risks.append("Linux desktop input support is partial and depends on X11/Wayland compositor tooling")
        score_penalty = 24
    score = _score_from_checks(checks, penalty=score_penalty)
    return _group(
        "input_control",
        summary="Click, type, and shortcut actions are available only through permission-aware guarded paths.",
        checks=checks,
        score=score,
        signals=signals,
        risks=risks,
        permissions=permissions,
        next_actions=["Route all future autonomous input through preview, user confirmation, execution, and screenshot verification."],
    )


def _screen_understanding_group(system: str) -> dict[str, Any]:
    checks = {
        "screenshot_tool": _file_available("shell_screenshot.py"),
        "vision_operating_layer": _file_available("core", "vision", "screen.py"),
        "ocr_tool": _file_available("shell_ocr.py"),
        "screen_vision_tool": _file_available("shell_screen_vision.py"),
    }
    optional = {
        "mss": _module_available("mss"),
        "PIL": _module_available("PIL"),
        "pytesseract": _module_available("pytesseract"),
    }
    risks: list[str] = []
    permissions: list[str] = []
    signals = ["screen/OCR/vision primitives exist for observe-then-act desktop workflows"]
    if system == "macos":
        checks["macos_screencapture"] = _which("screencapture")
        permissions.append("macOS Screen Recording permission")
    if not optional["pytesseract"]:
        risks.append("OCR quality may be limited because pytesseract is unavailable")
    return _group(
        "screen_understanding",
        summary="Screenshots, OCR, and UI-element parsing support computer-use observation loops.",
        checks=checks,
        signals=signals,
        risks=risks,
        permissions=permissions,
        next_actions=["Create a screenshot-to-action verification loop before enabling multi-step visual automation."],
        metadata={"optional_dependencies": optional},
    )


def _clipboard_group(system: str) -> dict[str, Any]:
    checks = {"clipboard_tool": _file_available("shell_clipboard.py"), "pyperclip_optional": _module_available("pyperclip")}
    if system == "macos":
        checks.update({"pbcopy": _which("pbcopy"), "pbpaste": _which("pbpaste")})
    elif system == "windows":
        checks.update({"windows_clip": _which("clip")})
    elif system == "linux":
        checks.update({"xclip": _which("xclip"), "wl_clipboard": _which("wl-copy") and _which("wl-paste")})
    return _group(
        "clipboard",
        summary="Clipboard access is available as a low-level capability and should stay explicit in agent plans.",
        checks=checks,
        signals=["clipboard capability is present"],
        risks=["clipboard may contain sensitive data; reads and writes must be visible to the user"],
        permissions=["user approval for sensitive clipboard reads/writes"],
        next_actions=["Show clipboard reads/writes in the automation audit timeline."],
    )


def _windows_mcp_group(system: str) -> dict[str, Any]:
    checks = {"windows_mcp_module": _file_available("shell_windows_mcp.py"), "uvx_available": _which("uvx")}
    runtime_supported = system == "windows" or _truthy(os.environ.get("SHELL_WINDOWS_MCP_ALLOW_NON_WINDOWS"))
    try:
        from shell_windows_mcp import WINDOWS_MCP_STATIC_TOOLS, windows_mcp_install_hint

        static_count = len(WINDOWS_MCP_STATIC_TOOLS)
        install_hint = windows_mcp_install_hint()
    except Exception:
        static_count = 0
        install_hint = "Windows-MCP catalog unavailable."
    checks["runtime_supported_here"] = runtime_supported
    score = 88 if runtime_supported and checks["windows_mcp_module"] else 58 if checks["windows_mcp_module"] else 30
    return _group(
        "windows_mcp",
        summary="Windows-MCP is the preferred native Windows desktop automation harness.",
        checks=checks,
        status="ready" if runtime_supported and checks["windows_mcp_module"] else "attention",
        score=score,
        signals=[f"{static_count} Windows-MCP actions are statically cataloged"] if static_count else [],
        risks=[] if runtime_supported else ["Windows-MCP runtime is only executable on Windows unless explicitly allowed for development"],
        next_actions=["Validate Windows-MCP end to end on a real Windows machine before marketing full Windows control."],
        metadata={"static_tool_count": static_count, "install_hint": install_hint},
    )


def _macos_group(system: str) -> dict[str, Any]:
    checks = {
        "current_platform": system == "macos",
        "open": _which("open"),
        "osascript": _which("osascript"),
        "screencapture": _which("screencapture"),
        "cliclick": _which("cliclick"),
    }
    score = _score_from_checks(checks, penalty=10 if system == "macos" else 35)
    risks = [] if system == "macos" else ["macOS adapter is dormant on this platform"]
    if system == "macos":
        risks.append("Accessibility and Screen Recording permissions must be granted by the user for reliable control")
    return _group(
        "macos_control",
        summary="macOS automation currently uses open, AppleScript/System Events, screencapture, and optional cliclick.",
        checks=checks,
        status="attention" if system == "macos" else "blocked",
        score=score,
        signals=["macOS command-line automation primitives detected"] if system == "macos" else [],
        risks=risks,
        permissions=["Accessibility", "Screen Recording"],
        next_actions=["Replace ad hoc macOS calls with a dedicated permission-aware MacDesktopController."],
    )


def _linux_group(system: str) -> dict[str, Any]:
    checks = {
        "current_platform": system == "linux",
        "xdg_open": _which("xdg-open"),
        "gtk_launch": _which("gtk-launch"),
        "xdotool": _which("xdotool"),
        "wtype": _which("wtype"),
        "wayland_session_hint": bool(os.environ.get("WAYLAND_DISPLAY")),
        "x11_session_hint": bool(os.environ.get("DISPLAY")),
    }
    score = _score_from_checks(checks, penalty=15 if system == "linux" else 35)
    return _group(
        "linux_control",
        summary="Linux desktop support is planned around X11/Wayland-specific adapters.",
        checks=checks,
        status="attention" if system == "linux" else "blocked",
        score=score,
        signals=["Linux desktop session hints detected"] if system == "linux" else [],
        risks=["Linux adapter remains partial until X11 and Wayland paths are implemented and tested"],
        permissions=["compositor-specific automation permission"],
        next_actions=["Implement separate X11 and Wayland controller adapters instead of assuming one Linux desktop model."],
    )


def _safety_group() -> dict[str, Any]:
    flags = []
    enabled_count = 0
    for key, reason in SAFETY_FLAGS.items():
        enabled = _truthy(os.environ.get(key))
        enabled_count += int(enabled)
        flags.append({"key": key, "enabled": enabled, "reason": reason})
    risks = [f"{row['key']} is enabled ({row['reason']})" for row in flags if row["enabled"]]
    checks = {
        "automation_preview_layer": _file_available("core", "automation", "layer.py"),
        "security_model": _file_available("core", "security", "model.py"),
        "dangerous_flags_disabled": enabled_count == 0,
    }
    return _group(
        "safety",
        summary="Computer control is designed as observe, preview, confirm, execute, and verify.",
        checks=checks,
        status="ready" if not risks else "attention",
        score=95 if not risks else max(55, 95 - (enabled_count * 9)),
        signals=["high-impact actions remain policy-gated", "environment values are redacted to boolean flag states"],
        risks=risks,
        permissions=["explicit user approval for irreversible, credential, financial, external-send, and destructive actions"],
        next_actions=["Add an always-visible automation audit timeline before enabling long-running desktop agents."],
        metadata={
            "flags": flags,
            "policy": {
                "default_mode": "observe_then_confirm",
                "observation_actions": list(OBSERVATION_ACTIONS),
                "direct_control_actions": list(DIRECT_CONTROL_ACTIONS),
                "high_impact_actions": list(HIGH_IMPACT_ACTIONS),
            },
        },
    )


def _desktop_agent_loop_group() -> dict[str, Any]:
    checks = {
        "desktop_agent_loop": _file_available("core", "computer_control", "agent_loop.py"),
        "automation_preview_layer": _file_available("core", "automation", "layer.py"),
        "vision_operating_layer": _file_available("core", "vision", "screen.py"),
        "execution_gateway": _file_available("shell_tool_gateway.py"),
        "status_tools": _file_available("shell_computer_control.py"),
    }
    return _group(
        "desktop_agent_loop",
        summary="Desktop Agent can observe, preview, require confirmation, dry-run, execute one step, and request verification.",
        checks=checks,
        status="ready" if all(checks.values()) else "attention",
        score=_score_from_checks(checks),
        signals=["observe-preview-confirm-execute-verify loop is available"],
        risks=["execution is intentionally one-step-at-a-time and approval-gated"],
        permissions=["explicit approval before any non-dry-run desktop action"],
        next_actions=["Add a visible automation audit timeline and post-step screenshot comparison UI."],
    )


def _catalog_matches() -> dict[str, Any]:
    try:
        from shell_tool_catalog import discover_capabilities

        catalog = discover_capabilities().get("catalog", [])
    except Exception as exc:
        return {"available": False, "error": type(exc).__name__, "matches": []}
    tokens = ("desktop", "window", "screenshot", "screen", "clipboard", "windows-mcp", "mouse", "keyboard")
    matches = [
        {
            "id": str(row.get("id") or ""),
            "kind": str(row.get("kind") or ""),
            "category": str(row.get("category") or ""),
            "risk": str(row.get("risk") or ""),
        }
        for row in catalog
        if any(token in str(row.get("id") or "").lower() for token in tokens)
    ]
    return {"available": True, "count": len(matches), "matches": matches[:40]}


def build_computer_control_snapshot(*, include_catalog: bool = True) -> dict[str, Any]:
    """Return a redacted, read-only desktop-control readiness snapshot."""
    started = time.perf_counter()
    system = _platform_key()
    groups = [
        _app_control_group(system),
        _input_control_group(system),
        _screen_understanding_group(system),
        _clipboard_group(system),
        _windows_mcp_group(system),
        _macos_group(system),
        _linux_group(system),
        _desktop_agent_loop_group(),
        _safety_group(),
    ]
    weighted_groups = [group for group in groups if group["name"] not in {"macos_control", "linux_control", "windows_mcp"} or system in group["name"]]
    score = round(sum(int(group["score"]) for group in weighted_groups) / max(1, len(weighted_groups)))
    risks = []
    signals = []
    next_actions = []
    for group in groups:
        risks.extend(f"{group['name']}: {item}" for item in group.get("risks", [])[:3])
        signals.extend(group.get("signals", [])[:2])
        next_actions.extend(group.get("next_actions", [])[:1])
    snapshot = {
        "profile": "computer_control_os",
        "generated_at": time.time(),
        "status": _status(score),
        "score": int(score),
        "platform": system,
        "platform_release": platform.release(),
        "control_policy": {
            "default_mode": "observe_then_confirm",
            "requires_confirmation": list(DIRECT_CONTROL_ACTIONS),
            "always_high_impact": list(HIGH_IMPACT_ACTIONS),
            "safe_observation": list(OBSERVATION_ACTIONS),
            "silent_fallback_allowed": False,
        },
        "groups": groups,
        "signals": signals[:12],
        "risks": risks[:12],
        "next_actions": next_actions[:10],
        "catalog": _catalog_matches() if include_catalog else {"available": False, "skipped": True},
        "snapshot_ms": round((time.perf_counter() - started) * 1000.0, 3),
    }
    return snapshot
