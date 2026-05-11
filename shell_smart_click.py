"""shell_smart_click — deterministic UI clicking for Shell.

Three new tools the agent can call from text-chat or voice:

    find_window_geometry_tool(title_substring)
        → returns dict {found, title, left, top, width, height}.
        The LLM can use these coordinates to compute exactly where to click.

    click_in_window_tool(title_substring, anchor, dx, dy)
        → finds the window, computes (x, y) from anchor + offsets, clicks.
        Anchors: "center", "top-left", "top-right", "bottom-left",
                 "bottom-right", "top-center", "bottom-center",
                 "left-center", "right-center", "chat-input"
        dx, dy are pixel offsets from the anchor (positive = right/down).

    click_text_on_screen_tool(text, window_title)
        → screenshots, OCR/Vision-locates the text, clicks its centre.
        Optionally constrained to a single window so multi-window false
        positives don't fire.

Why these matter
----------------
Existing Shell tools either click at raw screen coordinates (fragile —
breaks on different resolutions / DPI) or rely on slow Gemini Vision
calls. These three are FAST, deterministic, and resolution-aware:
they ground every click in a real window's geometry. This is exactly
how a human would think — "click the search box in the Notepad window"
rather than "click pixel (847, 1031)".
"""
from __future__ import annotations

import logging
import re
from typing import Optional

try:
    # Use the project's wrapped function_tool — it adds tool_event
    # telemetry, error tracking, and circuit-breaker plumbing so the
    # UI sees these clicks in the live tool feed.
    from shell_safe_executor import god_tier_tool as function_tool
except Exception:
    from livekit.agents import function_tool

logger = logging.getLogger("shell_smart_click")

try:
    import pygetwindow as gw
    _GW_OK = True
except Exception as _e:  # pragma: no cover
    logger.warning("pygetwindow unavailable: %s", _e)
    _GW_OK = False

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    _PG_OK = True
except Exception as _e:  # pragma: no cover
    logger.warning("pyautogui unavailable: %s", _e)
    _PG_OK = False


# ---------------------------------------------------------------------------
# Window finding
# ---------------------------------------------------------------------------
def _find_window(title_substring: str):
    """Return the first visible window whose title contains the substring.

    Case-insensitive, ignores empty titles. Returns the pygetwindow
    Window object or None.
    """
    if not _GW_OK or not title_substring:
        return None
    needle = title_substring.lower().strip()
    matches = []
    try:
        for w in gw.getAllWindows():
            t = (getattr(w, "title", "") or "").strip()
            if not t:
                continue
            if needle in t.lower() and (w.width > 50 and w.height > 50):
                matches.append(w)
    except Exception as e:
        logger.warning("getAllWindows failed: %s", e)
        return None
    if not matches:
        return None
    # Prefer non-minimised, larger windows
    matches.sort(key=lambda w: (
        0 if not getattr(w, "isMinimized", False) else 1,
        -w.width * w.height,
    ))
    return matches[0]


def _anchor_xy(win, anchor: str, dx: int, dy: int):
    """Compute absolute (x, y) screen coords from a window-relative anchor."""
    L, T, W, H = win.left, win.top, win.width, win.height
    a = (anchor or "center").lower().strip().replace("_", "-")
    if a in ("center", "centre", "middle"):
        x, y = L + W // 2, T + H // 2
    elif a == "top-left":
        x, y = L, T
    elif a == "top-right":
        x, y = L + W, T
    elif a == "bottom-left":
        x, y = L, T + H
    elif a == "bottom-right":
        x, y = L + W, T + H
    elif a == "top-center" or a == "top":
        x, y = L + W // 2, T
    elif a == "bottom-center" or a == "bottom":
        x, y = L + W // 2, T + H
    elif a == "left-center" or a == "left":
        x, y = L, T + H // 2
    elif a == "right-center" or a == "right":
        x, y = L + W, T + H // 2
    elif a == "chat-input":
        # Common pattern: sidebar on the left (~200px), input row at
        # the bottom (~60px above the window edge).
        x, y = L + 200 + (W - 200) // 2, T + H - 60
    else:
        x, y = L + W // 2, T + H // 2
    return x + int(dx or 0), y + int(dy or 0)


# ---------------------------------------------------------------------------
# Tool 1 — find_window_geometry
# ---------------------------------------------------------------------------
@function_tool
async def find_window_geometry_tool(title_substring: str) -> str:
    """
    🔎 Find a window by title substring and return its geometry.

    The LLM can use the returned (left, top, width, height) to compute
    exact click positions inside that window — same way a human reasons
    about UI ("click 100px from the right edge of the title bar").

    Args:
        title_substring: Any substring of the window title, case-insensitive.
                         Examples: "Notepad", "Chrome", "Shell OS", "Calculator".

    Returns:
        A short status string with the window's geometry, or "not found".
    """
    win = _find_window(title_substring)
    if not win:
        return f"❌ Window not found: '{title_substring}'"
    return (
        f"✅ Window: {win.title!r}  "
        f"left={win.left}  top={win.top}  "
        f"width={win.width}  height={win.height}  "
        f"(center=({win.left + win.width // 2}, {win.top + win.height // 2}))"
    )


