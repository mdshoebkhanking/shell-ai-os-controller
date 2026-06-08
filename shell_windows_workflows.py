"""Safe desktop workflow helpers for common Shell voice/chat commands."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from shell_safe_executor import god_tier_tool as function_tool


def _system() -> str:
    return platform.system().lower()


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


async def _open_path(path: Path) -> str:
    target = str(path)
    system = _system()
    if system == "windows":
        code, output = await _run(["cmd", "/c", "start", "", target])
        return f"Opened {target}" if code == 0 else f"Could not open {target}: {output}"
    if system == "darwin":
        code, output = await _run(["open", target])
        return f"Opened {target}" if code == 0 else f"Could not open {target}: {output}"
    if shutil.which("xdg-open"):
        code, output = await _run(["xdg-open", target])
        return f"Opened {target}" if code == 0 else f"Could not open {target}: {output}"
    return f"Created {target}. Opening folders is not available on this platform."


async def _open_uri(uri: str) -> str:
    system = _system()
    if system == "windows":
        code, output = await _run(["cmd", "/c", "start", "", uri])
        return f"Opened {uri}" if code == 0 else f"Could not open {uri}: {output}"
    if system == "darwin":
        code, output = await _run(["open", uri])
        return f"Opened {uri}" if code == 0 else f"Could not open {uri}: {output}"
    if shutil.which("xdg-open"):
        code, output = await _run(["xdg-open", uri])
        return f"Opened {uri}" if code == 0 else f"Could not open {uri}: {output}"
    return f"Could not open {uri}: no platform opener is available."


def _safe_folder_name(value: str, default: str = "Shell Folder") -> str:
    cleaned = "".join(ch for ch in str(value or "").strip() if ch not in '<>:"/\\|?*')
    cleaned = " ".join(cleaned.split())
    return cleaned[:80] or default


def _desktop_dir() -> Path:
    return Path.home() / "Desktop"


def _downloads_dir() -> Path:
    return Path.home() / "Downloads"


def _screenshots_dir() -> Path:
    pictures = Path.home() / "Pictures"
    screenshots = pictures / "Screenshots"
    return screenshots if screenshots.exists() else _desktop_dir()


@function_tool(category="system")
async def create_desktop_folder_tool(folder_name: str, open_folder: bool = True) -> dict[str, Any]:
    """Create a folder on Desktop and optionally open it."""
    name = _safe_folder_name(folder_name, "Shell Folder")
    path = _desktop_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    opened_message = await _open_path(path) if open_folder else ""
    return {
        "ok": True,
        "action": "created_folder",
        "path": str(path),
        "folder_name": name,
        "opened": bool(open_folder),
        "message": f"Created Desktop folder: {name}" + (f". {opened_message}" if opened_message else ""),
    }


@function_tool(category="files")
async def organize_downloads_setups_pdfs_tool(
    zip_folder: str = "Setups",
    pdf_folder: str = "PDFs",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Move ZIP/installer files and PDFs from Downloads into named subfolders."""
    downloads = _downloads_dir()
    if not downloads.exists():
        return {"ok": False, "message": f"Downloads folder not found: {downloads}", "moved": []}

    setup_dir = downloads / _safe_folder_name(zip_folder, "Setups")
    pdf_dir = downloads / _safe_folder_name(pdf_folder, "PDFs")
    setup_exts = {".zip", ".msi", ".exe"}
    moved: list[dict[str, str]] = []
    for item in downloads.iterdir():
        if not item.is_file():
            continue
        suffix = item.suffix.lower()
        if suffix in setup_exts:
            target_dir = setup_dir
        elif suffix == ".pdf":
            target_dir = pdf_dir
        else:
            continue
        target = target_dir / item.name
        counter = 1
        while target.exists():
            target = target_dir / f"{item.stem}_{counter}{item.suffix}"
            counter += 1
        moved.append({"from": str(item), "to": str(target)})
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(target))

    return {
        "ok": True,
        "action": "organized_downloads",
        "dry_run": bool(dry_run),
        "downloads": str(downloads),
        "setups_folder": str(setup_dir),
        "pdfs_folder": str(pdf_dir),
        "moved_count": len(moved),
        "moved": moved[:50],
        "message": (
            f"{'Would move' if dry_run else 'Moved'} {len(moved)} Downloads files "
            f"into {setup_dir.name} and {pdf_dir.name}."
        ),
    }


