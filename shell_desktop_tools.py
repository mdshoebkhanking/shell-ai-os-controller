from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import webbrowser

from shell_safe_executor import god_tier_tool as function_tool


def _system() -> str:
    return platform.system().lower()


def _normalize_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    if "://" not in raw and not raw.startswith(("mailto:", "tel:")):
        raw = "https://" + raw
    return raw


def _applescript_string(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


async def _run(argv: list[str], timeout_s: float = 8.0) -> tuple[int, str]:
    def _call() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout_s,
        )

    try:
        proc = await asyncio.to_thread(_call)
        return proc.returncode, (proc.stdout or "").strip()
    except subprocess.TimeoutExpired:
        return 124, f"Timed out after {timeout_s}s"
    except FileNotFoundError:
        return 127, f"Missing executable: {argv[0]}"


@function_tool(category="system")
async def open_url_tool(url: str) -> str:
    """Open a URL with the current platform's default browser."""
    target = _normalize_url(url)
    if not target:
        return "Error: URL is empty."
    system = _system()
    if system == "darwin":
        code, output = await _run(["open", target])
        return f"Opened URL on macOS: {target}" if code == 0 else f"Could not open URL on macOS: {target}\n{output}"
    if system == "windows":
        code, output = await _run(["cmd", "/c", "start", "", target])
        return f"Opened URL on Windows: {target}" if code == 0 else f"Could not open URL on Windows: {target}\n{output}"
    if shutil.which("xdg-open"):
        code, output = await _run(["xdg-open", target])
        return f"Opened URL on Linux: {target}" if code == 0 else f"Could not open URL on Linux: {target}\n{output}"
    ok = await asyncio.to_thread(webbrowser.open, target)
    return f"Opened URL: {target}" if ok else f"Could not open URL: {target}"


@function_tool(category="system")
async def desktop_click_tool(x: int, y: int, button: str = "left") -> str:
    """Click a screen coordinate using the best available local automation backend."""
    btn = str(button or "left").lower().strip()
    system = _system()
    if system == "darwin" and shutil.which("cliclick"):
        code, output = await _run(["cliclick", f"c:{int(x)},{int(y)}"])
        if code == 0:
            return f"Clicked at ({int(x)},{int(y)}) on macOS via cliclick."
        if "Accessibility" in output or "privileges" in output:
            return "Click blocked by macOS Accessibility permission. Enable Accessibility for Terminal/Python/Codex."
        return f"Click failed on macOS:\n{output}"
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        await asyncio.to_thread(pyautogui.click, int(x), int(y), button=btn)
        return f"Clicked at ({int(x)},{int(y)}) via pyautogui."
    except Exception as exc:
        return f"Click unavailable: {exc}"


@function_tool(category="system")
async def desktop_type_tool(text: str, clear: bool = False) -> str:
    """Type text into the active window using local desktop automation."""
    value = str(text or "")
    if not value:
        return "Error: Text is empty."
    system = _system()
    if system == "darwin" and shutil.which("osascript"):
        script = ""
        if clear:
            script += 'tell application "System Events" to keystroke "a" using command down\n'
        script += f'tell application "System Events" to keystroke {_applescript_string(value)}'
        code, output = await _run(["osascript", "-e", script])
        if code == 0:
            return "Typed text on macOS via System Events."
        return "Type blocked or failed on macOS. Enable Accessibility for Terminal/Python/Codex.\n" + output
    try:
        import pyautogui
        if clear:
            await asyncio.to_thread(pyautogui.hotkey, "ctrl", "a")
        await asyncio.to_thread(pyautogui.write, value, interval=0.001)
        return "Typed text via pyautogui."
    except Exception as exc:
        return f"Typing unavailable: {exc}"


@function_tool(category="system")
async def desktop_shortcut_tool(keys: str) -> str:
    """Press a keyboard shortcut such as command+space, ctrl+c, or enter."""
    raw = str(keys or "").strip()
    if not raw:
        return "Error: Shortcut keys are empty."
    parts = [p.strip().lower() for p in raw.replace("-", "+").split("+") if p.strip()]
    if not parts:
        return "Error: Shortcut keys are empty."
    system = _system()
    if system == "darwin" and shutil.which("osascript"):
        key = parts[-1]
        modifiers = []
        modifier_map = {
            "cmd": "command down",
            "command": "command down",
            "ctrl": "control down",
            "control": "control down",
            "alt": "option down",
            "option": "option down",
            "shift": "shift down",
        }
        for part in parts[:-1]:
            mapped = modifier_map.get(part)
            if mapped:
                modifiers.append(mapped)
        mod_clause = f" using {{{', '.join(modifiers)}}}" if modifiers else ""
        special = {
            "enter": 36,
            "return": 36,
            "tab": 48,
            "esc": 53,
            "escape": 53,
            "space": 49,
            "delete": 51,
            "backspace": 51,
        }
        if key in special:
            script = f'tell application "System Events" to key code {special[key]}{mod_clause}'
        else:
            script = f'tell application "System Events" to keystroke {_applescript_string(key)}{mod_clause}'
        code, output = await _run(["osascript", "-e", script])
        if code == 0:
            return f"Pressed shortcut on macOS: {raw}"
        return "Shortcut blocked or failed on macOS. Enable Accessibility for Terminal/Python/Codex.\n" + output
    try:
        import pyautogui
        await asyncio.to_thread(pyautogui.hotkey, *parts)
        return f"Pressed shortcut via pyautogui: {raw}"
    except Exception as exc:
        return f"Shortcut unavailable: {exc}"
