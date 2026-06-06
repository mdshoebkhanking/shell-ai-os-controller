"""
Shell Clipboard Tools v1.0
----------------------------
Clipboard manipulation tools for Shell AI.
Copy, paste, clear, and track clipboard history.

Uses pyperclip with Windows subprocess fallback.

Usage:
    from shell_safe_executor import god_tier_tool as function_tool
"""

import os
import sys
import subprocess
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_clipboard")

# In-memory clipboard history (last 20 entries)
_clipboard_history: list = []
_MAX_HISTORY = 20


def _copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using best available method."""
    if sys.platform == "win32":
        # Prefer native Windows clipboard plumbing over pyperclip. It avoids
        # backend-selection issues on fresh installs and RDP sessions.
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Set-Clipboard -Value ([Console]::In.ReadToEnd())",
                ],
                input=text,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
        except Exception as e:
            logger.debug("PowerShell Set-Clipboard failed: %s", e)

        try:
            result = subprocess.run(
                "clip",
                input=text,
                capture_output=True,
                text=True,
                shell=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
        except Exception as e:
            logger.debug("clip command failed: %s", e)

        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32

            user32.OpenClipboard(0)
            user32.EmptyClipboard()

            CF_UNICODETEXT = 13
            data = text.encode("utf-16le") + b"\x00\x00"
            h_mem = kernel32.GlobalAlloc(0x0042, len(data))
            p_mem = kernel32.GlobalLock(h_mem)
            ctypes.memmove(p_mem, data, len(data))
            kernel32.GlobalUnlock(h_mem)
            user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            user32.CloseClipboard()
            return True
        except Exception as e:
            logger.debug("ctypes clipboard copy failed: %s", e)

    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except ImportError as _e:
        logger.debug("ignored ImportError: %s", _e)
    except Exception as e:
        logger.debug("pyperclip copy failed: %s", e)

    return False


def _read_from_clipboard() -> str:
    """Read text from clipboard using best available method."""
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.rstrip("\r\n")
        except Exception as e:
            logger.debug("PowerShell Get-Clipboard failed: %s", e)

        try:
            import ctypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            user32.OpenClipboard(0)
            CF_UNICODETEXT = 13
            h_data = user32.GetClipboardData(CF_UNICODETEXT)
            if h_data:
                p_data = kernel32.GlobalLock(h_data)
                text = ctypes.wstring_at(p_data)
                kernel32.GlobalUnlock(h_data)
                user32.CloseClipboard()
                return text
            user32.CloseClipboard()
            return ""
        except Exception as e:
            logger.debug("ctypes clipboard read failed: %s", e)

    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError as _e:
        logger.debug("ignored ImportError: %s", _e)
    except Exception as e:
        logger.debug("pyperclip paste failed: %s", e)

    return ""


def _add_to_history(text: str):
    """Add a clipboard entry to history."""
    global _clipboard_history
    if text and text.strip():
        # Avoid duplicates of the last entry
        if not _clipboard_history or _clipboard_history[-1] != text:
            _clipboard_history.append(text)
            if len(_clipboard_history) > _MAX_HISTORY:
                _clipboard_history = _clipboard_history[-_MAX_HISTORY:]


# ================================================================
#  TOOL 1: COPY TO CLIPBOARD
# ================================================================

@function_tool
async def clipboard_copy_tool(text: str) -> str:
    """
    Copy text to the system clipboard.
    Args:
        text: The text to copy to clipboard.
    """
    if not text:
        return "Error: No text provided to copy."

    success = _copy_to_clipboard(text)
    if success:
        _add_to_history(text)
        preview = text[:100] + "..." if len(text) > 100 else text
        return (
            f"Successfully copied to clipboard.\n"
            f"  Length: {len(text)} characters\n"
            f"  Preview: {preview}"
        )
    else:
        return (
            "Error: Could not copy to clipboard. "
            "Install pyperclip (pip install pyperclip) for best results."
        )


# ================================================================
#  TOOL 2: PASTE FROM CLIPBOARD
# ================================================================

@function_tool
async def clipboard_paste_tool() -> str:
    """
    Read and return the current contents of the system clipboard.
    """
    text = _read_from_clipboard()

    if text:
        _add_to_history(text)
        return (
            f"Clipboard contents ({len(text)} characters):\n"
            f"{text}"
        )
    else:
        return "Clipboard is empty or could not be read."


# ================================================================
#  TOOL 3: CLEAR CLIPBOARD
# ================================================================

@function_tool
async def clipboard_clear_tool() -> str:
    """
    Clear the system clipboard contents.
    """
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $null"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return "Clipboard cleared successfully."
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)

        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.OpenClipboard(0)
            user32.EmptyClipboard()
            user32.CloseClipboard()
            return "Clipboard cleared successfully."
        except Exception as e:
            logger.debug("ctypes clipboard clear failed: %s", e)

    try:
        import pyperclip
        pyperclip.copy("")
        return "Clipboard cleared successfully."
    except ImportError as _e:
        logger.debug("ignored ImportError: %s", _e)
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)
    return (
        "Error: Could not clear clipboard. "
        "Install pyperclip (pip install pyperclip) for best results."
    )


# ================================================================
#  TOOL 4: CLIPBOARD HISTORY
# ================================================================

@function_tool
async def clipboard_history_tool() -> str:
    """
    Show the clipboard history (last 20 entries tracked in this session).
    History is stored in-memory and resets when the application restarts.
    """
    if not _clipboard_history:
        return (
            "Clipboard history is empty.\n"
            "History is tracked from copy/paste operations during this session."
        )

    lines = [
        f"Clipboard History ({len(_clipboard_history)} entries):",
        "=" * 40,
    ]

    for i, entry in enumerate(reversed(_clipboard_history), 1):
        preview = entry[:80].replace("\n", " ")
        if len(entry) > 80:
            preview += "..."
        lines.append(f"  {i}. [{len(entry)} chars] {preview}")

    return "\n".join(lines)
