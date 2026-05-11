"""
shell_whatsapp.py — unified public surface for WhatsApp tools
==============================================================

Historically, WhatsApp automation was split across 5 files with significant
duplication (~2,600 lines total):

 * `shell_whatsapp_CTRL.py`        — desktop app send (PyAutoGUI)
 * `shell_whatsapp_ULTRA.py`       — bulk + media (PyAutoGUI)
 * `shell_whatsapp_auto_reply.py`  — AI auto-reply loop (multi-provider)
 * `shell_whatsapp_monitor.py`     — lightweight monitor
 * `shell_whatsapp_web_real.py`    — Selenium WhatsApp Web backend

This module is the ONE import point for the whole stack. Internally it
re-exports from the existing backend files (unchanged) so behavior is
preserved. Over time the backend files will be reduced to thin shims
pointing back here, but for now we keep them working.

Consumers (agent.py, tests, docs) should import from `shell_whatsapp`:

    from shell_whatsapp import (
        send_whatsapp_message, send_whatsapp_bulk, send_whatsapp_media,
        check_whatsapp_and_reply, start_auto_reply, stop_auto_reply,
        ...
    )

Backends: two transport strategies are exposed.

 * Desktop (PyAutoGUI + OCR): primary path, fast but fragile on UI updates
 * Web (Selenium): slower but more deterministic (DOM selectors)

The `describe_backends()` helper returns the active status of each so a
caller can decide which send path to use at runtime.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("shell_whatsapp")


# ─────────────────────────────────────────────────────────────────────
# Backend imports — tolerate missing optional deps so this module still
# loads when (for example) selenium is not installed. Each backend's
# availability flag is published via `describe_backends()`.
# ─────────────────────────────────────────────────────────────────────

_DESKTOP_OK = True
_WEB_OK = True
_AUTO_REPLY_OK = True
_MONITOR_OK = True
_load_errors: dict[str, str] = {}


# ── Desktop: send ────────────────────────────────────────────────────
try:
    from shell_whatsapp_CTRL import send_whatsapp_message
except Exception as e:
    _DESKTOP_OK = False
    _load_errors["CTRL"] = repr(e)
    logger.debug("shell_whatsapp_CTRL unavailable: %s", e)

    async def send_whatsapp_message(recipient: str, message: str) -> str:  # type: ignore[misc]
        return f"⚠️ Desktop backend unavailable ({_load_errors.get('CTRL', 'unknown')})."


# ── Desktop: bulk + media + status ──────────────────────────────────
try:
    from shell_whatsapp_ULTRA import (
        send_whatsapp_bulk,
        send_whatsapp_media,
    )
    # check_whatsapp_running_tool may or may not be decorated; import defensively
    try:
        from shell_whatsapp_ULTRA import check_whatsapp_running_tool
    except Exception:
        check_whatsapp_running_tool = None
except Exception as e:
    _DESKTOP_OK = False
    _load_errors["ULTRA"] = repr(e)
    logger.debug("shell_whatsapp_ULTRA unavailable: %s", e)

    async def send_whatsapp_bulk(contacts: list[str], message: str) -> str:  # type: ignore[misc]
        return f"⚠️ Bulk send unavailable ({_load_errors.get('ULTRA', 'unknown')})."

    async def send_whatsapp_media(recipient: str, file_path: str, caption: str = "") -> str:  # type: ignore[misc]
        return f"⚠️ Media send unavailable ({_load_errors.get('ULTRA', 'unknown')})."

    check_whatsapp_running_tool = None  # type: ignore[assignment]


# ── AI auto-reply + log + contact memory ────────────────────────────
try:
    from shell_whatsapp_auto_reply import (
        check_whatsapp_and_reply,
        check_whatsapp_messages,
        start_auto_reply,
        stop_auto_reply,
        auto_reply_status,
        whatsapp_reply_log,
        whatsapp_contact_memory,
    )
except Exception as e:
    _AUTO_REPLY_OK = False
    _load_errors["auto_reply"] = repr(e)
    logger.debug("shell_whatsapp_auto_reply unavailable: %s", e)

    async def check_whatsapp_and_reply() -> str:  # type: ignore[misc]
        return f"⚠️ Auto-reply unavailable ({_load_errors.get('auto_reply', 'unknown')})."

    async def check_whatsapp_messages() -> str:  # type: ignore[misc]
        return f"⚠️ Message read unavailable ({_load_errors.get('auto_reply', 'unknown')})."

    async def start_auto_reply() -> str:  # type: ignore[misc]
        return f"⚠️ Auto-reply unavailable ({_load_errors.get('auto_reply', 'unknown')})."

    async def stop_auto_reply() -> str:  # type: ignore[misc]
        return f"⚠️ Auto-reply unavailable ({_load_errors.get('auto_reply', 'unknown')})."

    async def auto_reply_status() -> str:  # type: ignore[misc]
        return "auto-reply: unavailable"

    async def whatsapp_reply_log(filter: str = "") -> str:  # type: ignore[misc]
        return "[]"

    async def whatsapp_contact_memory() -> str:  # type: ignore[misc]
        return "{}"


# ── Monitor loop ────────────────────────────────────────────────────
try:
    from shell_whatsapp_monitor import (
        start_whatsapp_monitor,
        stop_whatsapp_monitor,
        whatsapp_monitor_status,
        set_whatsapp_contact_name,
    )
except Exception as e:
    _MONITOR_OK = False
    _load_errors["monitor"] = repr(e)
    logger.debug("shell_whatsapp_monitor unavailable: %s", e)

    async def start_whatsapp_monitor(your_name: str = "Me") -> str:  # type: ignore[misc]
        return f"⚠️ Monitor unavailable ({_load_errors.get('monitor', 'unknown')})."

    async def stop_whatsapp_monitor() -> str:  # type: ignore[misc]
        return f"⚠️ Monitor unavailable ({_load_errors.get('monitor', 'unknown')})."

    async def whatsapp_monitor_status() -> str:  # type: ignore[misc]
        return "monitor: unavailable"

    async def set_whatsapp_contact_name(name: str) -> str:  # type: ignore[misc]
        return f"⚠️ Monitor unavailable ({_load_errors.get('monitor', 'unknown')})."


# ── Web (Selenium) backend ──────────────────────────────────────────
try:
    from shell_whatsapp_web_real import (
        link_whatsapp_device,
        whatsapp_web_send,
        whatsapp_web_check,
    )
except Exception as e:
    _WEB_OK = False
    _load_errors["web_real"] = repr(e)
    logger.debug("shell_whatsapp_web_real unavailable: %s", e)

    async def link_whatsapp_device() -> str:  # type: ignore[misc]
        return f"⚠️ Web backend unavailable ({_load_errors.get('web_real', 'unknown')})."

    async def whatsapp_web_send(contact: str, message: str) -> str:  # type: ignore[misc]
        return f"⚠️ Web backend unavailable ({_load_errors.get('web_real', 'unknown')})."

    async def whatsapp_web_check() -> str:  # type: ignore[misc]
        return f"⚠️ Web backend unavailable ({_load_errors.get('web_real', 'unknown')})."


# ─────────────────────────────────────────────────────────────────────
# Convenience surface
# ─────────────────────────────────────────────────────────────────────

def describe_backends() -> dict[str, Any]:
    """Return the active status of each backend. Useful for /health tools."""
    return {
        "desktop": {
            "ok": _DESKTOP_OK,
            "transport": "pyautogui + window focus",
            "error": _load_errors.get("CTRL") or _load_errors.get("ULTRA"),
        },
        "auto_reply": {
            "ok": _AUTO_REPLY_OK,
            "transport": "desktop + multi-provider AI",
            "error": _load_errors.get("auto_reply"),
        },
        "monitor": {
            "ok": _MONITOR_OK,
            "transport": "desktop + vision",
            "error": _load_errors.get("monitor"),
        },
        "web": {
            "ok": _WEB_OK,
            "transport": "selenium webdriver",
            "error": _load_errors.get("web_real"),
        },
    }


# Explicit public surface — mirrors the 17 tools agent.py used to import
# from five different files. Anything else internal can stay in the
# legacy modules; nothing in this list should be renamed without
# updating agent.py's tools_list.
TOOL_NAMES: tuple[str, ...] = (
    # Desktop send
    "send_whatsapp_message",
    "send_whatsapp_bulk",
    "send_whatsapp_media",
    # Auto-reply
    "check_whatsapp_and_reply",
    "check_whatsapp_messages",
    "start_auto_reply",
    "stop_auto_reply",
    "auto_reply_status",
    "whatsapp_reply_log",
    "whatsapp_contact_memory",
    # Monitor
    "start_whatsapp_monitor",
    "stop_whatsapp_monitor",
    "whatsapp_monitor_status",
    "set_whatsapp_contact_name",
    # Web (Selenium)
    "link_whatsapp_device",
    "whatsapp_web_send",
    "whatsapp_web_check",
)


__all__ = list(TOOL_NAMES) + ["describe_backends", "TOOL_NAMES"]
