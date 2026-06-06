import os
import subprocess
import logging
import sys
import asyncio
import shutil
import difflib
import re
try:
    from fuzzywuzzy import process
except ImportError:
    process = None

try:
    from shell_safe_executor import god_tier_tool as function_tool
except ImportError:
    def function_tool(func):
        return func

try:
    import win32gui
    import win32con
    import win32process
except ImportError:
    win32gui = None
    win32con = None
    win32process = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None

# Setup encoding and logger
sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App command map - simplified, uses PATH lookup
APP_MAPPINGS = {
    "notepad": "notepad",
    "calculator": "calc",
    "chrome": "chrome",
    "vlc": "vlc",
    "command prompt": "cmd",
    "powershell": "powershell",
    "explorer": "explorer",
    "control panel": "control",
    "settings": "ms-settings:",
    "paint": "mspaint",
    "vs code": "code",
    "postman": "postman",
    "firefox": "firefox",
    "edge": "msedge",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "whatsapp": "whatsapp:",
    # --- NEW APPS ---
    "spotify": "spotify",
    "discord": "discord",
    "slack": "slack",
    "zoom": "zoom",
    "teams": "teams",
    "telegram": "telegram",
    "obs": "obs64",
    "blender": "blender",
    "photoshop": "photoshop",
    "illustrator": "illustrator",
}

APP_ALIASES = {
    "calc": "calculator",
    "calculater": "calculator",
    "calculetor": "calculator",
    "calculator app": "calculator",
    "note pad": "notepad",
    "notes app": "notepad",
    "google chrome": "chrome",
    "chrom": "chrome",
    "crome": "chrome",
    "microsoft edge": "edge",
    "ms edge": "edge",
    "window settings": "settings",
    "windows settings": "settings",
    "setting": "settings",
    "settings app": "settings",
    "controlpanel": "control panel",
    "file explorer": "explorer",
    "explorer": "explorer",
    "files": "explorer",
    "cmd": "command prompt",
    "terminal": "command prompt",
    "powershell": "powershell",
    "visual studio code": "vs code",
    "vscode": "vs code",
    "whats app": "whatsapp",
    "whatapp": "whatsapp",
    "ms teams": "teams",
    "microsoft teams": "teams",
}

MAC_APP_ALIASES = {
    "calculator": "Calculator",
    "calc": "Calculator",
    "textedit": "TextEdit",
    "text edit": "TextEdit",
    "notes": "Notes",
    "calendar": "Calendar",
    "dictionary": "Dictionary",
    "safari": "Safari",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "terminal": "Terminal",
    "finder": "Finder",
    "settings": "System Settings",
    "system settings": "System Settings",
    "music": "Music",
    "mail": "Mail",
    "maps": "Maps",
    "preview": "Preview",
    "messages": "Messages",
    "telegram": "Telegram",
    "slack": "Slack",
    "zoom": "zoom.us",
    "discord": "Discord",
    "vs code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "code": "Visual Studio Code",
}

# Common install paths for apps not always on PATH
APP_INSTALL_PATHS = {
    "spotify": [
        os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
    ],
    "discord": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "Update.exe"),
    ],
    "slack": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "slack", "slack.exe"),
    ],
    "zoom": [
        os.path.join(os.environ.get("APPDATA", ""), "Zoom", "bin", "Zoom.exe"),
    ],
    "teams": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Teams", "Update.exe"),
    ],
    "telegram": [
        os.path.join(os.environ.get("APPDATA", ""), "Telegram Desktop", "Telegram.exe"),
    ],
    "obs": [
        r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    ],
    "blender": [
        r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender\blender.exe",
    ],
    "photoshop": [
        r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop CC 2019\Photoshop.exe",
    ],
    "illustrator": [
        r"C:\Program Files\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
        r"C:\Program Files\Adobe\Adobe Illustrator 2023\Support Files\Contents\Windows\Illustrator.exe",
    ],
}

def find_app_path(app_name):
    """Find app path using shutil.which for PATH lookup"""
    return shutil.which(app_name)

