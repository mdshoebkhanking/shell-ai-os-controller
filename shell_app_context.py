from __future__ import annotations

import json
import platform
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ActiveWindowInfo:
    app_name: str = ""
    title: str = ""
    process_name: str = ""
    url: str = ""
    selected_text: str = ""
    clipboard_text: str = ""


class AppContextAdapter(Protocol):
    name: str

    def can_handle(self, window: ActiveWindowInfo) -> bool:
        ...

    def get_context(self, window: ActiveWindowInfo) -> dict[str, Any]:
        ...


def _run_text(command: list[str], timeout: float = 2.5) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return (completed.stdout or "").strip()
    except Exception:
        return ""


def _active_window_macos() -> ActiveWindowInfo:
    script = """
    tell application "System Events"
      set frontApp to first application process whose frontmost is true
      set appName to name of frontApp
      set windowTitle to ""
      try
        set windowTitle to name of front window of frontApp
      end try
      return appName & "\n" & windowTitle
    end tell
    """
    lines = _run_text(["osascript", "-e", script]).splitlines()
    app_name = lines[0].strip() if lines else ""
    title = lines[1].strip() if len(lines) > 1 else ""
    url = ""
    if app_name.lower() in {"google chrome", "microsoft edge", "safari"}:
        browser_script = {
            "google chrome": 'tell application "Google Chrome" to return URL of active tab of front window',
            "microsoft edge": 'tell application "Microsoft Edge" to return URL of active tab of front window',
            "safari": 'tell application "Safari" to return URL of front document',
        }.get(app_name.lower(), "")
        if browser_script:
            url = _run_text(["osascript", "-e", browser_script])
    return ActiveWindowInfo(app_name=app_name, title=title, process_name=app_name, url=url)


def _active_window_windows() -> ActiveWindowInfo:
    # This script gets the active window's details and, if it belongs to a browser
    # (Chrome/Edge/Brave/Firefox), uses UIAutomationClient to extract the active tab URL.
    # We use $processId instead of $pid because $pid is read-only in PowerShell.
    script = r"""
Add-Type -AssemblyName UIAutomationClient
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinApi {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@
$hwnd = [WinApi]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 512
[void][WinApi]::GetWindowText($hwnd, $sb, $sb.Capacity)
$processId = 0
[void][WinApi]::GetWindowThreadProcessId($hwnd, [ref]$processId)
$proc = Get-Process -Id $processId -ErrorAction SilentlyContinue

$url = ""
if ($proc.ProcessName -match "chrome|msedge|brave|firefox") {
  try {
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
    $condition = New-Object System.Windows.Automation.PropertyCondition(
      [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
      [System.Windows.Automation.ControlType]::Edit
    )
    $edits = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
    foreach ($edit in $edits) {
      try {
        $vp = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
        if ($vp -and $vp.Current.Value -match "\.|:|/") {
          $url = $vp.Current.Value
          break
        }
      } catch {}
    }
  } catch {}
}

[pscustomobject]@{ app_name = $proc.ProcessName; process_name = $proc.ProcessName; title = $sb.ToString(); url = $url } | ConvertTo-Json -Compress
"""
    import base64
    try:
        encoded_script = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        raw = _run_text(["powershell", "-NoProfile", "-EncodedCommand", encoded_script], timeout=4)
        data = json.loads(raw)
    except Exception:
        data = {}
    
    url = str(data.get("url") or "").strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url

    return ActiveWindowInfo(
        app_name=str(data.get("app_name") or ""),
        process_name=str(data.get("process_name") or ""),
        title=str(data.get("title") or ""),
        url=url,
    )