@function_tool(category="system")
async def open_work_session_tool(
    chrome_urls: list[str] | None = None,
    include_vscode: bool = True,
    include_chrome: bool = True,
    include_spotify: bool = True,
) -> dict[str, Any]:
    """Open a basic work session: VS Code, Chrome/dev tabs, and Spotify."""
    urls = chrome_urls or [
        "https://github.com/",
        "http://localhost:5173/",
        "http://localhost:3000/",
    ]
    actions: list[str] = []
    if include_vscode:
        actions.append(await _open_uri("vscode:"))
    if include_chrome:
        for url in urls[:6]:
            actions.append(await _open_uri(str(url)))
    if include_spotify:
        actions.append(await _open_uri("spotify:"))
    return {"ok": True, "action": "opened_work_session", "actions": actions, "message": "Work session launch requested."}


@function_tool(category="system")
async def open_task_manager_high_cpu_review_tool(open_task_manager: bool = True) -> dict[str, Any]:
    """Open Task Manager and list high-CPU candidates without killing anything."""
    actions: list[str] = []
    if open_task_manager:
        actions.append(await _open_uri("taskmgr"))
    candidates: list[dict[str, Any]] = []
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                cpu = float(proc.info.get("cpu_percent") or 0.0)
            except Exception:
                cpu = 0.0
            if cpu >= 10.0:
                candidates.append({"pid": proc.pid, "name": proc.info.get("name") or "", "cpu_percent": cpu})
        candidates.sort(key=lambda item: float(item["cpu_percent"]), reverse=True)
    except Exception:
        candidates = []
    return {
        "ok": True,
        "action": "review_high_cpu",
        "actions": actions,
        "candidates": candidates[:10],
        "message": "Opened Task Manager and listed high-CPU candidates. I did not close apps automatically for safety.",
    }


@function_tool(category="system")
async def open_focus_assist_tool(minutes: int = 30) -> dict[str, Any]:
    """Open Windows Focus/Do Not Disturb settings for the requested duration."""
    minutes = max(1, min(240, int(minutes or 30)))
    message = await _open_uri("ms-settings:quiethours")
    return {
        "ok": True,
        "action": "opened_focus_settings",
        "minutes": minutes,
        "message": f"Opened Focus/Do Not Disturb settings. Set it for {minutes} minutes if Windows asks for confirmation. {message}",
    }


@function_tool(category="system")
async def open_whatsapp_spotify_side_by_side_tool() -> dict[str, Any]:
    """Open WhatsApp and Spotify; window tiling is left to Windows if needed."""
    actions = [
        await _open_uri("whatsapp:"),
        await _open_uri("https://web.whatsapp.com/"),
        await _open_uri("spotify:"),
    ]
    return {
        "ok": True,
        "action": "opened_whatsapp_spotify",
        "actions": actions,
        "message": "WhatsApp and Spotify launch requested. Use Snap Layouts if Windows does not tile them automatically.",
    }


@function_tool(category="system")
async def open_recent_screenshots_slideshow_tool() -> dict[str, Any]:
    """Open the screenshots folder and Photos app for manual slideshow."""
    screenshots = _screenshots_dir()
    actions = [await _open_path(screenshots)]
    if _system() == "windows":
        actions.append(await _open_uri("ms-photos:"))
    return {
        "ok": True,
        "action": "opened_recent_screenshots",
        "screenshots_folder": str(screenshots),
        "actions": actions,
        "message": "Opened recent screenshots location and Photos. Start slideshow from Photos if Windows prompts.",
    }


@function_tool(category="system")
async def screen_comfort_tool(brightness_level: int = 40, enable_night_light: bool = True) -> dict[str, Any]:
    """Reduce brightness and open Night Light settings safely."""
    actions: list[str] = []
    try:
        from shell_system_pro import set_brightness_tool

        actions.append(await set_brightness_tool(int(brightness_level)))
    except Exception as exc:
        actions.append(f"Brightness change unavailable: {exc}")
    if enable_night_light:
        actions.append(await _open_uri("ms-settings:nightlight"))
    return {
        "ok": True,
        "action": "screen_comfort",
        "brightness_level": int(brightness_level),
        "night_light": bool(enable_night_light),
        "actions": actions,
        "message": "Brightness command sent and Night Light settings opened.",
    }


__all__ = [
    "create_desktop_folder_tool",
    "open_focus_assist_tool",
    "open_recent_screenshots_slideshow_tool",
    "open_task_manager_high_cpu_review_tool",
    "open_whatsapp_spotify_side_by_side_tool",
    "open_work_session_tool",
    "organize_downloads_setups_pdfs_tool",
    "screen_comfort_tool",
]