def _normalize_app_title(app_title: str) -> str:
    cleaned = str(app_title or "").lower().strip()
    cleaned = cleaned.replace("_", " ").replace("-", " ")
    cleaned = " ".join(cleaned.split())
    cleaned = re.sub(r"^(open|launch|start|run|khol|kholo|chalao)\s+", "", cleaned)
    cleaned = re.sub(r"\s+(app|application|software|program)$", "", cleaned).strip()
    if cleaned in APP_ALIASES:
        return APP_ALIASES[cleaned]
    if cleaned in APP_MAPPINGS:
        return cleaned
    match = difflib.get_close_matches(cleaned, list(APP_MAPPINGS.keys()) + list(APP_ALIASES.keys()), n=1, cutoff=0.84)
    if match:
        return APP_ALIASES.get(match[0], match[0])
    return cleaned

def _windows_start_command(target: str) -> subprocess.Popen:
    # `start` treats the first quoted argument as a window title; pass an
    # explicit empty title so app names/paths with spaces are interpreted as
    # the command target.
    return subprocess.Popen(["cmd", "/c", "start", "", target])

def _windows_launch_uri(uri: str) -> None:
    if hasattr(os, "startfile"):
        os.startfile(uri)  # type: ignore[attr-defined]
        return
    _windows_start_command(uri)

def _mac_app_name(app_title: str) -> str:
    key = str(app_title or "").strip().lower()
    return MAC_APP_ALIASES.get(key, str(app_title or "").strip())