def _clipboard_text(system: str) -> str:
    if system == "darwin":
        return _run_text(["pbpaste"], timeout=1.5)[:4000]
    if system == "windows":
        return _run_text(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"], timeout=2)[:4000]
    return _run_text(["sh", "-lc", "xclip -selection clipboard -o 2>/dev/null || wl-paste 2>/dev/null"], timeout=2)[:4000]


def active_window_info() -> ActiveWindowInfo:
    system = platform.system().lower()
    window = _active_window_windows() if system.startswith("win") else _active_window_macos() if system == "darwin" else ActiveWindowInfo()
    clip = _clipboard_text("windows" if system.startswith("win") else system)
    return ActiveWindowInfo(
        app_name=window.app_name,
        title=window.title,
        process_name=window.process_name,
        url=window.url,
        selected_text="",
        clipboard_text=clip,
    )


class BrowserAdapter:
    name = "browser"

    def can_handle(self, window: ActiveWindowInfo) -> bool:
        haystack = f"{window.app_name} {window.process_name} {window.title} {window.url}".lower()
        return any(token in haystack for token in ("chrome", "edge", "firefox", "safari", "browser", "youtube"))

    def get_context(self, window: ActiveWindowInfo) -> dict[str, Any]:
        is_youtube = bool(re.search(r"(youtube\.com|youtu\.be|youtube)", f"{window.url} {window.title}", re.I))
        return {
            "app_type": "browser",
            "adapter": self.name,
            "app_name": window.app_name or window.process_name or "Browser",
            "title": window.title,
            "url": window.url,
            "selected_text": window.selected_text,
            "clipboard_text": window.clipboard_text[:1500],
            "metadata": {
                "is_youtube": is_youtube,
                "video_title": window.title if is_youtube else "",
                "online_transcript_available": False,
            },
        }


class CodeEditorAdapter:
    name = "code_editor"

    def can_handle(self, window: ActiveWindowInfo) -> bool:
        haystack = f"{window.app_name} {window.process_name} {window.title}".lower()
        return any(token in haystack for token in ("visual studio code", "code.exe", "vscode", "cursor", "sublime", "pycharm"))

    def get_context(self, window: ActiveWindowInfo) -> dict[str, Any]:
        return {
            "app_type": "editor",
            "adapter": self.name,
            "app_name": window.app_name or "Code Editor",
            "title": window.title,
            "selected_text": window.selected_text,
            "surrounding_text": window.clipboard_text[:2500],
            "metadata": {"capture_level": "window_title_and_clipboard", "insert_supported": False},
        }


class TerminalAdapter:
    name = "terminal"

    def can_handle(self, window: ActiveWindowInfo) -> bool:
        haystack = f"{window.app_name} {window.process_name} {window.title}".lower()
        return any(token in haystack for token in ("terminal", "powershell", "cmd", "windows terminal", "wezterm"))

    def get_context(self, window: ActiveWindowInfo) -> dict[str, Any]:
        return {
            "app_type": "terminal",
            "adapter": self.name,
            "app_name": window.app_name or "Terminal",
            "title": window.title,
            "logs": window.clipboard_text[:3000],
            "metadata": {"capture_level": "window_title_and_clipboard"},
        }


class GenericAdapter:
    name = "generic"

    def can_handle(self, _window: ActiveWindowInfo) -> bool:
        return True

    def get_context(self, window: ActiveWindowInfo) -> dict[str, Any]:
        return {
            "app_type": "generic",
            "adapter": self.name,
            "app_name": window.app_name or window.process_name or "Unknown app",
            "title": window.title,
            "selected_text": window.selected_text,
            "clipboard_text": window.clipboard_text[:2000],
            "metadata": {"capture_level": "window_title_and_clipboard"},
        }


ADAPTERS: tuple[AppContextAdapter, ...] = (
    CodeEditorAdapter(),
    TerminalAdapter(),
    BrowserAdapter(),
    GenericAdapter(),
)


def capture_app_context() -> dict[str, Any]:
    window = active_window_info()
    for adapter in ADAPTERS:
        if adapter.can_handle(window):
            context = adapter.get_context(window)
            context["captured_at"] = time.time()
            context["window"] = {
                "app_name": window.app_name,
                "process_name": window.process_name,
                "title": window.title,
            }
            return context
    return GenericAdapter().get_context(window)


def context_prompt_block(context: dict[str, Any]) -> str:
    if not isinstance(context, dict) or not context:
        return ""
    allowed = {
        "app_type",
        "adapter",
        "app_name",
        "title",
        "url",
        "selected_text",
        "surrounding_text",
        "logs",
        "clipboard_text",
        "metadata",
    }
    compact = {key: context.get(key) for key in allowed if context.get(key)}
    if not compact:
        return ""
    return "Active app context for this Shell overlay request:\n" + json.dumps(compact, ensure_ascii=False, indent=2)[:6000]


__all__ = ["capture_app_context", "context_prompt_block", "active_window_info", "ADAPTERS"]
