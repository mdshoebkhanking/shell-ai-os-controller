from __future__ import annotations

import logging
import os
import sys
from typing import Any


BACKEND_CLASSIC = "classic"
BACKEND_SHELLAI_CORE = "shellai_core"
BACKEND_ENV_VAR = "SHELLAI_BACKEND_MODE"

logger = logging.getLogger("shellai.desktop_bridge")


def backend_mode() -> str:
    mode = os.environ.get(BACKEND_ENV_VAR, BACKEND_CLASSIC)
    normalized = str(mode or BACKEND_CLASSIC).strip().lower()
    return normalized or BACKEND_CLASSIC


def shellai_core_enabled() -> bool:
    return backend_mode() == BACKEND_SHELLAI_CORE


def build_desktop_context(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    context = {
        "source": "desktop_shell",
        "cwd": os.getcwd(),
        "platform": sys.platform,
    }
    context.update(dict(extra or {}))
    context.setdefault("source", "desktop_shell")
    context.setdefault("cwd", os.getcwd())
    context.setdefault("platform", sys.platform)
    return context


def handle_user_request(
    text: str,
    context: dict[str, Any] | None = None,
    *,
    auto_approve_ask: bool = False,
) -> dict[str, Any] | None:
    """Handle a desktop request through ShellAI Core when the flag is enabled.

    Returning None means the caller should continue with the existing classic
    desktop path. This keeps the feature flag non-invasive.
    """
    if not shellai_core_enabled():
        return None

    from shellai.api import run_shellai_task

    result = run_shellai_task(
        text,
        context=build_desktop_context(context),
        auto_approve_ask=auto_approve_ask,
    )
    log_shellai_result(result)
    return result


def format_shellai_reply(result: dict[str, Any] | None) -> str:
    if not isinstance(result, dict):
        return "ShellAI Core did not return a structured response."

    status = str(result.get("status") or "")
    if status == "blocked":
        message = result.get("summary") or "Command blocked by ShellAI safety policy."
        return f"Blocked for safety: {message}"
    if status == "needs_confirmation":
        message = result.get("summary") or "This command needs explicit approval before running."
        return f"Approval required: {message}"

    if result.get("ok") is False or status == "error":
        error = result.get("error") if isinstance(result.get("error"), dict) else {}
        message = error.get("message") or result.get("summary") or "ShellAI Core request failed."
        return f"ShellAI Core error: {message}"

    summary = result.get("summary") or result.get("message")
    if summary:
        return str(summary)

    steps = result.get("steps") if isinstance(result.get("steps"), list) else []
    if steps:
        statuses = ", ".join(
            f"{step.get('tool', 'tool')}={step.get('status', 'unknown')}"
            for step in steps[:5]
        )
        return f"ShellAI Core completed the request. Steps: {statuses}."
    return "ShellAI Core completed the request."


def log_shellai_result(result: dict[str, Any] | None) -> None:
    if not isinstance(result, dict):
        logger.warning("ShellAI Core returned non-dict result: %r", result)
        return
    logger.info(
        "ShellAI Core result status=%s trace_id=%s",
        result.get("status"),
        result.get("trace_id"),
    )
    for step in result.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        command = ""
        metadata = step.get("metadata")
        if isinstance(metadata, dict):
            command = str(metadata.get("command") or "")
        logger.info(
            "ShellAI Core step tool=%s status=%s description=%s command=%s",
            step.get("tool"),
            step.get("status"),
            step.get("description"),
            command,
        )


__all__ = [
    "BACKEND_CLASSIC",
    "BACKEND_ENV_VAR",
    "BACKEND_SHELLAI_CORE",
    "backend_mode",
    "build_desktop_context",
    "format_shellai_reply",
    "handle_user_request",
    "log_shellai_result",
    "shellai_core_enabled",
]