def _applescript_string(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'

async def _open_app_macos(app_title: str) -> str:
    app_name = _mac_app_name(app_title)
    if not app_name:
        return "App name is empty."
    proc = await asyncio.to_thread(
        subprocess.run,
        ["open", "-a", app_name],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode == 0:
        await asyncio.sleep(0.8)
        return f"App launched on macOS: {app_name}"
    output = (proc.stdout or "").strip()
    return f"App not found on macOS: {app_name}" + (f"\n{output}" if output else "")

async def _close_app_macos(app_title: str) -> str:
    app_name = _mac_app_name(app_title)
    if not app_name:
        return "App name is empty."
    script = (
        f"if application {_applescript_string(app_name)} is running then\n"
        f"  tell application {_applescript_string(app_name)} to quit\n"
        f"  return \"closed\"\n"
        f"else\n"
        f"  return \"not running\"\n"
        f"end if"
    )
    proc = await asyncio.to_thread(
        subprocess.run,
        ["osascript", "-e", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = (proc.stdout or "").strip()
    if proc.returncode == 0 and "closed" in output.lower():
        await asyncio.sleep(0.5)
        return f"App closed on macOS: {app_name}"
    if proc.returncode == 0 and "not running" in output.lower():
        return f"App was not running on macOS: {app_name}"
    return f"Could not close macOS app: {app_name}" + (f"\n{output}" if output else "")

async def _open_app_linux(app_title: str, app_command: str) -> str:
    candidate = shutil.which(app_command) or shutil.which(str(app_title).strip())
    if candidate:
        proc = subprocess.Popen([candidate], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(0.8)
        return f"App launched on Linux: {app_title} (PID: {proc.pid})"
    launcher = shutil.which("gtk-launch")
    if launcher:
        proc = subprocess.run([launcher, str(app_title).strip()], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        if proc.returncode == 0:
            return f"App launch attempted on Linux: {app_title}"
    return f"App not found on Linux: {app_title}"

async def _close_app_linux(app_title: str) -> str:
    if not shutil.which("pkill"):
        return "pkill not available on Linux."
    proc = await asyncio.to_thread(
        subprocess.run,
        ["pkill", "-f", str(app_title).strip()],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode == 0:
        return f"App close signal sent on Linux: {app_title}"
    return f"App process not found on Linux: {app_title}"

def _find_app_install_path(app_title):
    """Check common install locations for an app"""
    paths = APP_INSTALL_PATHS.get(app_title, [])
    for p in paths:
        if os.path.exists(p):
            return p
    return None

# -------------------------
# Helper: find window handle by title
# -------------------------
def _find_window_hwnd(title_keyword):
    """Find the first visible window handle matching title_keyword (case-insensitive)."""
    if not win32gui:
        return None
    result = []
    title_low = title_keyword.lower().strip()
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            txt = win32gui.GetWindowText(hwnd).lower()
            if title_low in txt:
                result.append(hwnd)
    win32gui.EnumWindows(callback, None)
    return result[0] if result else None

def _get_pywinauto_driver():
    try:
        from core.automation.windows_pywinauto import create_pywinauto_driver
        return create_pywinauto_driver()
    except Exception as exc:
        logger.debug("pywinauto driver unavailable: %s", exc)
        return None

async def _run_pywinauto(action: str, *args):
    driver = _get_pywinauto_driver()
    if driver is None:
        return None
    method = getattr(driver, action, None)
    if method is None:
        return None
    try:
        return await asyncio.to_thread(method, *args)
    except Exception as exc:
        logger.debug("pywinauto %s failed: %s", action, exc)
        return None

# -------------------------
# Global focus utility
# -------------------------
async def focus_window(title_keyword: str) -> bool:
    if sys.platform.startswith("win"):
        result = await _run_pywinauto("focus_window", title_keyword)
        if result is not None and getattr(result, "ok", False):
            return True

    if not gw:
        logger.warning("pygetwindow not available")
        return False

    for _ in range(5): # Fast retry loop (5x 0.2s = 1.0s max wait)
        await asyncio.sleep(0.2)
        for window in gw.getAllWindows():
            if title_keyword in window.title.lower():
                if window.isMinimized:
                    window.restore()
                try:
                    window.activate()
                    return True
                except Exception:
                    pass  # Window may not be activatable
    return False

# Index files/folders
async def index_items(base_dirs):
    item_index = []
    for base_dir in base_dirs:
        for root, dirs, files in os.walk(base_dir):
            for d in dirs:
                item_index.append({"name": d, "path": os.path.join(root, d), "type": "folder"})
            for f in files:
                item_index.append({"name": f, "path": os.path.join(root, f), "type": "file"})
    logger.info(f"Indexed {len(item_index)} items.")
    return item_index

async def search_item(query, index, item_type):
    filtered = [item for item in index if item["type"] == item_type]
    choices = [item["name"] for item in filtered]
    if not choices:
        return None
    if process:
        best_match, score = process.extractOne(query, choices)
    else:
        matches = difflib.get_close_matches(query, choices, n=1, cutoff=0.7)
        if not matches:
            return None
        best_match, score = matches[0], 75
    logger.info(f"Matched '{query}' to '{best_match}' with score {score}")
    if score > 70:
        for item in filtered:
            if item["name"] == best_match:
                return item
    return None

# File/folder actions
async def open_folder(path):
    """Open a folder in file explorer using Popen (Prevents timeouts)"""
    try:
        if not os.path.exists(path):
            return f"Folder not found: {path}"

        # Use explorer.exe explicitly to avoid ShellExecute timeouts
        subprocess.Popen(["explorer", path])

        # Best effort focus (don't fail if this times out)
        try:
             await asyncio.sleep(1.0)
             await focus_window(os.path.basename(path))
        except Exception as _e:
             logger.debug("ignored Exception: %s", _e)

        return f"Folder opened: {path}"
    except Exception as e:
        logger.error(f"Error opening folder {path}: {e}")
        return f"Error opening folder: {str(e)}"

async def play_file(path):
    """Open/play a file with default application"""
    try:
        if not os.path.exists(path):
            return f"File not found: {path}"

        os.startfile(path)
        return f"File opened: {path}"
    except Exception as e:
        logger.error(f"Error opening file {path}: {e}")
        return f"Error opening file: {str(e)}"

async def create_folder(path):
    """Create a new folder"""
    try:
        if not path:
            return "Folder path is empty."

        # Clean path logic
        path = path.replace('"', '').strip()

        os.makedirs(path, exist_ok=True)
        logger.info(f"Created folder: {path}")

        # Auto-open after creation
        subprocess.Popen(["explorer", path])

        return f"Folder created: {path}"
    except Exception as e:
        logger.error(f"Error creating folder {path}: {e}")
        try:
            # Fallback to Desktop if full path fails
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            safe_path = os.path.join(desktop, os.path.basename(path))
            os.makedirs(safe_path, exist_ok=True)
            subprocess.Popen(["explorer", safe_path])
            return f"Error corrected. Folder created on Desktop: {safe_path}"
        except Exception:
             return f"Error creating folder: {str(e)}"

async def rename_item(old_path, new_path):
    """Rename a file or folder"""
    try:
        if not os.path.exists(old_path):
            return f"Item not found: {old_path}"
        if not old_path or not new_path:
            return "Path is empty."
        os.rename(old_path, new_path)
        logger.info(f"Renamed {old_path} to {new_path}")
        return f"Renamed to: {new_path}"
    except Exception as e:
        logger.error(f"Error renaming {old_path}: {e}")
        return f"Rename error: {str(e)}"

async def delete_item(path):
    """Delete a file or folder"""
    try:
        if not path:
            return "Path is empty."
        if not os.path.exists(path):
            return f"Item not found: {path}"
        if os.path.isdir(path):
            os.rmdir(path)
        else:
            os.remove(path)
        logger.info(f"Deleted: {path}")
        return f"Deleted: {path}"
    except Exception as e:
        logger.error(f"Error deleting {path}: {e}")
        return f"Delete error: {str(e)}"

# App control
@function_tool
async def write_to_notepad_tool(content: str, filename: str = "notes.txt", auto_run: bool = False) -> str:
    """
    Writes content to Notepad with a typing effect (Hacker/Jarvis style).
    Breaks long text into multiple lines for better readability.

    Args:
        content: The text/code to type.
        filename: Optional filename for saving context.
        auto_run: If true, tries to execute the code (Python only) after typing.
    """
    try:
        import pyautogui
        import textwrap
        import time

        # 1. Open fresh Notepad
        subprocess.Popen(["notepad.exe"])
        await asyncio.sleep(1.5) # Wait for launch
        await focus_window("notepad")

        # 2. Direct Content (NO WRAPPING - Preserves Code Structure)
        # wrapping removed to keep indentation/newlines exact

        # 3. Type it out visibly
        # Adjust interval for speed (0.001 is very fast "hacker" style)
        pyautogui.write(content, interval=0.001)

        status = f"Typed content into Notepad (Visual Mode)."

        # 4. AUTO-RUN LOGIC — gated (was a straight RCE path)
        # Previously this wrote user content to temp_shell_code.py and launched
        # a subprocess to run it, with no safety check. That let any prompt-
        # injection attack escalate to arbitrary Python execution. Auto-run
        # now requires SHELL_ALLOW_CODE_WRITE=1 and funnels through
        # shell_code_engine's write_code_tool so the same gate + path checks
        # apply.
        if auto_run:
            try:
                from shell_safety_gate import check_code_write, audit_write
            except Exception:
                status += "\nAuto-Run skipped: shell_safety_gate unavailable."
                return status
            ok, reason = check_code_write(origin="write_to_notepad_tool.auto_run")
            if not ok:
                status += f"\nAuto-Run BLOCKED by safety gate: {reason.splitlines()[0]}"
                return status
            import tempfile
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", suffix=".py",
                    prefix="shell_autorun_", delete=False,
                ) as tmp:
                    tmp.write(content)
                    temp_filename = tmp.name
                audit_write("write_to_notepad_tool.auto_run", temp_filename, "auto_run=True")
                subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", "python", temp_filename])
                status += f"\nCode Auto-Run initiated! (Temp: {temp_filename})"
            except Exception as e2:
                status += f"\nAuto-Run failed: {e2}"

        return status

    except ImportError:
         # Fallback to file write if pyautogui is missing
        home = os.path.expanduser("~")
        filepath = os.path.join(home, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        subprocess.Popen(["notepad.exe", filepath])
        return f"(Fallback) Written to file {filename}."
    except Exception as e:
        logger.error(f"Error writing to notepad: {e}")
        return f"Error: {str(e)}"

@function_tool
async def open_app(app_title: str) -> str:
    """
    Open an application by name. Returns process PID after launch.
    Supports: notepad, calculator, chrome, vlc, cmd, control panel, settings,
    paint, vs code, postman, firefox, edge, word, excel, powerpoint, whatsapp,
    spotify, discord, slack, zoom, teams, telegram, obs, blender, photoshop, illustrator.

    Args:
        app_title: Name of the application to open.
    """
    raw_app_title = str(app_title or "").strip()
    app_title = _normalize_app_title(raw_app_title)
    if not app_title:
        return "App name is empty."

    app_command = APP_MAPPINGS.get(app_title, app_title)

    try:
        if sys.platform == "darwin":
            return await _open_app_macos(app_title)
        if sys.platform.startswith("linux"):
            return await _open_app_linux(app_title, app_command)

        install_path_hint = _find_app_install_path(app_title)
        pywinauto_result = await _run_pywinauto(
            "open_app",
            app_title,
            app_command,
            install_path_hint,
        )
        if pywinauto_result is not None and getattr(pywinauto_result, "ok", False):
            return pywinauto_result.message

        proc = None

        # Special case for settings (URI protocol)
        if app_title == "settings":
            _windows_launch_uri("ms-settings:")
            await asyncio.sleep(2)
            return f"Settings launched (URI protocol, no PID tracking)."

        # Special case for whatsapp (URI protocol)
        if app_title == "whatsapp":
            _windows_launch_uri("whatsapp:")
            await asyncio.sleep(2)
            return f"WhatsApp launched (URI protocol, no PID tracking)."

        # Special case for Discord (uses Update.exe --processStart)
        if app_title == "discord":
            install_path = _find_app_install_path("discord")
            if install_path and os.path.exists(install_path):
                proc = subprocess.Popen([install_path, "--processStart", "Discord.exe"])
            else:
                app_path = find_app_path("discord")
                if app_path:
                    proc = subprocess.Popen([app_path])
                else:
                    _windows_start_command(app_command)
                    await asyncio.sleep(2)
                    return f"{app_title} launch requested through Windows Shell."

        # Special case for Teams (uses Update.exe)
        elif app_title == "teams":
            install_path = _find_app_install_path("teams")
            if install_path and os.path.exists(install_path):
                proc = subprocess.Popen([install_path, "--processStart", "Teams.exe"])
            else:
                app_path = find_app_path("teams") or find_app_path("ms-teams")
                if app_path:
                    proc = subprocess.Popen([app_path])
                else:
                    _windows_launch_uri("msteams:")
                    await asyncio.sleep(2)
                    return f"Teams launch attempted via URI protocol."
        else:
            # 1) Try PATH lookup
            app_path = find_app_path(app_command)
            if app_path:
                proc = subprocess.Popen([app_path])
            else:
                # 2) Try known install paths
                install_path = install_path_hint
                if install_path:
                    proc = subprocess.Popen([install_path])
                else:
                    # 3) Try a direct Windows process launch before asking the
                    # shell to resolve aliases/URI handlers.
                    try:
                        proc = subprocess.Popen([app_command])
                    except FileNotFoundError:
                        proc = _windows_start_command(app_command)

        # Get PID
        pid = proc.pid if proc else None

        # Wait for app to load
        await asyncio.sleep(2)
        focused = await focus_window(app_title)

        pid_info = f" (PID: {pid})" if pid else ""
        if focused:
            return f"App launched and focused: {app_title}{pid_info}"
        else:
            return f"{app_title} launch requested (may be in background){pid_info}"

    except FileNotFoundError:
        return f"{app_title} not found. Make sure it is installed."
    except Exception as e:
        logger.error(f"Error opening app {app_title}: {e}")
        return f"Error opening {app_title}: {str(e)}"

@function_tool
async def close_app(window_title: str) -> str:
    """Close a window by title"""
    window_title = window_title.lower().strip()
    if not window_title:
        return "Window name is empty."

    if sys.platform == "darwin":
        return await _close_app_macos(window_title)
    if sys.platform.startswith("linux"):
        return await _close_app_linux(window_title)

    pywinauto_result = await _run_pywinauto("close_window", window_title)
    if pywinauto_result is not None and getattr(pywinauto_result, "ok", False):
        return pywinauto_result.message

    if not win32gui:
        logger.warning("win32gui module not available")
        return "win32gui not available"

    try:
        found = False
        def enumHandler(hwnd, _):
            nonlocal found
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd).lower()
                if window_title in window_text:
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    found = True
                    logger.info(f"Closed window: {window_text}")

        win32gui.EnumWindows(enumHandler, None)
        if found:
            return f"Window closed: {window_title}"
        else:
            return f"Window not found: {window_title}"
    except Exception as e:
        logger.error(f"Error closing window {window_title}: {e}")
        return f"Error closing window: {str(e)}"

@function_tool
async def minimize_window(window_title: str) -> str:
    """
    Minimizes a window to the taskbar.
    Args:
        window_title: The name/title of the window (e.g., 'chrome', 'notepad').
    """
    pywinauto_result = await _run_pywinauto("minimize_window", window_title)
    if pywinauto_result is not None and getattr(pywinauto_result, "ok", False):
        return pywinauto_result.message
    if not win32gui: return "System module missing"
    try:
        found = False
        title_low = window_title.lower()
        def callback(hwnd, _):
            nonlocal found
            if win32gui.IsWindowVisible(hwnd):
                txt = win32gui.GetWindowText(hwnd).lower()
                if title_low in txt:
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                    found = True
        win32gui.EnumWindows(callback, None)
        return f"{window_title} minimized." if found else f"{window_title} not found."
    except Exception as e:
        return f"Error: {str(e)}"

@function_tool
async def maximize_window(window_title: str) -> str:
    """
    Maximizes a window to fill the screen.
    Args:
        window_title: The name/title of the window.
    """
    pywinauto_result = await _run_pywinauto("maximize_window", window_title)
    if pywinauto_result is not None and getattr(pywinauto_result, "ok", False):
        return pywinauto_result.message
    if not win32gui: return "System module missing"
    try:
        found = False
        title_low = window_title.lower()
        def callback(hwnd, _):
            nonlocal found
            if win32gui.IsWindowVisible(hwnd):
                txt = win32gui.GetWindowText(hwnd).lower()
                if title_low in txt:
                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                    found = True
        win32gui.EnumWindows(callback, None)
        return f"{window_title} maximized." if found else f"{window_title} not found."
    except Exception as e:
        return f"Error: {str(e)}"

@function_tool
async def resize_window(window_title: str, width: int = 800, height: int = 600) -> str:
    """
    Resizes a window to a specific size.
    Args:
        window_title: The name/title of the window.
        width: New width in pixels.
        height: New height in pixels.
    """
    pywinauto_result = await _run_pywinauto("resize_window", window_title, width, height)
    if pywinauto_result is not None and getattr(pywinauto_result, "ok", False):
        return pywinauto_result.message
    if not win32gui: return "System module missing"
    try:
        found = False
        title_low = window_title.lower()
        def callback(hwnd, _):
            nonlocal found
            if win32gui.IsWindowVisible(hwnd):
                txt = win32gui.GetWindowText(hwnd).lower()
                if title_low in txt:
                    # Get existing position to keep it in place
                    rect = win32gui.GetWindowRect(hwnd)
                    win32gui.MoveWindow(hwnd, rect[0], rect[1], width, height, True)
                    found = True
        win32gui.EnumWindows(callback, None)
        return f"{window_title} resized to {width}x{height}." if found else f"{window_title} not found."
    except Exception as e:
        return f"Error: {str(e)}"

@function_tool
async def folder_file(command: str) -> str:
    """Handle folder and file operations"""
    try:
        if not command:
            return "Command is empty."

        # 1. OPTIMIZATION: Check if command is already a valid absolute path
        clean_path = command.replace('"', '').strip()
        if os.path.exists(clean_path):
            if os.path.isdir(clean_path):
                return await open_folder(clean_path)
            elif os.path.isfile(clean_path):
                return await play_file(clean_path)

        # Get default folders to search
        home_dir = os.path.expanduser("~")
        documents = os.path.join(home_dir, "Documents")
        desktop = os.path.join(home_dir, "Desktop")
        downloads = os.path.join(home_dir, "Downloads")

        folders_to_index = [documents, desktop, downloads]

        # Only index if folders exist
        valid_folders = [f for f in folders_to_index if os.path.exists(f)]
        if not valid_folders:
            return "No valid folders found."

        index = await index_items(valid_folders)
        command_lower = command.lower().strip()

        # Create folder
        if "create folder" in command_lower:
            folder_name = command_lower.replace("create folder", "").strip()
            if folder_name:
                path = os.path.join(desktop, folder_name)
                return await create_folder(path)
            return "Please provide a folder name."

        # Rename
        if "rename" in command_lower:
            parts = command_lower.replace("rename", "").strip().split(" to ")
            if len(parts) == 2:
                old_name = parts[0].strip()
                new_name = parts[1].strip()
                if old_name and new_name:
                    item = await search_item(old_name, index, "folder")
                    if not item:
                        item = await search_item(old_name, index, "file")
                    if item:
                        new_path = os.path.join(os.path.dirname(item["path"]), new_name)
                        return await rename_item(item["path"], new_path)
            return "Rename command format: 'rename old_name to new_name'"

        # Delete
        if "delete" in command_lower:
            item_name = command_lower.replace("delete", "").strip()
            if item_name:
                item = await search_item(item_name, index, "folder")
                if not item:
                    item = await search_item(item_name, index, "file")
                if item:
                    return await delete_item(item["path"])
            return "Item to delete not found."

        # Open folder
        if "folder" in command_lower or "open folder" in command_lower:
            folder_name = command_lower.replace("open folder", "").replace("folder", "").strip()
            if not folder_name:
                return "Please provide a folder name."
            item = await search_item(folder_name, index, "folder")
            if item:
                return await open_folder(item["path"])
            return f"Folder not found: {folder_name}"

        # Open file (Search in indexed folders)
        item = await search_item(command, index, "file")
        if item:
            return await play_file(item["path"])

        return f"'{command}' not found (searched Desktop/Docs/Downloads)."
    except Exception as e:
        logger.error(f"Error in folder_file: {e}")
        return f"Error: {str(e)}"

@function_tool
async def run_terminal_command_tool(command: str) -> str:
    """
    Executes a system terminal command (CMD/PowerShell).
    Use this for: 'ipconfig', 'dir', 'ping', 'whoami', 'systeminfo', etc.
    WARNING: Use with caution.
    """
    try:
        # Use subprocess to run command
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        output = stdout.decode('utf-8', errors='ignore').strip()
        error = stderr.decode('utf-8', errors='ignore').strip()

        if output:
            return f"Output:\n{output[:2000]}" # Truncate long output
        if error:
            return f"Error: {error}"
        return "Command Executed (No Output)"
    except Exception as e:
        logger.error(f"Terminal Command Error: {e}")
        return f"Execution Failed: {str(e)}"


# =========================================================
# NEW TOOLS
# =========================================================

@function_tool
async def list_open_windows_tool() -> str:
    """
    Lists all visible windows with their titles, positions, sizes, window handle, and process name.
    Uses win32gui.EnumWindows to enumerate all top-level windows.
    """
    pywinauto_result = await _run_pywinauto("list_windows")
    if pywinauto_result is not None and getattr(pywinauto_result, "ok", False):
        rows = pywinauto_result.details.get("windows", [])
        if not rows:
            return "No visible windows found via pywinauto."
        lines = [f"{'PID':<10} {'Size':<12} {'Position':<14} Title"]
        lines.append("-" * 80)
        for row in rows:
            pid = row.get("process_id") or "-"
            lines.append(
                f"{pid!s:<10} {row.get('size', ''):<12} {row.get('position', ''):<14} {row.get('title', '')}"
            )
        lines.append(f"\nTotal: {len(rows)} windows (pywinauto)")
        return "\n".join(lines)

    if not win32gui:
        return "win32gui not available. Install pywin32."

    windows_info = []

    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return  # Skip untitled windows
            try:
                rect = win32gui.GetWindowRect(hwnd)
                x, y, x2, y2 = rect
                width = x2 - x
                height = y2 - y

                # Get process name
                process_name = "unknown"
                if win32process:
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        if psutil:
                            try:
                                proc = psutil.Process(pid)
                                process_name = proc.name()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                process_name = f"PID:{pid}"
                        else:
                            process_name = f"PID:{pid}"
                    except Exception as _e:
                        logger.debug("ignored Exception: %s", _e)

                windows_info.append({
                    "handle": hwnd,
                    "title": title,
                    "process": process_name,
                    "position": f"({x}, {y})",
                    "size": f"{width}x{height}",
                })
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)

    win32gui.EnumWindows(enum_callback, None)

    if not windows_info:
        return "No visible windows found."

    lines = [f"{'Handle':<10} {'Process':<25} {'Size':<12} {'Position':<14} Title"]
    lines.append("-" * 100)
    for w in windows_info:
        lines.append(
            f"{w['handle']:<10} {w['process']:<25} {w['size']:<12} {w['position']:<14} {w['title']}"
        )
    lines.append(f"\nTotal: {len(windows_info)} windows")
    return "\n".join(lines)


@function_tool
async def snap_window_tool(window_title: str, position: str = "left") -> str:
    """
    Snaps a window to left/right/top-left/top-right of the screen (like Windows Snap).
    Uses win32gui.MoveWindow to reposition and resize the window.

    Args:
        window_title: The title (or partial title) of the window to snap.
        position: Where to snap - 'left', 'right', 'top-left', 'top-right'.
    """
    if not win32gui:
        return "win32gui not available. Install pywin32."

    position = position.lower().strip()
    valid_positions = ["left", "right", "top-left", "top-right"]
    if position not in valid_positions:
        return f"Invalid position '{position}'. Use one of: {', '.join(valid_positions)}"

    # Get screen dimensions
    try:
        screen_w = win32gui.GetSystemMetrics(0)  # SM_CXSCREEN
        screen_h = win32gui.GetSystemMetrics(1)  # SM_CYSCREEN
    except Exception:
        screen_w, screen_h = 1920, 1080  # Fallback

    # Calculate target rectangle
    half_w = screen_w // 2
    half_h = screen_h // 2

    snap_map = {
        "left":      (0, 0, half_w, screen_h),
        "right":     (half_w, 0, half_w, screen_h),
        "top-left":  (0, 0, half_w, half_h),
        "top-right": (half_w, 0, half_w, half_h),
    }

    target_x, target_y, target_w, target_h = snap_map[position]

    hwnd = _find_window_hwnd(window_title)
    if not hwnd:
        return f"Window not found: {window_title}"

    try:
        # Restore window first if it is maximized/minimized
        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] != win32con.SW_SHOWNORMAL:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            await asyncio.sleep(0.2)

        win32gui.MoveWindow(hwnd, target_x, target_y, target_w, target_h, True)
        actual_title = win32gui.GetWindowText(hwnd)
        return f"Snapped '{actual_title}' to {position} ({target_w}x{target_h} at {target_x},{target_y})."
    except Exception as e:
        return f"Error snapping window: {str(e)}"


@function_tool
async def always_on_top_tool(window_title: str, enable: bool = True) -> str:
    """
    Sets a window to always stay on top (or removes always-on-top).
    Uses win32gui.SetWindowPos with HWND_TOPMOST / HWND_NOTOPMOST.

    Args:
        window_title: The title (or partial title) of the window.
        enable: True to set always-on-top, False to remove it.
    """
    if not win32gui:
        return "win32gui not available. Install pywin32."

    hwnd = _find_window_hwnd(window_title)
    if not hwnd:
        return f"Window not found: {window_title}"

    try:
        flag = win32con.HWND_TOPMOST if enable else win32con.HWND_NOTOPMOST
        win32gui.SetWindowPos(
            hwnd, flag, 0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )
        actual_title = win32gui.GetWindowText(hwnd)
        state = "always-on-top" if enable else "normal (not on top)"
        return f"'{actual_title}' set to {state}."
    except Exception as e:
        return f"Error setting always-on-top: {str(e)}"


@function_tool
async def switch_to_window_tool(window_title: str) -> str:
    """
    Brings a specific window to the foreground and gives it focus.
    Uses win32gui.SetForegroundWindow.

    Args:
        window_title: The title (or partial title) of the window to switch to.
    """
    pywinauto_result = await _run_pywinauto("focus_window", window_title)
    if pywinauto_result is not None and getattr(pywinauto_result, "ok", False):
        return pywinauto_result.message

    if not win32gui:
        return "win32gui not available. Install pywin32."

    hwnd = _find_window_hwnd(window_title)
    if not hwnd:
        return f"Window not found: {window_title}"

    try:
        # If minimized, restore first
        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] == win32con.SW_SHOWMINIMIZED:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            await asyncio.sleep(0.2)

        win32gui.SetForegroundWindow(hwnd)
        actual_title = win32gui.GetWindowText(hwnd)
        return f"Switched to: '{actual_title}'"
    except Exception as e:
        # Fallback: try using pygetwindow
        try:
            if gw:
                title_low = window_title.lower().strip()
                for window in gw.getAllWindows():
                    if title_low in window.title.lower():
                        if window.isMinimized:
                            window.restore()
                        window.activate()
                        return f"Switched to: '{window.title}' (via pygetwindow fallback)"
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        return f"Error switching window: {str(e)}"