# ---------------------------------------------------------------------------
# Tool 2 — click_in_window
# ---------------------------------------------------------------------------
@function_tool
async def click_in_window_tool(
    title_substring: str,
    anchor: str = "center",
    dx: int = 0,
    dy: int = 0,
    button: str = "left",
    activate: bool = True,
) -> str:
    """
    🎯 Deterministic click inside a named window — no vision, no OCR.

    This is how humans think about UI: 'click roughly in the centre of
    Notepad' or '20px below the top-right of Chrome's title bar'. The
    tool finds the window by title, computes pixel coordinates from the
    anchor + offset, and clicks. Works at any screen resolution / DPI.

    Args:
        title_substring: Substring of the target window's title.
        anchor: Reference point inside the window. Choices —
            "center" (default), "top-left", "top-right", "bottom-left",
            "bottom-right", "top-center", "bottom-center",
            "left-center", "right-center", "chat-input".
        dx, dy: Pixel offset from the anchor (positive = right / down).
        button: "left" (default), "right", "middle".
        activate: If True, brings the window to the foreground first.

    Examples:
        - "Click the centre of the Notepad window"
            → click_in_window_tool("Notepad", "center")
        - "Click 50px below the top-right of Chrome"
            → click_in_window_tool("Chrome", "top-right", dx=-30, dy=50)
        - "Click Shell OS's chat input box"
            → click_in_window_tool("Shell OS", "chat-input")
    """
    if not _PG_OK:
        return "❌ pyautogui unavailable on this machine."
    win = _find_window(title_substring)
    if not win:
        return f"❌ Window not found: '{title_substring}'"
    if activate:
        try:
            win.activate()
            import time as _t
            _t.sleep(0.4)
        except Exception as _e:
            logger.debug("activate failed (continuing): %s", _e)
    try:
        x, y = _anchor_xy(win, anchor, dx, dy)
        pyautogui.click(x, y, button=button)
        return (
            f"✅ Clicked {button} at ({x},{y}) — "
            f"window={win.title!r} anchor={anchor} dx={dx} dy={dy}"
        )
    except Exception as e:
        return f"❌ Click failed: {e}"


# ---------------------------------------------------------------------------
# Tool 3 — click_text_on_screen
# ---------------------------------------------------------------------------
@function_tool
async def click_text_on_screen_tool(
    text: str,
    window_title: str = "",
    button: str = "left",
) -> str:
    """
    🔤 Find text on screen via OCR/Vision and click its centre.

    Uses the project's vision engine which prefers Tesseract OCR (fast)
    and falls back to Gemini Vision (slower, works without OCR install).
    Optionally constrains the search to a single named window so the
    same word in another window doesn't get hit.

    Args:
        text: Visible text to locate (case-insensitive substring).
        window_title: Optional — only click if the match falls inside
                      this window's bounding box.
        button: "left" (default), "right", "middle".

    Examples:
        - "Click the 'Send' button"
            → click_text_on_screen_tool("Send")
        - "Click 'File' menu in Notepad"
            → click_text_on_screen_tool("File", window_title="Notepad")
    """
    if not _PG_OK:
        return "❌ pyautogui unavailable on this machine."
    try:
        from vision_engine import vision_engine
    except Exception as e:
        return f"❌ vision engine unavailable: {e}"

    pos = vision_engine.vision_click(text)
    if not pos:
        return f"❌ Text not found on screen: {text!r}"

    x, y = pos
    if window_title:
        win = _find_window(window_title)
        if not win:
            return f"❌ Window '{window_title}' not found (text was at {pos})."
        if not (win.left <= x <= win.left + win.width
                and win.top <= y <= win.top + win.height):
            return (
                f"❌ Text {text!r} found at {pos} but outside window "
                f"{win.title!r} ({win.left},{win.top},{win.width},{win.height})."
            )
        try:
            win.activate()
            import time as _t
            _t.sleep(0.3)
        except Exception:
            pass

    try:
        pyautogui.click(x, y, button=button)
        return f"✅ Clicked {button} on text {text!r} at ({x},{y})"
    except Exception as e:
        return f"❌ Click failed: {e}"


# ---------------------------------------------------------------------------
# Bulk export
# ---------------------------------------------------------------------------
SMART_CLICK_TOOLS = [
    find_window_geometry_tool,
    click_in_window_tool,
    click_text_on_screen_tool,
]
