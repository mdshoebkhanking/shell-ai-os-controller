"""
Shell OS 1.0.0 — Premium Desktop AI Interface.
Matches reference HTML designs exactly: tonal depth, glass morphism,
no-line philosophy, ambient glows, premium typography, spacious layouts.
"""

from __future__ import annotations

import os as _os
_os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
_os.environ.setdefault("OMP_NUM_THREADS", "1")

import asyncio, json, logging, math, os, random, re, sys, time as _time
from collections import deque
from datetime import datetime

# Module-level logger so the Phase 10 `logger.debug("ignored ...")` calls
# (added by the silent-except sweep) resolve correctly. Without this the
# UI crashes with `NameError: name 'logger' is not defined` the first time
# an exception is swallowed (e.g. missing `pandas` metadata on this host).
logger = logging.getLogger("shell_ui")
APP_VERSION = "1.0.0"
APP_CREATOR = "mdshoebking"
APP_CREDIT = f"Created by {APP_CREATOR}"

_ui_dir = os.path.dirname(os.path.abspath(__file__))
if _ui_dir not in sys.path:
    sys.path.insert(0, _ui_dir)

from PyQt6.QtCore import (QPointF, QRectF, Qt, QThread, QTimer, pyqtSignal,
                           QElapsedTimer, QObject, QSize, QPropertyAnimation,
                           QEasingCurve, QPoint, QCoreApplication, QUrl)
from PyQt6.QtGui import (QColor, QFont, QIcon, QPainter, QPainterPath, QPen,
                          QPixmap, QRadialGradient, QLinearGradient, QBrush,
                          QPalette, QFontDatabase, QDesktopServices)
from PyQt6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout,
                              QLabel, QMainWindow, QPushButton, QSizePolicy,
                              QGraphicsDropShadowEffect, QVBoxLayout, QWidget,
                              QStackedWidget, QScrollArea, QTextEdit, QLineEdit,
                              QSlider, QSpacerItem, QGraphicsOpacityEffect,
                              QComboBox, QFileDialog, QToolTip, QSplitter,
                              QListWidget, QListWidgetItem)


def _shell_logo_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(os.path.join(_ui_dir, "shell_logo.png"))
    if pixmap.isNull():
        return pixmap
    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

try:
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
except Exception as _e:
    logger.debug("QtWebEngine share context setup failed: %s", _e)

from sound_fx import SoundFX

_USE_3D_ORB = False
try:
    from shell_orb_3d import ShellOrb3D; _USE_3D_ORB = True
except Exception as e:
    logger.debug("Optional 3D orb unavailable; using native voice visualizer: %s", e)
if not _USE_3D_ORB:
    try: from ai_orb import AIOrb
    except Exception: AIOrb = None

try: import psutil
except Exception: psutil = None
try: import GPUtil
except Exception: GPUtil = None

from shell_ai_runtime import (
    brain_has_providers,
    brain_provider_names,
    get_brain,
    has_configured_ai_key,
    reload_brain_providers,
)
from shell_realtime_audio_runtime import LiveKitAudioClient


def _load_socketio_client_class():
    from shell_network_runtime import SocketIOClient

    return SocketIOClient


def _create_socketio_client(*args, **kwargs):
    return _load_socketio_client_class()(*args, **kwargs)


def __getattr__(name):
    if name == "SocketIOClient":
        return _load_socketio_client_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _hub_base_url_candidates(default_url="http://localhost:5000"):
    candidates = []
    env_url = str(os.environ.get("SHELL_HUB_URL", "")).strip()
    if env_url: candidates.append(env_url.rstrip("/"))
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        hint = os.path.join(root, ".shell_hub_port")
        if os.path.exists(hint):
            with open(hint, "r", encoding="utf-8") as _hf:
                txt = _hf.read().strip()
            if txt.isdigit(): candidates.append(f"http://127.0.0.1:{int(txt)}")
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)
    candidates.append(default_url.rstrip("/"))
    for p in (5000, 5001, 5002, 5003): candidates.append(f"http://127.0.0.1:{p}")
    seen, unique = set(), []
    for c in candidates:
        c = c.strip().rstrip("/")
        if c and c not in seen: seen.add(c); unique.append(c)
    return unique

def _resolve_hub_base_url(default_url="http://localhost:5000"):
    return _hub_base_url_candidates(default_url)[0]

def _resolve_token_url():
    env = str(os.environ.get("SHELL_TOKEN_URL", "")).strip()
    return env if env else f"{_resolve_hub_base_url()}/token"


def _hub_auth_token():
    return (os.environ.get("SHELL_HUB_TOKEN") or os.environ.get("SHELL_API_TOKEN") or "").strip()


def _hub_socket_auth():
    token = _hub_auth_token()
    return {"token": token} if token else None


def _hub_auth_headers(extra=None):
    headers = dict(extra or {})
    token = _hub_auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _api_auth_headers(extra=None):
    headers = dict(extra or {})
    token = (os.environ.get("SHELL_V2_TOKEN") or os.environ.get("SHELL_API_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _sync_settings_backend(values: dict, timeout: float = 0.5) -> dict:
    """Post UI settings to the hub, falling back to the local backend store."""
    import json as _json
    import urllib.request as _ur

    payload = {"settings": values or {}}
    body = _json.dumps(payload).encode("utf-8")
    headers = _hub_auth_headers({"Content-Type": "application/json"})
    last_error = None
    for base in _hub_base_url_candidates():
        try:
            req = _ur.Request(base.rstrip("/") + "/settings", data=body, headers=headers, method="POST")
            with _ur.urlopen(req, timeout=timeout) as resp:
                result = _json.loads(resp.read().decode("utf-8") or "{}")
            result["_source"] = "hub"
            return result
        except Exception as exc:
            last_error = exc
    try:
        from shell_settings_manager import set_settings
        ok, msg, applied = set_settings(payload["settings"])
        return {"ok": ok, "message": msg, "settings": applied, "_source": "local", "_hub_error": str(last_error)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "_source": "unavailable", "_hub_error": str(last_error)}


def _mcp_base_url_candidates(default_url="http://127.0.0.1:3333"):
    candidates = []
    env_url = str(os.environ.get("SHELL_MCP_URL", "")).strip()
    if env_url:
        candidates.append(env_url.rstrip("/"))
    port = str(os.environ.get("SHELL_MCP_PORT", "")).strip()
    if port.isdigit():
        candidates.append(f"http://127.0.0.1:{int(port)}")
        candidates.append(f"http://localhost:{int(port)}")
    candidates.extend([default_url.rstrip("/"), "http://localhost:3333"])
    unique = []
    for item in candidates:
        clean = str(item).strip().rstrip("/")
        if clean and clean not in unique:
            unique.append(clean)
    return unique


def _mcp_auth_headers(extra=None):
    headers = dict(extra or {})
    token = os.environ.get("SHELL_MCP_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _post_mcp_action(payload, timeout=20):
    import json as _json
    import urllib.request as _ur
    last_error = None
    body = _json.dumps(payload).encode("utf-8")
    headers = _mcp_auth_headers({"Content-Type": "application/json"})
    for base in _mcp_base_url_candidates():
        try:
            req = _ur.Request(base, data=body, headers=headers, method="POST")
            with _ur.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return _json.loads(raw)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(str(last_error) if last_error else "MCP request failed")


# =====================================================================
#  Backend Clients (unchanged)
# =====================================================================

class ShellActionExecutor:
    """Detects actionable commands in user text and executes matching shell tools."""

    # Each entry: (keywords_list, module_name, function_name, arg_extractor_description)
    ACTION_MAP = [
        # ═══════════════ NETWORK & INTERNET (before search so 'ping google' doesn't trigger search) ═══════════════
        # Ping (must be before Google search!)
        (["ping"],
         "shell_network", "ping_host_tool", "ping"),
        # DNS lookup
        (["dns lookup", "dns check", "domain lookup"],
         "shell_network", "dns_lookup_tool", "dns"),
        # Port check
        (["port check", "port scan", "port open"],
         "shell_network", "check_port_tool", "portcheck"),
        # Traceroute
        (["traceroute", "trace route", "network path"],
         "shell_network", "traceroute_tool", "traceroute"),
        # Network info
        (["network info", "wifi info", "ip address", "mera ip", "my ip"],
         "shell_network", "get_network_info", "netinfo"),

        # ═══════════════ CORE TOOLS ═══════════════
        # Screenshot
        (["screenshot", "ss le", "screen capture", "screenshot le", "snap le"],
         "shell_screenshot", "take_screenshot_tool", "screenshot"),
        # Google search
        (["google", "search kar", "search karo", "search for", "google kar", "google pe"],
         "shell_google_search", "google_search", "search"),
        # Calculator
        (["calculate", "calc", "hisaab", "kitna hota", "plus", "minus", "multiply", "divide", "math"],
         "shell_calculator", "calculate_tool", "calculate"),
        # Weather
        (["weather", "mausam", "temperature", "garmi", "sardi", "barish"],
         "shell_get_whether", "get_weather", "weather"),
        # News
        (["news", "khabar", "headlines", "latest news", "aaj ki khabar"],
         "shell_news", "get_latest_news_tool", "news"),
        # Translator
        (["translate", "tarjuma", "translation", "translate kar"],
         "shell_translator", "translate_text_tool", "translate"),
        # Clipboard
        (["copy", "clipboard", "paste", "copy kar", "copy karo"],
         "shell_clipboard", "clipboard_copy_tool", "clipboard"),

        # ═══════════════ SYSTEM & POWER ═══════════════
        # System info
        (["system info", "system status", "pc info", "computer info", "ram kitni"],
         "shell_terminal", "system_info_tool", "sysinfo"),
        # Full system specs
        (["full specs", "hardware info", "system specs", "spec dikha", "processor"],
         "shell_system_pro", "get_system_specs_tool", "specs"),
        # Running processes
        (["processes", "running tasks", "task manager", "kya chal raha", "process list"],
         "shell_system_pro", "get_running_processes_tool", "processes"),
        # Kill process
        (["kill process", "process band", "task kill", "process end"],
         "shell_system_pro", "kill_process_tool", "killproc"),
        # Battery
        (["battery", "battery status", "charge kitni", "battery level"],
         "shell_system_pro", "get_battery_status_tool", "battery"),
        # Brightness
        (["brightness", "screen bright", "roshan", "dhoop"],
         "shell_system_pro", "set_brightness_tool", "brightness"),
        # WiFi password
        (["wifi password", "wifi ka password", "wifi pass"],
         "shell_system_pro", "get_wifi_password_tool", "wifipass"),
        # Saved WiFi
        (["saved wifi", "wifi list", "wifi networks"],
         "shell_system_pro", "list_saved_wifi_tool", "wifilist"),
        # Installed apps
        (["installed apps", "installed programs", "software list", "apps list", "kya install hai"],
         "shell_system_pro", "get_installed_apps_tool", "programs"),
        # Startup apps
        (["startup apps", "startup programs", "boot programs"],
         "shell_system_pro", "get_startup_apps_tool", "startup"),
        # System uptime
        (["uptime", "kitni der se chalu", "system uptime"],
         "shell_system_pro", "get_system_uptime_tool", "uptime"),
        # Disk cleanup
        (["disk cleanup", "clean disk", "junk clean", "temp files delete"],
         "shell_system_pro", "disk_cleanup_tool", "cleanup"),
        # Shutdown/Restart/Sleep
        (["shutdown", "restart", "sleep mode", "band karo pc", "pc band"],
         "shell_system_pro", "system_power_tool", "power"),
        # System health scan
        (["health check", "system scan", "system health", "diagnostic"],
         "shell_diagnostics", "scan_system_health", "healthscan"),
        # Resource hogs
        (["resource hog", "heavy process", "slow kyu", "memory leak"],
         "shell_diagnostics", "list_resource_hogs_tool", "reshogs"),
        # Disk health
        (["disk health", "hard disk check", "storage health"],
         "shell_diagnostics", "check_disk_health_tool", "diskhealth"),
        # Network health
        (["network health", "internet check", "connection check"],
         "shell_diagnostics", "check_network_health_tool", "nethealth"),
        # Event log
        (["event log", "error log", "windows error", "system errors"],
         "shell_diagnostics", "get_event_log_errors_tool", "eventlog"),

        # ═══════════════ CODE & DEVELOPMENT ═══════════════
        # Write code
        (["write code", "code likh", "create code", "code bana", "program likh"],
         "shell_code_engine", "write_code_tool", "writecode"),
        # Run code
        (["run code", "code chala", "execute code", "code run"],
         "shell_code_engine", "execute_code_tool", "runcode"),
        # Create app
        (["create app", "app bana", "fullstack app", "project bana", "web app bana"],
         "shell_code_engine", "create_fullstack_app_tool", "createapp"),
        # Terminal
        (["run command", "terminal", "cmd", "command chala", "powershell"],
         "shell_terminal", "run_command_tool", "terminal"),

        # ═══════════════ DOWNLOAD & YOUTUBE ═══════════════
        # Download file
        (["download file", "file download", "download kar"],
         "shell_downloader", "download_file_tool", "download"),
        # YouTube audio download
        (["youtube download", "audio download", "youtube audio", "song download", "gana download"],
         "shell_downloader", "download_youtube_audio_tool", "ytdownload"),
        # YouTube info
        (["youtube info", "video info", "youtube details"],
         "shell_youtube_summary", "get_video_info_tool", "ytinfo"),
        # YouTube summary
        (["youtube summary", "video summary", "video summarize"],
         "shell_youtube_summary", "video_summary_tool", "ytsummary"),

        # ═══════════════ IMAGE & AI ART ═══════════════
        # Generate image
        (["generate image", "image bana", "photo bana", "picture bana", "image generate", "draw", "art bana"],
         "shell_image_ai", "generate_image_tool", "imagegen"),
        # Image styles
        (["image styles", "art styles", "style list"],
         "shell_image_ai", "list_image_styles_tool", "imgstyles"),
        # OCR — image to text
        (["ocr", "text from image", "image se text", "image read", "text extract"],
         "shell_ocr", "ocr_image_tool", "ocr"),
        # OCR screenshot
        (["screen ocr", "screen text", "screen se text"],
         "shell_ocr", "ocr_screenshot_tool", "ocrscrn"),
        # Image convert
        (["convert image", "image convert", "jpg to png", "png to jpg"],
         "shell_file_converter", "convert_image_format_tool", "imgconvert"),
        # Resize image
        (["resize image", "image resize", "photo resize", "image size change"],
         "shell_file_converter", "resize_image_tool", "imgresize"),
        # Compress image
        (["compress image", "image compress", "photo compress", "image chhota"],
         "shell_file_converter", "compress_image_tool", "imgcompress"),

        # ═══════════════ PDF TOOLS ═══════════════
        # Read PDF
        (["read pdf", "pdf padh", "pdf text", "pdf extract", "pdf open"],
         "shell_pdf", "pdf_extract_text_tool", "pdfread"),
        # PDF info
        (["pdf info", "pdf details", "pdf pages"],
         "shell_pdf", "pdf_info_tool", "pdfinfo"),
        # Merge PDF
        (["merge pdf", "pdf merge", "pdf jodo", "combine pdf"],
         "shell_pdf", "pdf_merge_tool", "pdfmerge"),
        # Split PDF
        (["split pdf", "pdf split", "pdf todo"],
         "shell_pdf", "pdf_split_tool", "pdfsplit"),
        # Protect PDF
        (["protect pdf", "pdf lock", "pdf password"],
         "shell_pdf", "pdf_protect_tool", "pdfprotect"),

        # ═══════════════ QR CODE ═══════════════
        # Generate QR
        (["qr generate", "qr bana", "qr code bana", "create qr", "make qr"],
         "shell_qr", "qr_generate_tool", "qrgen"),
        # Read QR
        (["qr read", "qr scan", "qr decode", "qr padh"],
         "shell_qr", "qr_read_tool", "qrread"),
        # WiFi QR
        (["wifi qr", "qr wifi"],
         "shell_qr", "qr_wifi_tool", "qrwifi"),

        # ═══════════════ SECURITY & CRYPTO ═══════════════
        # Hash text
        (["hash", "md5", "sha256", "hash bana"],
         "shell_hash", "hash_string_tool", "hash"),
        # Hash file
        (["hash file", "file hash", "checksum"],
         "shell_hash", "hash_file_tool", "hashfile"),
        # Encrypt
        (["encrypt", "encrypt kar", "text encrypt"],
         "shell_crypto", "encrypt_text_tool", "encrypt"),
        # Decrypt
        (["decrypt", "decrypt kar", "text decrypt"],
         "shell_crypto", "decrypt_text_tool", "decrypt"),
        # Password generator
        (["password generate", "generate password", "password bana", "strong password", "random password"],
         "shell_crypto", "generate_password_tool", "passgen"),
        # Encrypt file
        (["encrypt file", "file encrypt", "file lock"],
         "shell_crypto", "encrypt_file_tool", "encryptfile"),

        # ═══════════════ ZIP & ARCHIVE ═══════════════
        # Create zip
        (["zip bana", "create zip", "compress folder", "zip create"],
         "shell_zip", "zip_create_tool", "zipcreate"),
        # Extract zip
        (["unzip", "extract zip", "zip extract", "zip khol"],
         "shell_zip", "zip_extract_tool", "zipextract"),
        # List zip contents
        (["zip list", "zip contents", "zip mein kya"],
         "shell_zip", "zip_list_tool", "ziplist"),

        # ═══════════════ STOCK & CRYPTO MARKET ═══════════════
        # Stock price
        (["stock price", "share price", "stock check", "share rate"],
         "shell_stock", "stock_price_tool", "stock"),
        # Stock info
        (["stock info", "company info", "share info"],
         "shell_stock", "stock_info_tool", "stockinfo"),
        # Crypto price
        (["bitcoin", "crypto price", "bitcoin price", "ethereum", "crypto rate"],
         "shell_stock", "crypto_price_tool", "crypto"),

        # ═══════════════ PRODUCTIVITY ═══════════════
        # Todo/Task
        (["todo", "task add", "task list", "kaam add", "task bana"],
         "shell_productivity", "manage_tasks_tool", "todo"),
        # Timer
        (["timer", "timer laga", "set timer", "countdown"],
         "shell_productivity", "set_timer_tool", "timer"),
        # Alarm
        (["alarm", "alarm laga", "set alarm", "wake up"],
         "shell_productivity", "set_alarm_tool", "alarm"),
        # Pomodoro
        (["pomodoro", "focus mode", "pomodoro start"],
         "shell_productivity", "pomodoro_tool", "pomodoro"),
        # Quick note
        (["quick note", "note save", "note likh", "note bana"],
         "shell_productivity", "quick_note_tool", "quicknote"),
        # Daily planner
        (["daily planner", "aaj ka plan", "din ka plan", "planner"],
         "shell_productivity", "daily_planner_tool", "planner"),
        # Habit tracker
        (["habit track", "habit add", "habit list", "aadat"],
         "shell_productivity", "habit_tracker_tool", "habit"),

        # ═══════════════ SCHEDULER ═══════════════
        # Schedule task
        (["schedule task", "baad mein chala", "schedule kar"],
         "shell_scheduler", "schedule_task_tool", "schedule"),
        # List schedules
        (["schedules", "scheduled tasks", "schedule list"],
         "shell_scheduler", "list_schedules_tool", "schedlist"),

        # ═══════════════ MEMORY & KNOWLEDGE ═══════════════
        # Remember
        (["remember", "yaad rakh", "save memory", "yaad kar"],
         "shell_memory", "update_memory_tool", "remember"),
        # Recall
        (["recall", "yaad karo", "kya yaad hai", "memory search"],
         "shell_memory", "search_memory_tool", "recall"),
        # Show memory
        (["show memory", "full memory", "sab yaad"],
         "shell_memory", "get_full_memory", "fullmemory"),
        # Learn knowledge
        (["learn", "seekh", "knowledge add", "fact add"],
         "shell_knowledge", "add_knowledge_tool", "learn"),
        # Recall knowledge
        (["knowledge", "kya jaanta", "knowledge search"],
         "shell_knowledge", "recall_knowledge_tool", "knowrecall"),
        # Learn from file
        (["learn from file", "file se seekh", "file learn"],
         "shell_knowledge", "learn_from_file_tool", "learnfile"),

        # ═══════════════ WINDOW & APP CONTROL ═══════════════
        # Open app
        (["open app", "app khol", "launch app", "start app"],
         "shell_window_CTRL", "open_app", "openapp"),
        # Close app
        (["close app", "app band", "close window", "window band"],
         "shell_window_CTRL", "close_app", "closeapp"),
        # Minimize
        (["minimize", "minimize kar", "chhota kar"],
         "shell_window_CTRL", "minimize_window", "minimize"),
        # Maximize
        (["maximize", "maximize kar", "bada kar", "fullscreen"],
         "shell_window_CTRL", "maximize_window", "maximize"),
        # List windows
        (["open windows", "window list", "kya khula hai"],
         "shell_window_CTRL", "list_open_windows_tool", "winlist"),
        # Snap window
        (["snap window", "window snap", "side mein"],
         "shell_window_CTRL", "snap_window_tool", "snapwin"),
        # Always on top
        (["always on top", "upar rakh", "pin window"],
         "shell_window_CTRL", "always_on_top_tool", "ontop"),

        # ═══════════════ KEYBOARD & MOUSE ═══════════════
        # Type text
        (["type text", "text type", "likh do", "type kar"],
         "keyboard_mouse_CTRL", "type_text_tool", "typetxt"),
        # Press key
        (["press key", "key press", "key daba"],
         "keyboard_mouse_CTRL", "press_key_tool", "presskey"),
        # Hotkey
        (["hotkey", "shortcut", "key combo"],
         "keyboard_mouse_CTRL", "press_hotkey_tool", "hotkey"),
        # Volume control
        (["volume", "volume up", "volume down", "mute", "awaz"],
         "keyboard_mouse_CTRL", "control_volume_tool", "volume"),
        # Mouse click
        (["mouse click", "click kar", "right click", "double click"],
         "keyboard_mouse_CTRL", "mouse_click_tool", "click"),

        # ═══════════════ JSON & REGEX ═══════════════
        # JSON format
        (["json format", "format json", "json pretty"],
         "shell_json_tools", "json_format_tool", "jsonformat"),
        # JSON validate
        (["json validate", "json check", "valid json"],
         "shell_json_tools", "json_validate_tool", "jsoncheck"),
        # Regex test
        (["regex test", "regex check", "regex match"],
         "shell_regex", "regex_test_tool", "regex"),

        # ═══════════════ VIDEO TOOLS ═══════════════
        # Video info
        (["video info", "video details"],
         "shell_video", "video_info_tool", "vidinfo"),
        # Extract audio from video
        (["extract audio", "video se audio", "audio nikaal"],
         "shell_video", "video_extract_audio_tool", "vidaudio"),
        # Video trim
        (["video trim", "video cut", "video crop", "video kaato"],
         "shell_video", "video_trim_tool", "vidtrim"),
        # Video convert
        (["video convert", "convert video"],
         "shell_video", "video_convert_tool", "vidconvert"),

        # ═══════════════ PRESENTATION ═══════════════
        # Create PPT
        (["create presentation", "presentation bana", "ppt bana", "slides bana", "powerpoint"],
         "shell_ppt_god", "create_presentation_tool", "pptcreate"),
        # Add slide
        (["add slide", "slide add", "slide daal"],
         "shell_ppt_god", "add_slide_to_ppt_tool", "pptslide"),

        # ═══════════════ EMAIL ═══════════════
        # Send email
        (["send email", "email bhej", "mail send", "mail bhej"],
         "shell_email_tool", "send_email_tool", "emailsend"),
        # Draft email
        (["draft email", "email likh", "email draft", "professional email"],
         "shell_email_tool", "draft_professional_email_tool", "emaildraft"),

        # ═══════════════ GAMES ═══════════════
        # Rock paper scissors
        (["rock paper scissors", "patthar kainchi kagaz"],
         "shell_games", "rock_paper_scissors_tool", "rps"),
        # Coin flip
        (["coin flip", "toss", "heads or tails", "sikka uchalo"],
         "shell_games", "coin_flip_tool", "coinflip"),
        # Dice roll
        (["dice roll", "pasa phenko", "roll dice"],
         "shell_games", "dice_roll_tool", "dice"),
        # Quiz
        (["quiz", "trivia", "sawal", "quiz khelo"],
         "shell_games", "trivia_quiz_tool", "quiz"),
        # Word game
        (["word game", "word scramble", "shabd khel"],
         "shell_games", "word_scramble_tool", "wordgame"),

        # ═══════════════ FILE & FOLDER ═══════════════
        # File search
        (["file search", "file dhundho", "file find", "file khojo", "find file"],
         "shell_file_opner", "search_files_tool", "filesearch"),
        # Notepad
        (["notepad", "notepad mein likh"],
         "shell_file_opner", "write_to_notepad_tool", "notepad"),
        # Organizer
        (["organize", "folder organize", "files organize", "clean folder", "sort files"],
         "shell_organizer", "organize_folder_tool", "organize"),
        # Large files
        (["large files", "badi files", "space kha raha"],
         "shell_organizer", "find_large_files_tool", "largefiles"),
        # Open URL / browser
        (["open website", "website khol", "browser open", "url open", "open url"],
         "shell_browser_CTRL", "open_new_tab_tool", "browser"),
        # Music
        (["play music", "gana", "song", "music chala", "gaana"],
         "shell_music", "play_audio_tool", "music"),
    ]

    # Filler words to strip from extracted arguments
    _FILLERS = {"kar", "karo", "kro", "do", "de", "dikha", "dikhao", "bata", "batao",
                "le", "lo", "lao", "pe", "par", "mein", "se", "ka", "ki", "ke",
                "hai", "ho", "hain", "for", "the", "a", "an", "please", "pls",
                "about", "on", "in", "of", "ye", "yeh", "woh", "wo", "is", "us",
                "kaisa", "kaisi", "kaise", "kya", "open", "khol", "chala",
                "search", "find", "dhundho", "khojo", "likh", "baja",
                "bhai", "yaar", "ji", "na", "to", "toh", "bhi", "aur",
                "mere", "mera", "meri", "tera", "teri", "uska", "uski",
                "abhi", "jaldi", "achhe", "achi", "acha", "theek",
                "sab", "sara", "sari", "show", "give", "tell", "get",
                "my", "me", "i", "just", "now", "can", "you", "will",
                "mere liye", "mujhe", "hume", "humko"}

    @classmethod
    def _clean_arg(cls, raw, original_text):
        """Strip filler words from raw arg to get the real argument."""
        words = raw.split()
        cleaned = [w for w in words if w.lower() not in cls._FILLERS]
        result = " ".join(cleaned).strip().strip('"').strip("'").strip()
        return result  # Can be empty — executor handles 0-arg functions

    @classmethod
    def _json_object_arg(cls, arg):
        text = str(arg or "").strip()
        if not text.startswith("{"):
            return None
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else None
        except Exception:
            return None

    @classmethod
    def _parse_write_code_args(cls, arg):
        text = str(arg or "").strip()
        if not text:
            return None
        parsed = cls._json_object_arg(text)
        if parsed and parsed.get("filename") and parsed.get("content") is not None:
            return parsed

        kv_match = re.search(
            r"(?:file(?:name)?\s*=\s*|file(?:name)?\s+)(?P<filename>[^\s:]+)"
            r".*?(?:content\s*=\s*|content\s+|code\s*=\s*|code\s+)(?P<content>.+)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if kv_match:
            return {
                "filename": kv_match.group("filename").strip().strip('"').strip("'"),
                "content": kv_match.group("content").strip(),
            }

        filename_pattern = r"(?P<filename>[A-Za-z0-9_. -]+\.(?:py|js|html|css|txt|md|json|bat|cmd|ps1|sh|yaml|yml))"
        colon_match = re.match(filename_pattern + r"\s*[:\-]\s*(?P<content>.+)", text, flags=re.IGNORECASE | re.DOTALL)
        if colon_match:
            return {
                "filename": colon_match.group("filename").strip(),
                "content": colon_match.group("content").strip(),
            }

        split_match = re.match(filename_pattern + r"\s+(?P<content>.+)", text, flags=re.IGNORECASE | re.DOTALL)
        if split_match:
            return {
                "filename": split_match.group("filename").strip(),
                "content": split_match.group("content").strip(),
            }
        return None

    @classmethod
    def _missing_args_message(cls, func_name, required_names):
        joined = ", ".join(required_names)
        if func_name == "write_code_tool":
            return (
                "Tool needs filename and content. Example:\n"
                "write code hello.py: print('hello from Shell')\n\n"
                "For real file writing, code-write safety must also be enabled by the user."
            )
        return f"Tool needs required argument(s): {joined}. Please give those details in chat."

    @classmethod
    def _prepare_call(cls, func_name, arg, required_params):
        required_names = [p.name for p in required_params]
        text_arg = str(arg or "").strip()

        if func_name == "write_code_tool":
            parsed = cls._parse_write_code_args(text_arg)
            if parsed:
                return [], parsed, ""
            return [], {}, cls._missing_args_message(func_name, required_names)

        parsed = cls._json_object_arg(text_arg)
        if parsed:
            missing = [name for name in required_names if name not in parsed]
            if missing:
                return [], {}, cls._missing_args_message(func_name, missing)
            return [], parsed, ""

        if len(required_params) == 0:
            return [], {}, ""
        if len(required_params) == 1 and text_arg:
            return [text_arg], {}, ""
        if len(required_params) == 1:
            return [], {}, cls._missing_args_message(func_name, required_names)
        return [], {}, cls._missing_args_message(func_name, required_names)

    @classmethod
    def detect_action(cls, text):
        """Returns (module, func_name, action_type, cleaned_arg) or None.
        Uses word-boundary matching to avoid false positives like 'paper' matching 'pe'."""
        t = text.lower().strip()
        for keywords, module, func, action_type in cls.ACTION_MAP:
            for kw in keywords:
                # Use word-boundary regex for single words, plain 'in' for multi-word phrases
                if " " in kw:
                    if kw in t:
                        remaining = t.replace(kw, "", 1).strip()
                        arg = cls._clean_arg(remaining, text)
                        return module, func, action_type, arg
                else:
                    if re.search(r'\b' + re.escape(kw) + r'\b', t):
                        remaining = re.sub(r'\b' + re.escape(kw) + r'\b', '', t, count=1).strip()
                        arg = cls._clean_arg(remaining, text)
                        return module, func, action_type, arg
        return None

    @classmethod
    def execute(cls, module_name, func_name, arg):
        """Import and run the tool function synchronously. Returns result string."""
        import importlib, inspect
        try:
            mod = importlib.import_module(module_name)
            func = getattr(mod, func_name)

            # Unwrap decorated tool to get the real function
            inner = func
            while hasattr(inner, '__wrapped__'):
                inner = inner.__wrapped__

            # Check how many args the function expects
            try:
                sig = inspect.signature(inner)
                required_params = [p for p in sig.parameters.values()
                                   if p.default is inspect.Parameter.empty
                                   and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
                n_required = len(required_params)
            except (ValueError, TypeError):
                n_required = 1  # Assume 1 arg if we can't inspect

            call_args, call_kwargs, arg_error = cls._prepare_call(func_name, arg, required_params)
            if arg_error:
                return arg_error

            # Execute — handle both async and sync
            result = None
            is_async = asyncio.iscoroutinefunction(inner)
            if is_async:
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(inner(*call_args, **call_kwargs))
                finally:
                    loop.close()
            else:
                result = inner(*call_args, **call_kwargs)

            return str(result) if result else "Done — no output."
        except TypeError as te:
            return f"Tool argument error: {te}"
        except Exception as e:
            return f"Tool error: {e}"


class ShellV2Worker(QThread):
    """Posts the user's text to the Shell-v2 brain at /api/say and emits the reply.

    Why: the in-process MultiBrain depends on per-process env keys which the
    .pyw launcher does not load, leaving every chat turn stuck on
    "All Brains Failed". Shell-v2 already runs on 127.0.0.1:8765 with the
    real keys + 44 agents, so the UI just talks to it directly.
    """
    reply_ready = pyqtSignal(str)
    reply_error = pyqtSignal(str)
    chunk_received = pyqtSignal(str)
    stream_done = pyqtSignal()
    latency_event = pyqtSignal(str, object)

    SHELL_V2_URL = os.environ.get("SHELL_V2_URL", "http://127.0.0.1:8765").rstrip("/")
    TIMEOUT_S = float(os.environ.get("SHELL_V2_TIMEOUT_S", "12"))

    def __init__(self, message: str, history=None, parent=None):
        super().__init__(parent)
        self._message = message
        self._history = history or []

    @staticmethod
    def stream_enabled() -> bool:
        return os.environ.get("SHELL_V2_STREAM", "1").strip().lower() in ("1", "true", "yes", "on")

    def _emit_latency(self, event: str, started: float, **payload):
        try:
            payload["elapsed_ms"] = round((_time.perf_counter() - started) * 1000.0, 2)
            self.latency_event.emit(event, payload)
        except Exception:
            pass

    def run(self):
        started = _time.perf_counter()
        try:
            import re as _re
            import urllib.request
            import urllib.error
            import json as _json

            # Optional `@agent_name: prompt` prefix routes the turn to a
            # specific Shell-v2 agent. Lets the user (or a test harness)
            # target any of the 44 registered agents from the chat box.
            text = self._message
            agent: str | None = None
            m = _re.match(r"^@([A-Za-z_][\w]*)\s*:\s*(.+)$", text, flags=_re.DOTALL)
            if m:
                agent = m.group(1)
                text = m.group(2).strip()

            body: dict = {"text": text}
            if agent:
                body["agent"] = agent

            payload = _json.dumps(body).encode("utf-8")
            self._emit_latency("request_prepared", started, bytes=len(payload), agent=agent or "")

            # ── Streaming path ────────────────────────────────────────
            # Enabled by default via env var `SHELL_V2_STREAM=1`. Hits the new
            # /api/say-stream SSE endpoint, parses event/data line pairs,
            # emits chunk_received per `delta` and reply_ready on `end`.
            # Any failure falls through to the legacy non-streaming POST
            # below so the UI never hangs on a broken stream.
            if self.stream_enabled():
                try:
                    self._emit_latency("stream_connect_start", started)
                    sreq = urllib.request.Request(
                        f"{self.SHELL_V2_URL}/api/say-stream",
                        data=payload,
                        headers=_api_auth_headers({
                            "Content-Type": "application/json",
                            "Accept": "text/event-stream",
                        }),
                        method="POST",
                    )
                    full_reply: str = ""
                    saw_end = False
                    saw_error: str | None = None
                    first_chunk_seen = False
                    with urllib.request.urlopen(sreq, timeout=self.TIMEOUT_S) as sresp:
                        self._emit_latency("stream_headers", started)
                        # SSE frames are separated by a blank line; within
                        # one frame each line is `event: <kind>` or
                        # `data: <json>`. We accumulate per-frame and
                        # flush on the blank line.
                        cur_event: str | None = None
                        cur_data: list[str] = []
                        while True:
                            raw = sresp.readline()
                            if not raw:
                                break
                            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                            if line == "":
                                # Frame boundary — dispatch what we have.
                                if cur_event is not None and cur_data:
                                    payload_str = "\n".join(cur_data)
                                    try:
                                        ev_payload = _json.loads(payload_str)
                                    except Exception:
                                        ev_payload = {"raw": payload_str}
                                    if cur_event == "delta":
                                        chunk = str(ev_payload.get("text") or "")
                                        if chunk:
                                            full_reply += chunk
                                            if not first_chunk_seen:
                                                first_chunk_seen = True
                                                self._emit_latency("first_text_chunk", started, chars=len(chunk))
                                            try:
                                                self.chunk_received.emit(chunk)
                                            except Exception:
                                                pass
                                    elif cur_event == "end":
                                        full_reply = str(ev_payload.get("full_reply") or full_reply)
                                        saw_end = True
                                    elif cur_event == "error":
                                        saw_error = str(ev_payload.get("message") or "stream error")
                                        break
                                cur_event = None
                                cur_data = []
                                continue
                            if line.startswith(":"):
                                # SSE comment / heartbeat — ignore.
                                continue
                            if line.startswith("event:"):
                                cur_event = line[len("event:"):].strip()
                            elif line.startswith("data:"):
                                cur_data.append(line[len("data:"):].lstrip())
                            # Other field lines (id:, retry:) are ignored.
                    if saw_error:
                        self._emit_latency("stream_error", started, message=saw_error)
                        self.reply_error.emit(f"Shell-v2 stream error: {saw_error}")
                        return
                    if saw_end:
                        self._emit_latency("stream_done", started, chars=len(full_reply))
                        try:
                            self.stream_done.emit()
                        except Exception:
                            pass
                        if full_reply.strip():
                            self.reply_ready.emit(full_reply)
                        else:
                            self.reply_error.emit("Shell-v2 stream returned empty reply")
                        return
                    # No `end` frame — treat as broken stream and fall
                    # through to non-streaming path.
                    self._emit_latency("stream_missing_end", started)
                except urllib.error.URLError as exc:
                    self._emit_latency("stream_unreachable", started, error=str(exc)[:180])
                    pass  # fall through to non-streaming
                except Exception as exc:
                    self._emit_latency("stream_exception", started, error=str(exc)[:180])
                    pass  # fall through to non-streaming

            # ── Legacy non-streaming path (default + fallback) ────────
            self._emit_latency("nonstream_start", started)
            req = urllib.request.Request(
                f"{self.SHELL_V2_URL}/api/say",
                data=payload,
                headers=_api_auth_headers({"Content-Type": "application/json"}),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT_S) as resp:
                body_b = resp.read().decode("utf-8", errors="replace")
            data = _json.loads(body_b)
            reply = (data.get("reply") or "").strip()
            if reply:
                self._emit_latency("nonstream_done", started, chars=len(reply))
                self.reply_ready.emit(reply)
            else:
                self._emit_latency("nonstream_empty", started)
                self.reply_error.emit("Shell-v2 returned empty reply")
        except urllib.error.URLError as e:
            self._emit_latency("request_unreachable", started, error=str(e)[:180])
            self.reply_error.emit(f"Shell-v2 unreachable: {e}")
        except Exception as e:
            self._emit_latency("request_exception", started, error=str(e)[:180])
            self.reply_error.emit(f"Shell-v2 error: {e}")


class AIChatWorker(QThread):
    """Background thread: detects actions → runs tools, or does AI chat with memory.
    Supports streaming via chunk_received signal for real-time token display."""
    reply_ready = pyqtSignal(str)
    reply_error = pyqtSignal(str)
    chunk_received = pyqtSignal(str)  # Streaming: emits each chunk as it arrives
    stream_done = pyqtSignal()        # Signals end of streaming

    _SYSTEM_PROMPT = (
        f"You are Shell OS {APP_VERSION}, a desktop AI assistant created by {APP_CREATOR}. "
        "Be useful, honest, friendly, and natural. "
        "The user may talk in Hinglish (Hindi+English mix) — reply in the same style they use. "
        "If they speak English, reply in English. If Hinglish, reply in Hinglish. "
        "Keep answers concise but complete. Be conversational, not robotic.\n\n"
        "REAL CAPABILITIES — when configured and permitted, Shell can help with:\n"
        "SYSTEM: system info, specs, processes, kill process, battery, brightness, "
        "wifi passwords, installed apps, startup apps, uptime, disk cleanup, "
        "shutdown/restart/sleep, health scan, diagnostics, event logs\n"
        "CODE: write code, run code, create fullstack apps, terminal commands\n"
        "FILES: search files, organize folders, find large files, zip/unzip, "
        "PDF read/merge/split/protect, file conversion, image resize/compress/convert\n"
        "NETWORK: IP info, ping, DNS lookup, port check, traceroute, network health\n"
        "MEDIA: generate AI images, OCR (image to text), video info/trim/convert, "
        "extract audio, play music, screenshot\n"
        "DOWNLOAD: download files, YouTube audio download, YouTube video info/summary\n"
        "PRODUCTIVITY: todo/tasks, timer, alarm, pomodoro, quick notes, daily planner, "
        "habit tracker, scheduler, reminders\n"
        "SECURITY: encrypt/decrypt text & files, hash (MD5/SHA), password generator, "
        "QR code generate/read/WiFi QR\n"
        "MARKET: stock prices, company info, crypto prices (Bitcoin/Ethereum)\n"
        "CREATIVE: presentations (PPT), email drafting, code generation\n"
        "CONTROL: open/close/minimize/maximize apps, snap windows, always-on-top, "
        "type text, press keys, hotkeys, volume control, mouse clicks\n"
        "DATA: JSON format/validate, regex test, translate 60+ languages\n"
        "FUN: rock paper scissors, coin flip, dice roll, trivia quiz, word games\n"
        "MEMORY: remember things, recall memories, knowledge base, learn from files\n"
        "SEARCH: Google search, news, weather\n\n"
        "Do not exaggerate. Explain capabilities as real software features, not magic. "
        f"If asked who built this project, say it was built by {APP_CREATOR}. "
        "When user asks to DO something, do not pretend it happened unless an actual tool result confirms success. "
        "Never claim that email, Telegram, file, app, payment, or PC-control actions were completed from chat-only text. "
        "If the needed tool is not configured, say the exact missing setup instead of inventing success. "
        "When user asks a QUESTION, answer directly and clearly."
    )

    def __init__(self, brain, message, history=None, parent=None):
        super().__init__(parent)
        self._brain = brain
        self._message = message
        self._history = history or []

    def run(self):
        try:
            # --- Step 1: Check if this is an ACTION (do something) ---
            action = ShellActionExecutor.detect_action(self._message)
            if action:
                module, func_name, action_type, arg = action
                logging.info(f"Action detected: {action_type} -> {module}.{func_name}({arg!r})")

                # Execute the tool
                tool_result = ShellActionExecutor.execute(module, func_name, arg)

                # Send tool result to AI to format a nice reply
                if self._brain and self._brain.providers:
                    format_prompt = (
                        f"User asked: \"{self._message}\"\n"
                        f"Tool executed: {action_type}\n"
                        f"Tool result:\n{tool_result[:2000]}\n\n"
                        "Summarize the result in a friendly way for the user. "
                        "If Hinglish mein baat ho rahi thi, Hinglish mein jawab do. "
                        "Keep it concise. If there's an error, explain simply."
                    )
                    loop = asyncio.new_event_loop()
                    try:
                        reply = loop.run_until_complete(
                            self._brain.generate_response(format_prompt,
                                system_prompt="You are Shell OS, a friendly AI assistant. Format tool results nicely for the user. Be concise.",
                                mode="FAST")
                        )
                    finally:
                        try:
                            if hasattr(self._brain, "close_provider_sessions"):
                                loop.run_until_complete(self._brain.close_provider_sessions())
                        except Exception as _e:
                            logging.debug("brain provider session cleanup failed: %s", _e)
                        loop.close()

                    if reply and "All Brains Failed" not in reply:
                        self.reply_ready.emit(reply)
                        return

                # If AI formatting failed, show raw result
                self.reply_ready.emit(f"Done! Result:\n\n{tool_result[:1500]}")
                return

            # --- Step 2: Normal AI chat with conversation context ---
            # Build context from history (last 20 messages max)
            context_parts = []
            for role, text in self._history[-20:]:
                prefix = "User" if role == "user" else "Shell"
                context_parts.append(f"{prefix}: {text}")
            context_parts.append(f"User: {self._message}")
            full_prompt = "\n".join(context_parts)

            # Detect best mode based on the query
            from brain.router import SmartRouter
            mode = SmartRouter.detect_mode(self._message)

            loop = asyncio.new_event_loop()
            try:
                # Try streaming first for real-time display
                if hasattr(self._brain, 'generate_response_stream'):
                    collected = []
                    async def _stream():
                        async for chunk in self._brain.generate_response_stream(
                            full_prompt, system_prompt=self._SYSTEM_PROMPT, mode=mode
                        ):
                            # Defence — drop sentinel error chunks so they
                            # never reach the user's chat bubble even if a
                            # future provider regresses and yields them.
                            if chunk and "All Brains Failed" in str(chunk):
                                continue
                            if chunk:
                                collected.append(chunk)
                                self.chunk_received.emit(chunk)
                    try:
                        loop.run_until_complete(_stream())
                        reply = "".join(collected)
                        if reply and "All Brains Failed" not in reply:
                            self.stream_done.emit()
                            return
                    except Exception:
                        pass  # Fall through to non-streaming

                # Fallback: non-streaming chat
                if hasattr(self._brain, 'chat'):
                    reply = loop.run_until_complete(
                        self._brain.chat(full_prompt, system_prompt=self._SYSTEM_PROMPT, mode=mode)
                    )
                else:
                    reply = loop.run_until_complete(
                        self._brain.generate_response(full_prompt, system_prompt=self._SYSTEM_PROMPT, mode=mode)
                    )
            finally:
                try:
                    if hasattr(self._brain, "close_provider_sessions"):
                        loop.run_until_complete(self._brain.close_provider_sessions())
                except Exception as _e:
                    logging.debug("brain provider session cleanup failed: %s", _e)
                loop.close()

            if reply and "All Brains Failed" not in reply:
                self.reply_ready.emit(reply)
            else:
                self.reply_error.emit(reply or "Empty response")
        except Exception as e:
            self.reply_error.emit(str(e))


# =====================================================================
#  TTS runtime service
# =====================================================================

from shell_voice_runtime import (
    TTSSpeaker,
    _EDGE_TTS_AVAILABLE,
    _LOCAL_TTS_AVAILABLE,
    _system_tts_available,
)

# =====================================================================
#  Color Palette v9.1 — Reference-matched
# =====================================================================

# =====================================================================
#  ThemeEngine — Dynamic theme management
# =====================================================================

def _theme_dict_from_design_tokens(p):
    """Bridge the modern design-token palette into legacy ThemeEngine keys."""
    return {
        "bg": p.bg,
        "surface": p.surface,
        "surface_low": p.surface,
        "surface_cont": p.surface_2,
        "surface_high": p.surface_2,
        "surface_highest": p.surface_3,
        "surface_bright": p.surface_3,
        "surface_lowest": p.bg,
        "primary": p.accent,
        "primary_bold": p.accent,
        "primary_cont": p.accent_hover,
        "primary_dim": p.accent,
        "secondary": p.accent_hover,
        "sec_dim": p.accent,
        "sec_container": p.accent_soft,
        "tertiary": p.success,
        "text": p.text,
        "text_dim": p.text_muted,
        "text_muted": p.text_subtle,
        "outline": p.text_subtle,
        "outline_var": p.border,
        "error": p.error,
        "success": p.success,
        "warning": p.warning,
        "glass_bg": p.glass,
        "glass_border": p.glass_border,
        "glass_border_top": p.glass_hi,
        "glass_tonal": p.glass_strong,
        "glass_tonal_border": p.border,
    }


try:
    from shell_ui import design_tokens as _THEME_TOKENS
    _CANONICAL_THEMES = {
        name: _theme_dict_from_design_tokens(p)
        for name, p in _THEME_TOKENS.PALETTES.items()
    }
except Exception as _theme_bootstrap_error:
    logger.debug("design token theme bootstrap failed: %s", _theme_bootstrap_error)
    _CANONICAL_THEMES = {}

class ThemeEngine:
    """Singleton theme manager with multiple presets."""

    THEMES = _CANONICAL_THEMES or {
        "DARK": {
            "bg": "#080b10", "surface": "#111720", "surface_low": "#111720",
            "surface_cont": "#1a2230", "surface_high": "#1a2230",
            "surface_highest": "#242d3c", "surface_bright": "#242d3c",
            "surface_lowest": "#080b10",
            "primary": "#60a5fa", "primary_bold": "#60a5fa",
            "primary_cont": "#93c5fd", "primary_dim": "#60a5fa",
            "secondary": "#93c5fd", "sec_dim": "#60a5fa",
            "sec_container": "rgba(96,165,250,0.13)", "tertiary": "#34d399",
            "text": "#edf2f8", "text_dim": "#a4b0c0", "text_muted": "#697587",
            "outline": "#697587", "outline_var": "rgba(202,213,226,0.09)",
            "error": "#f87171", "success": "#34d399", "warning": "#fbbf24",
            "glass_bg": "rgba(22,30,42,0.58)", "glass_border": "rgba(202,213,226,0.13)",
            "glass_border_top": "rgba(226,235,247,0.13)",
            "glass_tonal": "rgba(28,38,52,0.76)", "glass_tonal_border": "rgba(202,213,226,0.09)",
        }
    }

    _instance = None

    @classmethod
    def get(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.active_name = "CYBER_NEON" if "CYBER_NEON" in self.THEMES else next(iter(self.THEMES))
        self._callbacks = []
        # Load saved theme
        try:
            import json
            cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shell_theme.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    data = json.load(f)
                    name = data.get("theme", self.active_name)
                    if name in self.THEMES:
                        self.active_name = name
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        # Sync the design_tokens palette to the loaded theme on startup
        # (otherwise C.* stays on the module-level default until first switch).
        try:
            from shell_ui import design_tokens as _DT
            _DT.set_palette_by_name(self.active_name)
        except Exception as _e:
            logger.debug("design_tokens initial palette sync failed: %s", _e)
    @property
    def t(self):
        return self.THEMES[self.active_name]

    def switch(self, name):
        if name not in self.THEMES:
            return
        self.active_name = name
        # Save preference
        try:
            import json
            cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shell_theme.json")
            with open(cfg_path, "w") as f:
                json.dump({"theme": name}, f)
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        # Update global color variables
        _apply_theme_globals(self.t)
        # Flip the design-token palette so every widget that reads
        # `design_tokens.C.*` gets the new colours. Listeners on the
        # design_tokens side then re-polish or repaint as needed.
        try:
            from shell_ui import design_tokens as _DT
            _DT.set_palette_by_name(name)
        except Exception as _e:
            logger.debug("design_tokens palette swap failed: %s", _e)
        # Notify listeners
        for cb in self._callbacks:
            try:
                cb(name)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
    def on_change(self, callback):
        self._callbacks.append(callback)

    @property
    def theme_names(self):
        return list(self.THEMES.keys())


def _apply_theme_globals(t):
    """Update module-level color constants from theme dict."""
    global C_BG, C_SURFACE, C_SURFACE_LOW, C_SURFACE_CONT, C_SURFACE_HIGH
    global C_SURFACE_HIGHEST, C_SURFACE_BRIGHT, C_SURFACE_LOWEST
    global C_PRIMARY, C_PRIMARY_BOLD, C_PRIMARY_CONT, C_PRIMARY_DIM
    global C_SECONDARY, C_SEC_DIM, C_SEC_CONTAINER, C_TERTIARY
    global C_ON_SURFACE, C_TEXT, C_TEXT_DIM, C_TEXT_MUTED
    global C_OUTLINE, C_OUTLINE_VAR
    global C_ERROR, C_SUCCESS, C_WARNING

    C_BG = t["bg"]; C_SURFACE = t["surface"]; C_SURFACE_LOW = t["surface_low"]
    C_SURFACE_CONT = t["surface_cont"]; C_SURFACE_HIGH = t["surface_high"]
    C_SURFACE_HIGHEST = t["surface_highest"]; C_SURFACE_BRIGHT = t["surface_bright"]
    C_SURFACE_LOWEST = t["surface_lowest"]
    C_PRIMARY = t["primary"]; C_PRIMARY_BOLD = t["primary_bold"]
    C_PRIMARY_CONT = t["primary_cont"]; C_PRIMARY_DIM = t["primary_dim"]
    C_SECONDARY = t["secondary"]; C_SEC_DIM = t["sec_dim"]
    C_SEC_CONTAINER = t["sec_container"]; C_TERTIARY = t["tertiary"]
    C_ON_SURFACE = t["text"]; C_TEXT = t["text"]; C_TEXT_DIM = t["text_dim"]
    C_TEXT_MUTED = t["text_muted"]; C_OUTLINE = t["outline"]
    C_OUTLINE_VAR = t["outline_var"]
    C_ERROR = t["error"]; C_SUCCESS = t["success"]; C_WARNING = t["warning"]


# Initialize theme and color globals
_te = ThemeEngine.get()
_t = _te.t

C_BG            = _t["bg"]
C_SURFACE       = _t["surface"]
C_SURFACE_LOW   = _t["surface_low"]
C_SURFACE_CONT  = _t["surface_cont"]
C_SURFACE_HIGH  = _t["surface_high"]
C_SURFACE_HIGHEST = _t["surface_highest"]
C_SURFACE_BRIGHT  = _t["surface_bright"]
C_SURFACE_LOWEST  = _t["surface_lowest"]

C_PRIMARY       = _t["primary"]
C_PRIMARY_BOLD  = _t["primary_bold"]
C_PRIMARY_CONT  = _t["primary_cont"]
C_PRIMARY_DIM   = _t["primary_dim"]
C_SECONDARY     = _t["secondary"]
C_SEC_DIM       = _t["sec_dim"]
C_SEC_CONTAINER = _t["sec_container"]
C_TERTIARY      = _t["tertiary"]

C_ON_SURFACE    = _t["text"]
C_TEXT          = _t["text"]
C_TEXT_DIM      = _t["text_dim"]
C_TEXT_MUTED    = _t["text_muted"]
C_OUTLINE       = _t["outline"]
C_OUTLINE_VAR   = _t["outline_var"]

C_ERROR         = _t["error"]
C_SUCCESS       = _t["success"]
C_WARNING       = _t["warning"]

# Font selection — safe: only queries QFontDatabase if QApplication already exists
def _pick_font(candidates, fallback):
    if QApplication.instance() is None:
        return fallback
    try:
        families = QFontDatabase.families()
        for c in candidates:
            if c in families:
                return c
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)
    return fallback

_FONT = _pick_font(["Arial", "Segoe UI", "Helvetica Neue", "Noto Sans"], "Arial")
_MONO = _pick_font(["Cascadia Code", "Consolas", "SF Mono", "Menlo", "Courier New"], "Courier New")


# =====================================================================
#  Style Helpers
# =====================================================================

def _glass_card(extra=""):
    """iOS-style frosted glass card — multi-layer translucent with luminous top edge + frost bloom."""
    t = ThemeEngine.get().t
    return (f"background: qlineargradient(x1:0,y1:0,x2:0.15,y2:1,"
            f"stop:0 {t['glass_border_top']}, stop:0.08 {t['glass_tonal']}, "
            f"stop:0.52 {t['glass_bg']}, stop:1 {t['glass_bg']}); "
            f"border:1px solid {t['glass_border']}; "
            f"border-top:2px solid {t['glass_border_top']}; "
            f"border-left:1px solid {t['glass_border_top']}; "
            f"border-radius:22px; {extra}")

def _tonal_card(extra=""):
    """Deeper frosted glass variant for dashboard cards — richer iOS frost."""
    t = ThemeEngine.get().t
    return (f"background: qlineargradient(x1:0,y1:0,x2:0.2,y2:1,"
            f"stop:0 {t['glass_border_top']}, stop:0.10 {t['glass_tonal']}, "
            f"stop:0.62 {t['surface_high']}, stop:1 {t['glass_bg']}); "
            f"border:1px solid {t['glass_tonal_border']}; "
            f"border-top:2px solid {t['glass_border']}; "
            f"border-left:1px solid {t['glass_border']}; "
            f"border-radius:22px; {extra}")

def _glass_btn(extra=""):
    """iOS-style translucent button — frosted with luminous edge."""
    t = ThemeEngine.get().t
    return (f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {t['glass_border_top']}, stop:0.12 {t['surface_high']}, "
            f"stop:1 {t['glass_bg']}); "
            f"border:1px solid {t['glass_tonal_border']}; "
            f"border-top:2px solid {t['glass_border']}; "
            f"border-left:1px solid {t['glass_border']}; "
            f"border-radius:16px; {extra}")

def _glass_input(extra=""):
    """iOS-style frosted input field — recessed glass with inner depth."""
    t = ThemeEngine.get().t
    return (f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {t['surface_low']}, stop:0.12 {t['glass_bg']}, "
            f"stop:0.88 {t['glass_tonal']}, stop:1 {t['surface_high']}); "
            f"border:1px solid {t['glass_border']}; "
            f"border-bottom:2px solid {t['glass_border_top']}; "
            f"border-radius:24px; {extra}")

def _glass_pill(extra=""):
    """iOS-style frosted pill badge — thin glass with shimmer edge."""
    t = ThemeEngine.get().t
    return (f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {t['glass_border_top']}, stop:0.16 {t['glass_tonal']}, "
            f"stop:0.84 {t['glass_bg']}, stop:1 {t['surface_high']}); "
            f"border:1px solid {t['glass_tonal_border']}; "
            f"border-top:2px solid {t['glass_border']}; "
            f"border-left:1px solid {t['glass_border']}; "
            f"border-radius:24px; {extra}")


def _accent_text_color():
    try:
        from shell_ui.design_tokens import accent_text_color
        return accent_text_color()
    except Exception:
        return "#041018"

def _section_label():
    return (f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:10px; "
            f"font-weight:700; letter-spacing:4px; text-transform:uppercase;")

def _body_text():
    return f"color:{C_TEXT}; font-family:'{_FONT}'; font-size:14px;"

def _mono_text():
    return f"color:{C_TEXT}; font-family:'{_MONO}'; font-size:13px;"

def _glow_shadow(widget, color=None, radius=24, alpha=50):
    if color is None:
        color = ThemeEngine.get().t["primary_bold"]
    eff = QGraphicsDropShadowEffect(widget)
    c = QColor(color); c.setAlpha(alpha)
    eff.setColor(c); eff.setBlurRadius(radius); eff.setOffset(0, 3)
    widget.setGraphicsEffect(eff)

def _frost_shadow(widget, radius=40, alpha=20):
    """iOS-style soft diffused shadow for glass panels."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setColor(QColor(0, 0, 0, alpha))
    eff.setBlurRadius(radius); eff.setOffset(0, 8)
    widget.setGraphicsEffect(eff)


_icon_cache = {}

def _make_icon_pixmap(icon_name, size=20, color=C_TEXT_DIM):
    """Create a hand-painted icon pixmap using QPainter. Cached for performance."""
    cache_key = (icon_name, size, color)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]
    pix = _render_icon_pixmap(icon_name, size, color)
    _icon_cache[cache_key] = pix
    return pix

def _clear_icon_cache():
    """Clear icon cache (call on theme change)."""
    _icon_cache.clear()

def _render_icon_pixmap(icon_name, size, color):
    """Render a hand-painted icon pixmap using QPainter."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QColor(color)
    pen = QPen(c, 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    m = size * 0.2  # margin
    s = size - 2 * m  # drawable area

    if icon_name == "mute":
        # Microphone with slash
        cx, cy = size / 2, size / 2
        r = s * 0.18
        p.drawRoundedRect(QRectF(cx - r, m + s * 0.05, r * 2, s * 0.45), r, r)
        p.drawArc(QRectF(cx - r * 1.6, cy - s * 0.08, r * 3.2, s * 0.42), 0, -180 * 16)
        p.drawLine(QPointF(cx, cy + s * 0.22), QPointF(cx, cy + s * 0.38))
        # Slash across
        slash_pen = QPen(c, 2.0)
        slash_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(slash_pen)
        p.drawLine(QPointF(m + s * 0.15, m + s * 0.15), QPointF(m + s * 0.85, m + s * 0.85))

    elif icon_name == "mic":
        # Microphone
        cx, cy = size / 2, size / 2
        r = s * 0.18
        p.drawRoundedRect(QRectF(cx - r, m + s * 0.05, r * 2, s * 0.45), r, r)
        p.drawArc(QRectF(cx - r * 1.7, cy - s * 0.10, r * 3.4, s * 0.45), 0, -180 * 16)
        p.drawLine(QPointF(cx, cy + s * 0.24), QPointF(cx, cy + s * 0.42))
        p.drawLine(QPointF(cx - s * 0.17, cy + s * 0.42), QPointF(cx + s * 0.17, cy + s * 0.42))

    elif icon_name == "power":
        # Power symbol (circle with line at top)
        cx, cy = size / 2, size / 2
        r = s * 0.38
        pen2 = QPen(c, 2.2)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen2)
        p.drawArc(QRectF(cx - r, cy - r + s * 0.05, r * 2, r * 2), 50 * 16, 260 * 16)
        p.drawLine(QPointF(cx, cy - r - s * 0.02), QPointF(cx, cy + s * 0.05))

    elif icon_name == "eye":
        # Eye icon
        cx, cy = size / 2, size / 2
        # Eye outline
        path = QPainterPath()
        path.moveTo(m, cy)
        path.cubicTo(m + s * 0.2, cy - s * 0.35, m + s * 0.8, cy - s * 0.35, m + s, cy)
        path.cubicTo(m + s * 0.8, cy + s * 0.35, m + s * 0.2, cy + s * 0.35, m, cy)
        p.drawPath(path)
        # Pupil
        p.setBrush(c)
        p.drawEllipse(QPointF(cx, cy), s * 0.12, s * 0.12)

    elif icon_name == "trash":
        # Trash can
        p.setPen(QPen(c, 1.6, cap=Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(m + s * 0.22, m + s * 0.26), QPointF(m + s * 0.78, m + s * 0.26))
        p.drawLine(QPointF(m + s * 0.42, m + s * 0.14), QPointF(m + s * 0.58, m + s * 0.14))
        p.drawLine(QPointF(m + s * 0.36, m + s * 0.20), QPointF(m + s * 0.64, m + s * 0.20))
        body = QRectF(m + s * 0.28, m + s * 0.30, s * 0.44, s * 0.56)
        p.drawRoundedRect(body, 2, 2)
        p.drawLine(QPointF(m + s * 0.42, m + s * 0.40), QPointF(m + s * 0.42, m + s * 0.76))
        p.drawLine(QPointF(m + s * 0.58, m + s * 0.40), QPointF(m + s * 0.58, m + s * 0.76))

    elif icon_name == "chat":
        # Chat bubble
        p.drawRoundedRect(QRectF(m, m, s * 0.85, s * 0.7), 3, 3)
        p.drawLine(QPointF(m + s * 0.2, m + s * 0.7), QPointF(m + s * 0.1, m + s * 0.92))
        p.drawLine(QPointF(m + s * 0.1, m + s * 0.92), QPointF(m + s * 0.4, m + s * 0.7))

    elif icon_name == "voice":
        # Waveform / mic
        cx = size / 2
        p.setPen(QPen(c, 1.8, cap=Qt.PenCapStyle.RoundCap))
        heights = [0.2, 0.5, 0.85, 0.5, 0.2]
        total_w = s * 0.7
        gap = total_w / (len(heights) - 1)
        x_start = cx - total_w / 2
        for i, h in enumerate(heights):
            x = x_start + i * gap
            half_h = s * h * 0.4
            p.drawLine(QPointF(x, size / 2 - half_h), QPointF(x, size / 2 + half_h))

    elif icon_name == "play":
        # Play triangle
        p.setBrush(c)
        p.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.moveTo(m + s * 0.32, m + s * 0.18)
        path.lineTo(m + s * 0.32, m + s * 0.82)
        path.lineTo(m + s * 0.82, m + s * 0.50)
        path.closeSubpath()
        p.drawPath(path)

    elif icon_name == "pause":
        # Pause bars
        p.setBrush(c)
        p.setPen(Qt.PenStyle.NoPen)
        bar_w = s * 0.18
        gap = s * 0.16
        x1 = m + s * 0.28
        y = m + s * 0.18
        h = s * 0.64
        p.drawRoundedRect(QRectF(x1, y, bar_w, h), 2.5, 2.5)
        p.drawRoundedRect(QRectF(x1 + bar_w + gap, y, bar_w, h), 2.5, 2.5)

    elif icon_name == "system":
        # Dashboard / grid
        p.setPen(QPen(c, 1.4, cap=Qt.PenCapStyle.RoundCap))
        gap = 1.5
        half = s * 0.45
        # Top-left large square
        p.drawRoundedRect(QRectF(m, m, half, half), 2, 2)
        # Top-right
        p.drawRoundedRect(QRectF(m + half + gap, m, half, half * 0.4), 2, 2)
        # Bottom-right large
        p.drawRoundedRect(QRectF(m + half + gap, m + half * 0.4 + gap, half, half * 0.6 - gap), 2, 2)
        # Bottom-left
        p.drawRoundedRect(QRectF(m, m + half + gap, half, half), 2, 2)

    elif icon_name == "tools":
        # Wrench-like tool mark
        p.setPen(QPen(c, 2.0, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        p.drawLine(QPointF(m + s * 0.25, m + s * 0.75), QPointF(m + s * 0.72, m + s * 0.28))
        p.drawLine(QPointF(m + s * 0.62, m + s * 0.18), QPointF(m + s * 0.82, m + s * 0.38))
        p.drawLine(QPointF(m + s * 0.18, m + s * 0.82), QPointF(m + s * 0.32, m + s * 0.68))

    elif icon_name == "settings":
        # Gear icon
        cx, cy = size / 2, size / 2
        outer = s * 0.42
        inner = s * 0.28
        teeth = 6
        p.setPen(QPen(c, 1.5, cap=Qt.PenCapStyle.RoundCap))
        path = QPainterPath()
        for i in range(teeth * 2):
            angle = math.radians(i * 360 / (teeth * 2) - 90)
            r = outer if i % 2 == 0 else inner
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        p.drawPath(path)
        # Center hole
        p.drawEllipse(QPointF(cx, cy), s * 0.1, s * 0.1)

    elif icon_name == "palette":
        # Paint palette
        cx, cy = size / 2, size / 2
        p.drawEllipse(QPointF(cx, cy), s * 0.4, s * 0.35)
        p.setBrush(c)
        for dx, dy in [(-0.15, -0.12), (0.1, -0.15), (0.2, 0.05), (-0.05, 0.12)]:
            p.drawEllipse(QPointF(cx + s * dx, cy + s * dy), 2, 2)

    elif icon_name == "equalizer":
        # EQ bars
        p.setPen(QPen(c, 2.0, cap=Qt.PenCapStyle.RoundCap))
        heights = [0.5, 0.8, 0.35, 0.65]
        total_w = s * 0.6
        gap = total_w / (len(heights) - 1)
        x_start = size / 2 - total_w / 2
        for i, h in enumerate(heights):
            x = x_start + i * gap
            top = m + s * (1 - h)
            bot = m + s
            p.drawLine(QPointF(x, top), QPointF(x, bot))

    elif icon_name == "send":
        # Arrow pointing right
        p.setPen(QPen(c, 2.2, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        cx, cy = size / 2, size / 2
        p.drawLine(QPointF(m + s * 0.15, cy), QPointF(m + s * 0.85, cy))
        p.drawLine(QPointF(m + s * 0.55, cy - s * 0.3), QPointF(m + s * 0.85, cy))
        p.drawLine(QPointF(m + s * 0.55, cy + s * 0.3), QPointF(m + s * 0.85, cy))

    elif icon_name == "new_session":
        # Plus icon
        cx, cy = size / 2, size / 2
        p.setPen(QPen(c, 2.0, cap=Qt.PenCapStyle.RoundCap))
        r = s * 0.3
        p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
        p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))

    p.end()
    return pix


# =====================================================================
#  TopBar
# =====================================================================

class TopBar(QWidget):
    # Emitted when the user clicks the profile-avatar button. The host
    # (ShellHoloUI) wires this up to open the AvatarMenu dropdown.
    avatar_clicked = pyqtSignal()
    theme_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Apple-glassy upgrade: dropped from 56 → 44px (closer to macOS
        # Sonoma toolbar height of 38–44).
        self.setFixedHeight(44)
        # Mac-style vibrancy panel: translucent QSS overlay only.
        # NOTE: GlassBackdrop (real parent.grab() blur) was REMOVED here —
        # its 80ms snapshot loop was a primary cause of nav-button clicks
        # being dropped (UI thread saturation + hide/show events tearing
        # through the widget tree). Static vibrancy gradient looks close
        # enough at this scale and is essentially free.
        try:
            from shell_ui.design_tokens import (
                C as _DC, accent_text_color as _accent_txt, vibrancy_layer_qss as _vib,
            )
            _bar_text = _DC.text
            _bar_text_muted = _DC.text_muted
            _gb = _DC.glass_border
            _bar_panel = _DC.glass_strong
            _bar_hi = _DC.glass_hi
            _bar_hover = _DC.hover_overlay
            _bar_accent = _DC.accent
            _bar_accent_hover = _DC.accent_hover
            _bar_accent_text = _accent_txt()
            _bar_bg = _DC.bg
            self.setStyleSheet(
                _vib("dark", bordered=False, radius=0)
                + f" border-bottom:1px solid {_gb};"
            )
            self._backdrop = None
        except Exception:
            # Soft fallback — keeps the original behaviour if the new
            # primitives aren't importable for any reason.
            _g  = "rgba(50,44,38,0.70)"
            _gh = "rgba(255,240,225,0.10)"
            _gb = "rgba(255,240,225,0.10)"
            _bar_text = "#f3ece1"; _bar_text_muted = "#a39a8d"
            _bar_panel = _g
            _bar_hi = _gh
            _bar_hover = "rgba(255,240,225,0.10)"
            _bar_accent = "#22d3ee"
            _bar_accent_hover = "#67e8f9"
            _bar_accent_text = "#041018"
            _bar_bg = "#06080f"
            self.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
                f"  stop:0 {_gh}, stop:0.04 {_g}, stop:1 {_g}); "
                f"border:none; border-bottom:1px solid {_gb};"
            )
            self._backdrop = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(0)

        # "Shell" logo — soft, quiet, no aggressive negative kerning.
        logo = QLabel("Shell")
        logo.setStyleSheet(
            f"color:{_bar_text}; font-family:'{_FONT}'; font-size:18px; "
            f"font-weight:600; border:none; background:transparent;"
        )
        lay.addWidget(logo)
        lay.addSpacing(16)

        # Divider
        divider = QLabel()
        divider.setFixedSize(1, 16)
        divider.setStyleSheet(f"background:{_gb}; border:none;")
        lay.addWidget(divider)
        lay.addSpacing(16)

        # Context label — page name, mixed case, no letter-spacing.
        self.context_lbl = QLabel("Chat")
        self.context_lbl.setStyleSheet(
            f"color:{_bar_text_muted}; font-family:'{_FONT}'; font-size:13px; "
            f"font-weight:500; border:none; background:transparent;"
        )
        lay.addWidget(self.context_lbl)

        lay.addStretch(1)

        # Right side: token count (updates dynamically)
        self.token_lbl = QLabel("0 tokens")
        self._token_count = 0
        self.token_lbl.setStyleSheet(f"""
            color:{C_TEXT_MUTED}; font-family:'{_MONO}'; font-size:10px;
            border:none; background:transparent;
        """)
        lay.addWidget(self.token_lbl)
        lay.addSpacing(12)

        # Voice output toggle button
        self.voice_btn = QPushButton()
        self.voice_btn.setFixedSize(32, 32)
        self.voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.voice_btn.setIcon(QIcon(_make_icon_pixmap("voice", 16, _bar_accent)))
        self.voice_btn.setIconSize(QSize(16, 16))
        self.voice_btn.setToolTip("Voice ON — Shell speaks replies")
        self.voice_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {_bar_hi}, stop:0.08 {_bar_panel}, stop:1 {_bar_panel});
                border:1px solid {_gb};
                border-top:1px solid {_bar_hi};
                border-radius:16px;
            }}
            QPushButton:hover {{
                background:{_bar_hover};
                border:1px solid {_bar_accent};
            }}
        """)
        lay.addWidget(self.voice_btn)
        lay.addSpacing(8)

        # Notification bell — opens the persistent NotificationCenter.
        # The actual click handler is wired by ShellHoloUI; we just expose
        # the button + a `set_unread_count(int)` helper that paints the
        # accent badge top-right.
        try:
            from shell_ui.notification_center import make_bell_pixmap as _bell_px
        except Exception:
            _bell_px = None
        self.bell_btn = QPushButton()
        self.bell_btn.setFixedSize(32, 32)
        self.bell_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bell_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bell_btn.setToolTip("Notifications")
        if _bell_px is not None:
            try:
                self.bell_btn.setIcon(QIcon(_bell_px(18, _bar_text)))
                self.bell_btn.setIconSize(QSize(18, 18))
            except Exception as _e:
                logger.debug("bell icon paint failed: %s", _e)
        self.bell_btn.setStyleSheet(
            f"QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
            f"  stop:0 {_bar_hi}, stop:0.08 {_bar_panel}, stop:1 {_bar_panel}); "
            f"  border:1px solid {_gb}; "
            f"  border-top:1px solid {_bar_hi}; "
            f"  border-radius:16px; }} "
            f"QPushButton:hover {{ background:{_bar_hover}; "
            f"  border:1px solid {_bar_accent}; }}"
        )
        # Badge — small accent pill drawn over the bell. Hidden when 0.
        self.bell_badge = QLabel("", self.bell_btn)
        self.bell_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bell_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._restyle_bell_badge(0)
        self.bell_badge.hide()
        lay.addWidget(self.bell_btn)
        lay.addSpacing(8)

        # Theme quick-toggle — cycles through registered themes.
        self.theme_btn = QPushButton("◐")
        self.theme_btn.setFixedSize(32, 32)
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setToolTip("Cycle theme")
        self.theme_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        try:
            from shell_ui.design_tokens import C as _DC2
            _surf2 = _DC2.surface_2; _ac = _DC2.accent
            _txtm = _DC2.text_muted; _accent_soft = _DC2.accent_soft
        except Exception:
            _surf2 = "#141d33"; _ac = "#00f0ff"
            _txtm = "#8fa3bd"; _accent_soft = "rgba(0,240,255,0.12)"
        self.theme_btn.setStyleSheet(
            f"QPushButton {{ background:{_surf2}; color:{_txtm}; "
            f"  border:none; border-radius:16px; "
            f"  font-size:16px; "
            f"}} "
            f"QPushButton:hover {{ background:{_accent_soft}; color:{_ac}; }}"
        )
        # The actual theme cycle wires to ThemeEngine via main window.
        # We stash the click and let ShellHoloUI hook it.
        self.theme_btn.clicked.connect(self._cycle_theme_clicked)
        lay.addWidget(self.theme_btn)
        lay.addSpacing(8)

        # Profile avatar with user initial — now a clickable button so
        # the host can pop the AvatarMenu dropdown beneath it. Same size,
        # same gradient fill, same border. The button forwards clicks via
        # the `avatar_clicked` signal so ShellHoloUI can wire it up
        # without TopBar needing to know about AvatarMenu.
        self.avatar = QPushButton("U")
        self.avatar.setFixedSize(32, 32)
        self.avatar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.avatar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.avatar.setToolTip("Profile menu")
        self.avatar.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {_bar_accent}, stop:1 {_bar_accent_hover});
                border-radius: 16px; border: 1px solid {_gb};
                color:{_bar_accent_text}; font-family:'{_FONT}'; font-size:13px; font-weight:800;
            }}
            QPushButton:hover {{
                border: 1px solid {_bar_accent};
            }}
        """)
        self.avatar.clicked.connect(self.avatar_clicked.emit)
        lay.addWidget(self.avatar)

    def set_context(self, text):
        # Keep mixed case — no more SHOUTING. The page label is just
        # informational, not an alert.
        self.context_lbl.setText(text)

    def _restyle_bell_badge(self, count: int):
        """Repaint the bell badge label QSS for the current count.

        0  → hidden. 1 → tiny accent dot. 2-9 → pill with number. 9+ → '9+'.
        """
        try:
            from shell_ui.design_tokens import C as _DCB, accent_text_color as _accent_txt
            ac = _DCB.accent
            bg_dark = _DCB.bg
            ac_text = _accent_txt()
        except Exception:
            ac = "#00f0ff"; bg_dark = "#06080f"
            ac_text = "#041018"
        if count <= 0:
            self.bell_badge.setText("")
            self.bell_badge.setVisible(False)
            return
        if count == 1:
            # Tiny accent dot.
            self.bell_badge.setText("")
            self.bell_badge.setFixedSize(8, 8)
            self.bell_badge.move(20, 4)
            self.bell_badge.setStyleSheet(
                f"background-color:{ac}; "
                f"border:1.5px solid {bg_dark}; "
                f"border-radius:4px;"
            )
        else:
            label = "9+" if count > 9 else str(count)
            # Pill — auto width via setFixedSize after measuring.
            w = 18 if len(label) >= 2 else 14
            self.bell_badge.setText(label)
            self.bell_badge.setFixedSize(w, 14)
            self.bell_badge.move(32 - w - 1, 1)
            self.bell_badge.setStyleSheet(
                f"background-color:{ac}; color:{ac_text}; "
                f"border:1.5px solid {bg_dark}; "
                f"border-radius:7px; "
                f"font-family:'{_FONT}'; font-size:9px; font-weight:800; "
                f"padding:0 2px;"
            )
        self.bell_badge.setVisible(True)
        self.bell_badge.raise_()

    def set_unread_count(self, count: int):
        """Public — called by ShellHoloUI when the store changes."""
        try:
            self._restyle_bell_badge(int(count or 0))
        except Exception as _e:
            logger.debug("bell badge update failed: %s", _e)

    def _cycle_theme_clicked(self):
        """Quick-cycle through registered ThemeEngine themes."""
        try:
            te = ThemeEngine.get()
            names = list(te.theme_names)
            if not names:
                return
            try:
                idx = names.index(te.active_name)
            except ValueError:
                idx = -1
            nxt = names[(idx + 1) % len(names)]
            self.theme_requested.emit(nxt)
        except Exception as _e:
            logger.debug("theme cycle failed: %s", _e)

    def add_tokens(self, count):
        self._token_count += count
        if self._token_count >= 1000:
            self.token_lbl.setText(f"{self._token_count:,} tokens")
        else:
            self.token_lbl.setText(f"{self._token_count} tokens")

    def reset_tokens(self):
        self._token_count = 0
        self.token_lbl.setText("0 tokens")


# =====================================================================
#  SidebarNav
# =====================================================================

class SidebarNav(QWidget):
    page_changed = pyqtSignal(int)
    new_session = pyqtSignal()
    # Emitted when the user clicks a row in the chat history list. The
    # main window switches the ChatPage over to that conversation.
    history_session_clicked = pyqtSignal(str)
    history_rename_requested = pyqtSignal(str, str)
    history_delete_requested = pyqtSignal(str)

    NAV_ITEMS = [
        ("Chat", 0, "chat"),
        ("Voice", 1, "voice"),
        ("System", 2, "system"),
        ("Tools", 3, "tools"),
        ("Settings", 4, "settings"),
    ]

    CONTEXT_LABELS = ["CORE INTERFACE", "VOICE CORE", "SYSTEM DASHBOARD", "TOOLS / MCP", "CONFIGURATION"]

    def __init__(self, parent=None, history_store=None):
        super().__init__(parent)
        # Apple-glassy upgrade: 256 → 232 (closer to macOS Sonoma sidebar).
        self.setFixedWidth(232)
        self._history_store = history_store
        self.history_list = None  # Set below if `history_store` was supplied
        # Mac-style vibrancy sidebar: translucent QSS overlay only.
        # NOTE: GlassBackdrop (real parent.grab() blur) was REMOVED here —
        # its 80ms timer was blocking the UI thread, queueing nav-button
        # click events for 5–15s and dropping presses entirely while the
        # snapshot loop hide()/show()'d this widget. The static vibrancy
        # gradient still gives the frosted look without that cost.
        try:
            from shell_ui.design_tokens import (
                C as _DC, vibrancy_layer_qss as _vib,
            )
            _gb = _DC.glass_border
            self.setStyleSheet(
                _vib("dark", bordered=False, radius=0)
                + f" border-right:1px solid {_gb};"
            )
            self._backdrop = None
        except Exception:
            # Fallback — preserves old behaviour if new primitives fail.
            _g = "rgba(50,44,38,0.70)"; _gh = "rgba(255,240,225,0.10)"
            _gb = "rgba(255,240,225,0.10)"
            self.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
                f"  stop:0 {_gh}, stop:0.05 {_g}, stop:1 {_g}); "
                f"border:none; border-right:1px solid {_gb};"
            )
            self._backdrop = None
        self._active = 0
        self._sfx = SoundFX()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 28, 20, 20)
        lay.setSpacing(0)

        # Shell OS branding
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)

        # Brand block — calmer, no halo, version is a quiet small label.
        try:
            from shell_ui.design_tokens import C as _DC, accent_text_color as _accent_txt
            _accent = _DC.accent
            _accent_text = _accent_txt()
            _txt = _DC.text
            _txt_subtle = _DC.text_subtle
            _bg_card = _DC.surface_2
            _input_bg = _DC.glass
            _input_hi = _DC.glass_hi
            _input_border = _DC.glass_border
            _input_focus = _DC.accent
            _input_placeholder = _DC.text_subtle
        except Exception:
            _accent = "#d97757"; _txt = "#f3ece1"; _txt_subtle = "#6f675c"
            _accent_text = "#ffffff"
            _bg_card = "#2c2823"
            _input_bg = "rgba(22,30,46,0.55)"
            _input_hi = "rgba(255,255,255,0.10)"
            _input_border = "rgba(255,255,255,0.12)"
            _input_focus = _accent
            _input_placeholder = _txt_subtle

        icon = QLabel()
        icon.setFixedSize(36, 36)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _logo = _shell_logo_pixmap(36)
        if _logo.isNull():
            icon.setText("Shell")
            icon.setStyleSheet(
                f"background:{_accent}; border-radius:10px; border:none; "
                f"color:{_accent_text}; font-family:'{_FONT}'; font-size:11px; font-weight:700;"
            )
        else:
            icon.setPixmap(_logo)
            icon.setStyleSheet("background:transparent; border:none;")
        brand_row.addWidget(icon)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand = QLabel("Shell")
        brand.setStyleSheet(
            f"color:{_txt}; font-family:'{_FONT}'; font-size:18px; "
            f"font-weight:700; border:none; background:transparent;"
        )
        brand_text.addWidget(brand)
        ver = QLabel(f"v{APP_VERSION}")
        ver.setStyleSheet(
            f"color:{_txt_subtle}; font-family:'{_FONT}'; font-size:11px; "
            f"font-weight:500; border:none; background:transparent;"
        )
        brand_text.addWidget(ver)
        credit = QLabel(APP_CREDIT)
        credit.setStyleSheet(
            f"color:{_txt_subtle}; font-family:'{_FONT}'; font-size:10px; "
            f"font-weight:500; border:none; background:transparent;"
        )
        brand_text.addWidget(credit)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        lay.addLayout(brand_row)
        lay.addSpacing(24)

        # New Session button — quiet primary, no glow, no letter-spacing.
        new_btn = QPushButton("  New chat")
        new_btn.setFixedHeight(40)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            from shell_ui.design_tokens import C as _DC2, accent_text_color as _accent_txt2
            _ac = _DC2.accent; _ach = _DC2.accent_hover
            _ac_text = _accent_txt2()
        except Exception:
            _ac = "#d97757"; _ach = "#c66848"
            _ac_text = "#ffffff"
        new_btn.setIcon(QIcon(_make_icon_pixmap("new_session", 16, _ac_text)))
        new_btn.setIconSize(QSize(16, 16))
        new_btn.setStyleSheet(
            f"QPushButton {{ "
            f"  background-color:{_ac}; color:{_ac_text}; "
            f"  border:none; border-radius:10px; "
            f"  font-family:'{_FONT}'; font-size:14px; font-weight:600; "
            f"  text-align:center; padding:0 14px; "
            f"}} "
            f"QPushButton:hover  {{ background-color:{_ach}; }}"
        )
        new_btn.clicked.connect(self.new_session.emit)
        lay.addWidget(new_btn)
        lay.addSpacing(12)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("  Search...")
        self._search.setFixedHeight(38)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {_input_hi}, stop:0.08 {_input_bg}, stop:1 {_input_bg});
                border:1px solid {_input_border};
                border-top:2px solid {_input_hi};
                border-radius:14px;
                color:{_txt}; font-family:'{_FONT}'; font-size:12px;
                padding:4px 12px;
            }}
            QLineEdit::placeholder {{
                color:{_input_placeholder}; font-style:italic;
            }}
            QLineEdit:focus {{
                border:1px solid {_input_focus};
                border-top:2px solid {_input_focus};
            }}
        """)
        self._search.textChanged.connect(self._filter_nav)
        lay.addWidget(self._search)
        lay.addSpacing(12)

        # ── Chat history list — ChatGPT/Claude-style left rail of past
        # conversations. Sits between the search bar and the nav block so
        # switching between Chat / Voice / System / Settings still feels
        # primary. Only inserted if a store was passed in so this stays
        # backwards-compatible (e.g. theme reload paths).
        if self._history_store is not None:
            try:
                from shell_ui.chat_history import ChatHistoryList
                self.history_list = ChatHistoryList(self._history_store, self)
                self.history_list.setMinimumHeight(180)
                self.history_list.setMaximumHeight(220)
                # Bubble row signals up so ShellHoloUI can wire them.
                self.history_list.session_clicked.connect(self.history_session_clicked.emit)
                self.history_list.rename_requested.connect(self.history_rename_requested.emit)
                self.history_list.delete_requested.connect(self.history_delete_requested.emit)
                lay.addWidget(self.history_list)
                lay.addSpacing(10)
            except Exception as _e:
                logger.debug("ChatHistoryList init failed: %s", _e)
                self.history_list = None

        # Nav buttons — fixed top section, history list above flexes
        # vertically while these stay anchored.
        self._btns = []
        self._nav_icon_names = []
        for label, idx, icon_name in self.NAV_ITEMS:
            btn = QPushButton(f"  {label}")
            btn.setFixedHeight(42)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(QIcon(_make_icon_pixmap(icon_name, 16, C_OUTLINE)))
            btn.setIconSize(QSize(16, 16))
            btn.clicked.connect(lambda checked, i=idx: self._select(i))
            self._btns.append(btn)
            self._nav_icon_names.append(icon_name)
            lay.addWidget(btn)
            lay.addSpacing(4)

        lay.addStretch(1)

        # Connection status with dot indicator
        conn_row = QHBoxLayout()
        conn_row.setSpacing(8)
        conn_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._conn_dot = QLabel()
        self._conn_dot.setFixedSize(8, 8)
        self._conn_dot.setStyleSheet(f"""
            background:{C_TEXT_MUTED}; border-radius:4px; border:none;
        """)
        conn_row.addWidget(self._conn_dot)
        self._conn_lbl = QLabel("OFFLINE")
        self._conn_lbl.setStyleSheet(f"""
            color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:9px;
            letter-spacing:3px; border:none; background:transparent;
        """)
        conn_row.addWidget(self._conn_lbl)
        conn_row.addStretch(1)
        lay.addLayout(conn_row)
        lay.addSpacing(16)

        # Documentation link
        doc = QPushButton("DOCUMENTATION")
        doc.setCursor(Qt.CursorShape.PointingHandCursor)
        doc.setStyleSheet(f"""
            QPushButton {{
                color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:9px;
                letter-spacing:3px; border:none; background:transparent;
                text-align:left; padding:4px 0;
            }}
            QPushButton:hover {{
                color:{C_PRIMARY};
            }}
        """)
        doc.clicked.connect(self._open_docs)
        lay.addWidget(doc)

        self._apply_styles()

    def _apply_styles(self):
        # Calmer Claude-style nav: mixed-case labels at body weight, no
        # `letter-spacing:5px` shouting. Active state = warm surface_2
        # background + 3px accent left bar; hover = subtle accent wash.
        try:
            from shell_ui.design_tokens import C as _DC
            _accent = _DC.accent
            _surf2 = _DC.surface_2
            _accent_soft = _DC.accent_soft
            _txt = _DC.text
            _txt_muted = _DC.text_muted
        except Exception:
            _accent = "#d97757"; _surf2 = "#2c2823"
            _accent_soft = "rgba(217,119,87,0.14)"
            _txt = "#f3ece1"; _txt_muted = "#a39a8d"

        for i, btn in enumerate(self._btns):
            icon_name = self._nav_icon_names[i]
            if i == self._active:
                btn.setIcon(QIcon(_make_icon_pixmap(icon_name, 16, _accent)))
                btn.setStyleSheet(
                    f"QPushButton {{ "
                    f"  color:{_txt}; font-family:'{_FONT}'; font-size:14px; "
                    f"  font-weight:600; text-align:left; "
                    f"  padding:0 16px; "
                    f"  border:none; border-left:3px solid {_accent}; "
                    f"  background-color:{_surf2}; border-radius:10px; "
                    f"}}"
                )
            else:
                btn.setIcon(QIcon(_make_icon_pixmap(icon_name, 16, _txt_muted)))
                btn.setStyleSheet(
                    f"QPushButton {{ "
                    f"  color:{_txt_muted}; font-family:'{_FONT}'; font-size:14px; "
                    f"  font-weight:500; text-align:left; "
                    f"  padding:0 16px; border:none; "
                    f"  background:transparent; border-radius:10px; "
                    f"}} "
                    f"QPushButton:hover {{ "
                    f"  color:{_txt}; background-color:{_accent_soft}; "
                    f"}}"
                )

    def _select(self, idx):
        """Switch to nav idx. ALWAYS fires the page_changed signal."""
        try: self._sfx.play_click()
        except Exception: pass
        self._active = idx
        self._apply_styles()
        self.page_changed.emit(idx)

    def set_connection(self, connected):
        if connected:
            self._conn_lbl.setText("ONLINE")
            self._conn_lbl.setStyleSheet(f"""
                color:{C_SUCCESS}; font-family:'{_FONT}'; font-size:9px;
                letter-spacing:3px; border:none; background:transparent;
            """)
            self._conn_dot.setStyleSheet(f"""
                background:{C_SUCCESS}; border-radius:4px; border:none;
            """)
        else:
            self._conn_lbl.setText("OFFLINE")
            self._conn_lbl.setStyleSheet(f"""
                color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:9px;
                letter-spacing:3px; border:none; background:transparent;
            """)
            self._conn_dot.setStyleSheet(f"""
                background:{C_TEXT_MUTED}; border-radius:4px; border:none;
            """)

    def _filter_nav(self, text):
        """Filter navigation buttons by search text + quick page jump."""
        query = text.strip().lower()
        # Quick-jump keywords map to pages
        page_keywords = {
            0: ["chat", "message", "talk", "baat", "type"],
            1: ["voice", "speak", "mic", "audio", "bol", "sun"],
            2: ["system", "cpu", "ram", "gpu", "monitor", "stats", "performance"],
            3: ["tools", "tool", "mcp", "backend", "feature", "action", "automation"],
            4: ["settings", "config", "theme", "provider", "api", "key"],
        }
        # Auto-navigate to matching page on Enter
        if query:
            for page_idx, kws in page_keywords.items():
                if any(query in kw for kw in kws):
                    # Highlight only matching button
                    for i in range(len(self._btns)):
                        self._btns[i].setVisible(i == page_idx)
                    return
        # Default: show all buttons
        for i, (label, idx, icon_name) in enumerate(self.NAV_ITEMS):
            if i < len(self._btns):
                visible = not query or query in label.lower()
                self._btns[i].setVisible(visible)

    def _open_docs(self):
        """Open documentation — look for README or docs folder."""
        doc_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs"),
        ]
        for p in doc_paths:
            if os.path.exists(p):
                try:
                    ok = QDesktopServices.openUrl(QUrl.fromLocalFile(p))
                    if not ok:
                        logger.warning("docs open request was rejected by Qt: %s", p)
                except Exception as _e:
                    logger.debug("docs open failed: %s", _e)
                return
        logger.warning("documentation target not found")


# =====================================================================
#  Voice listener runtime service
# =====================================================================

from shell_voice_listener_runtime import VoiceListenerThread, _SD_AVAILABLE, _SR_AVAILABLE


# =====================================================================
#  WaveformWidget
# =====================================================================

class VoiceVisualizer(QWidget):
    """Mac/Apple-class centerpiece for the Voice page.
    Central glowing pulse + 24 perimeter bars driven by a Perlin-ish
    noise field (idle) or live mic amplitude (listening / speaking).
    State transitions are animated via QPropertyAnimation."""
    clicked = pyqtSignal()
    from PyQt6.QtCore import pyqtProperty as _qprop  # type: ignore

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 260)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background:transparent; border:none;")

        self._n_bars = 24
        self._bar_vals = [0.0] * self._n_bars
        self._bar_targets = [0.0] * self._n_bars
        self._bar_phases = [random.random() * math.tau for _ in range(self._n_bars)]
        self._bar_freqs = [0.7 + random.random() * 0.6 for _ in range(self._n_bars)]

        self._intensity = 0.25
        self._warmth = 0.5
        self._pulse_phase = 0.0
        self._noise_t = 0.0
        self._mic_amp = 0.0
        self._state = "idle"
        self._hover = False
        self._hover_amt = 0.0

        # Modern particle orb: a deterministic Fibonacci point cloud so the
        # voice surface feels like a living audio field, not a flat ball.
        self._n_particles = 168
        self._particles = []
        golden = math.pi * (3.0 - math.sqrt(5.0))
        for i in range(self._n_particles):
            y = 1.0 - (2.0 * i / max(1, self._n_particles - 1))
            r = math.sqrt(max(0.0, 1.0 - y * y))
            theta = i * golden
            self._particles.append({
                "x": math.cos(theta) * r,
                "y": y,
                "z": math.sin(theta) * r,
                "phase": random.random() * math.tau,
                "size": 1.2 + random.random() * 2.2,
                "drift": 0.18 + random.random() * 0.36,
            })

        # ---- Apple-glassy orb upgrade: liquid blobs + orbiting wisps ----
        # 4 inner "lava-lamp" blobs that move in slow looping orbits
        # inside the sphere, giving the surface a living, iridescent feel.
        self._n_blobs = 4
        self._blob_phases = [random.random() * math.tau for _ in range(self._n_blobs)]
        self._blob_rates  = [0.22 + random.random() * 0.30 for _ in range(self._n_blobs)]
        self._blob_radii  = [0.34 + random.random() * 0.18 for _ in range(self._n_blobs)]
        # Perpendicular axis ratio per blob → makes the orbits elliptical.
        self._blob_axes   = [(0.55 + random.random() * 0.30,
                              0.40 + random.random() * 0.35) for _ in range(self._n_blobs)]
        # Hue offsets in [-1, +1] — used to mix accent / accent_hover /
        # a complementary purple for the iridescent rainbow feel.
        self._blob_hues   = [-0.6, -0.2, 0.3, 0.7]

        # 8 orbiting wisp particles around the outside of the orb.
        # They follow tilted elliptical paths to look like glints of
        # light moving over a glass marble.
        self._n_wisps = 8
        self._wisp_phases = [random.random() * math.tau for _ in range(self._n_wisps)]
        self._wisp_rates  = [0.018 + random.random() * 0.022 for _ in range(self._n_wisps)]
        self._wisp_tilts  = [random.random() * math.tau for _ in range(self._n_wisps)]
        self._wisp_radii  = [1.10 + random.random() * 0.55 for _ in range(self._n_wisps)]
        self._wisp_sizes  = [1.6 + random.random() * 2.4 for _ in range(self._n_wisps)]

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        # 50 ms (~20 fps) instead of 33 ms (~30 fps). Visually identical
        # to the human eye, but RDP wire traffic drops ~40%, freeing
        # bandwidth for snappy page transitions.
        self._tick_timer.start(50)

        self._intensity_anim = None
        self._warmth_anim = None

    def sizeHint(self):
        return QSize(260, 260)

    def minimumSizeHint(self):
        return QSize(260, 260)

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            e.accept()
            return
        super().mousePressEvent(e)

    def _get_intensity(self): return self._intensity
    def _set_intensity(self, v): self._intensity = float(v); self.update()
    def _get_warmth(self): return self._warmth
    def _set_warmth(self, v): self._warmth = float(v); self.update()
    intensity = _qprop(float, _get_intensity, _set_intensity)  # type: ignore
    warmth    = _qprop(float, _get_warmth, _set_warmth)        # type: ignore

    def set_amplitude(self, amp):
        try:
            amp = max(0.0, min(1.0, float(amp)))
        except Exception:
            amp = 0.0
        self._mic_amp = max(self._mic_amp * 0.85, amp)
        for i in range(self._n_bars):
            jitter = 0.5 + 0.5 * math.sin(self._bar_phases[i] + self._noise_t * self._bar_freqs[i])
            self._bar_targets[i] = max(self._bar_targets[i], amp * (0.45 + 0.55 * jitter))

    def set_state(self, state):
        if state == self._state:
            return
        self._state = state
        targets = {
            "idle":      (0.26, 0.50),
            "listening": (0.70, 0.18),
            "speaking":  (0.95, 0.90),
            "muted":     (0.10, 0.30),
            "error":     (0.16, 0.78),
        }.get(state, (0.25, 0.50))
        self._animate_to(*targets)

    def set_speaking(self, speaking):
        if speaking:
            self.set_state("speaking")
        elif self._state == "speaking":
            self.set_state("listening")

    def _animate_to(self, intensity, warmth, ms=300):
        try:
            ai = QPropertyAnimation(self, b"intensity", self)
            ai.setDuration(ms); ai.setEasingCurve(QEasingCurve.Type.OutCubic)
            ai.setStartValue(self._intensity); ai.setEndValue(intensity)
            ai.start(); self._intensity_anim = ai
            aw = QPropertyAnimation(self, b"warmth", self)
            aw.setDuration(ms); aw.setEasingCurve(QEasingCurve.Type.OutCubic)
            aw.setStartValue(self._warmth); aw.setEndValue(warmth)
            aw.start(); self._warmth_anim = aw
        except Exception:
            self._intensity = intensity; self._warmth = warmth; self.update()

    def _tick(self):
        self._pulse_phase += 0.05
        self._noise_t += 0.06
        for i in range(self._n_bars):
            idle_floor = 0.05 + 0.18 * self._intensity * (
                0.5 + 0.5 * math.sin(self._bar_phases[i] + self._noise_t * self._bar_freqs[i])
            )
            target = max(idle_floor, self._bar_targets[i])
            self._bar_vals[i] += (target - self._bar_vals[i]) * 0.28
            self._bar_targets[i] *= 0.90
        self._mic_amp *= 0.92
        # Advance liquid blobs and orbiting wisps. Speed scales with
        # intensity so the orb gets "more alive" when listening / speaking.
        boost = 0.55 + 0.85 * self._intensity
        for i in range(self._n_blobs):
            self._blob_phases[i] += self._blob_rates[i] * 0.03 * boost
        for i in range(self._n_wisps):
            self._wisp_phases[i] += self._wisp_rates[i] * (0.6 + 0.9 * self._intensity)
        hover_target = 1.0 if self._hover else 0.0
        self._hover_amt += (hover_target - self._hover_amt) * 0.22
        self.update()

    def _accent_color(self):
        try:
            from shell_ui.design_tokens import C as _DC
            return QColor(_DC.accent)
        except Exception:
            return QColor(C_PRIMARY)

    def _accent_soft_color(self):
        try:
            from shell_ui.design_tokens import C as _DC
            a = QColor(_DC.accent); m = QColor(_DC.text_muted)
            mix = 0.55
            return QColor(
                int(a.red() * (1 - mix) + m.red() * mix),
                int(a.green() * (1 - mix) + m.green() * mix),
                int(a.blue() * (1 - mix) + m.blue() * mix),
            )
        except Exception:
            return QColor(C_PRIMARY)

    def _palette(self):
        try:
            from shell_ui.design_tokens import C as _DC
            if self._state == "error":
                return QColor(_DC.error), QColor(_DC.error)
            if self._state == "muted":
                return QColor(_DC.text_muted), QColor(_DC.text_subtle)
            if self._state == "listening":
                return QColor(_DC.accent), QColor(_DC.accent_hover)
            if self._state == "speaking":
                return QColor(_DC.success), QColor(_DC.success)
        except Exception:
            if self._state == "error":
                return QColor("#ff716c"), QColor("#ff716c")
            if self._state == "muted":
                return QColor("#73757c"), QColor("#73757c")
        cool = self._accent_soft_color()
        warm = self._accent_color()
        w = max(0.0, min(1.0, self._warmth))
        col = QColor(
            int(cool.red() * (1 - w) + warm.red() * w),
            int(cool.green() * (1 - w) + warm.green() * w),
            int(cool.blue() * (1 - w) + warm.blue() * w),
        )
        return col, warm

    def _iridescent_blob_colors(self):
        """4 QColor for inner liquid blobs.

        Mixes accent + accent_hover with a hue-shifted complement so
        the sphere surface reads iridescent (Siri-class). Order:
        accent, hover, complement (≈+200°), accent.
        """
        try:
            from shell_ui.design_tokens import C as _DC
            accent = QColor(_DC.accent)
            accent_h = QColor(_DC.accent_hover)
        except Exception:
            accent = QColor("#00f0ff")
            accent_h = QColor("#5cf6ff")
        try:
            h, s, v, _a = accent.getHsv()
            comp = QColor.fromHsv((h + 200) % 360, max(140, s), min(255, v + 10))
        except Exception:
            comp = QColor("#b06bff")
        return [accent, accent_h, comp, accent]

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            p.end()
            return
        col, warm = self._palette()
        state_level = {
            "idle": 0.30,
            "listening": 0.72,
            "speaking": 1.0,
            "muted": 0.14,
            "error": 0.18,
        }.get(self._state, 0.30)
        level = max(state_level, min(1.0, self._mic_amp + state_level * 0.42))
        disabled = self._state in ("muted", "error")

        cx, cy = w * 0.5, h * 0.5
        pulse = 0.5 + 0.5 * math.sin(self._pulse_phase * (1.5 + level * 2.2))
        ring_r = min(w, h) * 0.34
        core_r = min(w, h) * (0.165 + 0.015 * pulse * (0.4 + level))
        if disabled:
            core_r *= 0.92

        # Modern particle field. Error/muted are deliberately subdued so the
        # orb does not look "active" when voice cannot run.
        halo_r = ring_r * (1.62 + 0.16 * level)
        halo = QRadialGradient(QPointF(cx, cy), halo_r)
        h0 = QColor(warm); h0.setAlpha(int((62 if not disabled else 22) * level))
        h_mid = QColor(col); h_mid.setAlpha(int((34 if not disabled else 12) * level))
        h1 = QColor(warm); h1.setAlpha(0)
        halo.setColorAt(0.0, h0)
        halo.setColorAt(0.45, h_mid)
        halo.setColorAt(1.0, h1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), halo_r, halo_r)

        # Thin orbital shells give the particles spatial structure without
        # reintroducing the old "solid marble" look.
        orbit_alpha = int((28 + 50 * level + 26 * self._hover_amt) * (0.45 if disabled else 1.0))
        for idx, (scale, squash, rot) in enumerate((
            (1.12, 0.38, -18),
            (1.38, 0.30, 17),
            (1.62, 0.24, 48),
        )):
            oc = QColor(warm)
            oc.setAlpha(max(0, orbit_alpha - idx * 14))
            p.save()
            p.translate(cx, cy)
            p.rotate(rot + math.sin(self._noise_t * 0.42 + idx) * 6.0)
            p.scale(1.0, squash)
            p.setPen(QPen(oc, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(0, 0), ring_r * scale, ring_r * scale)
            p.restore()

        # Audio-reactive perimeter sparks. These read like a modern realtime
        # voice assistant, especially when speech amplitude is active.
        tick_count = 42
        tick_base = ring_r * 0.96
        max_len = 11 + 17 * level
        for i in range(tick_count):
            angle = (math.tau * i / tick_count) - math.pi / 2.0
            wave = 0.5 + 0.5 * math.sin(self._noise_t * 1.7 + i * 0.58)
            amp = max(self._bar_vals[i % self._n_bars], wave * 0.13 * level)
            if disabled:
                amp *= 0.30
            length = 2.0 + max_len * min(1.0, amp)
            x0 = cx + math.cos(angle) * tick_base
            y0 = cy + math.sin(angle) * tick_base
            x1 = cx + math.cos(angle) * (tick_base + length)
            y1 = cy + math.sin(angle) * (tick_base + length)
            tick_col = QColor(col)
            tick_col.setAlpha(int(54 + 135 * min(1.0, amp + level * 0.28)))
            pen = QPen(tick_col, 2.0 if not disabled else 1.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

        # Projection helper for the point cloud.
        rot_y = self._noise_t * (0.30 + 0.26 * level)
        rot_x = math.sin(self._noise_t * 0.38) * 0.30
        spread = ring_r * (0.84 + 0.10 * level + 0.05 * self._hover_amt)
        cloud = []
        sy, cyy = math.sin(rot_y), math.cos(rot_y)
        sx, cxx = math.sin(rot_x), math.cos(rot_x)
        for i, pt in enumerate(self._particles):
            wobble = 1.0 + 0.055 * math.sin(self._noise_t * pt["drift"] + pt["phase"]) + 0.07 * self._bar_vals[i % self._n_bars]
            x = pt["x"] * wobble
            y = pt["y"] * wobble
            z = pt["z"] * wobble
            x, z = x * cyy + z * sy, -x * sy + z * cyy
            y, z = y * cxx - z * sx, y * sx + z * cxx
            proj = 1.0 + z * 0.16
            px = cx + x * spread * proj
            py = cy + y * spread * 0.92 * proj
            cloud.append((z, px, py, pt["size"], i))
        cloud.sort(key=lambda item: item[0])

        # Draw a soft non-solid center so the orb still has a focal point.
        core_glow_r = core_r * (1.32 + 0.34 * level)
        core_glow = QRadialGradient(QPointF(cx, cy), core_glow_r)
        cg0 = QColor(warm); cg0.setAlpha(int(86 + 80 * level if not disabled else 34))
        cg1 = QColor(col); cg1.setAlpha(int(22 + 32 * level if not disabled else 10))
        cg2 = QColor(warm); cg2.setAlpha(0)
        core_glow.setColorAt(0.0, cg0)
        core_glow.setColorAt(0.46, cg1)
        core_glow.setColorAt(1.0, cg2)
        p.setBrush(core_glow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), core_glow_r, core_glow_r)

        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for z, px, py, base_size, i in cloud:
            front = (z + 1.0) * 0.5
            amp = self._bar_vals[i % self._n_bars]
            size = base_size * (0.82 + front * 1.25 + level * 0.35 + amp * 0.9)
            alpha = int((36 + front * 142 + amp * 80) * (0.38 if disabled else 1.0))
            pc = QColor(warm if (i % 3) else col)
            pc.setAlpha(max(0, min(230, alpha)))
            pg = QRadialGradient(QPointF(px, py), size * 3.1)
            bright = QColor(255, 255, 255, max(16, min(210, alpha + 32)))
            fade = QColor(pc); fade.setAlpha(max(0, int(alpha * 0.22)))
            clear = QColor(pc); clear.setAlpha(0)
            pg.setColorAt(0.0, bright if front > 0.64 else pc)
            pg.setColorAt(0.42, fade)
            pg.setColorAt(1.0, clear)
            p.setBrush(pg)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(px, py), size * 3.1, size * 3.1)

            dot = QColor(pc)
            dot.setAlpha(max(0, min(245, alpha + 28)))
            p.setBrush(dot)
            p.drawEllipse(QPointF(px, py), size * 0.72, size * 0.72)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # A front rim of tiny points sells the spherical silhouette.
        rim_col = QColor(255, 255, 255, int(34 + 52 * level if not disabled else 18))
        p.setPen(QPen(rim_col, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), spread * 1.02, spread * 0.94)

        if self._state == "error":
            x = core_r * 0.32
            err_pen = QPen(QColor(255, 255, 255, 150), 3.0)
            err_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(err_pen)
            p.drawLine(QPointF(cx - x, cy - x), QPointF(cx + x, cy + x))
            p.drawLine(QPointF(cx + x, cy - x), QPointF(cx - x, cy + x))

        p.end()
        return

        # ================================================================
        # Apple-glassy orb v2 — Siri-class cinematic sphere.
        # 12 layers from back to front:
        #   0. Floor shadow (soft elliptical drop below the orb)
        #   1. Wide ambient halo
        #   2. Expanding pulse rings (only when listening/speaking)
        #   3. Perimeter bars (audio-reactive)
        #   4. Inner radiant glow cushion
        #   5. Sphere base (saturated solid disc)
        #   6. Iridescent liquid blobs (clipped to sphere, additive)
        #   7. Sphere shading overlay (offset highlight + bottom dim)
        #   8. Specular highlight (small bright dot, clipped)
        #   9. Rim light (1px white ring inside edge)
        #  10. Outer accent ring at equator
        #  11. Orbiting wisp particles (8 around the orb)
        #
        # Audio-reactive: the sphere subtly squishes wider on loud audio.
        # ================================================================
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        col, warm = self._palette()
        blob_cols = self._iridescent_blob_colors()

        # Compute core radius with subtle breathing wobble + audio squish.
        inner_r = min(w, h) * 0.30
        pulse_speed = 1.6 + 4.0 * self._intensity
        pulse = 0.5 + 0.5 * math.sin(self._pulse_phase * pulse_speed)
        base_core_r = inner_r * (0.55 + 0.18 * pulse * (0.5 + self._intensity))
        breath_x = 1.0 + 0.025 * math.sin(self._pulse_phase * 1.30) + 0.06 * self._mic_amp
        breath_y = 1.0 + 0.025 * math.cos(self._pulse_phase * 1.55) - 0.030 * self._mic_amp
        core_rx = base_core_r * breath_x
        core_ry = base_core_r * breath_y

        # ---- LAYER 0: Floor shadow ----
        sh_y = cy + base_core_r * 1.55
        shadow_r = base_core_r * 1.45
        shadow = QRadialGradient(QPointF(cx, sh_y), shadow_r)
        shadow.setColorAt(0.0, QColor(0, 0, 0, int(55 + 35 * self._intensity)))
        shadow.setColorAt(0.5, QColor(0, 0, 0, 22))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(shadow); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, sh_y), shadow_r, shadow_r * 0.30)

        # ---- LAYER 1: Wide ambient halo ----
        halo_radius = min(w, h) * 0.50
        halo_alpha = int(50 + 110 * self._intensity)
        halo = QRadialGradient(QPointF(cx, cy), halo_radius)
        h0 = QColor(warm); h0.setAlpha(halo_alpha)
        h_mid = QColor(warm); h_mid.setAlpha(int(halo_alpha * 0.35))
        h1 = QColor(warm); h1.setAlpha(0)
        halo.setColorAt(0.0, h0)
        halo.setColorAt(0.45, h_mid)
        halo.setColorAt(1.0, h1)
        p.setBrush(halo); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), halo_radius, halo_radius)

        # ---- LAYER 2: Expanding pulse rings (Siri-style) ----
        if self._state in ("listening", "speaking"):
            for i in range(3):
                t = ((self._pulse_phase * 0.18) + i * 0.33) % 1.0
                ring_r = base_core_r * (1.0 + t * 2.6)
                fade = (1.0 - t) ** 1.4
                ring_alpha = int(70 * fade * (0.4 + 0.6 * self._intensity))
                if ring_alpha <= 0:
                    continue
                ring_col = QColor(warm); ring_col.setAlpha(ring_alpha)
                p.setPen(QPen(ring_col, 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

        # ---- GLASS CRADLE: subtle orbital ellipses behind the bars ----
        cradle_alpha = int(18 + 38 * self._intensity + 28 * self._hover_amt)
        for i, scale in enumerate((1.48, 1.72, 1.96)):
            cradle_col = QColor(warm)
            cradle_col.setAlpha(max(0, cradle_alpha - i * 10))
            p.save()
            p.translate(cx, cy + base_core_r * 0.08)
            p.rotate(-18 + i * 18 + math.sin(self._pulse_phase * 0.55 + i) * 3)
            p.scale(1.0, 0.34 + i * 0.035)
            p.setPen(QPen(cradle_col, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(0, 0), base_core_r * scale, base_core_r * scale)
            p.restore()

        if self._hover_amt > 0.01:
            hover_col = QColor(255, 255, 255, int(54 * self._hover_amt))
            p.setPen(QPen(hover_col, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), base_core_r * 2.02, base_core_r * 2.02)

        # ---- LAYER 3: 24 perimeter bars ----
        max_extra = min(w, h) * 0.13
        bar_w = 4.0
        for i in range(self._n_bars):
            angle = (math.tau * i / self._n_bars) - math.pi / 2.0
            v = max(0.05, min(1.0, self._bar_vals[i]))
            length = 6.0 + max_extra * (0.35 + v * 1.2 * (0.6 + 0.4 * self._intensity))
            x0 = cx + math.cos(angle) * inner_r
            y0 = cy + math.sin(angle) * inner_r
            x1 = cx + math.cos(angle) * (inner_r + length)
            y1 = cy + math.sin(angle) * (inner_r + length)
            grad = QLinearGradient(QPointF(x0, y0), QPointF(x1, y1))
            inner_col = QColor(col); inner_col.setAlpha(int(140 + v * 110))
            outer_col = QColor(col); outer_col.setAlpha(int(20 + v * 60))
            grad.setColorAt(0.0, inner_col)
            grad.setColorAt(1.0, outer_col)
            pen = QPen(QBrush(grad), bar_w)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

        # ---- LAYER 4: Inner radiant glow cushion ----
        glow_r = base_core_r * 1.95
        glow = QRadialGradient(QPointF(cx, cy), glow_r)
        gc0 = QColor(warm); gc0.setAlpha(int(95 + 130 * self._intensity))
        gc_mid = QColor(warm); gc_mid.setAlpha(int(40 + 50 * self._intensity))
        gc1 = QColor(warm); gc1.setAlpha(0)
        glow.setColorAt(0.0, gc0)
        glow.setColorAt(0.55, gc_mid)
        glow.setColorAt(1.0, gc1)
        p.setBrush(glow); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        # Build sphere clipping path (used by layers 6-8).
        sphere_path = QPainterPath()
        sphere_path.addEllipse(QPointF(cx, cy), core_rx, core_ry)

        # ---- LAYER 5: Sphere base (saturated solid disc) ----
        base_col = QColor(warm); base_col.setAlpha(int(210 + 35 * self._intensity))
        p.setBrush(base_col); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), core_rx, core_ry)

        # ---- LAYER 6: Iridescent liquid blobs (clipped, additive) ----
        p.save()
        p.setClipPath(sphere_path)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for i in range(self._n_blobs):
            ax, ay = self._blob_axes[i]
            rad = self._blob_radii[i]
            ph = self._blob_phases[i]
            bx = cx + math.cos(ph) * core_rx * ax * rad
            by = cy + math.sin(ph * 0.85 + 1.7) * core_ry * ay * rad
            bsize = base_core_r * (0.55 + 0.20 * (0.5 + 0.5 * math.sin(ph * 1.3)))
            bg = QRadialGradient(QPointF(bx, by), bsize)
            c = QColor(blob_cols[i])
            c.setAlpha(int(95 + 70 * self._intensity))
            c1 = QColor(c); c1.setAlpha(int(55 + 45 * self._intensity))
            c2 = QColor(c); c2.setAlpha(0)
            bg.setColorAt(0.0, c)
            bg.setColorAt(0.55, c1)
            bg.setColorAt(1.0, c2)
            p.setBrush(bg); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(bx, by), bsize, bsize)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.restore()

        # ---- LAYER 7: Sphere shading overlay (offset highlight + bottom dim) ----
        # Drawn ON TOP of the blobs so the offset light reads as 3D depth.
        sphere = QRadialGradient(
            QPointF(cx - core_rx * 0.32, cy - core_ry * 0.38),
            max(core_rx, core_ry) * 1.45,
        )
        hi = QColor(255, 255, 255, int(150 + 60 * self._intensity))
        warm_bright = QColor(warm); warm_bright.setAlpha(int(60 + 40 * self._intensity))
        mid_clear = QColor(0, 0, 0, 0)
        edge_dim = QColor(0, 0, 0, int(50 + 30 * self._intensity))
        sphere.setColorAt(0.00, hi)
        sphere.setColorAt(0.20, warm_bright)
        sphere.setColorAt(0.55, mid_clear)
        sphere.setColorAt(1.00, edge_dim)
        p.save()
        p.setClipPath(sphere_path)
        p.setBrush(sphere); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), core_rx, core_ry)
        p.restore()

        # ---- LAYER 8: Specular highlight ----
        spec_x = cx - core_rx * 0.42
        spec_y = cy - core_ry * 0.52
        spec_r = base_core_r * 0.32
        spec = QRadialGradient(QPointF(spec_x, spec_y), spec_r)
        spec.setColorAt(0.00, QColor(255, 255, 255, int(180 + 50 * self._intensity)))
        spec.setColorAt(0.55, QColor(255, 255, 255, 50))
        spec.setColorAt(1.00, QColor(255, 255, 255, 0))
        p.save()
        p.setClipPath(sphere_path)
        p.setBrush(spec); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(spec_x, spec_y), spec_r, spec_r * 0.85)
        p.restore()

        # ---- LAYER 9: Rim light ----
        rim_alpha = int(70 + 80 * self._intensity)
        rim = QColor(255, 255, 255, rim_alpha)
        p.setPen(QPen(rim, 1.0)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), core_rx * 0.985, core_ry * 0.985)

        # ---- LAYER 10: Outer accent ring at equator ----
        outer_ring = QColor(warm); outer_ring.setAlpha(int(110 + 80 * self._intensity))
        p.setPen(QPen(outer_ring, 1.2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), core_rx, core_ry)

        # ---- LAYER 11: Orbiting wisp particles (in front of sphere) ----
        for i in range(self._n_wisps):
            angle = self._wisp_phases[i]
            rx = core_rx * self._wisp_radii[i]
            ry = core_ry * self._wisp_radii[i] * 0.55
            tilt = self._wisp_tilts[i]
            local_x = math.cos(angle) * rx
            local_y = math.sin(angle) * ry
            wx = cx + local_x * math.cos(tilt) - local_y * math.sin(tilt)
            wy = cy + local_x * math.sin(tilt) + local_y * math.cos(tilt)
            sz = self._wisp_sizes[i] * (0.7 + 0.6 * self._intensity)
            # Glow halo
            wisp_grad = QRadialGradient(QPointF(wx, wy), sz * 3.5)
            wc = QColor(warm); wc.setAlpha(int(150 + 60 * self._intensity))
            wc_mid = QColor(wc.red(), wc.green(), wc.blue(), 60)
            wc_clear = QColor(wc.red(), wc.green(), wc.blue(), 0)
            wisp_grad.setColorAt(0.0, wc)
            wisp_grad.setColorAt(0.4, wc_mid)
            wisp_grad.setColorAt(1.0, wc_clear)
            p.setBrush(wisp_grad); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(wx, wy), sz * 3.5, sz * 3.5)
            # Bright dot in centre
            wb = QColor(255, 255, 255, int(170 + 60 * self._intensity))
            p.setBrush(wb); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(wx, wy), sz, sz)

        p.end()


class WaveformWidget(QWidget):
    """Horizontal bar visualiser. Responsive width (24-32 bars), gradient
    fill from accent to accent_soft, subtle glow halo on tall bars.
    Keeps `set_amplitude` and `_t` (QTimer) so the existing wiring in
    `_build_ui` and `_on_voice_amplitude` continues to work."""
    def __init__(self, parent=None, bars=28):
        super().__init__(parent)
        self._n = bars
        self._vals = [0.0] * bars
        self._targets = [0.0] * bars
        self.setFixedHeight(60)
        self.setMinimumWidth(280)
        self.setMaximumWidth(640)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background:transparent; border:none;")
        self._idle_phase = 0.0
        self._t = QTimer(self); self._t.timeout.connect(self._tick); self._t.start(35)

    def set_amplitude(self, amp):
        try:
            amp = max(0.0, min(1.0, float(amp)))
        except Exception:
            amp = 0.0
        for i in range(self._n):
            dist = abs(i - self._n / 2) / (self._n / 2)
            self._targets[i] = max(0.08, amp * (1.0 - dist * 0.55) * random.uniform(0.65, 1.2))

    def _tick(self):
        self._idle_phase += 0.05
        for i in range(self._n):
            dist = abs(i - self._n / 2) / (self._n / 2)
            idle_val = 0.05 + 0.12 * (1.0 - dist) * (0.5 + 0.5 * math.sin(self._idle_phase + i * 0.32))
            target = max(idle_val, self._targets[i])
            self._vals[i] += (target - self._vals[i]) * 0.25
            self._targets[i] *= 0.92
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        try:
            from shell_ui.design_tokens import C as _DC
            accent = QColor(_DC.accent)
            accent_soft = QColor(_DC.accent); accent_soft.setAlpha(90)
        except Exception:
            accent = QColor(C_PRIMARY); accent_soft = QColor(C_PRIMARY); accent_soft.setAlpha(90)

        bar_w = max(3.0, (w / self._n) * 0.45)
        slot = w / self._n
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(self._n):
            v = max(0.05, min(1.0, self._vals[i]))
            bar_h = max(3, v * h * 0.92)
            x = i * slot + (slot - bar_w) / 2
            y = (h - bar_h) / 2

            grad = QLinearGradient(0, y, 0, y + bar_h)
            top = QColor(accent); top.setAlpha(int(160 + v * 95))
            bot = QColor(accent_soft); bot.setAlpha(int(60 + v * 90))
            grad.setColorAt(0.0, top)
            grad.setColorAt(0.5, top)
            grad.setColorAt(1.0, bot)
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), bar_w / 2, bar_w / 2)

            if v > 0.40:
                halo = QRadialGradient(QPointF(x + bar_w / 2, h / 2), bar_w * 3.0)
                hc0 = QColor(accent); hc0.setAlpha(int(v * 35))
                hc1 = QColor(accent); hc1.setAlpha(0)
                halo.setColorAt(0.0, hc0); halo.setColorAt(1.0, hc1)
                p.setBrush(halo)
                p.drawEllipse(QPointF(x + bar_w / 2, h / 2), bar_w * 3.0, bar_w * 3.0)
        p.end()


class VoiceStage(QWidget):
    """Unframed aura layer behind the orb and waveform."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background:transparent; border:none;")
        # Trimmed from 420 → 340 so the orb area no longer crowds the
        # transcript card below.
        self.setMinimumHeight(340)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._phase = 0.0
        self._amp = 0.0
        self._state = "idle"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(80)

    def sizeHint(self):
        return QSize(720, 360)

    def set_state(self, state):
        self._state = state or "idle"
        self.update()

    def set_amplitude(self, amp):
        try:
            amp = max(0.0, min(1.0, float(amp)))
        except Exception:
            amp = 0.0
        self._amp = max(self._amp * 0.82, amp)
        self.update()

    def _tick(self):
        self._phase += 0.045
        self._amp *= 0.90
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            p.end()
            return
        # Paint a real base layer before every animated frame. On macOS/RDP,
        # fully transparent animated children can leave stale backing-store
        # pixels while the page is prewarmed and resized.
        base = QLinearGradient(QPointF(0, 0), QPointF(0, h))
        try:
            from shell_ui.design_tokens import C as _DC
            base.setColorAt(0.0, QColor(_DC.surface_2))
            base.setColorAt(0.56, QColor(_DC.surface))
            base.setColorAt(1.0, QColor(_DC.bg))
        except Exception:
            base.setColorAt(0.0, QColor(12, 26, 43))
            base.setColorAt(0.55, QColor(10, 23, 39))
            base.setColorAt(1.0, QColor(9, 20, 34))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base)
        p.drawRect(self.rect())

        try:
            from shell_ui.design_tokens import C as _DC
            if self._state == "error":
                accent = QColor(_DC.error)
                hover = QColor(_DC.error)
            elif self._state == "muted":
                accent = QColor(_DC.text_muted)
                hover = QColor(_DC.text_subtle)
            elif self._state == "speaking":
                accent = QColor(_DC.success)
                hover = QColor(_DC.success)
            else:
                accent = QColor(_DC.accent)
                hover = QColor(_DC.accent_hover)
            border = QColor(accent)
            border.setAlpha(46)
        except Exception:
            accent = QColor("#ff716c" if self._state == "error" else C_PRIMARY)
            hover = QColor("#ff716c" if self._state == "error" else "#5cf6ff")
            border = QColor(143, 245, 255, 46)

        state_boost = {
            "idle": 0.25,
            "listening": 0.65,
            "speaking": 1.0,
            "muted": 0.18,
            "error": 0.18,
        }.get(self._state, 0.25)
        level = max(state_boost, min(1.0, self._amp + state_boost * 0.45))
        cx, cy = w * 0.5, h * 0.48
        radius = min(w, h) * 0.62

        wash = QRadialGradient(QPointF(cx, cy), radius)
        c0 = QColor(accent); c0.setAlpha(int(24 + 50 * level))
        c1 = QColor(hover); c1.setAlpha(int(16 + 30 * level))
        c2 = QColor(accent); c2.setAlpha(0)
        wash.setColorAt(0.0, c0)
        wash.setColorAt(0.46, c1)
        wash.setColorAt(1.0, c2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(wash)
        p.drawEllipse(QPointF(cx, cy), radius * 1.18, radius * 0.68)

        floor = QLinearGradient(QPointF(w * 0.16, h * 0.78), QPointF(w * 0.84, h * 0.78))
        edge = QColor(border); edge.setAlpha(int(20 + 44 * level))
        clear = QColor(edge); clear.setAlpha(0)
        floor.setColorAt(0.0, clear)
        floor.setColorAt(0.48, edge)
        floor.setColorAt(1.0, clear)
        pen = QPen(QBrush(floor), 1.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(w * 0.18, h * 0.78), QPointF(w * 0.82, h * 0.78))

        p.end()


# =====================================================================
#  VoicePage
# =====================================================================

class VoicePage(QWidget):
    # Public signals — wired by ShellHoloUI.__init__ / _build_ui.
    mute_toggled = pyqtSignal(bool)
    session_terminated = pyqtSignal()
    visuals_toggled = pyqtSignal(bool)
    voice_text_sent = pyqtSignal(str)  # recognized text -> AI pipeline

    def __init__(self, parent=None):
        super().__init__(parent)
        from shell_ui import design_tokens as _DT
        self._DT = _DT
        C = _DT.C; T = _DT.T; S = _DT.S; R = _DT.R

        self.setStyleSheet("background:transparent; border:none;")
        self._muted = False
        self._visuals_on = True
        self._session_active = False
        self._sfx = SoundFX()
        self._status_phase = 0.0
        self._voice_persona = "Aoede · Hinglish"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(S.xl, S.lg, S.xl, S.lg)
        outer.setSpacing(S.lg)

        # 1. TOP BAR: compact voice state + persona.
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(S.md)

        self._status_pill = QFrame()
        status_pill = self._status_pill
        status_pill.setObjectName("voiceStatusPill")
        status_pill.setStyleSheet(
            f"#voiceStatusPill {{ "
            f"  background-color:{C.surface_2}; "
            f"  border:1px solid {C.glass_border}; "
            f"  border-radius:{R.pill}px; "
            f"}}"
        )
        sp_lay = QHBoxLayout(status_pill)
        sp_lay.setContentsMargins(S.md, 4, S.md, 4)
        sp_lay.setSpacing(S.sm)

        self._status_dot = QLabel()
        self._status_dot.setFixedSize(8, 8)
        self._status_dot.setStyleSheet(
            f"background:{C.success}; border-radius:4px; border:none;"
        )
        sp_lay.addWidget(self._status_dot)

        self.status_badge = QLabel("READY")
        self.status_badge.setStyleSheet(
            f"color:{C.text}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.small_size}px; "
            f"font-weight:700; letter-spacing:1.5px;"
        )
        sp_lay.addWidget(self.status_badge)

        # Live session timer (hidden until session starts).
        self._session_timer_lbl = QLabel("")
        self._session_timer_lbl.setStyleSheet(
            f"color:{C.text_muted}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.small_size - 1}px; "
            f"font-weight:500; letter-spacing:1px; margin-left:6px;"
        )
        sp_lay.addWidget(self._session_timer_lbl)

        status_row.addWidget(status_pill, 0, Qt.AlignmentFlag.AlignLeft)
        status_row.addStretch(1)

        # Persona pill (right side) — Apple-style frosted chip with mic
        # icon and the active voice persona.
        self._persona_pill = QFrame()
        self._persona_pill.setObjectName("voicePersonaPill")
        self._persona_pill.setStyleSheet(
            f"#voicePersonaPill {{ "
            f"  background-color:{C.surface_2}; "
            f"  border:1px solid {C.glass_border}; "
            f"  border-radius:{R.pill}px; "
            f"}}"
        )
        pp_lay = QHBoxLayout(self._persona_pill)
        pp_lay.setContentsMargins(S.md, 4, S.md, 4)
        pp_lay.setSpacing(S.sm)
        _persona_icon = QLabel()
        _persona_icon.setPixmap(_make_icon_pixmap("mic", 14, C.accent))
        _persona_icon.setFixedSize(14, 14)
        pp_lay.addWidget(_persona_icon)
        self._persona_lbl = QLabel(self._voice_persona)
        persona_lbl = self._persona_lbl
        persona_lbl.setStyleSheet(
            f"color:{C.text}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.small_size}px; "
            f"font-weight:600; letter-spacing:0.5px;"
        )
        pp_lay.addWidget(persona_lbl)
        status_row.addWidget(self._persona_pill, 0, Qt.AlignmentFlag.AlignRight)

        outer.addLayout(status_row)

        # 2. CONTENT: assistant voice stage + live transcript as sibling panes.
        content = QWidget(self)
        content.setStyleSheet("background:transparent; border:none;")
        content_grid = QGridLayout(content)
        content_grid.setContentsMargins(0, 0, 0, 0)
        content_grid.setHorizontalSpacing(S.xl)
        content_grid.setVerticalSpacing(S.lg)
        content_grid.setColumnStretch(0, 7)
        content_grid.setColumnStretch(1, 5)
        content_grid.setRowStretch(0, 1)
        outer.addWidget(content, 1)

        assistant_pane = QFrame(content)
        assistant_pane.setObjectName("voiceAssistantPane")
        assistant_pane.setMinimumWidth(460)
        assistant_pane.setStyleSheet(
            f"#voiceAssistantPane {{ "
            f"  background:qlineargradient(x1:0,y1:0,x2:0,y2:1, "
            f"    stop:0 {C.glass_hi}, stop:0.10 {C.glass_strong}, stop:1 {C.glass}); "
            f"  border:1px solid {C.glass_border}; "
            f"  border-top:1px solid {C.glass_hi}; "
            f"  border-radius:{R.lg}px; "
            f"}}"
        )
        try:
            pane_shadow = QGraphicsDropShadowEffect(assistant_pane)
            pane_shadow.setBlurRadius(34)
            pane_shadow.setOffset(0, 14)
            pane_shadow.setColor(QColor(0, 0, 0, 78))
            assistant_pane.setGraphicsEffect(pane_shadow)
        except Exception:
            pass
        assistant_lay = QVBoxLayout(assistant_pane)
        assistant_lay.setContentsMargins(S.xl, S.lg, S.xl, S.lg)
        assistant_lay.setSpacing(S.md)
        content_grid.addWidget(assistant_pane, 0, 0)

        title_block = QVBoxLayout()
        title_block.setSpacing(3)
        title_block.setContentsMargins(0, 0, 0, 0)
        self._title_lbl = QLabel("Shell Voice")
        title_lbl = self._title_lbl
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(
            f"color:{C.text}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.h1_size}px; font-weight:700;"
        )
        title_block.addWidget(title_lbl)

        self._subtitle_lbl = QLabel("Ready for voice")
        subtitle_lbl = self._subtitle_lbl
        subtitle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_lbl.setStyleSheet(
            f"color:{C.text_muted}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.body_size}px;"
        )
        title_block.addWidget(subtitle_lbl)
        assistant_lay.addLayout(title_block)

        # 3. VOICE STAGE: animated aura + tappable orb + waveform.
        # Centerpiece is the new Three.js particle sphere
        # (WebGLParticleOrb). Falls back to the legacy painted
        # VoiceVisualizer if QtWebEngine is unavailable. Both expose the
        # same `clicked` / `set_amplitude` / `set_state` / `set_speaking`
        # surface, so all downstream call-sites work either way.
        self.stage = VoiceStage(self)
        stage_lay = QVBoxLayout(self.stage)
        stage_lay.setContentsMargins(0, 0, 0, S.sm)
        stage_lay.setSpacing(0)
        stage_lay.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        stage_lay.addStretch(1)
        try:
            if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
                raise RuntimeError("QtWebEngine disabled under offscreen Qt platform")
            if os.environ.get("SHELL_ENABLE_WEBGL_ORB", "0").strip().lower() not in {"1", "true", "yes"}:
                raise RuntimeError("WebGL orb disabled by default; using embedded native visualizer")
            from shell_ui.webgl_particle_orb import WebGLParticleOrb as _Orb, _WEB_OK as _ORB_OK
            if not _ORB_OK:
                raise RuntimeError("QtWebEngine unavailable")
            self.visualizer = _Orb(self.stage)
        except Exception as _orb_e:
            logger.debug("WebGLParticleOrb unavailable, using native voice visualizer: %s", _orb_e)
            self.visualizer = VoiceVisualizer(self.stage)
        self.visualizer.clicked.connect(self._terminate_session)
        stage_lay.addWidget(self.visualizer, 0, Qt.AlignmentFlag.AlignCenter)
        self.waveform = WaveformWidget(self)
        stage_lay.addWidget(self.waveform, 0, Qt.AlignmentFlag.AlignCenter)
        stage_lay.addStretch(1)
        assistant_lay.addWidget(self.stage, 1)

        # 4. CONTROL DOCK: real stateful actions, not decorative icon dots.
        control_dock = QFrame()
        control_dock.setObjectName("voiceControlDock")
        control_dock.setStyleSheet(
            f"#voiceControlDock {{ "
            f"  background-color:{C.surface_2}; "
            f"  border:1px solid {C.glass_border}; "
            f"  border-top:1px solid {C.glass_hi}; "
            f"  border-radius:{R.lg}px; "
            f"}}"
        )
        ctl_row = QHBoxLayout(control_dock)
        ctl_row.setContentsMargins(S.sm, S.sm, S.sm, S.sm)
        ctl_row.setSpacing(S.sm)

        self.mute_btn = self._make_voice_control_btn("Mic On", "mic", tooltip="Mute microphone")
        self.mute_btn.clicked.connect(self._toggle_mute)
        ctl_row.addWidget(self.mute_btn, 1)

        self.term_btn = self._make_voice_control_btn(
            "Start Voice", "play", tooltip="Start or pause voice", primary=True
        )
        self._apply_term_style(active=False)
        self.term_btn.clicked.connect(self._terminate_session)
        self._term_shadow = QGraphicsDropShadowEffect(self.term_btn)
        self._term_shadow.setBlurRadius(18)
        self._term_shadow.setOffset(0, 6)
        gc = QColor(C.accent); gc.setAlpha(80)
        self._term_shadow.setColor(gc)
        self.term_btn.setGraphicsEffect(self._term_shadow)
        ctl_row.addWidget(self.term_btn, 2)

        self.visuals_btn = self._make_voice_control_btn("Visual On", "eye", tooltip="Toggle visuals")
        self.visuals_btn.clicked.connect(self._toggle_visuals)
        ctl_row.addWidget(self.visuals_btn, 1)

        assistant_lay.addWidget(control_dock)

        self._desc = QLabel("Ready")
        self._desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc.setStyleSheet(
            f"color:{C.text_muted}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.body_size}px;"
        )
        assistant_lay.addWidget(self._desc)

        transcript_pane = QFrame(content)
        transcript_pane.setObjectName("voiceTranscriptPane")
        transcript_pane.setMinimumWidth(320)
        transcript_pane.setStyleSheet(
            f"#voiceTranscriptPane {{ "
            f"  background-color:{C.glass}; "
            f"  border:1px solid {C.glass_border}; "
            f"  border-top:1px solid {C.glass_hi}; "
            f"  border-radius:{R.lg}px; "
            f"}}"
        )
        transcript_lay = QVBoxLayout(transcript_pane)
        transcript_lay.setContentsMargins(S.lg, S.lg, S.lg, S.lg)
        transcript_lay.setSpacing(S.md)
        content_grid.addWidget(transcript_pane, 0, 1)

        transcript_head = QHBoxLayout()
        transcript_head.setContentsMargins(2, 0, 2, 0)
        transcript_head.setSpacing(S.sm)
        transcript_title_block = QVBoxLayout()
        transcript_title_block.setContentsMargins(0, 0, 0, 0)
        transcript_title_block.setSpacing(2)
        transcript_lbl = QLabel("Live Transcript")
        transcript_lbl.setStyleSheet(
            f"color:{C.text}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.body_size + 1}px; font-weight:700;"
        )
        transcript_title_block.addWidget(transcript_lbl)
        transcript_subtitle = QLabel("Voice turns")
        transcript_subtitle.setStyleSheet(
            f"color:{C.text_subtle}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.small_size}px;"
        )
        transcript_title_block.addWidget(transcript_subtitle)
        transcript_head.addLayout(transcript_title_block)
        transcript_head.addStretch(1)
        self.clear_btn = self._make_satellite_btn("trash", tooltip="Clear transcript", size=34, icon_size=15)
        self.clear_btn.clicked.connect(self.clear_transcript)
        transcript_head.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignRight)
        transcript_lay.addLayout(transcript_head)

        self._transcript_scroll = QScrollArea()
        self._transcript_scroll.setWidgetResizable(True)
        self._transcript_scroll.setMinimumHeight(240)
        self._transcript_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._transcript_scroll.setStyleSheet(
            f"QScrollArea {{ "
            f"  background-color:transparent; "
            f"  border:none; "
            f"}} "
            f"QScrollBar:vertical {{ width:6px; background:transparent; margin:4px 2px; }} "
            f"QScrollBar::handle:vertical {{ background:{C.border_strong}; border-radius:3px; min-height:24px; }} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0px; }} "
        )
        self._transcript_widget = QWidget()
        self._transcript_widget.setStyleSheet("background:transparent; border:none;")
        self._transcript_layout = QVBoxLayout(self._transcript_widget)
        self._transcript_layout.setContentsMargins(0, S.sm, 0, 0)
        self._transcript_layout.setSpacing(S.md)
        self._transcript_layout.addStretch(1)
        self._transcript_scroll.setWidget(self._transcript_widget)

        self._hint_lbl = QLabel("No voice turns yet")
        self._hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_lbl.setStyleSheet(
            f"color:{C.text_subtle}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.body_size}px; "
            f"padding:{S.xl}px 0;"
        )
        self._transcript_layout.insertWidget(0, self._hint_lbl)
        transcript_lay.addWidget(self._transcript_scroll, 1)

        # Tick the session timer once a second when the session is active.
        self._session_started_at = None
        self._session_timer = QTimer(self)
        self._session_timer.setInterval(1000)
        self._session_timer.timeout.connect(self._tick_session_timer)
        self._session_timer.start()

        # Pulse timer (kept name `_pulse_timer` for compat)
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_status)
        self._pulse_timer.start(80)

        # Hidden labels — kept for any legacy code that pokes at them.
        self._term_lbl = QLabel(""); self._term_lbl.setVisible(False)
        self._mute_lbl = QLabel(""); self._mute_lbl.setVisible(False)
        self._visuals_lbl = QLabel(""); self._visuals_lbl.setVisible(False)

    def _make_voice_control_btn(self, label, icon_name, tooltip="", primary=False):
        from shell_ui import design_tokens as _DT
        C = _DT.C
        btn = QPushButton(label)
        btn.setMinimumHeight(48)
        btn.setMinimumWidth(118 if not primary else 168)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        icon_col = "#061018" if primary else C.text_muted
        btn.setIcon(QIcon(_make_icon_pixmap(icon_name, 18, icon_col)))
        btn.setIconSize(QSize(18, 18))
        btn._voice_icon_name = icon_name
        btn._voice_icon_size = 18
        btn._voice_primary = bool(primary)
        self._apply_voice_control_style(btn, primary=primary)
        return btn

    def _apply_voice_control_style(self, btn, *, active=False, danger=False, primary=False):
        from shell_ui import design_tokens as _DT
        C = _DT.C; T = _DT.T; R = _DT.R
        primary = bool(primary or getattr(btn, "_voice_primary", False))
        if primary:
            bg = C.accent if active else C.accent_soft
            fg = "#061018" if active else C.text
            border = C.accent_hover if active else C.glass_border
            hover_bg = C.accent_hover
        elif danger:
            bg = "rgba(255,113,108,0.14)"
            fg = C.error
            border = C.error
            hover_bg = "rgba(255,113,108,0.22)"
        elif active:
            bg = C.accent_soft
            fg = C.accent
            border = C.accent
            hover_bg = C.surface_3
        else:
            bg = C.surface
            fg = C.text_muted
            border = C.border
            hover_bg = C.surface_3
        btn.setStyleSheet(
            f"QPushButton {{ "
            f"  background-color:{bg}; "
            f"  color:{fg}; "
            f"  border:1px solid {border}; "
            f"  border-radius:{R.md}px; "
            f"  padding:0 14px; "
            f"  font-family:'{T.family}'; "
            f"  font-size:{T.small_size}px; "
            f"  font-weight:700; "
            f"  text-align:center; "
            f"}} "
            f"QPushButton:hover {{ background-color:{hover_bg}; border-color:{C.accent}; }} "
            f"QPushButton:pressed {{ background-color:{C.surface_3}; }}"
        )

    def _make_satellite_btn(self, icon_name, tooltip="", size=40, icon_size=18):
        from shell_ui import design_tokens as _DT
        C = _DT.C
        btn = QPushButton()
        btn.setFixedSize(size, size)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setIcon(QIcon(_make_icon_pixmap(icon_name, icon_size, C.text_muted)))
        btn.setIconSize(QSize(icon_size, icon_size))
        btn._voice_icon_name = icon_name
        btn._voice_icon_size = icon_size
        self._apply_satellite_style(btn)
        sh_rest = 10 if size >= 40 else 7
        sh_hover = 18 if size >= 40 else 13
        sh = QGraphicsDropShadowEffect(btn)
        sh.setBlurRadius(sh_rest); sh.setOffset(0, 2)
        sh.setColor(QColor(0, 0, 0, 90))
        btn.setGraphicsEffect(sh)
        def _on_enter(_e, b=btn, s=sh):
            anim = QPropertyAnimation(s, b"blurRadius", b)
            anim.setDuration(_DT.M.fast_ms)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setEndValue(sh_hover)
            anim.start(); b._sat_anim = anim
        def _on_leave(_e, b=btn, s=sh):
            anim = QPropertyAnimation(s, b"blurRadius", b)
            anim.setDuration(_DT.M.fast_ms)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setEndValue(sh_rest)
            anim.start(); b._sat_anim = anim
        btn.enterEvent = _on_enter  # type: ignore
        btn.leaveEvent = _on_leave  # type: ignore
        return btn

    def _apply_satellite_style(self, btn, *, active=False, danger=False):
        from shell_ui import design_tokens as _DT
        C = _DT.C
        size = max(1, btn.width() or btn.height() or 40)
        bg = C.accent_soft if active else C.surface_2
        border = C.error if danger else (C.accent if active else C.border)
        hover_border = C.error if danger else C.accent
        hover_bg = C.surface_3 if not active else C.accent_soft
        btn.setStyleSheet(
            f"QPushButton {{ "
            f"  background-color:{bg}; "
            f"  border:1px solid {border}; "
            f"  border-radius:{size // 2}px; "
            f"}} "
            f"QPushButton:hover {{ "
            f"  background-color:{hover_bg}; "
            f"  border:1px solid {hover_border}; "
            f"}} "
            f"QPushButton:pressed {{ background-color:{C.surface_3}; }}"
        )

    def _apply_term_style(self, active):
        from shell_ui import design_tokens as _DT
        C = _DT.C
        if active:
            self.term_btn.setText("Pause Voice")
            self.term_btn.setIcon(QIcon(_make_icon_pixmap("pause", 18, "#061018")))
            self._apply_voice_control_style(self.term_btn, active=True, primary=True)
        else:
            self.term_btn.setText("Start Voice")
            self.term_btn.setIcon(QIcon(_make_icon_pixmap("play", 18, C.text)))
            self._apply_voice_control_style(self.term_btn, active=False, primary=True)

    def _animate_term_glow(self, active):
        from shell_ui import design_tokens as _DT
        target = 36 if active else 16
        try:
            anim = QPropertyAnimation(self._term_shadow, b"blurRadius", self)
            anim.setDuration(_DT.M.base_ms)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setEndValue(target)
            anim.start(); self._term_glow_anim = anim
            gc = QColor(_DT.C.accent); gc.setAlpha(180 if active else 80)
            self._term_shadow.setColor(gc)
        except Exception:
            self._term_shadow.setBlurRadius(target)

    def _set_state(self, dot_color, badge_text, desc_text, viz_state):
        from shell_ui import design_tokens as _DT
        C = _DT.C; R = _DT.R
        c = QColor(dot_color)
        self._status_dot.setStyleSheet(
            f"background:rgba({c.red()},{c.green()},{c.blue()},255); "
            f"border-radius:3px; border:none;"
        )
        if hasattr(self, "_status_pill"):
            self._status_pill.setStyleSheet(
                f"#voiceStatusPill {{ "
                f"  background-color:{C.surface_2}; "
                f"  border:1px solid rgba({c.red()},{c.green()},{c.blue()},108); "
                f"  border-radius:{R.pill}px; "
                f"}}"
            )
        self.status_badge.setText(badge_text)
        if hasattr(self, "_subtitle_lbl"):
            self._subtitle_lbl.setText(desc_text)
        self._desc.setText(desc_text)
        try:
            self.visualizer.set_state(viz_state)
        except Exception:
            pass
        try:
            self.stage.set_state(viz_state)
        except Exception:
            pass

    def _toggle_mute(self):
        from shell_ui import design_tokens as _DT
        C = _DT.C
        self._muted = not self._muted
        self._sfx.play_click()
        if self._muted:
            self.mute_btn.setIcon(QIcon(_make_icon_pixmap("mute", 18, C.error)))
            self.mute_btn.setText("Muted")
            self._apply_voice_control_style(self.mute_btn, active=True, danger=True)
            self._set_state(C.error, "MUTED", "Microphone is muted. Tap Mic to resume.", "muted")
        else:
            self.mute_btn.setIcon(QIcon(_make_icon_pixmap("mic", 18, C.text_muted)))
            self.mute_btn.setText("Mic On")
            self._apply_voice_control_style(self.mute_btn, active=False)
            if self._session_active:
                self._set_state(C.warning, "Listening", "Listening... speak naturally", "listening")
            else:
                self._set_state(C.success, "Ready", "Tap to start", "idle")
        self.mute_toggled.emit(self._muted)

    def _terminate_session(self):
        from shell_ui import design_tokens as _DT
        C = _DT.C
        self._sfx.play_click()
        self._session_active = not self._session_active
        if self._session_active:
            self._apply_term_style(active=True)
            self._animate_term_glow(active=True)
            self._session_started_at = _time.time()
            if self._muted:
                self._set_state(C.error, "MUTED", "Microphone is muted. Tap mic to resume.", "muted")
            else:
                self._set_state(C.warning, "LISTENING", "Listening... speak naturally", "listening")
        else:
            self._apply_term_style(active=False)
            self._animate_term_glow(active=False)
            self._session_started_at = None
            try:
                self._session_timer_lbl.setText("")
            except Exception:
                pass
            self._set_state(C.text_muted, "PAUSED", "Session paused. Tap to resume.", "idle")
        self.session_terminated.emit()

    def set_error_state(self, message):
        """Put the voice controls back into a usable stopped state after mic failure."""
        from shell_ui import design_tokens as _DT
        C = _DT.C
        self._session_active = False
        self._session_started_at = None
        try:
            self._session_timer_lbl.setText("")
        except Exception:
            pass
        self._apply_term_style(active=False)
        self._animate_term_glow(active=False)
        self._set_state(C.error, "ERROR", f"Voice unavailable: {message}", "error")

    def _tick_session_timer(self):
        """Update the live mm:ss session duration label, if active."""
        if not self._session_active or self._session_started_at is None:
            return
        try:
            elapsed = int(_time.time() - self._session_started_at)
            mm, ss = divmod(elapsed, 60)
            self._session_timer_lbl.setText(f"·  {mm:02d}:{ss:02d}")
        except Exception:
            pass

    def _toggle_visuals(self):
        from shell_ui import design_tokens as _DT
        C = _DT.C
        self._visuals_on = not self._visuals_on
        self._sfx.play_click()
        # QGraphicsOpacityEffect on this transparent, animated widget is not
        # reliable on macOS/RDP: after toggling off/on, Qt can replay the
        # cached source pixmap at the wrong offset. Use real visibility and
        # force the stage layout/repaint instead.
        try:
            self._viz_opacity_anim = None
            if self.visualizer.graphicsEffect() is not None:
                self.visualizer.setGraphicsEffect(None)
        except Exception:
            pass
        self.visualizer.setVisible(self._visuals_on)
        try:
            self.stage.layout().activate()
            self.stage.updateGeometry()
            self.stage.update()
            self.visualizer.updateGeometry()
            self.visualizer.update()
        except Exception:
            pass
        col = C.text_muted if self._visuals_on else C.text_subtle
        self.visuals_btn.setIcon(QIcon(_make_icon_pixmap("eye", 18, col)))
        self.visuals_btn.setText("Visual On" if self._visuals_on else "Visual Off")
        self._apply_voice_control_style(self.visuals_btn, active=not self._visuals_on)
        self.visuals_toggled.emit(self._visuals_on)

    # Speaking / amplitude entry points (called by main UI)
    def set_amplitude(self, amp):
        try:
            self.visualizer.set_amplitude(amp)
        except Exception:
            pass
        try:
            self.waveform.set_amplitude(amp)
        except Exception:
            pass
        try:
            self.stage.set_amplitude(amp)
        except Exception:
            pass

    def set_speaking(self, speaking):
        from shell_ui import design_tokens as _DT
        C = _DT.C
        try:
            self.visualizer.set_speaking(speaking)
        except Exception:
            pass
        if speaking:
            self._set_state(C.accent, "Speaking", "Shell speaking...", "speaking")
        elif self._session_active and not self._muted:
            self._set_state(C.warning, "Listening", "Listening... speak naturally", "listening")

    def add_transcript(self, role, text):
        """Add a transcript entry (user speech or shell reply)."""
        from shell_ui import design_tokens as _DT
        C = _DT.C; T = _DT.T; S = _DT.S; R = _DT.R; SH = _DT.SH

        if hasattr(self, '_hint_lbl') and self._hint_lbl.isVisible():
            self._hint_lbl.setVisible(False)

        is_user = (role == "user")
        prefix = "You" if is_user else "Shell"

        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent; border:none;")
        w_lay = QVBoxLayout(wrapper)
        w_lay.setContentsMargins(0, 0, 0, 0)
        w_lay.setSpacing(4)
        if is_user:
            w_lay.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            w_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)

        role_lbl = QLabel(prefix)
        role_lbl.setStyleSheet(
            f"color:{C.text_subtle}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.small_size}px; font-weight:600; "
            f"padding:0 {S.sm}px;"
        )
        if is_user:
            role_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        w_lay.addWidget(role_lbl)

        bubble = QFrame()
        bubble.setObjectName("voiceBubble")
        if is_user:
            bubble.setStyleSheet(
                f"#voiceBubble {{ "
                f"  background-color:{C.accent_soft}; "
                f"  border:1px solid {C.glass_border}; "
                f"  border-radius:{R.lg}px; "
                f"}}"
            )
        else:
            bubble.setStyleSheet(
                f"#voiceBubble {{ "
                f"  background-color:{C.surface_2}; "
                f"  border:1px solid {C.border}; "
                f"  border-radius:{R.lg}px; "
                f"}}"
            )
        b_lay = QVBoxLayout(bubble)
        b_lay.setContentsMargins(S.lg, S.md, S.lg, S.md)
        b_lay.setSpacing(0)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color:{C.text}; background:transparent; border:none; "
            f"font-family:'{T.family}'; font-size:{T.body_size}px;"
        )
        b_lay.addWidget(body)

        try:
            sh = QGraphicsDropShadowEffect(bubble)
            sh.setBlurRadius(SH.soft.blur)
            sh.setOffset(0, SH.soft.offset_y)
            sh.setColor(QColor(0, 0, 0, 60))
            bubble.setGraphicsEffect(sh)
        except Exception:
            pass

        try:
            max_bubble_w = max(260, min(560, self._transcript_scroll.width() - S.xl * 2))
        except Exception:
            max_bubble_w = 560
        bubble.setMaximumWidth(max_bubble_w)
        w_lay.addWidget(bubble)

        count = self._transcript_layout.count()
        self._transcript_layout.insertWidget(count - 1, wrapper)

        QTimer.singleShot(50, lambda: self._transcript_scroll.verticalScrollBar().setValue(
            self._transcript_scroll.verticalScrollBar().maximum()))

    def clear_transcript(self):
        """Clear all transcript entries."""
        while self._transcript_layout.count():
            item = self._transcript_layout.takeAt(0)
            if not item:
                continue
            w = item.widget()
            if w is self._hint_lbl:
                w.setParent(None)
            elif w:
                w.deleteLater()
        if hasattr(self, '_hint_lbl'):
            self._hint_lbl.setVisible(True)
            self._transcript_layout.addWidget(self._hint_lbl)
        self._transcript_layout.addStretch(1)

    def _pulse_status(self):
        if not self._session_active:
            return
        from shell_ui import design_tokens as _DT
        C = _DT.C
        self._status_phase += 0.08
        alpha = int(140 + 115 * (0.5 + 0.5 * math.sin(self._status_phase)))
        if self._muted:
            color = C.error
        elif getattr(self.visualizer, "_state", "idle") == "speaking":
            color = C.accent
        else:
            color = C.warning
        c = QColor(color)
        self._status_dot.setStyleSheet(
            f"background:rgba({c.red()},{c.green()},{c.blue()},{alpha}); "
            f"border-radius:3px; border:none;"
        )


# =====================================================================

class _VoiceOrbBridge:
    """Non-visual adapter that keeps legacy orb call sites working."""

    def __init__(self, owner):
        self._owner = owner

    def setVisible(self, _visible):
        pass

    def set_energy(self, amp):
        try:
            self._owner.voice_page.set_amplitude(amp)
        except Exception:
            pass

    def set_speaking(self, speaking, *args, **kwargs):
        try:
            self._owner.voice_page.set_speaking(bool(speaking))
        except Exception:
            pass

    def set_thinking(self, thinking):
        try:
            vp = self._owner.voice_page
            if thinking:
                from shell_ui import design_tokens as _DT
                vp._set_state(_DT.C.warning, "THINKING", "Processing...", "listening")
            elif getattr(vp, "_session_active", False) and not getattr(vp, "_muted", False):
                from shell_ui import design_tokens as _DT
                vp._set_state(_DT.C.warning, "LISTENING", "Listening... speak naturally", "listening")
        except Exception:
            pass

    def set_listening_mode(self, listening):
        try:
            vp = self._owner.voice_page
            if listening and not getattr(vp, "_muted", False):
                from shell_ui import design_tokens as _DT
                vp._set_state(_DT.C.warning, "LISTENING", "Listening... speak naturally", "listening")
        except Exception:
            pass

    def trigger_user_speaking(self, strength=1.0):
        try:
            self._owner.voice_page.set_amplitude(strength)
        except Exception:
            pass

# =====================================================================

class ChatBubble(QFrame):
    # ── Hover-action toolbar signals ─────────────────────────────────
    # Both bubble roles get a hover toolbar (Copy for user; Copy +
    # Regenerate + Speak for shell). These signals let ChatPage hook
    # the actions without ChatBubble owning the TTS / message pipeline.
    regenerate_requested = pyqtSignal(object)  # carries the bubble itself
    speak_requested = pyqtSignal(str)          # carries the raw text
    # Emitted when a `stream_text(...)` typewriter run finishes (or is
    # finalised early because a new stream started). Lets ChatPage hook
    # post-stream behaviours (e.g. final scroll, TTS) without polling.
    stream_finished = pyqtSignal()

    def __init__(self, role, text, parent=None):
        super().__init__(parent)
        self._role = role
        self._raw_text = text
        self._actions_visible = False
        self._actions_anim = None  # keep ref so it isn't GC'd mid-fade
        # Live-typewriter state. The first prose QLabel created in the
        # constructor is captured as `_stream_label` so `stream_text(...)`
        # knows where to write characters. Code-block widgets are not
        # streamed — they render instantly via CodeBlock as before.
        self._stream_label = None
        self._stream_timer = None
        self._stream_caret_timer = None
        self._stream_caret_visible = True
        self._stream_text_full = ""
        self._stream_pos = 0
        self._stream_interval_ms = 6
        self._stream_paused = False
        self._stream_active = False
        is_user = role == "user"
        max_w = 780 if not is_user else 580

        self.setMaximumWidth(max_w)

        try:
            from shell_ui.design_tokens import C as _DC, accent_text_color as _accent_txt
            _bubble_glass = _DC.glass
            _bubble_strong = _DC.glass_strong
            _bubble_hi = _DC.glass_hi
            _bubble_border = _DC.glass_border
            _bubble_accent = _DC.accent
            _bubble_accent_hover = _DC.accent_hover
            _bubble_accent_soft = _DC.accent_soft
            _bubble_accent_text = _accent_txt()
            _bubble_text = _DC.text
            _bubble_muted = _DC.text_muted
            _bubble_subtle = _DC.text_subtle
            _bubble_bg = _DC.bg
        except Exception:
            _bubble_glass = "rgba(22,32,50,0.30)"
            _bubble_strong = "rgba(32,42,64,0.38)"
            _bubble_hi = "rgba(200,252,255,0.28)"
            _bubble_border = "rgba(143,245,255,0.14)"
            _bubble_accent = C_PRIMARY
            _bubble_accent_hover = C_SECONDARY
            _bubble_accent_soft = "rgba(143,245,255,0.08)"
            _bubble_accent_text = C_BG
            _bubble_text = C_TEXT
            _bubble_muted = C_TEXT_MUTED
            _bubble_subtle = C_TEXT_MUTED
            _bubble_bg = C_BG

        if is_user:
            self.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0,y1:0,x2:0.1,y2:1,
                        stop:0 {_bubble_hi}, stop:0.07 {_bubble_strong},
                        stop:0.58 {_bubble_accent_soft}, stop:1 {_bubble_glass});
                    border: 1px solid {_bubble_border};
                    border-top: 2px solid {_bubble_hi};
                    border-left: 1px solid {_bubble_hi};
                    border-radius: 22px;
                    border-bottom-right-radius: 6px;
                    padding: 16px 22px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0,y1:0,x2:0.1,y2:1,
                        stop:0 {_bubble_hi}, stop:0.07 {_bubble_strong},
                        stop:0.58 {_bubble_glass}, stop:1 {_bubble_glass});
                    border: 1px solid {_bubble_border};
                    border-top: 2px solid {_bubble_hi};
                    border-left: 1px solid {_bubble_hi};
                    border-radius: 22px;
                    border-bottom-left-radius: 6px;
                    padding: 16px 22px;
                }}
            """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # Role label with avatar
        role_row = QHBoxLayout()
        role_row.setSpacing(8)

        # Avatar circle
        avatar = QLabel("U" if is_user else "")
        avatar.setFixedSize(22, 22)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if is_user:
            avatar.setStyleSheet(f"""
                background:{_bubble_accent_soft}; border-radius:11px;
                color:{_bubble_muted}; font-family:'{_FONT}'; font-size:9px; font-weight:700;
                border:1px solid {_bubble_border};
            """)
        else:
            _avatar_logo = _shell_logo_pixmap(22)
            if _avatar_logo.isNull():
                avatar.setText("S")
                avatar.setStyleSheet(f"""
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 {_bubble_accent}, stop:1 {_bubble_accent_hover});
                    border-radius:11px;
                    color:{_bubble_accent_text}; font-family:'{_FONT}'; font-size:9px; font-weight:800;
                    border:none;
                """)
                _glow_shadow(avatar, _bubble_accent, 8, 60)
            else:
                avatar.setPixmap(_avatar_logo)
                avatar.setStyleSheet("background:transparent; border:none;")
        role_row.addWidget(avatar)

        role_lbl = QLabel("SHELL" if not is_user else "YOU")
        role_color = _bubble_accent if not is_user else _bubble_muted
        role_lbl.setStyleSheet(f"""
            color:{role_color}; font-family:'{_FONT}'; font-size:9px;
            font-weight:700; letter-spacing:3px;
            border:none; background:transparent;
        """)
        role_row.addWidget(role_lbl)
        role_row.addStretch(1)

        # Copy button
        copy_btn = QPushButton("COPY")
        copy_btn.setFixedSize(44, 20)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                color:{_bubble_subtle}; font-family:'{_FONT}'; font-size:8px;
                font-weight:700; letter-spacing:2px;
                background:transparent; border:1px solid {_bubble_border};
                border-radius:4px; padding:0;
            }}
            QPushButton:hover {{
                color:{_bubble_accent}; border:1px solid {_bubble_accent};
                background:{_bubble_accent_soft};
            }}
        """)
        copy_btn.clicked.connect(lambda: self._copy_text(text))
        role_row.addWidget(copy_btn)

        if not is_user:
            listen_btn = QPushButton()
            listen_btn.setFixedSize(24, 20)
            listen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            listen_btn.setIcon(QIcon(_make_icon_pixmap("voice", 13, _bubble_accent)))
            listen_btn.setIconSize(QSize(13, 13))
            listen_btn.setToolTip("Listen to this reply")
            listen_btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent;
                    border:1px solid {_bubble_border};
                    border-radius:4px; padding:0;
                }}
                QPushButton:hover {{
                    background:{_bubble_accent_soft};
                    border:1px solid {_bubble_accent};
                }}
            """)
            listen_btn.clicked.connect(
                lambda _checked=False: self.speak_requested.emit(self._raw_text)
            )
            role_row.addWidget(listen_btn)

        # Timestamp
        ts = QLabel(datetime.now().strftime("%H:%M"))
        ts.setStyleSheet(f"""
            color:{_bubble_subtle}; font-family:'{_FONT}'; font-size:9px;
            border:none; background:transparent;
        """)
        role_row.addWidget(ts)
        lay.addLayout(role_row)

        # Parse text for fenced code blocks. When a fence is present, route
        # code segments through the new Mac-style `CodeBlock` widget (with
        # pygments syntax highlighting + Copy button). Prose segments keep
        # the existing markdown-to-HTML QLabel rendering — strictly
        # backwards-compatible for prose-only messages.
        if "```" in text:
            try:
                from shell_ui.code_block import CodeBlock as _CodeBlock
            except Exception as _cb_err:
                logger.debug("CodeBlock import failed: %s", _cb_err)
                _CodeBlock = None
        else:
            _CodeBlock = None

        parts = text.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Regular text — render markdown via the new design-token
                # renderer. Falls back to the legacy in-class converter on
                # import failure so the bubble always shows something.
                if part.strip():
                    try:
                        from shell_ui.markdown_render import render as _md_render
                        html = _md_render(part.strip())
                    except Exception as _md_err:
                        logger.debug("markdown_render failed, using legacy: %s", _md_err)
                        html = self._markdown_to_html(part.strip())
                    text_color = _bubble_text if is_user else _bubble_muted
                    lbl = QLabel(html)
                    lbl.setTextFormat(Qt.TextFormat.RichText)
                    lbl.setWordWrap(True)
                    # TextBrowserInteraction enables link clicks + selection.
                    # Combined with setOpenExternalLinks(True) Qt routes a
                    # click through QDesktopServices.openUrl(...).
                    lbl.setOpenExternalLinks(True)
                    lbl.setTextInteractionFlags(
                        Qt.TextInteractionFlag.TextBrowserInteraction)
                    lbl.setStyleSheet(f"""
                        color:{text_color}; font-family:'{_FONT}'; font-size:14px;
                        line-height:1.6; border:none; background:transparent;
                    """)
                    lay.addWidget(lbl)
                    # Remember the first prose label so the typewriter
                    # streamer has a target. Keep the unstripped/stripped
                    # source text on the bubble for re-render at the end.
                    if self._stream_label is None:
                        self._stream_label = lbl
                        self._stream_label_source = part.strip()
            else:
                # Fenced code segment. Strip the leading language token
                # (single word, < 20 chars) from the first line, mirroring
                # the legacy behaviour.
                raw = part.lstrip("\n").rstrip()
                lines = raw.split("\n")
                lang = ""
                if lines and lines[0] and " " not in lines[0] and len(lines[0]) < 20:
                    lang = lines[0].strip()
                    code = "\n".join(lines[1:])
                else:
                    code = raw

                if _CodeBlock is not None:
                    try:
                        lay.addWidget(_CodeBlock(lang, code, parent=self))
                        continue
                    except Exception as _cb_err:
                        logger.debug("CodeBlock render failed, falling back: %s", _cb_err)

                # --- legacy fallback: terminal-style block with line numbers ---
                code_frame = QFrame()
                code_frame.setStyleSheet(f"""
                    QFrame {{
                        background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                            stop:0 {_bubble_strong}, stop:0.5 {_bubble_glass}, stop:1 {_bubble_glass});
                        border: 1px solid {_bubble_border};
                        border-top: 2px solid {_bubble_hi};
                        border-radius: 16px;
                    }}
                """)
                code_lay = QVBoxLayout(code_frame)
                code_lay.setContentsMargins(0, 0, 0, 0)
                code_lay.setSpacing(0)

                # Terminal header with dots
                header = QWidget()
                header.setFixedHeight(36)
                header.setStyleSheet(f"""
                    background:{_bubble_strong};
                    border:none;
                    border-top-left-radius:16px;
                    border-top-right-radius:16px;
                """)
                h_lay = QHBoxLayout(header)
                h_lay.setContentsMargins(14, 0, 14, 0)
                h_lay.setSpacing(6)

                # Traffic light dots
                for dot_color in [C_ERROR, C_WARNING, _bubble_accent]:
                    d = QLabel()
                    d.setFixedSize(8, 8)
                    d.setStyleSheet(f"background:{dot_color}; border-radius:4px; border:none;")
                    h_lay.addWidget(d)

                h_lay.addStretch(1)
                if lang:
                    lang_lbl = QLabel(lang)
                    lang_lbl.setStyleSheet(f"""
                        color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:10px;
                        font-weight:600; letter-spacing:2px; text-transform:uppercase;
                        border:none; background:transparent;
                    """)
                    h_lay.addWidget(lang_lbl)

                code_lay.addWidget(header)

                # Code content with line numbers
                code_content = QWidget()
                code_content.setStyleSheet("background:transparent; border:none;")
                cc_lay = QVBoxLayout(code_content)
                cc_lay.setContentsMargins(16, 12, 16, 12)
                cc_lay.setSpacing(2)

                code_lines = code.split("\n")
                for ln_num, ln in enumerate(code_lines, 1):
                    line_row = QHBoxLayout()
                    line_row.setSpacing(16)
                    # Line number
                    num_lbl = QLabel(str(ln_num))
                    num_lbl.setFixedWidth(20)
                    num_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    num_lbl.setStyleSheet(f"""
                        color:rgba(115,117,124,0.50); font-family:'{_MONO}';
                        font-size:12px; border:none; background:transparent;
                    """)
                    line_row.addWidget(num_lbl)
                    # Code line — syntax colored
                    colored = self._syntax_color(ln)
                    code_lbl = QLabel(colored)
                    code_lbl.setTextFormat(Qt.TextFormat.RichText)
                    code_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    code_lbl.setStyleSheet(f"""
                        font-family:'{_MONO}'; font-size:12px;
                        border:none; background:transparent;
                    """)
                    line_row.addWidget(code_lbl, 1)
                    cc_lay.addLayout(line_row)

                code_lay.addWidget(code_content)
                lay.addWidget(code_frame)

        # ── Hover-action toolbar (floating sibling overlay) ──────────
        # User bubbles get Copy only; shell bubbles get Copy +
        # Regenerate + Speak. Hidden at rest (opacity 0); fades in on
        # hover, out on leave. Positioned in resizeEvent so it tracks
        # the bubble's geometry.
        self._build_actions_toolbar(is_user)

    def _build_actions_toolbar(self, is_user):
        """Construct the floating top-right action toolbar. Lives as a
        child widget of the bubble so it inherits z-order automatically.
        Each button is 28x28 with hover accent_soft fill — matches the
        design tokens so theme switches flow through."""
        try:
            from shell_ui.design_tokens import C as _DC, R as _DR
            _accent = _DC.accent
            _accent_soft = _DC.accent_soft
            _border = _DC.glass_border
            _glass_strong = _DC.glass_strong
            _radius = _DR.md
        except Exception:
            _accent = "#00f0ff"
            _accent_soft = "rgba(0,240,255,0.12)"
            _border = "rgba(143,245,255,0.18)"
            _glass_strong = "rgba(26,36,58,0.72)"
            _radius = 12

        bar = QFrame(self)
        bar.setObjectName("bubbleActionsBar")
        bar.setCursor(Qt.CursorShape.ArrowCursor)
        # Subtle floating chip background so the buttons read as a
        # cohesive group rather than three loose icons.
        bar.setStyleSheet(
            f"QFrame#bubbleActionsBar {{ "
            f"  background: {_glass_strong}; "
            f"  border: 1px solid {_border}; "
            f"  border-radius: {_radius}px; "
            f"}}"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 4, 4, 4)
        bl.setSpacing(2)

        btn_qss = (
            f"QPushButton {{ "
            f"  background: transparent; border: none; "
            f"  border-radius: 8px; "
            f"  color: rgba(232,244,255,0.70); "
            f"  font-size: 14px; "
            f"}} "
            f"QPushButton:hover {{ "
            f"  background: {_accent_soft}; "
            f"  color: {_accent}; "
            f"}}"
        )

        # Copy — both roles get this.
        copy_act_btn = QPushButton("\U0001F4CB")  # 📋
        copy_act_btn.setFixedSize(28, 28)
        copy_act_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_act_btn.setToolTip("Copy")
        copy_act_btn.setStyleSheet(btn_qss)
        copy_act_btn.clicked.connect(self._on_copy_action)
        bl.addWidget(copy_act_btn)

        # Shell-only actions: Regenerate + Speak.
        if not is_user:
            regen_btn = QPushButton("\U0001F501")  # 🔄
            regen_btn.setFixedSize(28, 28)
            regen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            regen_btn.setToolTip("Regenerate")
            regen_btn.setStyleSheet(btn_qss)
            regen_btn.clicked.connect(
                lambda _checked=False: self.regenerate_requested.emit(self)
            )
            bl.addWidget(regen_btn)

            speak_btn = QPushButton("\U0001F50A")  # 🔊
            speak_btn.setFixedSize(28, 28)
            speak_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            speak_btn.setToolTip("Speak")
            speak_btn.setStyleSheet(btn_qss)
            speak_btn.clicked.connect(
                lambda _checked=False: self.speak_requested.emit(self._raw_text)
            )
            bl.addWidget(speak_btn)

        # Hidden by default — opacity effect drives the fade. We keep
        # the widget mapped (visible-but-transparent) so a future
        # fade-in animation has something to animate to.
        self._actions_bar = bar
        self._actions_opacity = QGraphicsOpacityEffect(bar)
        self._actions_opacity.setOpacity(0.0)
        bar.setGraphicsEffect(self._actions_opacity)
        bar.adjustSize()
        bar.show()
        # Initial position is set in showEvent / resizeEvent.

    def _position_actions_bar(self):
        """Pin the toolbar to the bubble's top-right corner with a
        small inset so it floats just inside the bubble border."""
        bar = getattr(self, "_actions_bar", None)
        if bar is None:
            return
        bar.adjustSize()
        inset_x, inset_y = 8, 6
        x = max(0, self.width() - bar.width() - inset_x)
        y = inset_y
        bar.move(x, y)
        bar.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_actions_bar()

    def showEvent(self, event):
        super().showEvent(event)
        # Defer one tick so child widget sizes settle before we measure.
        QTimer.singleShot(0, self._position_actions_bar)

    def enterEvent(self, event):
        self._fade_actions(True)
        # Pause any in-flight typewriter so the user can read partial
        # output without it racing past while they hover.
        try:
            self.pause_stream()
        except Exception:
            pass
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._fade_actions(False)
        try:
            self.resume_stream()
        except Exception:
            pass
        super().leaveEvent(event)

    def _fade_actions(self, show: bool):
        """Animate the toolbar opacity (160ms OutCubic per spec)."""
        eff = getattr(self, "_actions_opacity", None)
        if eff is None:
            return
        if self._actions_visible == show:
            return
        self._actions_visible = show
        try:
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(160)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(eff.opacity())
            anim.setEndValue(1.0 if show else 0.0)
            anim.start()
            self._actions_anim = anim
        except Exception as _e:
            try:
                eff.setOpacity(1.0 if show else 0.0)
            except Exception:
                pass
            logger.debug("actions fade failed: %s", _e)

    def _on_copy_action(self):
        """Copy + brief 'Copied!' tooltip flash near the toolbar."""
        self._copy_text(self._raw_text)
        try:
            bar = getattr(self, "_actions_bar", None)
            anchor = bar if bar is not None else self
            pos = anchor.mapToGlobal(QPoint(anchor.width() // 2, -4))
            QToolTip.showText(pos, "Copied!", anchor)
            QTimer.singleShot(1200, QToolTip.hideText)
        except Exception as _e:
            logger.debug("copied tooltip failed: %s", _e)

    def contextMenuEvent(self, event):
        """Right-click context menu on chat bubble."""
        from PyQt6.QtWidgets import QMenu
        try:
            from shell_ui.design_tokens import C as _DC
            _cm_strong = _DC.glass_strong
            _cm_glass = _DC.glass
            _cm_border = _DC.glass_border
            _cm_hi = _DC.glass_hi
            _cm_text = _DC.text
            _cm_accent = _DC.accent
            _cm_accent_soft = _DC.accent_soft
        except Exception:
            _cm_strong = "rgba(30,38,54,0.95)"
            _cm_glass = "rgba(20,28,42,0.92)"
            _cm_border = "rgba(143,245,255,0.20)"
            _cm_hi = "rgba(143,245,255,0.35)"
            _cm_text = C_TEXT
            _cm_accent = C_PRIMARY
            _cm_accent_soft = "rgba(143,245,255,0.12)"
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {_cm_strong}, stop:1 {_cm_glass});
                border:1px solid {_cm_border};
                border-top:2px solid {_cm_hi};
                border-radius:12px; padding:6px;
                color:{_cm_text}; font-family:'{_FONT}'; font-size:12px;
            }}
            QMenu::item {{
                padding:8px 24px; border-radius:8px;
            }}
            QMenu::item:selected {{
                background:{_cm_accent_soft};
                color:{_cm_accent};
            }}
        """)
        copy_act = menu.addAction("Copy Text")
        del_act = menu.addAction("Delete Message")
        action = menu.exec(event.globalPos())
        if action == copy_act:
            self._copy_text(self._raw_text)
        elif action == del_act:
            self.setVisible(False)
            self.deleteLater()

    @staticmethod
    def _copy_text(text):
        """Copy message text to clipboard."""
        app = QApplication.instance()
        if app:
            clipboard = app.clipboard()
            clipboard.setText(text)

    # ── Live typewriter streaming (Mac/ChatGPT-style char reveal) ──────
    def stream_text(self, text, speed_chars_per_sec=180):
        """Reveal `text` character-by-character on this bubble's first
        prose label, with a blinking caret while in flight.

        Behaviour:
          - Replaces the prose label's content with an empty string up
            front, then ticks one char in at ~`speed_chars_per_sec`.
          - For very long replies (>1500 chars) auto-scales speed up to
            320 chars/sec so the user isn't kept waiting.
          - For mixed prose+code messages, only the prose preceding the
            first code fence is streamed; code blocks render instantly
            via the existing CodeBlock widget (already done in __init__).
          - If a stream is already in progress, finalises it immediately
            and starts the new one.
          - Pauses while the user hovers the bubble (handled by the
            existing enterEvent/leaveEvent overrides), resumes on leave.
          - Emits `stream_finished` once the final char is on screen and
            the brief shimmer caret-removal has played.
        """
        # Bail-out cases — nothing to stream / no target label.
        if not text:
            try:
                self.stream_finished.emit()
            except Exception:
                pass
            return

        # If something is already streaming, snap it to the end so the
        # new one starts cleanly.
        if self._stream_active:
            try:
                self._finish_stream(emit=False)
            except Exception:
                pass

        # Pick the prose-only portion when the message contains code.
        # Mirrors the constructor's split-by-``` rule: the first segment
        # (index 0) is always prose. The CodeBlock widgets are already
        # mounted, so we only need to type the leading prose.
        if "```" in text:
            prose = text.split("```", 1)[0].strip()
        else:
            prose = text

        # If there's no prose to stream (e.g. message starts with a code
        # fence), just signal completion — code blocks are already shown.
        if not prose:
            try:
                self.stream_finished.emit()
            except Exception:
                pass
            return

        # No prose label was captured (defensive — should always exist
        # for streamable messages because we type the first prose part).
        if self._stream_label is None:
            try:
                self.stream_finished.emit()
            except Exception:
                pass
            return

        # Speed scaling — long replies type faster so the user doesn't
        # wait forever. 180 cps default, ramp linearly to 320 cps at
        # >=1500 chars.
        eff_cps = float(speed_chars_per_sec or 180)
        n = len(prose)
        if n > 1500:
            eff_cps = max(eff_cps, 320.0)
        # Convert chars/sec → ms/char (clamped to a sane range).
        interval_ms = max(3, int(round(1000.0 / max(1.0, eff_cps))))

        # Reset the prose label so the typewriter starts from blank.
        try:
            self._stream_label.setTextFormat(Qt.TextFormat.RichText)
            self._stream_label.setText("")
        except Exception:
            pass

        # Build the blinking caret as a sibling QLabel placed in the
        # bubble's main layout (so it sits naturally under the prose).
        # We tear it down at the end of streaming.
        self._build_stream_caret()

        # Persist run state.
        self._stream_text_full = prose
        self._stream_pos = 0
        self._stream_interval_ms = interval_ms
        self._stream_paused = False
        self._stream_active = True

        # Drive the reveal loop.
        if self._stream_timer is None:
            self._stream_timer = QTimer(self)
            self._stream_timer.timeout.connect(self._stream_tick)
        self._stream_timer.start(interval_ms)

    def _build_stream_caret(self):
        """Create (or reuse) the blinking caret label and attach it
        right after the streaming prose label. Uses C.accent for colour."""
        try:
            from shell_ui.design_tokens import C as _DC
            _accent = _DC.accent
        except Exception:
            _accent = "#00f0ff"
        caret = getattr(self, "_stream_caret", None)
        if caret is None:
            caret = QLabel(self)
            caret.setText("▍")  # ▍ — left-half block; reads as a slim caret
            caret.setStyleSheet(
                f"color:{_accent}; background:transparent; border:none; "
                f"font-family:'{_FONT}'; font-size:14px; "
                f"font-weight:700; padding:0; margin:0;"
            )
            caret.setFixedHeight(18)
            self._stream_caret = caret
        # Ensure it lives in the bubble's main vertical layout (below
        # the prose label). If already inserted, we leave it where it is.
        try:
            lay = self.layout()
            already_in = False
            if lay is not None:
                for i in range(lay.count()):
                    it = lay.itemAt(i)
                    if it is not None and it.widget() is caret:
                        already_in = True
                        break
                if not already_in:
                    lay.addWidget(caret)
        except Exception:
            pass
        caret.show()

        # Blink @ 2 Hz — toggle visibility every 250 ms.
        self._stream_caret_visible = True
        if self._stream_caret_timer is None:
            self._stream_caret_timer = QTimer(self)
            self._stream_caret_timer.timeout.connect(self._stream_caret_blink)
        self._stream_caret_timer.start(250)

    def _stream_caret_blink(self):
        caret = getattr(self, "_stream_caret", None)
        if caret is None:
            return
        self._stream_caret_visible = not self._stream_caret_visible
        try:
            caret.setVisible(self._stream_caret_visible)
        except Exception:
            pass

    def _stream_tick(self):
        """Reveal the next character. Called by `_stream_timer`."""
        if not self._stream_active:
            return
        if self._stream_paused:
            return
        self._stream_pos += 1
        if self._stream_pos >= len(self._stream_text_full):
            self._stream_pos = len(self._stream_text_full)
            self._render_stream_partial()
            self._finish_stream(emit=True)
            return
        self._render_stream_partial()
        # Smooth-scroll on every line break or every 80 chars so the
        # user always sees the bottom of the growing bubble.
        try:
            ch = self._stream_text_full[self._stream_pos - 1]
            if ch == "\n" or self._stream_pos % 80 == 0:
                self._request_smooth_scroll()
        except Exception:
            pass

    def _render_stream_partial(self):
        """Render the current `[0:_stream_pos]` slice through the same
        markdown→HTML pipeline used at rest, so partial bold/italic/code
        runs look right (and not raw asterisks)."""
        lbl = self._stream_label
        if lbl is None:
            return
        try:
            partial = self._stream_text_full[:self._stream_pos]
            html = ChatBubble._markdown_to_html(partial)
            lbl.setText(html)
        except Exception:
            try:
                lbl.setText(self._stream_text_full[:self._stream_pos])
            except Exception:
                pass

    def _request_smooth_scroll(self):
        """Walk up to the ChatPage and ask it to smooth-scroll. Done by
        attribute lookup so ChatBubble stays decoupled."""
        try:
            p = self.parent()
            hops = 0
            while p is not None and hops < 8:
                if hasattr(p, "_smooth_scroll_to_bottom"):
                    p._smooth_scroll_to_bottom()
                    return
                p = p.parent()
                hops += 1
        except Exception:
            pass

    def _finish_stream(self, emit=True):
        """Snap to the full text, play a brief caret shimmer, then tear
        the caret down. Always safe to call multiple times."""
        # Stop the reveal timer.
        try:
            if self._stream_timer is not None:
                self._stream_timer.stop()
        except Exception:
            pass
        # Snap to the full prose so partial markdown closes cleanly.
        if self._stream_label is not None:
            try:
                final_html = ChatBubble._markdown_to_html(self._stream_text_full)
                self._stream_label.setText(final_html)
            except Exception:
                pass
        self._stream_pos = len(self._stream_text_full)
        self._stream_active = False
        # Caret shimmer — brief opacity flash then remove. We use a
        # QGraphicsOpacityEffect anim so it actually fades rather than
        # just popping.
        caret = getattr(self, "_stream_caret", None)
        if caret is not None:
            try:
                if self._stream_caret_timer is not None:
                    self._stream_caret_timer.stop()
            except Exception:
                pass
            try:
                caret.setVisible(True)
                eff = QGraphicsOpacityEffect(caret)
                eff.setOpacity(1.0)
                caret.setGraphicsEffect(eff)
                anim = QPropertyAnimation(eff, b"opacity", caret)
                anim.setDuration(220)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.setKeyValueAt(0.0, 1.0)
                anim.setKeyValueAt(0.5, 0.2)
                anim.setKeyValueAt(1.0, 0.0)
                # Drop the caret entirely once the shimmer finishes so
                # it doesn't take layout space at rest.
                def _drop_caret(_c=caret):
                    try:
                        _c.hide()
                        _c.setParent(None)
                        _c.deleteLater()
                    except Exception:
                        pass
                    self._stream_caret = None
                anim.finished.connect(_drop_caret)
                anim.start()
                self._stream_caret_anim = anim
            except Exception:
                # Fallback — just drop it without the shimmer.
                try:
                    caret.hide()
                    caret.setParent(None)
                    caret.deleteLater()
                except Exception:
                    pass
                self._stream_caret = None
        # One last scroll so the final line is in view.
        self._request_smooth_scroll()
        if emit:
            try:
                self.stream_finished.emit()
            except Exception:
                pass

    def pause_stream(self):
        """Suspend the typewriter (called from enterEvent on hover)."""
        if self._stream_active:
            self._stream_paused = True

    def resume_stream(self):
        """Resume the typewriter (called from leaveEvent)."""
        if self._stream_active and self._stream_paused:
            self._stream_paused = False

    @staticmethod
    def _inline_fmt(text):
        """Apply inline markdown: bold, italic, code, links, strikethrough."""
        t = text
        t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
        t = re.sub(r'__(.+?)__', r'<b>\1</b>', t)
        t = re.sub(r'\*(.+?)\*', r'<i>\1</i>', t)
        t = re.sub(r'_(.+?)_', r'<i>\1</i>', t)
        t = re.sub(r'~~(.+?)~~', r'<s>\1</s>', t)
        t = re.sub(r'`(.+?)`', f'<code style="background:rgba(143,245,255,0.10);color:{C_PRIMARY};padding:1px 5px;border-radius:4px;font-size:13px">' + r'\1</code>', t)
        t = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" style="color:' + C_PRIMARY + r'">\1</a>', t)
        return t

    @staticmethod
    def _markdown_to_html(text):
        """Convert markdown text to HTML for rich display in chat bubbles."""
        lines = text.split('\n')
        html_lines = []
        list_type = None  # None, 'ul', 'ol'

        def _close_list():
            nonlocal list_type
            if list_type:
                html_lines.append(f'</{list_type}>')
                list_type = None

        for line in lines:
            stripped = line.strip()

            # Headers
            if stripped.startswith('### '):
                _close_list()
                html_lines.append(f'<b style="font-size:15px;color:{C_PRIMARY}">{ChatBubble._inline_fmt(stripped[4:])}</b><br>')
                continue
            if stripped.startswith('## '):
                _close_list()
                html_lines.append(f'<b style="font-size:16px;color:{C_PRIMARY}">{ChatBubble._inline_fmt(stripped[3:])}</b><br>')
                continue
            if stripped.startswith('# '):
                _close_list()
                html_lines.append(f'<b style="font-size:17px;color:{C_PRIMARY}">{ChatBubble._inline_fmt(stripped[2:])}</b><br>')
                continue

            # Unordered list items (- or *)
            if stripped.startswith('- ') or stripped.startswith('* '):
                if list_type != 'ul':
                    _close_list()
                    html_lines.append('<ul style="margin:2px 0px;padding-left:18px">')
                    list_type = 'ul'
                html_lines.append(f'<li>{ChatBubble._inline_fmt(stripped[2:])}</li>')
                continue

            # Ordered list items (1. 2. 3. etc)
            m = re.match(r'^(\d+)\.\s+(.+)$', stripped)
            if m:
                if list_type != 'ol':
                    _close_list()
                    html_lines.append('<ol style="margin:2px 0px;padding-left:22px">')
                    list_type = 'ol'
                html_lines.append(f'<li>{ChatBubble._inline_fmt(m.group(2))}</li>')
                continue

            # Empty line — close list, add break
            if not stripped:
                _close_list()
                html_lines.append('<br>')
                continue

            # Horizontal rule
            if stripped in ('---', '***', '___'):
                _close_list()
                html_lines.append(f'<hr style="border:1px solid rgba(143,245,255,0.15);margin:6px 0">')
                continue

            # Blockquote
            if stripped.startswith('> '):
                _close_list()
                html_lines.append(
                    f'<div style="border-left:3px solid {C_PRIMARY};padding-left:10px;'
                    f'color:{C_TEXT_DIM};margin:4px 0;font-style:italic">'
                    f'{ChatBubble._inline_fmt(stripped[2:])}</div>')
                continue

            # Regular text
            _close_list()
            html_lines.append(ChatBubble._inline_fmt(stripped) + '<br>')

        _close_list()
        return ''.join(html_lines)

    @staticmethod
    def _syntax_color(line):
        """Token-based syntax highlighting with proper string detection."""
        KEYWORDS = {'def','class','return','if','elif','else','for','while','in',
                     'import','from','try','except','with','as','not','and','or',
                     'is','None','True','False','print','range','len','lambda','yield'}

        # First, handle full strings and comments via regex before tokenizing
        result_parts = []
        pos = 0
        in_string = None

        # Pre-process: find strings and comments
        i = 0
        segments = []
        while i < len(line):
            ch = line[i]
            if in_string is None:
                if ch == '#':
                    # Rest is comment
                    segments.append(('comment', line[i:]))
                    i = len(line)
                    continue
                elif ch in ('"', "'"):
                    # Check for triple quote
                    if line[i:i+3] in ('"""', "'''"):
                        end = line.find(line[i:i+3], i+3)
                        if end == -1: end = len(line) - 3
                        segments.append(('string', line[i:end+3]))
                        i = end + 3
                    else:
                        end = line.find(ch, i+1)
                        if end == -1: end = len(line) - 1
                        segments.append(('string', line[i:end+1]))
                        i = end + 1
                    continue
                else:
                    # Find next special char
                    next_special = len(line)
                    for sc in ('#', '"', "'"):
                        si = line.find(sc, i)
                        if si != -1 and si < next_special:
                            next_special = si
                    segments.append(('code', line[i:next_special]))
                    i = next_special
            else:
                i += 1

        if not segments:
            segments = [('code', line)]

        parts = []
        prev_was_def = False
        for seg_type, seg_text in segments:
            esc = seg_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if seg_type == 'comment':
                parts.append(f'<span style="color:#45484e;font-style:italic">{esc}</span>')
            elif seg_type == 'string':
                parts.append(f'<span style="color:#8ff5ff">{esc}</span>')
            else:
                # Tokenize code segment
                tokens = re.split(r'(\W+)', seg_text)
                for tok in tokens:
                    if not tok:
                        continue
                    tok_esc = tok.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    if tok in KEYWORDS:
                        parts.append(f'<span style="color:#ff59e3">{tok_esc}</span>')
                        prev_was_def = tok == 'def'
                    elif prev_was_def and re.match(r'^[a-zA-Z_]\w*$', tok):
                        parts.append(f'<span style="color:#00F0FF">{tok_esc}</span>')
                        prev_was_def = False
                    elif re.match(r'^\d+\.?\d*$', tok):
                        parts.append(f'<span style="color:#ac89ff">{tok_esc}</span>')
                    else:
                        parts.append(f'<span style="color:#f5f6fe">{tok_esc}</span>')
                        if tok.strip():
                            prev_was_def = False

        return ''.join(parts)


class TypingIndicator(QWidget):
    """Mac-style 3-dot typing indicator. Each dot pulses on a phase offset
    so they cascade like the iMessage typing bubble. Uses the design-token
    accent so theme switches flow through automatically.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 28)
        self.setStyleSheet("background:transparent;border:none;")
        self._phase = 0.0
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(40)  # ~25 fps — buttery without burning CPU

    def _tick(self):
        self._phase += 0.10
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        try:
            from shell_ui import design_tokens as DT
            ac = QColor(DT.C.accent)
        except Exception:
            ac = QColor(0, 240, 255)
        cy = self.height() / 2
        for i in range(3):
            phase = self._phase + i * 0.55
            # 0..1 brightness curve (smoother than raw sin) for nicer cascade
            t = (math.sin(phase) + 1) / 2
            alpha = int(70 + 160 * t)
            size = 3.4 + 1.4 * t
            cx = 12 + i * 16
            # Outer subtle halo (Mac-style soft glow under the dot)
            halo = QColor(ac.red(), ac.green(), ac.blue(), int(alpha * 0.25))
            p.setBrush(halo)
            p.drawEllipse(QPointF(cx, cy), size + 3, size + 3)
            # Solid dot
            dot = QColor(ac.red(), ac.green(), ac.blue(), alpha)
            p.setBrush(dot)
            p.drawEllipse(QPointF(cx, cy), size, size)
        p.end()


class WorkspacePanel(QFrame):
    """Codex-style workspace file list and inline text viewer/editor."""
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = None
        self._mini_buttons = []
        self.setMinimumWidth(280)
        self._apply_theme_style()
        try:
            ThemeEngine.get().on_change(lambda _name: self._apply_theme_style())
        except Exception:
            pass

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("Workspace")
        title.setStyleSheet(f"""
            color:{C_TEXT};
            font-family:'{_FONT}';
            font-size:13px;
            font-weight:700;
            border:none;
            background:transparent;
        """)
        header.addWidget(title)
        header.addStretch(1)
        self._refresh_btn = self._mini_button("Refresh")
        self._open_btn = self._mini_button("Folder")
        self._save_btn = self._mini_button("Save")
        self._hide_btn = self._mini_button("Hide")
        self._refresh_btn.clicked.connect(lambda: self.refresh())
        self._open_btn.clicked.connect(self._open_workspace_folder)
        self._save_btn.clicked.connect(self._save_current)
        self._hide_btn.clicked.connect(self.close_requested.emit)
        header.addWidget(self._refresh_btn)
        header.addWidget(self._open_btn)
        header.addWidget(self._save_btn)
        header.addWidget(self._hide_btn)
        root.addLayout(header)

        self._path_label = QLabel("")
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._path_label.setStyleSheet(f"""
            color:{C_TEXT_MUTED};
            font-family:'{_MONO}';
            font-size:9px;
            border:none;
            background:transparent;
        """)
        self._path_label.setWordWrap(True)
        root.addWidget(self._path_label)

        self._files = QListWidget()
        self._files.setMinimumHeight(130)
        self._files.itemClicked.connect(self._on_file_clicked)
        root.addWidget(self._files, 1)

        self._file_title = QLabel("No file selected")
        self._file_title.setStyleSheet(f"""
            color:{C_TEXT};
            font-family:'{_MONO}';
            font-size:11px;
            font-weight:700;
            border:none;
            background:transparent;
        """)
        self._file_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self._file_title)

        self._editor = QTextEdit()
        self._editor.setPlaceholderText("Files created from chat will open here.")
        root.addWidget(self._editor, 2)

        self._status = QLabel("Ready")
        self._status.setStyleSheet(f"""
            color:{C_TEXT_MUTED};
            font-family:'{_FONT}';
            font-size:10px;
            border:none;
            background:transparent;
        """)
        root.addWidget(self._status)
        QTimer.singleShot(0, self.refresh)

    def _theme(self):
        try:
            return ThemeEngine.get().t
        except Exception:
            return {
                "surface": C_SURFACE,
                "surface_low": C_SURFACE_LOW,
                "surface_cont": C_SURFACE_CONT,
                "surface_high": C_SURFACE_HIGH,
                "text": C_TEXT,
                "text_dim": C_TEXT_DIM,
                "text_muted": C_TEXT_MUTED,
                "primary": C_PRIMARY,
                "primary_bold": C_PRIMARY_BOLD,
                "glass_bg": "rgba(255,255,255,0.65)",
                "glass_border": C_OUTLINE_VAR,
                "glass_tonal": C_SURFACE_LOW,
                "glass_tonal_border": C_OUTLINE_VAR,
            }

    def _apply_theme_style(self):
        t = self._theme()
        self.setStyleSheet(f"""
            WorkspacePanel {{
                background: {t.get('glass_bg')};
                border-left: 1px solid {t.get('glass_border')};
                border-top: none;
                border-right: none;
                border-bottom: none;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QListWidget {{
                background: {t.get('glass_tonal')};
                border: 1px solid {t.get('glass_tonal_border')};
                border-radius: 8px;
                color: {t.get('text')};
                font-family: '{_MONO}';
                font-size: 11px;
                outline: none;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 7px 8px;
                border-radius: 6px;
                margin: 1px;
            }}
            QListWidget::item:selected {{
                background: {t.get('primary')};
                color: {t.get('surface')};
            }}
            QTextEdit {{
                background: {t.get('surface')};
                border: 1px solid {t.get('glass_tonal_border')};
                border-radius: 8px;
                color: {t.get('text')};
                font-family: '{_MONO}';
                font-size: 12px;
                padding: 10px;
            }}
        """)
        try:
            self._path_label.setStyleSheet(
                f"color:{t.get('text_muted')}; font-family:'{_MONO}'; font-size:9px; border:none; background:transparent;"
            )
            self._file_title.setStyleSheet(
                f"color:{t.get('text')}; font-family:'{_MONO}'; font-size:11px; font-weight:700; border:none; background:transparent;"
            )
            self._status.setStyleSheet(
                f"color:{t.get('text_muted')}; font-family:'{_FONT}'; font-size:10px; border:none; background:transparent;"
            )
            for btn in list(getattr(self, "_mini_buttons", []) or []):
                self._style_mini_button(btn)
        except Exception:
            pass

    def _mini_button(self, text):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(26)
        self._mini_buttons.append(btn)
        self._style_mini_button(btn)
        return btn

    def _style_mini_button(self, btn):
        t = self._theme()
        btn.setStyleSheet(
            "QPushButton {"
            f"  background: {t.get('surface_low')};"
            f"  color: {t.get('text')};"
            f"  border: 1px solid {t.get('glass_tonal_border')};"
            "  border-radius: 7px;"
            "  padding: 0 9px;"
            "  font-size: 10px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            f"  background: {t.get('surface_high')};"
            f"  border-color: {t.get('primary')};"
            "}"
        )

    def _workspace_root(self):
        try:
            from shell_workspace_tools import resolve_workspace_path

            return resolve_workspace_path()
        except Exception:
            from pathlib import Path

            root = Path(os.environ.get("SHELL_WORKSPACE_PATH") or os.path.join(os.getcwd(), "shell_workspace"))
            root.mkdir(parents=True, exist_ok=True)
            return root.resolve()

    def _is_inside_workspace(self, path):
        try:
            root = self._workspace_root()
            full = path.resolve()
            full.relative_to(root)
            return True
        except Exception:
            return False

    def _friendly_size(self, value):
        try:
            size = int(value)
        except Exception:
            return "0 B"
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"

    def refresh(self, open_path=None):
        try:
            root = self._workspace_root()
            self._path_label.setText(str(root))
            self._files.clear()
            files = []
            for full in sorted(root.rglob("*")):
                if full.is_file():
                    files.append(full)
            for full in files[:500]:
                rel = str(full.relative_to(root))
                item = QListWidgetItem(rel)
                try:
                    item.setToolTip(f"{full}\n{self._friendly_size(full.stat().st_size)}")
                except Exception:
                    item.setToolTip(str(full))
                item.setData(Qt.ItemDataRole.UserRole, str(full))
                self._files.addItem(item)
            self._status.setText(f"{len(files)} file(s)")
            if open_path:
                self.open_file(open_path)
        except Exception as exc:
            self._status.setText(f"Workspace error: {exc}")

    def _on_file_clicked(self, item):
        try:
            path = item.data(Qt.ItemDataRole.UserRole)
            if path:
                self.open_file(path)
        except Exception as exc:
            self._status.setText(f"Open failed: {exc}")

    def open_file(self, path):
        from pathlib import Path

        root = self._workspace_root()
        full = Path(str(path or "")).expanduser()
        if not full.is_absolute():
            full = root / full
        full = full.resolve()
        if not self._is_inside_workspace(full):
            self._status.setText("Blocked: file is outside Shell workspace")
            return
        if not full.exists():
            self._status.setText("File not found in workspace")
            return
        if full.is_dir():
            self._status.setText("Selected path is a folder")
            return
        self._current_file = full
        try:
            text = full.read_text(encoding="utf-8")
            self._editor.setReadOnly(False)
            self._editor.setPlainText(text)
            rel = full.relative_to(root)
            self._file_title.setText(str(rel))
            self._status.setText(f"Opened {rel} ({self._friendly_size(full.stat().st_size)})")
            for i in range(self._files.count()):
                item = self._files.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == str(full):
                    self._files.setCurrentItem(item)
                    break
        except UnicodeDecodeError:
            self._editor.setReadOnly(True)
            self._editor.setPlainText("Binary or non UTF-8 file. Inline preview is unavailable.")
            self._file_title.setText(str(full.relative_to(root)))
            self._status.setText("Binary preview blocked")
        except Exception as exc:
            self._status.setText(f"Open failed: {exc}")

    def _save_current(self):
        if not self._current_file:
            self._status.setText("No file selected")
            return
        if not self._is_inside_workspace(self._current_file):
            self._status.setText("Blocked: file is outside Shell workspace")
            return
        try:
            self._current_file.write_text(self._editor.toPlainText(), encoding="utf-8")
            self._status.setText(f"Saved {self._current_file.name}")
            self.refresh(open_path=str(self._current_file))
        except Exception as exc:
            self._status.setText(f"Save failed: {exc}")

    def _open_workspace_folder(self):
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._workspace_root())))
        except Exception as exc:
            self._status.setText(f"Open folder failed: {exc}")


class ChatPage(QWidget):
    message_sent = pyqtSignal(str)
    # New: forward Speak requests from any reply bubble to the main UI
    # so the main TTS pipeline handles playback (see _on_speak below).
    speak_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent; border:none;")
        # Pending file attachments staged via drag-drop or paperclip.
        # Cleared after each send. Read from the outside so the
        # MainWindow's gui_input emitter can extend the payload with
        # a `files` field (forward-compatible — backend may ignore it).
        self._pending_files = []
        # Snapshot of the files included in the most recent send so
        # MainWindow's _on_chat_send can read them without racing the
        # cleared `_pending_files` list.
        self._last_sent_files = []
        # Drop-target highlight overlay is built lazily in dragEnter.
        self._drop_highlight = None
        # Allow the chat page to receive file drops anywhere in its area.
        self.setAcceptDrops(True)
        root_lay = QHBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.setChildrenCollapsible(False)
        self._chat_shell = QWidget()
        self._chat_shell.setStyleSheet("background:transparent; border:none;")
        lay = QVBoxLayout(self._chat_shell)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Conversation id of the active chat. Set by the host whenever a
        # new conversation is minted or the user switches threads. The
        # Export button reads this to know which conversation to call
        # the `/api/conversations/<id>/export` endpoint with.
        self._current_conv_id: str | None = None

        # ── Chat header — small floating row with the Export button ──
        # Sits above the scroll area; transparent so the ambient bg
        # bleeds through. Right-aligned so it doesn't compete with the
        # main scrollback. New: an "Export" button pops a tiny dialog
        # asking for the format (md/json/pdf) and the destination path,
        # then hits `/api/conversations/<id>/export?format=...` and
        # writes the response body to disk.
        chat_header = QWidget()
        chat_header.setStyleSheet("background: transparent; border: none;")
        chat_header.setFixedHeight(34)
        ch_lay = QHBoxLayout(chat_header)
        ch_lay.setContentsMargins(20, 4, 20, 4)
        ch_lay.setSpacing(8)
        ch_lay.addStretch(1)
        self._files_btn = QPushButton("Files")
        self._files_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._files_btn.setFixedHeight(26)
        self._files_btn.setToolTip("Show workspace files")
        self._files_btn.clicked.connect(lambda: self.set_workspace_visible(not getattr(self, "_workspace_visible", False)))
        ch_lay.addWidget(self._files_btn)
        self._model_combo = QComboBox()
        self._model_combo.addItems(["FAST", "SMART", "CODER"])
        self._model_combo.setToolTip("Shell model/routing mode")
        self._model_combo.setFixedHeight(26)
        self._model_combo.setMinimumWidth(96)
        current_mode = self._read_brain_mode()
        idx = self._model_combo.findText(current_mode)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        self._model_combo.currentTextChanged.connect(self._on_model_mode_changed)
        ch_lay.addWidget(self._model_combo)
        self._export_btn = QPushButton("⭳ Export")  # ⭳ glyph
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setFixedHeight(26)
        self._export_btn.setToolTip(
            "Export this conversation as Markdown, JSON, or PDF"
        )
        self._export_btn.clicked.connect(self._on_export_clicked)
        ch_lay.addWidget(self._export_btn)
        self._style_chat_header_controls()
        try:
            ThemeEngine.get().on_change(lambda _name: self._style_chat_header_controls())
        except Exception:
            pass
        lay.addWidget(chat_header)

        # Scroll area — iOS-style thin scrollbar
        try:
            from shell_ui.design_tokens import C as _DC
            _scroll_handle = _DC.border_strong
            _scroll_handle_hover = _DC.accent
            _typing_bg = _DC.glass
            _typing_strong = _DC.glass_strong
            _typing_hi = _DC.glass_hi
            _typing_border = _DC.glass_border
            _typing_muted = _DC.text_muted
        except Exception:
            _scroll_handle = "rgba(143,245,255,0.12)"
            _scroll_handle_hover = "rgba(143,245,255,0.25)"
            _typing_bg = "rgba(18,26,42,0.24)"
            _typing_strong = "rgba(32,42,60,0.36)"
            _typing_hi = "rgba(200,252,255,0.30)"
            _typing_border = "rgba(143,245,255,0.16)"
            _typing_muted = C_TEXT_MUTED
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollBar:vertical {{
                width:3px; background:transparent; margin:8px 0;
            }}
            QScrollBar::handle:vertical {{
                background:{_scroll_handle}; border-radius:1px; min-height:40px;
            }}
            QScrollBar::handle:vertical:hover {{ background:{_scroll_handle_hover}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
        """)

        self._chat_w = QWidget()
        self._chat_w.setStyleSheet("background:transparent;border:none;")
        self._chat_lay = QVBoxLayout(self._chat_w)
        self._chat_lay.setContentsMargins(32, 20, 32, 20)
        self._chat_lay.setSpacing(18)
        self._chat_lay.addStretch(1)
        self._scroll.setWidget(self._chat_w)
        lay.addWidget(self._scroll, 1)

        self.show_empty_state()

        # Typing indicator — glass pill
        self._typing_container = QWidget()
        self._typing_container.setFixedHeight(48)
        self._typing_container.setStyleSheet("background:transparent; border:none;")
        tc_lay = QHBoxLayout(self._typing_container)
        tc_lay.setContentsMargins(40, 4, 40, 4)

        self._typing_pill = QFrame()
        self._typing_pill.setFixedSize(100, 36)
        self._typing_pill.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:0.1,y2:1,
                    stop:0 {_typing_hi}, stop:0.08 {_typing_strong},
                    stop:0.5 {_typing_bg}, stop:1 {_typing_bg});
                border:1px solid {_typing_border};
                border-top:2px solid {_typing_hi};
                border-left:1px solid {_typing_hi};
                border-radius:18px;
            }}
        """)
        tp_lay = QHBoxLayout(self._typing_pill)
        tp_lay.setContentsMargins(12, 0, 12, 0)
        self._typing = TypingIndicator()
        tp_lay.addWidget(self._typing)
        tp_lbl = QLabel("typing")
        tp_lbl.setStyleSheet(f"""
            color:{_typing_muted}; font-family:'{_FONT}'; font-size:10px;
            font-style:italic; border:none; background:transparent;
        """)
        tp_lay.addWidget(tp_lbl)

        tc_lay.addWidget(self._typing_pill)
        tc_lay.addStretch(1)
        self._typing_container.setVisible(False)
        lay.addWidget(self._typing_container)

        # ---- Floating input bar — liquid glass ----
        inp_container = QWidget()
        inp_container.setStyleSheet("background:transparent; border:none;")
        # No longer fixed-height: the attachment-chips row above the
        # input may push the container taller when the user has staged
        # one or more files. We let the layout settle naturally.
        inp_container.setMinimumHeight(88)
        ic_lay = QVBoxLayout(inp_container)
        ic_lay.setContentsMargins(28, 6, 28, 14)
        ic_lay.setSpacing(6)

        # ── Attachment chips row (sits ABOVE the input pill) ─────────
        # One chip per pending file. Hidden until at least one chip is
        # added — keeps the resting layout identical to before.
        self._chips_row = QWidget()
        self._chips_row.setStyleSheet("background:transparent; border:none;")
        self._chips_lay = QHBoxLayout(self._chips_row)
        self._chips_lay.setContentsMargins(2, 0, 2, 0)
        self._chips_lay.setSpacing(8)
        self._chips_lay.addStretch(1)
        self._chips_row.setVisible(False)
        ic_lay.addWidget(self._chips_row)

        inp_frame = QFrame()
        try:
            from shell_ui.design_tokens import C as _DC
            _g = _DC.glass_strong; _gh = _DC.glass_hi; _gb = _DC.glass_border
        except Exception:
            _g = "rgba(50,44,38,0.70)"; _gh = "rgba(255,240,225,0.10)"
            _gb = "rgba(255,240,225,0.10)"
        # Glass pill input — translucent warm body, top-edge light catch,
        # warm hairline border. Sits over the ambient bg so the coral
        # wash subtly bleeds through.
        inp_frame.setStyleSheet(
            f"QFrame {{ "
            f"  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, "
            f"    stop:0 {_gh}, stop:0.10 {_g}, stop:1 {_g}); "
            f"  border:1px solid {_gb}; border-top:1px solid {_gh}; "
            f"  border-radius:22px; "
            f"}}"
        )
        # Mac-style elevated chat input — softer larger drop shadow,
        # bigger interior padding so the input feels like a sheet rather
        # than a stuffed pill.
        try:
            _is_eff = QGraphicsDropShadowEffect(inp_frame)
            _is_eff.setBlurRadius(36); _is_eff.setOffset(0, 12)
            _is_eff.setColor(QColor(0, 0, 0, 70))
            inp_frame.setGraphicsEffect(_is_eff)
        except Exception:
            pass
        # Focus state signalled by border colour change in stylesheet.
        inp_lay = QHBoxLayout(inp_frame)
        # Mac-spacious padding inside the pill.
        inp_lay.setContentsMargins(22, 12, 12, 12)
        inp_lay.setSpacing(12)

        # ── Paperclip "📎" attach button (BEFORE the text input) ─────
        # Opens a file dialog so users can attach without dragging.
        try:
            from shell_ui.design_tokens import C as _DC2
            _attach_accent = _DC2.accent
            _attach_accent_soft = _DC2.accent_soft
        except Exception:
            _attach_accent = "#00f0ff"
            _attach_accent_soft = "rgba(0,240,255,0.12)"
        attach_btn = QPushButton("\U0001F4CE")  # 📎
        attach_btn.setFixedSize(34, 34)
        attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        attach_btn.setToolTip("Attach files")
        attach_btn.setStyleSheet(
            f"QPushButton {{ "
            f"  background: transparent; border: none; "
            f"  border-radius: 17px; "
            f"  color: rgba(232,244,255,0.55); "
            f"  font-size: 16px; "
            f"}} "
            f"QPushButton:hover {{ "
            f"  background: {_attach_accent_soft}; "
            f"  color: {_attach_accent}; "
            f"}}"
        )
        attach_btn.clicked.connect(self._pick_files)
        inp_lay.addWidget(attach_btn)

        self._input = QTextEdit()
        self._input.setPlaceholderText("Message Shell…")
        self._input.setFixedHeight(40)
        self._input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._input.setStyleSheet(f"""
            QTextEdit {{
                background:transparent; color:{C_TEXT};
                font-family:'{_FONT}'; font-size:15px;
                border:none; padding:8px 0px;
            }}
        """)
        self._input.installEventFilter(self)
        self._input.textChanged.connect(self._on_text_changed)
        inp_lay.addWidget(self._input, 1)

        send = QPushButton()
        send.setFixedSize(38, 38)
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setIcon(QIcon(_make_icon_pixmap("send", 18, "#ffffff")))
        send.setIconSize(QSize(18, 18))
        try:
            from shell_ui.design_tokens import C as _DC
            _ac = _DC.accent; _ach = _DC.accent_hover
        except Exception:
            _ac = "#d97757"; _ach = "#c66848"
        send.setStyleSheet(
            f"QPushButton {{ background-color:{_ac}; border:none; border-radius:19px; }} "
            f"QPushButton:hover {{ background-color:{_ach}; }}"
        )
        send.clicked.connect(self._send)
        inp_lay.addWidget(send)
        ic_lay.addWidget(inp_frame)

        # Status indicators below input — real AI status + char count
        status_row = QHBoxLayout()
        status_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.setSpacing(20)
        # AI Brain status
        ai_available = brain_has_providers(load=False) or has_configured_ai_key()
        ai_label = "AI CONNECTED" if ai_available else "LOCAL MODE"
        ai_color = C_SUCCESS if ai_available else C_WARNING
        dot = QLabel()
        dot.setFixedSize(4, 4)
        dot.setStyleSheet(f"background:rgba({QColor(ai_color).red()},{QColor(ai_color).green()},{QColor(ai_color).blue()},0.50); border-radius:2px; border:none;")
        status_row.addWidget(dot)
        self._ai_status_lbl = QLabel(ai_label)
        self._ai_status_lbl.setStyleSheet(f"""
            color:rgba({QColor(ai_color).red()},{QColor(ai_color).green()},{QColor(ai_color).blue()},0.30); font-family:'{_FONT}'; font-size:8px;
            font-weight:600; letter-spacing:3px; border:none; background:transparent;
        """)
        status_row.addWidget(self._ai_status_lbl)
        # Voice status
        voice_dot = QLabel()
        voice_dot.setFixedSize(4, 4)
        vc = QColor(C_SECONDARY)
        voice_dot.setStyleSheet(f"background:rgba({vc.red()},{vc.green()},{vc.blue()},0.30); border-radius:2px; border:none;")
        status_row.addWidget(voice_dot)
        voice_lbl = QLabel("VOICE READY" if _LOCAL_TTS_AVAILABLE else "VOICE OFF")
        voice_lbl.setStyleSheet(f"""
            color:rgba({vc.red()},{vc.green()},{vc.blue()},0.25); font-family:'{_FONT}'; font-size:8px;
            font-weight:600; letter-spacing:3px; border:none; background:transparent;
        """)
        status_row.addWidget(voice_lbl)
        status_row.addStretch(1)
        self._char_count = QLabel("0")
        self._char_count.setStyleSheet(f"""
            color:rgba(143,245,255,0.15); font-family:'{_MONO}'; font-size:8px;
            border:none; background:transparent;
        """)
        status_row.addWidget(self._char_count)
        ic_lay.addLayout(status_row)

        lay.addWidget(inp_container)
        self.workspace_panel = WorkspacePanel()
        self.workspace_panel.close_requested.connect(lambda: self.set_workspace_visible(False))
        self._splitter.addWidget(self._chat_shell)
        self._splitter.addWidget(self.workspace_panel)
        self._splitter.setStretchFactor(0, 4)
        self._splitter.setStretchFactor(1, 1)
        root_lay.addWidget(self._splitter, 1)
        self._workspace_visible = False
        self.set_workspace_visible(False)

    def eventFilter(self, obj, event):
        """Mac-style chat-input shortcuts:
            * Enter           — send (Shift+Enter for newline)
            * Up (empty)      — recall last sent message
            * Esc             — cancel current request / clear draft
            * Ctrl+L / Cmd+K  — clear chat history
        """
        if obj == self._input and event.type() == event.Type.KeyPress:
            mod = event.modifiers()
            key = event.key()
            # Enter to send
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if mod & Qt.KeyboardModifier.ShiftModifier:
                    return False  # newline
                self._send()
                return True
            # Up arrow recalls last user message when input is empty
            if key == Qt.Key.Key_Up and not self._input.toPlainText().strip():
                last = self._last_user_message()
                if last:
                    self._input.setPlainText(last)
                    cursor = self._input.textCursor()
                    cursor.movePosition(cursor.MoveOperation.End)
                    self._input.setTextCursor(cursor)
                    return True
            # Esc clears draft (or future: cancels in-flight request)
            if key == Qt.Key.Key_Escape:
                if self._input.toPlainText().strip():
                    self._input.clear()
                    return True
            # Ctrl+L clears chat history
            if (mod & Qt.KeyboardModifier.ControlModifier) and key == Qt.Key.Key_L:
                self._clear_chat()
                return True
        return super().eventFilter(obj, event)

    def _last_user_message(self) -> str:
        """Pull the last bubble whose role was 'user' for Up-arrow recall."""
        try:
            for i in range(self._chat_lay.count() - 1, -1, -1):
                item = self._chat_lay.itemAt(i)
                if item is None: continue
                lay = item.layout()
                if lay is None: continue
                # Bubble is the only widget in our wrapper layout.
                for j in range(lay.count()):
                    w = lay.itemAt(j).widget()
                    if w is None: continue
                    if hasattr(w, "_role") and w._role == "user" and hasattr(w, "_raw_text"):
                        return w._raw_text
        except Exception:
            pass
        return ""

    def _read_brain_mode(self) -> str:
        try:
            from shell_settings_manager import get_settings

            mode = str(get_settings().get("brain_mode") or os.environ.get("SHELL_BRAIN_MODE") or "SMART")
        except Exception:
            mode = str(os.environ.get("SHELL_BRAIN_MODE") or "SMART")
        mode = mode.upper()
        return mode if mode in {"FAST", "SMART", "CODER"} else "SMART"

    def _header_theme(self):
        try:
            return ThemeEngine.get().t
        except Exception:
            return {
                "surface_low": C_SURFACE_LOW,
                "surface_high": C_SURFACE_HIGH,
                "surface": C_SURFACE,
                "text": C_TEXT,
                "primary": C_PRIMARY,
                "glass_border": C_OUTLINE_VAR,
            }

    def _style_chat_header_controls(self):
        t = self._header_theme()
        btn_qss = (
            "QPushButton {"
            f"  background: {t.get('surface_low')};"
            f"  color: {t.get('text')};"
            f"  border: 1px solid {t.get('glass_border')};"
            "  border-radius: 13px;"
            "  padding: 0 12px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover {"
            f"  background: {t.get('surface_high')};"
            f"  border-color: {t.get('primary')};"
            "}"
        )
        combo_qss = (
            "QComboBox {"
            f"  background: {t.get('surface_low')};"
            f"  color: {t.get('text')};"
            f"  border: 1px solid {t.get('glass_border')};"
            "  border-radius: 7px;"
            "  padding: 0 8px;"
            "  font-size: 11px;"
            "  font-weight: 650;"
            "}"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox QAbstractItemView {"
            f"  background: {t.get('surface')};"
            f"  color: {t.get('text')};"
            f"  selection-background-color: {t.get('primary')};"
            "}"
        )
        try:
            self._files_btn.setStyleSheet(btn_qss)
            self._export_btn.setStyleSheet(btn_qss)
            self._model_combo.setStyleSheet(combo_qss)
        except Exception:
            pass

    def set_workspace_visible(self, visible: bool):
        self._workspace_visible = bool(visible)
        try:
            self.workspace_panel.setVisible(self._workspace_visible)
            self._splitter.setSizes([900, 330] if self._workspace_visible else [1200, 0])
            self._files_btn.setText("Hide files" if self._workspace_visible else "Files")
            self._files_btn.setToolTip("Hide workspace files" if self._workspace_visible else "Show workspace files")
        except Exception as exc:
            logger.debug("workspace visibility failed: %s", exc)

    def _on_model_mode_changed(self, value):
        mode = str(value or "SMART").upper()
        try:
            from shell_settings_manager import set_settings

            set_settings({"brain_mode": mode})
        except Exception:
            os.environ["SHELL_BRAIN_MODE"] = mode
        try:
            self._ai_status_lbl.setText(f"{mode} MODE")
        except Exception:
            pass

    def refresh_workspace(self, open_path=None):
        try:
            self.set_workspace_visible(True)
            self.workspace_panel.refresh(open_path=open_path)
        except Exception as exc:
            logger.debug("workspace refresh failed: %s", exc)

    # ── Export support ─────────────────────────────────────────────────

    def set_current_conversation_id(self, conv_id):
        """Tell the chat page which conversation the Export button targets.

        Called by the host (ShellHoloUI) whenever a new conversation is
        minted or the user pivots onto an existing one. ``None`` is fine
        — the Export button degrades to a "no active conversation"
        warning rather than calling the API.
        """
        try:
            self._current_conv_id = str(conv_id) if conv_id else None
        except Exception:
            self._current_conv_id = None

    def _on_export_clicked(self):
        """Pop the export dialog, then call /api/conversations/<id>/export.

        Three choices: Markdown / JSON / PDF. Each branch picks a save
        path via QFileDialog, hits the local ws_server route, and writes
        the response body to disk. All errors are surfaced via a small
        QMessageBox so the user always knows what happened — silent
        failures here would be confusing.

        The HTTP layer is plain stdlib (urllib + json) on purpose: this
        UI lives in the OLD shell.v1.0 tree where adding a heavyweight
        client like ``httpx`` would bloat the .exe build. urllib is
        already in use elsewhere in this file so the dependency surface
        stays tight.
        """
        try:
            from PyQt6.QtWidgets import (
                QDialog,
                QDialogButtonBox,
                QMessageBox,
                QRadioButton,
                QButtonGroup,
                QVBoxLayout,
            )
        except Exception as _e:
            logger.debug("export dialog imports failed: %s", _e)
            return

        if not self._current_conv_id:
            try:
                QMessageBox.information(
                    self,
                    "Export",
                    "No active conversation to export. Send a message first.",
                )
            except Exception:
                pass
            return

        # ── Format-picker dialog ────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle("Export conversation")
        dlg.setModal(True)
        dlg.setStyleSheet(
            "QDialog { background: rgb(20,28,42); color: #e6f2ff; }"
            "QLabel  { color: #e6f2ff; }"
            "QRadioButton { color: #d8e8ff; padding: 4px 0; }"
        )
        d_lay = QVBoxLayout(dlg)
        d_lay.setContentsMargins(20, 18, 20, 14)
        d_lay.setSpacing(10)

        title_lbl = QLabel("Choose a format:")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        d_lay.addWidget(title_lbl)

        rb_md = QRadioButton("Markdown (.md)")
        rb_json = QRadioButton("JSON (.json)")
        rb_pdf = QRadioButton("PDF (.pdf)")
        rb_md.setChecked(True)
        group = QButtonGroup(dlg)
        group.addButton(rb_md, 0)
        group.addButton(rb_json, 1)
        group.addButton(rb_pdf, 2)
        d_lay.addWidget(rb_md)
        d_lay.addWidget(rb_json)
        d_lay.addWidget(rb_pdf)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        d_lay.addWidget(bb)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Map the picker selection → format string + filter + extension.
        choice = group.checkedId()
        if choice == 1:
            fmt = "json"
            file_filter = "JSON files (*.json)"
            default_ext = ".json"
        elif choice == 2:
            fmt = "pdf"
            file_filter = "PDF files (*.pdf)"
            default_ext = ".pdf"
        else:
            fmt = "md"
            file_filter = "Markdown files (*.md)"
            default_ext = ".md"

        # ── Destination path ────────────────────────────────────────
        try:
            default_name = f"conv-{self._current_conv_id}{default_ext}"
            target_path, _filter = QFileDialog.getSaveFileName(
                self,
                "Save exported conversation",
                default_name,
                file_filter,
            )
        except Exception as _e:
            logger.debug("export save dialog failed: %s", _e)
            return
        if not target_path:
            return

        # ── HTTP fetch ──────────────────────────────────────────────
        # The OLD UI talks to the local ws_server on 127.0.0.1:8765 by
        # default; we read SHELL_API_URL / SHELL_API_TOKEN from env so
        # users who customised the binding don't have to edit this code.
        try:
            import urllib.request
            import urllib.error
        except Exception as _e:
            logger.debug("export urllib import failed: %s", _e)
            return

        base = os.environ.get("SHELL_API_URL", "http://127.0.0.1:8765").rstrip("/")
        token = os.environ.get("SHELL_API_TOKEN", "").strip()
        url = f"{base}/api/conversations/{self._current_conv_id}/export?format={fmt}"
        req = urllib.request.Request(url, method="GET")
        if token:
            req.add_header("Authorization", f"Bearer {token}")

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as e:
            try:
                QMessageBox.warning(
                    self,
                    "Export failed",
                    f"Server returned HTTP {e.code}: {e.reason}",
                )
            except Exception:
                pass
            return
        except Exception as e:
            try:
                QMessageBox.warning(
                    self,
                    "Export failed",
                    f"Could not reach the Shell API: {e}",
                )
            except Exception:
                pass
            return

        # ── Write to disk ───────────────────────────────────────────
        try:
            with open(target_path, "wb") as fh:
                fh.write(payload)
        except OSError as e:
            try:
                QMessageBox.warning(
                    self, "Export failed", f"Could not write file: {e}"
                )
            except Exception:
                pass
            return

        # Success toast.
        try:
            QMessageBox.information(
                self,
                "Export complete",
                f"Saved to:\n{target_path}",
            )
        except Exception:
            pass

    def _clear_chat(self):
        """Drop every bubble and restore the empty-state hero."""
        try:
            # Remove every wrapper layout / widget except the trailing
            # stretch (last item) and bring back the empty state.
            while self._chat_lay.count() > 1:
                item = self._chat_lay.takeAt(0)
                if item is None: continue
                lay = item.layout()
                if lay is not None:
                    while lay.count():
                        c = lay.takeAt(0)
                        if c and c.widget():
                            c.widget().deleteLater()
                w = item.widget()
                if w: w.deleteLater()
            self.show_empty_state()
        except Exception as _e:
            logger.debug("clear chat failed: %s", _e)

    def show_empty_state(self):
        """Render the beginner starter surface when a chat has no messages."""
        try:
            existing = getattr(self, "_empty_state", None)
            if existing is not None:
                existing.show()
                return existing
            from shell_ui.widgets import EmptyState
            self._empty_state = EmptyState(
                title="How can I help today?",
                subtitle="Type a request, or pick a starter below.",
                chips=[
                    "Take a screenshot",
                    "Create notes.md",
                    "Play a song on YouTube",
                    "Summarise my screen",
                    "Show system stats",
                ],
            )
            self._empty_state.setMinimumHeight(360)
            self._empty_state.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            for btn in self._empty_state.chip_buttons():
                btn.clicked.connect(
                    lambda _checked=False, b=btn: self.message_sent.emit(b.text())
                )
            insert_at = max(0, self._chat_lay.count() - 1)
            self._chat_lay.insertWidget(insert_at, self._empty_state, 1)
            return self._empty_state
        except Exception as _e:
            logger.debug("EmptyState init failed: %s", _e)
            try:
                self.add_message(
                    "shell",
                    "Hi — type something to start. Tools, code, voice, "
                    "research, calculations: I'll handle it."
                )
            except Exception as _ee:
                logger.debug("empty fallback bubble failed: %s", _ee)
            return None

    def _on_text_changed(self):
        """Update character count and auto-resize input."""
        text = self._input.toPlainText()
        self._char_count.setText(str(len(text)))
        # Auto-grow up to 120px, shrink back to 36px when empty
        lines = text.count('\n') + 1
        new_h = min(120, max(36, 20 + lines * 20))
        self._input.setFixedHeight(new_h)

    def _send(self):
        t = self._input.toPlainText().strip()
        if not t:
            return
        self._input.clear()
        self._input.setFixedHeight(36)
        # Snapshot pending files BEFORE clearing — MainWindow's
        # _on_chat_send reads `_last_sent_files` to extend the
        # gui_input payload (forward-compatible: the agent may simply
        # ignore the `files` field today).
        self._last_sent_files = list(self._pending_files)
        self.add_message("user", t)
        # Forward to the rest of the app. Existing `str` signal stays
        # for backwards compat; the `_last_sent_files` attr carries the
        # extra payload data without a signature change.
        self.message_sent.emit(t)
        # Clear the staging area for the next message.
        if self._pending_files:
            self._pending_files = []
            self._refresh_chips()

    def add_message(self, role, text, stream=False):
        """Append a chat bubble.

        New `stream` flag (default False — fully backwards-compat) opts
        the bubble into the Mac-style live-typewriter reveal. Only
        honoured for `role == "shell"`; user messages always render
        instantly. The bubble is created with the full `text` (so the
        action toolbar / Copy still see the real content), then the
        prose label is blanked and re-typed by `bubble.stream_text(...)`
        once the entry-fade animation lands.
        """
        # Hide the empty-state hero the moment the conversation starts.
        try:
            es = getattr(self, "_empty_state", None)
            if es is not None and es.isVisible():
                es.hide()
                es.setParent(None)
                es.deleteLater()
                self._empty_state = None
        except Exception as _e:
            logger.debug("empty_state hide failed: %s", _e)

        bubble = ChatBubble(role, text, self._chat_w)
        # Wire the bubble's hover-toolbar signals back to ChatPage so
        # the bubble stays presentation-only (TTS + message replay live
        # higher in the stack).
        try:
            bubble.regenerate_requested.connect(self._on_regenerate)
            bubble.speak_requested.connect(self._on_speak)
        except Exception as _e:
            logger.debug("bubble action wiring failed: %s", _e)
        wrapper = QHBoxLayout()
        if role == "user":
            wrapper.addStretch(1)
            wrapper.addWidget(bubble)
        else:
            wrapper.addWidget(bubble)
            wrapper.addStretch(1)
        self._chat_lay.addLayout(wrapper)

        # Streaming opt-in is shell-only; user bubbles always render
        # instantly. Capture once so the fade callback and the fallback
        # path agree on whether to kick the typewriter.
        do_stream = bool(stream) and role == "shell"

        # Smooth slide+fade entry — replaces the old manual QTimer
        # poll. QPropertyAnimation is GPU-friendlier and produces a
        # cleaner curve. ~250ms OutCubic feels premium without being slow.
        try:
            opacity_eff = QGraphicsOpacityEffect(bubble)
            opacity_eff.setOpacity(0.0)
            bubble.setGraphicsEffect(opacity_eff)
            anim = QPropertyAnimation(opacity_eff, b"opacity", bubble)
            anim.setDuration(260)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            # Drop the effect once finished so subsequent layouts don't
            # carry the GPU cost. When streaming is requested, kick the
            # typewriter the moment the fade lands so the two animations
            # don't overlap awkwardly.
            def _post_fade(_b=bubble, _t=text, _do=do_stream):
                try:
                    _b.setGraphicsEffect(None)
                except Exception:
                    pass
                if _do:
                    try:
                        _b.stream_text(_t)
                    except Exception as _se:
                        logger.debug("stream_text failed: %s", _se)
            anim.finished.connect(_post_fade)
            anim.start()
            bubble._fade_anim = anim
        except Exception:
            # Fade init failed — still honour the streaming request via
            # a small delay so behaviour stays consistent.
            if do_stream:
                QTimer.singleShot(80, lambda b=bubble, t=text: b.stream_text(t))

        # Mac-smooth scroll to bottom — animate the scrollbar value
        # rather than snap. Replaces the previous instant `setValue`.
        QTimer.singleShot(60, self._smooth_scroll_to_bottom)

        # Return the bubble so streaming callers can mutate its text in
        # place (instead of creating a new bubble per chunk).
        return bubble

    def _smooth_scroll_to_bottom(self):
        try:
            from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
            sb = self._scroll.verticalScrollBar()
            if sb is None: return
            target = sb.maximum()
            current = sb.value()
            if target == current:
                return
            anim = QPropertyAnimation(sb, b"value", self)
            anim.setDuration(280)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(current)
            anim.setEndValue(target)
            anim.start()
            self._scroll_anim = anim
        except Exception:
            try:
                self._scroll.verticalScrollBar().setValue(
                    self._scroll.verticalScrollBar().maximum())
            except Exception:
                pass

    def set_thinking(self, v):
        self._typing_container.setVisible(v)

    # ── Bubble hover-toolbar slots ──────────────────────────────────
    def _on_regenerate(self, bubble):
        """Find the user message immediately preceding `bubble` and
        re-send it. The agent will produce a fresh reply."""
        try:
            target_idx = -1
            for i in range(self._chat_lay.count()):
                item = self._chat_lay.itemAt(i)
                if item is None:
                    continue
                lay = item.layout()
                if lay is None:
                    continue
                for j in range(lay.count()):
                    w = lay.itemAt(j).widget()
                    if w is bubble:
                        target_idx = i
                        break
                if target_idx >= 0:
                    break
            if target_idx < 0:
                return
            # Walk backwards from the bubble to find the most recent
            # user message — that's what we replay.
            for i in range(target_idx - 1, -1, -1):
                item = self._chat_lay.itemAt(i)
                if item is None:
                    continue
                lay = item.layout()
                if lay is None:
                    continue
                for j in range(lay.count()):
                    w = lay.itemAt(j).widget()
                    if (w is not None
                            and getattr(w, "_role", None) == "user"
                            and hasattr(w, "_raw_text")):
                        # Re-emit through the standard send pipeline so
                        # all the existing tracking / streaming logic
                        # kicks in.
                        self.message_sent.emit(w._raw_text)
                        return
        except Exception as _e:
            logger.debug("regenerate failed: %s", _e)

    def _on_speak(self, text):
        """Forward to the main UI's TTS pipeline via the page-level
        signal. The main window connects to this in its constructor."""
        try:
            self.speak_requested.emit(text or "")
        except Exception as _e:
            logger.debug("speak forward failed: %s", _e)

    # ── Drag-and-drop file attach ───────────────────────────────────
    def dragEnterEvent(self, event):
        """Accept the drop only when at least one local file URL is
        present. Show a soft accent border highlight on the scroll area
        while the drag is active."""
        try:
            md = event.mimeData()
            if md is not None and md.hasUrls():
                if any(u.isLocalFile() for u in md.urls()):
                    event.acceptProposedAction()
                    self._show_drop_highlight(True)
                    return
        except Exception as _e:
            logger.debug("dragEnter failed: %s", _e)
        event.ignore()

    def dragMoveEvent(self, event):
        # Mirror dragEnter so the drop indicator stays correct as the
        # cursor moves inside the widget.
        try:
            md = event.mimeData()
            if md is not None and md.hasUrls() and any(
                    u.isLocalFile() for u in md.urls()):
                event.acceptProposedAction()
                return
        except Exception:
            pass
        event.ignore()

    def dragLeaveEvent(self, event):
        self._show_drop_highlight(False)
        try:
            super().dragLeaveEvent(event)
        except Exception:
            pass

    def dropEvent(self, event):
        """Stage every dropped local file as a chip above the input."""
        self._show_drop_highlight(False)
        try:
            md = event.mimeData()
            if md is None or not md.hasUrls():
                event.ignore()
                return
            added = False
            for url in md.urls():
                if not url.isLocalFile():
                    continue
                path = url.toLocalFile()
                if path and path not in self._pending_files:
                    self._pending_files.append(path)
                    added = True
            if added:
                self._refresh_chips()
            event.acceptProposedAction()
        except Exception as _e:
            logger.debug("drop failed: %s", _e)
            event.ignore()

    def _show_drop_highlight(self, on: bool):
        """Lazily build and toggle a soft accent border overlay on the
        chat scroll area. Uses QGraphicsOpacityEffect so the highlight
        fades cleanly instead of popping."""
        try:
            from shell_ui.design_tokens import C as _DC
            _accent = _DC.accent
            _accent_soft = _DC.accent_soft
        except Exception:
            _accent = "#00f0ff"
            _accent_soft = "rgba(0,240,255,0.12)"
        if self._drop_highlight is None:
            hl = QFrame(self._scroll)
            hl.setObjectName("dropHighlight")
            hl.setStyleSheet(
                f"QFrame#dropHighlight {{ "
                f"  background: {_accent_soft}; "
                f"  border: 2px dashed {_accent}; "
                f"  border-radius: 18px; "
                f"}}"
            )
            hl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            eff = QGraphicsOpacityEffect(hl)
            eff.setOpacity(0.0)
            hl.setGraphicsEffect(eff)
            hl.hide()
            self._drop_highlight = hl
            self._drop_highlight_eff = eff

        # Resize / position to cover the scroll area's viewport.
        try:
            self._drop_highlight.setGeometry(self._scroll.rect())
            self._drop_highlight.raise_()
        except Exception:
            pass

        if on:
            self._drop_highlight.show()
            try:
                anim = QPropertyAnimation(
                    self._drop_highlight_eff, b"opacity", self)
                anim.setDuration(160)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.setStartValue(self._drop_highlight_eff.opacity())
                anim.setEndValue(1.0)
                anim.start()
                self._drop_highlight_anim = anim
            except Exception:
                self._drop_highlight_eff.setOpacity(1.0)
        else:
            try:
                anim = QPropertyAnimation(
                    self._drop_highlight_eff, b"opacity", self)
                anim.setDuration(160)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.setStartValue(self._drop_highlight_eff.opacity())
                anim.setEndValue(0.0)
                # Hide after the fade so it doesn't intercept paints.
                anim.finished.connect(
                    lambda hl=self._drop_highlight: hl.hide())
                anim.start()
                self._drop_highlight_anim = anim
            except Exception:
                self._drop_highlight_eff.setOpacity(0.0)
                self._drop_highlight.hide()

    # ── File-chip management ────────────────────────────────────────
    def _pick_files(self):
        """Open the native file dialog so users can attach without
        dragging. Mirrors the drop pipeline."""
        try:
            paths, _filter = QFileDialog.getOpenFileNames(
                self, "Attach files")
            if not paths:
                return
            added = False
            for p in paths:
                if p and p not in self._pending_files:
                    self._pending_files.append(p)
                    added = True
            if added:
                self._refresh_chips()
        except Exception as _e:
            logger.debug("pick files failed: %s", _e)

    def _refresh_chips(self):
        """Rebuild the chips strip from `_pending_files`. Cheap because
        the list is short and chips are tiny."""
        try:
            row = getattr(self, "_chips_row", None)
            lay = getattr(self, "_chips_lay", None)
            if row is None or lay is None:
                return
            # Strip every existing chip, keeping the trailing stretch.
            while lay.count() > 1:
                item = lay.takeAt(0)
                if item is None:
                    continue
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
            try:
                from shell_ui.design_tokens import C as _DC
                _accent = _DC.accent
                _accent_soft = _DC.accent_soft
                _border = _DC.glass_border
                _glass = _DC.glass_strong
                _muted = _DC.text_muted
            except Exception:
                _accent = "#00f0ff"
                _accent_soft = "rgba(0,240,255,0.12)"
                _border = "rgba(143,245,255,0.18)"
                _glass = "rgba(26,36,58,0.72)"
                _muted = "#8fa3bd"
            for path in self._pending_files:
                chip = self._make_chip(
                    path, _accent, _accent_soft, _border, _glass, _muted)
                lay.insertWidget(lay.count() - 1, chip)
            row.setVisible(bool(self._pending_files))
        except Exception as _e:
            logger.debug("refresh chips failed: %s", _e)

    def _make_chip(self, path, accent, accent_soft, border, glass, muted):
        """Build one attachment chip (paperclip + filename + × button)."""
        chip = QFrame()
        chip.setObjectName("attachChip")
        chip.setStyleSheet(
            f"QFrame#attachChip {{ "
            f"  background: {glass}; "
            f"  border: 1px solid {border}; "
            f"  border-radius: 12px; "
            f"}}"
        )
        h = QHBoxLayout(chip)
        h.setContentsMargins(10, 4, 4, 4)
        h.setSpacing(6)

        # Filename (truncate to keep chip width modest).
        name = os.path.basename(path) or path
        if len(name) > 32:
            name = name[:14] + "…" + name[-15:]
        lbl = QLabel(f"\U0001F4CE  {name}")  # 📎
        lbl.setToolTip(path)
        lbl.setStyleSheet(
            f"color: {muted}; background: transparent; border: none; "
            f"font-family: '{_FONT}'; font-size: 11px;"
        )
        h.addWidget(lbl)

        # × remove button.
        x = QPushButton("×")
        x.setFixedSize(20, 20)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setToolTip("Remove attachment")
        x.setStyleSheet(
            f"QPushButton {{ "
            f"  background: transparent; border: none; "
            f"  border-radius: 10px; "
            f"  color: {muted}; "
            f"  font-size: 14px; font-weight: 700; "
            f"}} "
            f"QPushButton:hover {{ "
            f"  background: {accent_soft}; "
            f"  color: {accent}; "
            f"}}"
        )
        x.clicked.connect(lambda _checked=False, p=path: self._remove_chip(p))
        h.addWidget(x)
        return chip

    def _remove_chip(self, path):
        """Drop a single staged file and rebuild the chip strip."""
        try:
            if path in self._pending_files:
                self._pending_files.remove(path)
                self._refresh_chips()
        except Exception as _e:
            logger.debug("remove chip failed: %s", _e)

    def resizeEvent(self, event):
        # Keep the drop-highlight overlay sized to the scroll area.
        super().resizeEvent(event)
        try:
            if self._drop_highlight is not None and self._drop_highlight.isVisible():
                self._drop_highlight.setGeometry(self._scroll.rect())
        except Exception:
            pass

    # ── Phase-22: live tool-activity pill ───────────────────────────
    # We render a small "🔧 tool_name … running" chip above the typing
    # indicator whenever the agent starts a tool. When the tool ends we
    # either remove it (quick success) or flash the result/error briefly.
    def on_tool_event(self, data: dict):
        """Receive {phase, tool, duration_ms, ok, preview, error, …}."""
        if not isinstance(data, dict):
            return
        if not hasattr(self, "_tool_chip"):
            self._tool_chip = QLabel()
            self._tool_chip.setWordWrap(True)
            self._tool_chip.setStyleSheet(
                "QLabel {"
                " color: #9ff0d0;"
                " background: rgba(18, 40, 55, 0.55);"
                " border: 1px solid rgba(100, 220, 180, 0.35);"
                " border-radius: 10px;"
                " padding: 6px 12px;"
                " font-size: 11px;"
                " font-family: 'JetBrains Mono','Consolas',monospace;"
                "}"
            )
            self._tool_chip.setVisible(False)
            # Insert right above the typing indicator.
            try:
                idx = self._chat_lay.indexOf(self._typing_container)
            except Exception:
                idx = -1
            if idx >= 0:
                self._chat_lay.insertWidget(idx, self._tool_chip)
            else:
                self._chat_lay.addWidget(self._tool_chip)
            self._tool_chip_timer = QTimer(self)
            self._tool_chip_timer.setSingleShot(True)
            self._tool_chip_timer.timeout.connect(
                lambda: self._tool_chip.setVisible(False) if hasattr(self, "_tool_chip") else None
            )

        phase = data.get("phase")
        tool = data.get("tool", "?")
        if phase == "start":
            args = (data.get("args_preview") or "")[:60]
            self._tool_chip.setText(f"🔧  running  {tool}  …  {args}".rstrip())
            self._tool_chip.setVisible(True)
            self._tool_chip_timer.stop()
        elif phase == "end":
            ok = data.get("ok", True)
            ms = data.get("duration_ms", 0)
            if ok:
                preview = (data.get("preview") or "")[:60]
                self._tool_chip.setText(f"✅  {tool}  ·  {ms} ms  ·  {preview}")
            else:
                err = (data.get("error") or "")[:80]
                self._tool_chip.setStyleSheet(
                    self._tool_chip.styleSheet().replace("9ff0d0", "ff9f8a")
                                                .replace("100, 220, 180", "255, 140, 110")
                )
                self._tool_chip.setText(f"❌  {tool}  ·  {ms} ms  ·  {err}")
            # Auto-hide after 3s so the chip doesn't linger.
            self._tool_chip_timer.start(3000)


# =====================================================================
#  SystemPage
# =====================================================================

def _hex_to_qcolor(s: str, alpha: int | None = None) -> QColor:
    """Resolve a token colour string (`#rrggbb` or `rgba(r,g,b,a)`) to a
    QColor. If `alpha` is given, override the alpha channel. Falls back
    to a neutral grey on any parse error so painting never crashes."""
    try:
        s = (s or "").strip()
        if s.startswith("rgba"):
            inner = s[s.find("(") + 1: s.rfind(")")]
            parts = [p.strip() for p in inner.split(",")]
            r, g, b = int(float(parts[0])), int(float(parts[1])), int(float(parts[2]))
            a = int(float(parts[3]) * 255) if len(parts) > 3 else 255
            c = QColor(r, g, b, a)
        else:
            c = QColor(s)
            if not c.isValid():
                c = QColor(143, 245, 255)
        if alpha is not None:
            c.setAlpha(max(0, min(255, alpha)))
        return c
    except Exception:
        return QColor(143, 245, 255, alpha if alpha is not None else 255)


class LiveLineChart(QWidget):
    """Rolling line chart — last 60 samples of one metric.

    * Smooth bezier-style line, gradient fill below to fade-to-zero.
    * Gridlines every 25%.
    * Top-left: metric label. Top-right: current value (H1-sized).
    * Bottom-right: units string.
    * 30 fps repaint via QTimer (started/stopped externally so the
      page-change handler can pause it when the page is hidden).
    * Smooth value transitions: target value is interpolated into the
      most recent sample over ~200 ms so jagged jumps are avoided.

    Reused for CPU / RAM / GPU / Network — change one, improve all four.
    """

    def __init__(self, label: str = "", units: str = "%", *,
                 value_max: float = 100.0,
                 fmt: str = "{:.0f}",
                 parent=None):
        super().__init__(parent)
        self._label = label
        self._units = units
        self._value_max = max(1.0, float(value_max))
        self._fmt = fmt
        # 60 historical samples — older on the left, newest on the right.
        self._data: deque[float] = deque([0.0] * 60, maxlen=60)
        # Target & display value used for the 200ms smooth transition.
        self._target = 0.0
        self._display = 0.0
        # Track the largest value we've ever seen so the auto-scaling
        # network chart doesn't permanently stretch to a one-off spike.
        self._auto_max = float(value_max)
        self._autoscale = (value_max <= 0)
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background:transparent;border:none;")
        # 30 fps repaint loop — page handler stops/starts this.
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(33)

    # -- public API --------------------------------------------------
    def push(self, v: float) -> None:
        """Set the next target sample. Smoothed into the last data
        point over the next ~200 ms (via _tick interpolation)."""
        try:
            v = float(v)
        except Exception:
            return
        if v < 0:
            v = 0.0
        self._target = v
        if self._autoscale and v > self._auto_max:
            # Grow the visible scale; never shrink (would cause jitter).
            self._auto_max = v * 1.15

    # -- frame loop --------------------------------------------------
    def _tick(self) -> None:
        # 200 ms ≈ 6 frames at 30 fps → factor ~0.18 per frame.
        self._display += (self._target - self._display) * 0.18
        # Replace the most-recent sample so the rolling line ends at
        # the live (smoothed) value. Older samples are immutable.
        if self._data:
            self._data[-1] = self._display
        self.update()

    def advance(self) -> None:
        """Advance the rolling window by one slot. Called by the page
        on its 1 Hz update tick — pushes the current display value as
        a new immutable sample so the line scrolls left."""
        self._data.append(self._display)

    # -- painting ----------------------------------------------------
    def paintEvent(self, _e):
        from shell_ui import design_tokens as DT
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        # Header strip (label + value + units) consumes the top 36 px.
        header_h = 36
        plot_x0, plot_y0 = 4, header_h + 4
        plot_w, plot_h = max(20, w - 8), max(20, h - header_h - 12)

        accent = _hex_to_qcolor(DT.C.accent)
        text   = _hex_to_qcolor(DT.C.text)
        muted  = _hex_to_qcolor(DT.C.text_muted)
        border = _hex_to_qcolor(DT.C.border, alpha=255)

        # ---- Header text ------------------------------------------
        # Label (top-left)
        p.setPen(muted)
        f_lbl = QFont(DT.T.family, 10)
        f_lbl.setWeight(QFont.Weight.DemiBold)
        p.setFont(f_lbl)
        p.drawText(QRectF(8, 4, plot_w * 0.6, 18),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   self._label)
        # Value (top-right, H1 size, accent colour)
        p.setPen(accent)
        f_val = QFont(DT.T.family, DT.T.h1_size)
        f_val.setWeight(QFont.Weight.Bold)
        p.setFont(f_val)
        try:
            val_text = self._fmt.format(self._display)
        except Exception:
            val_text = f"{self._display:.1f}"
        p.drawText(QRectF(plot_w * 0.4, 0, plot_w * 0.6 + 4, header_h),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                   val_text)

        # ---- Gridlines every 25% ----------------------------------
        grid_pen = QPen(border)
        grid_pen.setWidthF(0.6)
        grid_pen.setStyle(Qt.PenStyle.SolidLine)
        p.setPen(grid_pen)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = plot_y0 + plot_h - frac * plot_h
            p.drawLine(QPointF(plot_x0, y), QPointF(plot_x0 + plot_w, y))

        # ---- Units (bottom-right) ---------------------------------
        if self._units:
            p.setPen(muted)
            f_u = QFont(DT.T.family_mono, 9)
            p.setFont(f_u)
            p.drawText(QRectF(plot_x0 + plot_w - 80, plot_y0 + plot_h - 14, 80, 14),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       self._units)

        # ---- Path ----------------------------------------------------
        n = len(self._data)
        if n < 2 or plot_w <= 0:
            p.end()
            return
        scale = self._auto_max if self._autoscale else self._value_max
        scale = max(scale, 1.0)
        step = plot_w / (n - 1)

        # Build the line as a smooth bezier-ish path. We use cubicTo
        # with control points midway between samples for a "smooth"
        # feel without an external smoothing pass.
        pts = []
        for i, v in enumerate(self._data):
            x = plot_x0 + i * step
            y = plot_y0 + plot_h - (max(0.0, min(scale, v)) / scale) * plot_h
            pts.append(QPointF(x, y))

        line = QPainterPath()
        line.moveTo(pts[0])
        for i in range(1, n):
            prev = pts[i - 1]
            cur = pts[i]
            mid_x = (prev.x() + cur.x()) / 2
            c1 = QPointF(mid_x, prev.y())
            c2 = QPointF(mid_x, cur.y())
            line.cubicTo(c1, c2, cur)

        # Gradient fill under the line — accent → transparent.
        fill = QPainterPath(line)
        fill.lineTo(QPointF(pts[-1].x(), plot_y0 + plot_h))
        fill.lineTo(QPointF(pts[0].x(),  plot_y0 + plot_h))
        fill.closeSubpath()

        grad = QLinearGradient(0, plot_y0, 0, plot_y0 + plot_h)
        a_top = QColor(accent.red(), accent.green(), accent.blue(), 110)
        a_bot = QColor(accent.red(), accent.green(), accent.blue(), 0)
        grad.setColorAt(0.0, a_top)
        grad.setColorAt(1.0, a_bot)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(fill)

        # Stroke the line.
        line_pen = QPen(accent)
        line_pen.setWidthF(1.6)
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(line_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(line)

        # Tip dot — bright, small.
        tip = pts[-1]
        p.setBrush(accent)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(tip, 3.0, 3.0)
        # Soft glow halo behind the tip.
        halo = QRadialGradient(tip, 10)
        halo.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 120))
        halo.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
        p.setBrush(QBrush(halo))
        p.drawEllipse(tip, 10, 10)
        p.end()


class SystemPage(QWidget):
    """Real-time system page — 2x2 chart grid + activity log + top processes.

    Replaces the previous "Neural Load / EX-9020" sci-fi placeholder with
    real psutil-backed CPU / RAM / GPU / Network metrics, an activity
    log scoped to live tool events, and a top-5 process table refreshed
    every 5 s on a dedicated QTimer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent; border:none;")
        # Build deferred to a helper so the giant widget tree stays
        # readable. Keeps the same public surface (add_log_entry,
        # update_stats, add_process_row, _uptime_label, etc.).
        self._build_ui()

    def _build_ui(self):
        from shell_ui import design_tokens as DT
        from shell_ui.widgets import Card, H1, H2, Body, Muted, StatusDot

        outer = QVBoxLayout(self)
        outer.setContentsMargins(DT.S.xl, DT.S.sm, DT.S.xl, DT.S.xs)
        outer.setSpacing(DT.S.sm)

        # ---- Header -------------------------------------------------
        header = H1("System")
        outer.addWidget(header)

        status_row = QHBoxLayout()
        status_row.setSpacing(DT.S.md)
        dot = StatusDot(tone="success")
        status_row.addWidget(dot)
        active_lbl = Muted("Live")
        status_row.addWidget(active_lbl)
        sep = Muted("·")
        status_row.addWidget(sep)
        self._uptime_label = QLabel("UPTIME: 000:00:00:00")
        self._uptime_label.setStyleSheet(
            f"color:{DT.C.text_muted}; font-family:'{DT.T.family_mono}'; "
            f"font-size:{DT.T.small_size}px; font-weight:600; "
            f"border:none; background:transparent;"
        )
        status_row.addWidget(self._uptime_label)
        status_row.addStretch(1)
        outer.addLayout(status_row)

        # ---- Scroll area ----------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background:transparent; border:none; }} "
            f"QScrollBar:vertical {{ width:6px; background:transparent; }} "
            f"QScrollBar::handle:vertical {{ background:{DT.C.surface_2}; "
            f"  border-radius:3px; }} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}"
        )

        content = QWidget()
        content.setStyleSheet("background:transparent;border:none;")
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, DT.S.sm, 0)
        content_lay.setSpacing(DT.S.md)

        # ---- 2x2 grid of LiveLineChart cards --------------------------
        chart_grid = QGridLayout()
        chart_grid.setSpacing(DT.S.md)
        chart_grid.setContentsMargins(0, 0, 0, 0)

        def _make_chart_card(label: str, units: str, *,
                             value_max: float = 100.0,
                             fmt: str = "{:.0f}"):
            card = Card(glass=True, elevated=True, padded=True)
            chart = LiveLineChart(label, units, value_max=value_max, fmt=fmt)
            card.layout().addWidget(chart)
            return card, chart

        cpu_card,  self.cpu_chart  = _make_chart_card("CPU usage", "%",
                                                      value_max=100.0)
        ram_card,  self.ram_chart  = _make_chart_card("Memory",   "%",
                                                      value_max=100.0)
        gpu_card,  self.gpu_chart  = _make_chart_card("GPU",      "%",
                                                      value_max=100.0)
        # Network is auto-scaled (passing value_max<=0 enables autoscale).
        net_card,  self.net_chart  = _make_chart_card("Network",  "MB/s",
                                                      value_max=0.0,
                                                      fmt="{:.2f}")

        chart_grid.addWidget(cpu_card, 0, 0)
        chart_grid.addWidget(ram_card, 0, 1)
        chart_grid.addWidget(gpu_card, 1, 0)
        chart_grid.addWidget(net_card, 1, 1)
        chart_grid.setColumnStretch(0, 1)
        chart_grid.setColumnStretch(1, 1)
        chart_grid.setRowStretch(0, 1)
        chart_grid.setRowStretch(1, 1)

        chart_wrapper = QWidget()
        chart_wrapper.setStyleSheet("background:transparent;border:none;")
        chart_wrapper.setLayout(chart_grid)
        chart_wrapper.setMinimumHeight(380)
        content_lay.addWidget(chart_wrapper, 1)

        # ---- Bottom row: Activity Log + Top Processes -----------------
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(DT.S.md)

        # --- Activity log card ---
        log_card = Card(glass=True, elevated=True, padded=True)
        lc_lay = log_card.layout()
        log_header = QHBoxLayout()
        log_header.setSpacing(DT.S.sm)
        log_title = H2("Activity log")
        log_header.addWidget(log_title)
        log_header.addStretch(1)
        clear_btn = QPushButton("Clear")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            f"QPushButton {{ color:{DT.C.text_muted}; "
            f"  background:transparent; border:1px solid {DT.C.border_strong}; "
            f"  border-radius:{DT.R.sm}px; padding:4px 12px; "
            f"  font-family:'{DT.T.family}'; font-size:{DT.T.small_size}px; "
            f"  font-weight:600; }} "
            f"QPushButton:hover {{ color:{DT.C.text}; "
            f"  border:1px solid {DT.C.accent}; "
            f"  background:{DT.C.accent_soft}; }}"
        )
        clear_btn.clicked.connect(self._clear_log)
        log_header.addWidget(clear_btn)
        lc_lay.addLayout(log_header)

        self._log_container = QWidget()
        self._log_container.setStyleSheet("background:transparent;border:none;")
        self._log_lay = QVBoxLayout(self._log_container)
        self._log_lay.setContentsMargins(0, 0, 0, 0)
        self._log_lay.setSpacing(DT.S.xs)
        lc_lay.addWidget(self._log_container, 1)
        lc_lay.addStretch(0)
        # Bounded queue of last-N (timestamp, name, msg, level) tuples
        # for re-rendering. Kept in sync with `_log_lay` rows.
        self._log_entries = deque(maxlen=12)

        bottom_row.addWidget(log_card, 3)

        # --- Top processes card ---
        proc_card = Card(glass=True, elevated=True, padded=True)
        pc_lay = proc_card.layout()
        proc_title = H2("Top processes")
        pc_lay.addWidget(proc_title)

        # Table header
        ph = QHBoxLayout()
        ph.setSpacing(DT.S.sm)
        for col, stretch, align in (
            ("Process", 4, Qt.AlignmentFlag.AlignLeft),
            ("CPU",     2, Qt.AlignmentFlag.AlignRight),
            ("RAM",     2, Qt.AlignmentFlag.AlignRight),
        ):
            lbl = QLabel(col)
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet(
                f"color:{DT.C.text_subtle}; font-family:'{DT.T.family}'; "
                f"font-size:{DT.T.small_size}px; font-weight:600; "
                f"letter-spacing:1px; border:none; background:transparent;"
            )
            ph.addWidget(lbl, stretch)
        pc_lay.addLayout(ph)

        self._proc_container = QWidget()
        self._proc_container.setStyleSheet("background:transparent;border:none;")
        self._proc_lay = QVBoxLayout(self._proc_container)
        self._proc_lay.setContentsMargins(0, 0, 0, 0)
        self._proc_lay.setSpacing(DT.S.xs)
        pc_lay.addWidget(self._proc_container, 1)
        pc_lay.addStretch(0)

        bottom_row.addWidget(proc_card, 2)
        content_lay.addLayout(bottom_row, 0)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # ---- Live data wiring ----------------------------------------
        # Network rate counter — psutil net_io_counters() returns
        # cumulative byte totals, so we keep the previous reading and
        # the timestamp to compute MB/s deltas per tick.
        self._net_prev = None  # (bytes_total, monotonic_ts)

        # 1 Hz tick advances the rolling window and refreshes network
        # stats. Charts repaint at 30 fps independently.
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start(1000)

        # 5 s tick refreshes the top-process table.
        self._proc_timer = QTimer(self)
        self._proc_timer.timeout.connect(self._refresh_top_processes)
        self._proc_timer.start(5000)
        # Populate immediately so the card isn't empty on first show.
        QTimer.singleShot(150, self._refresh_top_processes)

    # ----------------------------------------------------------------
    # Per-tick housekeeping
    # ----------------------------------------------------------------
    def _on_tick(self):
        """Called once per second. Advances each chart's rolling window
        and feeds the network chart its computed MB/s delta."""
        for ch in (self.cpu_chart, self.ram_chart,
                   self.gpu_chart, self.net_chart):
            try:
                ch.advance()
            except Exception as _e:
                logger.debug("chart advance failed: %s", _e)

        if psutil is None:
            return
        try:
            io = psutil.net_io_counters()
            total = io.bytes_sent + io.bytes_recv
            now = _time.monotonic()
            prev = self._net_prev
            self._net_prev = (total, now)
            if prev is not None:
                dt = max(0.001, now - prev[1])
                d_bytes = max(0, total - prev[0])
                mbps = (d_bytes / dt) / (1024 * 1024)
                self.net_chart.push(mbps)
        except Exception as _e:
            logger.debug("net counters failed: %s", _e)

    # ----------------------------------------------------------------
    # Public API: real-time stats from shell_hub.system_stats event
    # ----------------------------------------------------------------
    def update_stats(self, cpu=0, ram=0, gpu=0):
        """Push the latest backend reading into the three percent-scale
        charts. Network is collected locally on `_on_tick`."""
        try:
            self.cpu_chart.push(float(cpu))
            self.ram_chart.push(float(ram))
            self.gpu_chart.push(float(gpu))
        except Exception as _e:
            logger.debug("update_stats push failed: %s", _e)

    # ----------------------------------------------------------------
    # Activity log (signature compat: name, msg, level)
    # ----------------------------------------------------------------
    _LOG_TONE = {
        "INFO":       "accent",
        "SUCCESS":    "success",
        "WARNING":    "warning",
        "ERROR":      "error",
        "PROCESSING": "accent",
        "FAILED":     "error",
    }

    def add_log_entry(self, name, msg, level="INFO"):
        """Append an entry to the activity log card.

        Signature is preserved: (name, msg, level). Older call sites
        passed (operation, latency, status) — same positional args
        still render sensibly, just labelled differently visually.
        """
        ts = datetime.now().strftime("%H:%M:%S")
        level_key = (level or "INFO").upper()
        self._log_entries.append((ts, str(name), str(msg), level_key))
        self._rebuild_log()

    def _clear_log(self):
        self._log_entries.clear()
        self._rebuild_log()

    def _rebuild_log(self):
        while self._log_lay.count():
            item = self._log_lay.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.deleteLater()
        for ts, name, msg, level in self._log_entries:
            self._log_lay.addWidget(self._make_log_row(ts, name, msg, level))

    def _make_log_row(self, ts, name, msg, level):
        from shell_ui import design_tokens as DT
        row = QFrame()
        row.setStyleSheet("background:transparent;border:none;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 2, 0, 2)
        rl.setSpacing(DT.S.sm)

        tone = self._LOG_TONE.get(level, "neutral")
        col = {
            "accent":  DT.C.accent,
            "success": DT.C.success,
            "warning": DT.C.warning,
            "error":   DT.C.error,
            "neutral": DT.C.text_subtle,
        }.get(tone, DT.C.text_subtle)
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background:{col}; border-radius:4px; border:none;")
        rl.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

        ts_lbl = QLabel(ts)
        ts_lbl.setStyleSheet(
            f"color:{DT.C.text_subtle}; font-family:'{DT.T.family_mono}'; "
            f"font-size:{DT.T.small_size}px; border:none; background:transparent;"
        )
        ts_lbl.setFixedWidth(64)
        rl.addWidget(ts_lbl, 0, Qt.AlignmentFlag.AlignTop)

        msg_box = QVBoxLayout()
        msg_box.setSpacing(0)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color:{DT.C.text}; font-family:'{DT.T.family}'; "
            f"font-size:{DT.T.small_size}px; font-weight:600; "
            f"border:none; background:transparent;"
        )
        msg_lbl = QLabel(msg)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color:{DT.C.text_muted}; font-family:'{DT.T.family}'; "
            f"font-size:{DT.T.small_size}px; border:none; background:transparent;"
        )
        msg_box.addWidget(name_lbl)
        msg_box.addWidget(msg_lbl)
        rl.addLayout(msg_box, 1)
        return row

    # ----------------------------------------------------------------
    # Top processes (psutil-backed, refreshed every 5 s)
    # ----------------------------------------------------------------
    def _refresh_top_processes(self):
        while self._proc_lay.count():
            item = self._proc_lay.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.deleteLater()
        if psutil is None:
            self.add_process_row("psutil unavailable", 0.0, 0.0)
            return
        rows = []
        try:
            # First pass cpu_percent() returns 0.0; subsequent passes
            # (driven by the 5 s timer) are accurate.
            for proc in psutil.process_iter(attrs=("name", "cpu_percent",
                                                   "memory_info")):
                try:
                    info = proc.info
                    name = info.get("name") or "?"
                    cpu_pct = float(info.get("cpu_percent") or 0.0)
                    mem = info.get("memory_info")
                    ram_mb = (mem.rss / (1024 * 1024)) if mem else 0.0
                    rows.append((name, cpu_pct, ram_mb))
                except Exception:
                    continue
        except Exception as _e:
            logger.debug("process_iter failed: %s", _e)
            return

        rows.sort(key=lambda r: r[1], reverse=True)
        rows = rows[:5]

        for name, cpu_pct, ram_mb in rows:
            self.add_process_row(name, cpu_pct, ram_mb)

    def add_process_row(self, name, cpu_pct, ram_mb):
        """Append a single row to the Top Processes card."""
        from shell_ui import design_tokens as DT
        row = QFrame()
        row.setStyleSheet(
            f"background:transparent; border:none; "
            f"border-bottom:1px solid {DT.C.border};"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(2, 4, 2, 4)
        rl.setSpacing(DT.S.sm)

        n_lbl = QLabel(str(name)[:32])
        n_lbl.setStyleSheet(
            f"color:{DT.C.text}; font-family:'{DT.T.family}'; "
            f"font-size:{DT.T.small_size}px; font-weight:500; "
            f"border:none; background:transparent;"
        )
        rl.addWidget(n_lbl, 4)

        cpu_lbl = QLabel(f"{cpu_pct:.1f}%")
        cpu_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        cpu_lbl.setStyleSheet(
            f"color:{DT.C.accent}; font-family:'{DT.T.family_mono}'; "
            f"font-size:{DT.T.small_size}px; font-weight:600; "
            f"border:none; background:transparent;"
        )
        rl.addWidget(cpu_lbl, 2)

        ram_lbl = QLabel(f"{ram_mb:,.0f} MB")
        ram_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ram_lbl.setStyleSheet(
            f"color:{DT.C.text_muted}; font-family:'{DT.T.family_mono}'; "
            f"font-size:{DT.T.small_size}px; "
            f"border:none; background:transparent;"
        )
        rl.addWidget(ram_lbl, 2)

        self._proc_lay.addWidget(row)

    # ----------------------------------------------------------------
    # Visibility helpers — _on_page_change uses these to pause animation
    # when the System page isn't on screen.
    # ----------------------------------------------------------------
    def start_animations(self):
        """Resume per-chart 30 fps repaint + the 1 Hz tick + 5 s proc tick."""
        for ch in (self.cpu_chart, self.ram_chart,
                   self.gpu_chart, self.net_chart):
            try:
                if not ch._t.isActive():
                    ch._t.start(33)
            except Exception as _e:
                logger.debug("chart timer start failed: %s", _e)
        try:
            if not self._tick_timer.isActive():
                self._tick_timer.start(1000)
            if not self._proc_timer.isActive():
                self._proc_timer.start(5000)
        except Exception as _e:
            logger.debug("system timers start failed: %s", _e)

    def stop_animations(self):
        """Pause every timer the page owns. Saves CPU when off-screen."""
        for ch in (self.cpu_chart, self.ram_chart,
                   self.gpu_chart, self.net_chart):
            try:
                ch._t.stop()
            except Exception as _e:
                logger.debug("chart timer stop failed: %s", _e)
        try:
            self._tick_timer.stop()
            self._proc_timer.stop()
        except Exception as _e:
            logger.debug("system timers stop failed: %s", _e)


class BackendToolCatalogWorker(QThread):
    catalog_ready = pyqtSignal(object)
    catalog_error = pyqtSignal(str)

    def run(self):
        try:
            try:
                data = _post_mcp_action({"action": "list_capabilities"}, timeout=1.5)
                if isinstance(data, dict) and data.get("status") == "success":
                    data["source"] = "mcp"
                    self.catalog_ready.emit(data)
                    return
                raise RuntimeError(str(data))
            except Exception as mcp_error:
                from shell_tool_catalog import discover_capabilities
                data = discover_capabilities()
                data["source"] = "local"
                data["mcp_error"] = str(mcp_error)
                self.catalog_ready.emit(data)
        except Exception as exc:
            self.catalog_error.emit(str(exc))


class BackendToolRunWorker(QThread):
    run_ready = pyqtSignal(object)
    run_error = pyqtSignal(str)

    def __init__(self, item, args, parent=None):
        super().__init__(parent)
        self._item = dict(item or {})
        self._args = dict(args or {})

    def run(self):
        try:
            item = self._item
            if item.get("kind") == "windows_mcp_tool":
                from shell_windows_mcp import call_windows_mcp_tool_sync
                result = call_windows_mcp_tool_sync(item.get("name") or item.get("id"), self._args)
                self.run_ready.emit(result)
                return
            if item.get("kind") == "mcp_action":
                payload = {"action": item.get("name")}
                payload.update(self._args)
            else:
                payload = {
                    "action": "run_tool",
                    "tool": item.get("id"),
                    "args": self._args,
                }
            try:
                ui_tool_timeout = float(os.environ.get("SHELL_UI_TOOL_TIMEOUT_S", "60"))
                result = _post_mcp_action(payload, timeout=ui_tool_timeout)
                if isinstance(result, dict):
                    result.setdefault("transport", "mcp")
                self.run_ready.emit(result)
                return
            except Exception as mcp_error:
                if item.get("kind") not in {"tool", "agent"}:
                    raise
                from shell_tool_gateway import execute_tool_sync
                result = execute_tool_sync(item.get("id", ""), self._args)
                result["transport"] = "local"
                result["mcp_error"] = str(mcp_error)
                self.run_ready.emit(result)
        except Exception as exc:
            self.run_error.emit(str(exc))


class BackendToolsPage(QWidget):
    tool_prompt_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._catalog = []
        self._selected = None
        self._catalog_worker = None
        self._run_worker = None
        self._build_ui()
        QTimer.singleShot(100, self.refresh_catalog)

    def _panel_style(self):
        return (
            f"background:{C_SURFACE}; border:1px solid {C_OUTLINE}; "
            "border-radius:8px;"
        )

    def _button_style(self, primary=False):
        bg = C_PRIMARY if primary else C_SURFACE_HIGH
        fg = "#ffffff" if primary else C_TEXT
        hover = C_PRIMARY_BOLD if primary else C_SURFACE_CONT
        return (
            "QPushButton {"
            f" background:{bg}; color:{fg}; border:1px solid {C_OUTLINE};"
            f" border-radius:8px; font-family:'{_FONT}'; font-size:12px;"
            " font-weight:700; padding:8px 12px;"
            "}"
            f"QPushButton:hover {{ background:{hover}; }}"
            "QPushButton:disabled { color:rgba(255,255,255,0.35); background:rgba(255,255,255,0.06); }"
        )

    def _input_style(self):
        return (
            f"background:{C_BG}; color:{C_TEXT}; border:1px solid {C_OUTLINE}; "
            f"border-radius:8px; padding:8px 10px; font-family:'{_FONT}'; "
            "font-size:12px;"
        )

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        left = QFrame()
        left.setFixedWidth(360)
        left.setStyleSheet(self._panel_style())
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(16, 16, 16, 16)
        left_lay.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("Tools / MCP")
        title.setStyleSheet(
            f"color:{C_TEXT}; font-family:'{_FONT}'; font-size:20px; "
            "font-weight:800; border:none; background:transparent;"
        )
        top.addWidget(title)
        top.addStretch(1)
        refresh = QPushButton("Refresh")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.setStyleSheet(self._button_style(False))
        refresh.clicked.connect(self.refresh_catalog)
        top.addWidget(refresh)
        left_lay.addLayout(top)

        self._status = QLabel("Loading catalog...")
        self._status.setStyleSheet(
            f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:11px; "
            "border:none; background:transparent;"
        )
        left_lay.addWidget(self._status)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search backend tools")
        self._search.setStyleSheet(self._input_style())
        self._search.textChanged.connect(self._render_list)
        left_lay.addWidget(self._search)

        self._category = QComboBox()
        self._category.setStyleSheet(self._input_style())
        self._category.currentTextChanged.connect(self._render_list)
        left_lay.addWidget(self._category)

        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setStyleSheet("background:transparent; border:none;")
        self._list_host = QWidget()
        self._list_host.setStyleSheet("background:transparent; border:none;")
        self._list_lay = QVBoxLayout(self._list_host)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(6)
        self._list_scroll.setWidget(self._list_host)
        left_lay.addWidget(self._list_scroll, 1)
        root.addWidget(left)

        right = QFrame()
        right.setStyleSheet(self._panel_style())
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(18, 18, 18, 18)
        right_lay.setSpacing(12)

        self._title = QLabel("Select a tool")
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            f"color:{C_TEXT}; font-family:'{_FONT}'; font-size:22px; "
            "font-weight:800; border:none; background:transparent;"
        )
        right_lay.addWidget(self._title)

        self._meta = QLabel("Catalog will load automatically.")
        self._meta.setWordWrap(True)
        self._meta.setStyleSheet(
            f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:12px; "
            "border:none; background:transparent;"
        )
        right_lay.addWidget(self._meta)

        self._desc = QLabel("")
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet(
            f"color:{C_TEXT}; font-family:'{_FONT}'; font-size:13px; "
            "border:none; background:transparent;"
        )
        right_lay.addWidget(self._desc)

        args_lbl = QLabel("Arguments JSON")
        args_lbl.setStyleSheet(
            f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:11px; "
            "font-weight:700; border:none; background:transparent;"
        )
        right_lay.addWidget(args_lbl)

        self._args = QTextEdit()
        self._args.setMinimumHeight(150)
        self._args.setStyleSheet(
            f"background:{C_BG}; color:{C_TEXT}; border:1px solid {C_OUTLINE}; "
            f"border-radius:8px; padding:10px; font-family:'{_MONO}'; font-size:12px;"
        )
        right_lay.addWidget(self._args)

        btns = QHBoxLayout()
        self._run_btn = QPushButton("Run")
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.setEnabled(False)
        self._run_btn.setStyleSheet(self._button_style(True))
        self._run_btn.clicked.connect(self._run_selected)
        btns.addWidget(self._run_btn)

        self._chat_btn = QPushButton("Send to chat")
        self._chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chat_btn.setEnabled(False)
        self._chat_btn.setStyleSheet(self._button_style(False))
        self._chat_btn.clicked.connect(self._send_to_chat)
        btns.addWidget(self._chat_btn)
        btns.addStretch(1)
        right_lay.addLayout(btns)

        out_lbl = QLabel("Result")
        out_lbl.setStyleSheet(
            f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:11px; "
            "font-weight:700; border:none; background:transparent;"
        )
        right_lay.addWidget(out_lbl)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setMinimumHeight(190)
        self._output.setStyleSheet(
            f"background:{C_BG}; color:{C_TEXT}; border:1px solid {C_OUTLINE}; "
            f"border-radius:8px; padding:10px; font-family:'{_MONO}'; font-size:12px;"
        )
        right_lay.addWidget(self._output, 1)
        root.addWidget(right, 1)

    def refresh_catalog(self):
        if self._catalog_worker and self._catalog_worker.isRunning():
            return
        self._status.setText("Loading catalog...")
        self._catalog_worker = BackendToolCatalogWorker(self)
        self._catalog_worker.catalog_ready.connect(self._on_catalog_ready)
        self._catalog_worker.catalog_error.connect(self._on_catalog_error)
        self._catalog_worker.start()

    def _on_catalog_ready(self, data):
        catalog = list(data.get("catalog") or [])
        self._catalog = catalog
        summary = data.get("summary") or {}
        source = data.get("source", "?")
        total = summary.get("total", len(catalog))
        tools = summary.get("tools", 0)
        agents = summary.get("agents", 0)
        actions = summary.get("actions", 0)
        suffix = ""
        if source == "local" and data.get("mcp_error"):
            suffix = " | MCP offline, local catalog"
        self._status.setText(
            f"{total} items ({actions} MCP, {tools} tools, {agents} agents) | {source}{suffix}"
        )
        categories = ["All"] + sorted({str(x.get("category", "general")) for x in catalog})
        self._category.blockSignals(True)
        self._category.clear()
        self._category.addItems(categories)
        self._category.blockSignals(False)
        self._render_list()
        if catalog and self._selected is None:
            self._select_item(catalog[0])

    def _on_catalog_error(self, message):
        self._status.setText("Catalog unavailable")
        self._output.setPlainText(message)

    def _filtered_items(self):
        query = self._search.text().strip().lower()
        category = self._category.currentText().strip().lower()
        items = []
        for item in self._catalog:
            blob = " ".join([
                str(item.get("name", "")),
                str(item.get("title", "")),
                str(item.get("module", "")),
                str(item.get("description", "")),
                str(item.get("category", "")),
            ]).lower()
            if query and query not in blob:
                continue
            if category and category != "all" and str(item.get("category", "")).lower() != category:
                continue
            items.append(item)
        return items

    def _clear_list(self):
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_list(self, *args):
        self._clear_list()
        for item in self._filtered_items():
            name = item.get("title") or item.get("name") or item.get("id")
            sub = f"{item.get('category', 'general')} | {item.get('module', '')}"
            btn = QPushButton(f"{name}\n{sub}")
            btn.setFixedHeight(54)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton {"
                f" background:{C_SURFACE_HIGH}; color:{C_TEXT}; border:1px solid {C_OUTLINE};"
                " border-radius:8px; text-align:left; padding:7px 10px;"
                f" font-family:'{_FONT}'; font-size:12px; font-weight:700;"
                "}"
                f"QPushButton:hover {{ background:{C_SURFACE_CONT}; border-color:{C_PRIMARY}; }}"
            )
            btn.clicked.connect(lambda _checked=False, it=item: self._select_item(it))
            self._list_lay.addWidget(btn)
        self._list_lay.addStretch(1)

    def _template_value(self, param):
        if not param.get("required") and param.get("default") is not None:
            return param.get("default")
        annotation = str(param.get("annotation", "")).lower()
        if "bool" in annotation:
            return False
        if "int" in annotation:
            return 0
        if "float" in annotation:
            return 0.0
        if "list" in annotation:
            return []
        if "dict" in annotation:
            return {}
        return ""

    def _args_template(self, item):
        import json
        params = item.get("params") or []
        return json.dumps(
            {p["name"]: self._template_value(p) for p in params},
            indent=2,
            ensure_ascii=False,
        )

    def _select_item(self, item):
        self._selected = dict(item or {})
        title = self._selected.get("title") or self._selected.get("name") or "Tool"
        self._title.setText(str(title))
        meta = (
            f"{self._selected.get('kind', 'tool')} | {self._selected.get('category', 'general')} "
            f"| {self._selected.get('id', '')} | risk: {self._selected.get('risk', 'normal')}"
        )
        self._meta.setText(meta)
        self._desc.setText(str(self._selected.get("description") or "No description available."))
        self._args.setPlainText(self._args_template(self._selected))
        self._run_btn.setEnabled(True)
        self._chat_btn.setEnabled(True)

    def _read_args(self):
        import json
        text = self._args.toPlainText().strip()
        if not text:
            return {}
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("Arguments must be a JSON object")
        return value

    def _run_selected(self):
        if not self._selected:
            return
        try:
            args = self._read_args()
        except Exception as exc:
            self._output.setPlainText(f"Invalid JSON: {exc}")
            return
        self._run_btn.setEnabled(False)
        self._output.setPlainText("Running...")
        self._run_worker = BackendToolRunWorker(self._selected, args, self)
        self._run_worker.run_ready.connect(self._on_run_ready)
        self._run_worker.run_error.connect(self._on_run_error)
        self._run_worker.start()

    def _on_run_ready(self, result):
        import json
        self._run_btn.setEnabled(True)
        self._output.setPlainText(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    def _on_run_error(self, message):
        self._run_btn.setEnabled(True)
        self._output.setPlainText(message)

    def _send_to_chat(self):
        if not self._selected:
            return
        try:
            args = self._read_args()
        except Exception:
            args = {}
        import json
        kind = str(self._selected.get("kind") or "tool").lower()
        if kind == "agent":
            command = "/agent"
            target = self._selected.get("id")
        elif kind in {"windows_mcp_tool", "mcp_action"}:
            command = "/mcp"
            target = self._selected.get("name") or self._selected.get("id")
        else:
            command = "/tool"
            target = self._selected.get("id")
        self.tool_prompt_requested.emit(
            f"{command} {target} {json.dumps(args, ensure_ascii=False)}"
        )

    def stop_workers(self):
        for name in ("_catalog_worker", "_run_worker"):
            worker = getattr(self, name, None)
            if worker is None:
                continue
            try:
                if worker.isRunning():
                    worker.requestInterruption()
                    if not worker.wait(2000):
                        worker.terminate()
                        worker.wait(1000)
            except Exception as exc:
                logger.debug("tools page worker stop failed (%s): %s", name, exc)

    def closeEvent(self, event):
        self.stop_workers()
        super().closeEvent(event)


# =====================================================================
#  ToggleSwitch
# =====================================================================

class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, on=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on = on
        self._pos = 28.0 if on else 4.0
        # Animation timer is created but NOT started until _kick_anim
        # is called. The previous version started a 60fps timer in
        # __init__ that ran forever — N toggles per Settings page = N
        # idle 16ms timers burning CPU even when nothing is animating.
        self._t = QTimer(self)
        self._t.timeout.connect(self._anim)

    def set_on(self, on):
        self._on = bool(on)
        self._kick_anim()

    def mousePressEvent(self, e):
        self._on = not self._on
        self.toggled.emit(self._on)
        self._kick_anim()
        e.accept()

    def _kick_anim(self):
        if not self._t.isActive():
            self._t.start(16)

    def _anim(self):
        tgt = 28.0 if self._on else 4.0
        self._pos += (tgt - self._pos) * 0.2
        if abs(tgt - self._pos) < 0.5:
            # Snap, stop the timer — no need to keep ticking.
            self._pos = tgt
            self._t.stop()
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        if self._on:
            p.setBrush(QColor(C_PRIMARY_BOLD))
        else:
            p.setBrush(QColor(C_SURFACE_HIGHEST))
        p.drawRoundedRect(QRectF(0, 0, 48, 24), 12, 12)

        # Knob
        if self._on:
            p.setBrush(QColor(255, 255, 255))
            # Glow
            glow = QRadialGradient(QPointF(self._pos + 8, 12), 14)
            glow.setColorAt(0, QColor(143, 245, 255, 60))
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(glow)
            p.drawEllipse(QPointF(self._pos + 8, 12), 14, 14)
            p.setBrush(QColor(255, 255, 255))
        else:
            p.setBrush(QColor(C_OUTLINE))
        p.drawEllipse(QPointF(self._pos + 8, 12), 8, 8)
        p.end()


# =====================================================================
#  SettingsPage
# =====================================================================

class SettingsPage(QWidget):
    """macOS System Preferences-style settings.

    Layout: a fixed-width left rail of category buttons + a right-pane
    `QStackedWidget` whose pages each scroll their own controls. Switching
    categories triggers a 120 ms cross-fade on the right pane only — the
    rail itself updates instantly.

    All persistence reuses the legacy handlers (`_save_toggle`,
    `_on_commit`, `_save_new_provider`, `_on_language_changed`,
    `on_api_key_update`, `_on_sensitivity_change`, `_switch_theme`) so
    the agent / hub side keeps working unchanged.
    """

    # Categories: (id, glyph, label). The id is what `_active_cat` stores
    # and what the per-category builders key off of. Glyphs use plain
    # symbol/emoji to dodge a font dependency.
    _CATEGORIES = [
        ("appearance", "🎨", "Appearance"),
        ("voice",      "🔊", "Voice & Speech"),
        ("language",   "🌐", "Language"),
        ("apikeys",    "🔑", "API Keys"),
        ("model",      "🤖", "Model & Brain"),
        ("shortcuts",  "⌨", "Shortcuts"),
        ("system",     "⚙", "System"),
        ("privacy",    "🛡", "Privacy & Safety"),
        ("help",       "?", "Help Center"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent; border:none;")

        # Local imports — keep them scoped so a module-level import-order
        # change can never cascade and break the rest of the file.
        from shell_ui.design_tokens import C as _DC, S as _DS, R as _DR, M as _DM, T as _DT
        from shell_ui.widgets import (
            Card, H1, H2, Body, Muted, PrimaryButton, SecondaryButton,
            GhostButton, Input, Pill,
        )
        self._DC, self._DS, self._DR, self._DM, self._DT = _DC, _DS, _DR, _DM, _DT
        self._Card = Card; self._H1 = H1; self._H2 = H2; self._Body = Body
        self._Muted = Muted; self._PrimaryButton = PrimaryButton
        self._SecondaryButton = SecondaryButton; self._GhostButton = GhostButton
        self._Input = Input; self._Pill = Pill

        # Voice sensitivity backing field — referenced by _on_commit. The
        # actual slider is built lazily inside _build_voice_page.
        self._voice_sensitivity = 65
        self._voice_slider = None
        self._sens_passive = None
        self._sens_active = None
        self._sens_aggressive = None
        self._toggle_auto_venv = None
        self._toggle_gpu_accel = None
        self._theme_btns = {}
        self._pending_settings_sync = {}
        self._settings_sync_timer = QTimer(self)
        self._settings_sync_timer.setSingleShot(True)
        self._settings_sync_timer.setInterval(250)
        self._settings_sync_timer.timeout.connect(self._flush_settings_sync)

        # ---- Outer chrome: header + (rail | stacked content) -----------
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 8, 24, 4)
        outer.setSpacing(0)

        outer.addWidget(self._H1("Settings"))
        outer.addSpacing(2)
        outer.addWidget(self._Muted(
            "Calibrate the interface, voice, providers, and safety policies."
        ))
        outer.addSpacing(_DS.md)

        split = QHBoxLayout()
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(_DS.lg)

        self._rail_buttons = {}            # cat_id → QPushButton
        rail = self._build_rail()
        split.addWidget(rail, 0)

        # Right pane is a QStackedWidget — one page per category. We
        # cross-fade the active page when switching, see _switch_cat.
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent; border:none;")
        self._page_for_cat = {}
        for cat_id, _g, _lbl in self._CATEGORIES:
            page = self._build_category_page(cat_id)
            idx = self._stack.addWidget(page)
            self._page_for_cat[cat_id] = idx
        split.addWidget(self._stack, 1)

        outer.addLayout(split, 1)

        # ---- Bottom action bar (Mac-style) -----------------------------
        outer.addSpacing(_DS.md)
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 0, 0, 0)
        btn_bar.setSpacing(_DS.sm)
        btn_bar.addStretch(1)

        discard = self._SecondaryButton("Discard Changes")
        discard.clicked.connect(self._on_discard)
        btn_bar.addWidget(discard)

        commit = self._PrimaryButton("Commit Settings")
        commit.clicked.connect(self._on_commit)
        btn_bar.addWidget(commit)
        outer.addLayout(btn_bar)

        # Default category.
        self._active_cat = self._CATEGORIES[0][0]
        self._switch_cat(self._active_cat, animate=False)

    # ==================================================================
    # Left rail
    # ==================================================================

    def _build_rail(self) -> QFrame:
        """Vertical category list — fixed 220 px wide, glass-panel
        background, Mac-sidebar feel."""
        DC, DS, DR = self._DC, self._DS, self._DR

        rail = QFrame()
        rail.setObjectName("settingsRail")
        rail.setFixedWidth(220)
        rail.setStyleSheet(
            f"#settingsRail {{ "
            f"  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"    stop:0 {DC.glass_hi}, "
            f"    stop:0.04 {DC.glass}, "
            f"    stop:1 {DC.glass}); "
            f"  border:1px solid {DC.glass_border}; "
            f"  border-top:1px solid {DC.glass_hi}; "
            f"  border-radius:{DR.lg}px; "
            f"}}"
        )
        rail_lay = QVBoxLayout(rail)
        rail_lay.setContentsMargins(DS.sm, DS.sm, DS.sm, DS.sm)
        rail_lay.setSpacing(2)

        for cat_id, glyph, label in self._CATEGORIES:
            # Qt QPushButton treats `&` as a mnemonic char (underlines the
            # next letter, hides the &). Double it so "Voice & Speech"
            # renders correctly instead of "Voice _Speech".
            safe_label = label.replace("&", "&&")
            btn = QPushButton(f"  {glyph}    {safe_label}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(40)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setProperty("cat_id", cat_id)
            self._apply_rail_button_style(btn, active=False)
            btn.clicked.connect(lambda _checked=False, c=cat_id: self._switch_cat(c))
            rail_lay.addWidget(btn)
            self._rail_buttons[cat_id] = btn

        rail_lay.addStretch(1)
        return rail

    def _apply_rail_button_style(self, btn: QPushButton, *, active: bool) -> None:
        DC, DR, DT = self._DC, self._DR, self._DT
        if active:
            qss = (
                f"QPushButton {{ "
                f"  background:{DC.surface_2}; "
                f"  color:{DC.text}; "
                f"  text-align:left; "
                f"  border:none; "
                f"  border-left:3px solid {DC.accent}; "
                f"  border-radius:{DR.sm}px; "
                f"  padding:0 10px; "
                f"  font-family:'{DT.family}'; font-size:{DT.body_size}px; "
                f"  font-weight:600; "
                f"}}"
            )
        else:
            qss = (
                f"QPushButton {{ "
                f"  background:transparent; "
                f"  color:{DC.text_muted}; "
                f"  text-align:left; "
                f"  border:none; "
                f"  border-left:3px solid transparent; "
                f"  border-radius:{DR.sm}px; "
                f"  padding:0 10px; "
                f"  font-family:'{DT.family}'; font-size:{DT.body_size}px; "
                f"  font-weight:500; "
                f"}} "
                f"QPushButton:hover {{ "
                f"  background:{DC.accent_soft}; "
                f"  color:{DC.text}; "
                f"}}"
            )
        btn.setStyleSheet(qss)

    def _switch_cat(self, cat_id: str, *, animate: bool = True) -> None:
        """Activate the named category. Rail repaints instantly; the
        right-pane content cross-fades for ~120 ms."""
        if cat_id not in self._page_for_cat:
            return
        for cid, btn in self._rail_buttons.items():
            self._apply_rail_button_style(btn, active=(cid == cat_id))
        self._active_cat = cat_id
        idx = self._page_for_cat[cat_id]
        self._stack.setCurrentIndex(idx)
        if not animate:
            return
        new_page = self._stack.widget(idx)
        try:
            eff = QGraphicsOpacityEffect(new_page)
            eff.setOpacity(0.0)
            new_page.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", new_page)
            anim.setDuration(120)  # explicit per spec
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(0.0); anim.setEndValue(1.0)
            anim.finished.connect(lambda: new_page.setGraphicsEffect(None))
            anim.start()
            self._fade_anim = anim  # keep alive
        except Exception as _e:
            logger.debug("settings cross-fade failed: %s", _e)

    # ==================================================================
    # Right pane — page builders
    # ==================================================================

    def _build_category_page(self, cat_id: str) -> QWidget:
        """Wrap a category's controls in a `QScrollArea` so each page
        scrolls independently (Mac sheets behave the same way)."""
        DC, DS = self._DC, self._DS

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background:transparent; border:none; }} "
            f"QScrollBar:vertical {{ width:6px; background:transparent; }} "
            f"QScrollBar::handle:vertical {{ background:{DC.border_strong}; "
            f"  border-radius:3px; min-height:24px; }} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}"
        )

        host = QWidget()
        host.setStyleSheet("background:transparent; border:none;")
        col = QVBoxLayout(host)
        col.setContentsMargins(DS.sm, DS.xs, DS.lg, DS.lg)
        col.setSpacing(DS.lg)

        builder = {
            "appearance": self._build_appearance_page,
            "voice":      self._build_voice_page,
            "language":   self._build_language_page,
            "apikeys":    self._build_apikeys_page,
            "model":      self._build_model_page,
            "shortcuts":  self._build_shortcuts_page,
            "system":     self._build_system_page,
            "privacy":    self._build_privacy_page,
            "help":       self._build_help_page,
        }.get(cat_id)
        if builder:
            try:
                builder(col)
            except Exception as _e:
                logger.debug("settings page build failed (%s): %s", cat_id, _e)
                col.addWidget(self._Body(f"Failed to render: {_e}", muted=True))
        col.addStretch(1)

        scroll.setWidget(host)
        return scroll

    # ---- helpers -----------------------------------------------------

    def _make_setting_card(self, heading: str, description: str = ""):
        """Build a card containing H2 heading + Muted description, returning
        (card, inner_layout) so the caller can append the actual control."""
        DS = self._DS
        card = self._Card(glass=True, padded=True)
        lay = card.layout()
        lay.setSpacing(DS.sm)
        lay.addWidget(self._H2(heading))
        if description:
            lay.addWidget(self._Muted(description))
        return card, lay

    def _styled_slider(self, value: int, vmin: int = 0, vmax: int = 100) -> QSlider:
        DC = self._DC
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(vmin, vmax); s.setValue(value)
        s.setStyleSheet(
            f"QSlider::groove:horizontal {{ "
            f"  background:{DC.surface_2}; height:4px; border-radius:2px; "
            f"  border:1px solid {DC.border}; }} "
            f"QSlider::handle:horizontal {{ "
            f"  background:#ffffff; width:16px; height:16px; "
            f"  margin:-7px 0; border-radius:8px; "
            f"  border:2px solid {DC.accent}; }} "
            f"QSlider::sub-page:horizontal {{ "
            f"  background:{DC.accent}; border-radius:2px; }}"
        )
        return s

    def _styled_combo(self, items) -> QComboBox:
        DC, DR, DT = self._DC, self._DR, self._DT
        cb = QComboBox()
        for it in items:
            cb.addItem(it)
        cb.setStyleSheet(
            f"QComboBox {{ background:{DC.surface}; "
            f"  border:1px solid {DC.border_strong}; border-radius:{DR.md}px; "
            f"  color:{DC.text}; font-family:'{DT.family}'; font-size:{DT.body_size}px; "
            f"  padding:8px 12px; }} "
            f"QComboBox:hover {{ border-color:{DC.accent}; }} "
            f"QComboBox::drop-down {{ border:none; width:24px; }} "
            f"QComboBox QAbstractItemView {{ "
            f"  background:{DC.surface}; color:{DC.text}; "
            f"  selection-background-color:{DC.accent_soft}; "
            f"  border:1px solid {DC.border_strong}; outline:none; }}"
        )
        return cb

    def _toggle_row(self, label_text: str, *, on: bool, on_change):
        """Compose a horizontal row: [ToggleSwitch] [label] [stretch].
        Returns (row_widget, switch_widget) so callers can keep a handle
        on the switch (for legacy `set_on` calls)."""
        DS = self._DS
        row = QWidget()
        row.setStyleSheet("background:transparent; border:none;")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(DS.md)
        sw = ToggleSwitch(on=on)
        sw.toggled.connect(on_change)
        h.addWidget(sw)
        h.addWidget(self._Body(label_text))
        h.addStretch(1)
        return row, sw

    def _settings_path(self) -> str:
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            ".shell_settings.json",
        )

    def _read_setting(self, key: str, default):
        """Load a single value from .shell_settings.json (returns
        `default` on any error)."""
        import json
        try:
            p = self._settings_path()
            if not os.path.exists(p):
                return default
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            value = cfg.get(key, default)
            return default if value is None else value
        except Exception:
            return default

    def _show_commit_toast(self, text: str = "Settings committed") -> None:
        """Mac-style transient toast pinned to the bottom of the page."""
        try:
            DC, DR, DT = self._DC, self._DR, self._DT
            toast = QLabel(text, self)
            toast.setStyleSheet(
                f"background:{DC.surface_3}; color:{DC.text}; "
                f"border:1px solid {DC.border_strong}; "
                f"border-radius:{DR.md}px; padding:8px 16px; "
                f"font-family:'{DT.family}'; font-size:{DT.body_size}px; "
                f"font-weight:600;"
            )
            toast.adjustSize()
            x = (self.width() - toast.width()) // 2
            y = self.height() - toast.height() - 24
            toast.move(max(8, x), max(8, y))
            toast.show()
            QTimer.singleShot(1800, toast.deleteLater)
        except Exception as _e:
            logger.debug("toast failed: %s", _e)

    # ==================================================================
    # Appearance page
    # ==================================================================

    def _build_appearance_page(self, col: QVBoxLayout) -> None:
        DC, DR, DT = self._DC, self._DR, self._DT

        # Theme picker (port of the original pill row).
        card, lay = self._make_setting_card(
            "Theme", "Switch between visual styles for the entire interface."
        )
        pill_frame = QFrame()
        pill_frame.setStyleSheet(
            f"background:{DC.surface_2}; "
            f"border:1px solid {DC.border}; "
            f"border-radius:{DR.md}px; padding:3px;"
        )
        pill_lay = QHBoxLayout(pill_frame)
        pill_lay.setContentsMargins(3, 3, 3, 3); pill_lay.setSpacing(2)
        try:
            te = ThemeEngine.get()
            theme_names = list(te.theme_names)
            active_name = te.active_name
        except Exception:
            theme_names = ["DARK", "LIGHT"]; active_name = "DARK"
        self._theme_btns = {}
        for theme_name in theme_names:
            display = theme_name.replace("_", " ").title()
            btn = QPushButton(display)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._style_theme_pill(btn, active=(theme_name == active_name))
            btn.clicked.connect(lambda _c=False, tn=theme_name: self._switch_theme(tn))
            pill_lay.addWidget(btn)
            self._theme_btns[theme_name] = btn
        lay.addWidget(pill_frame)
        col.addWidget(card)

        # Accent intensity slider.
        card, lay = self._make_setting_card(
            "Accent intensity",
            "How saturated the accent colour appears across buttons and highlights.",
        )
        intensity = int(self._read_setting("accent_intensity", 80))
        slider = self._styled_slider(intensity, 30, 100)
        slider.valueChanged.connect(
            lambda v: self._save_toggle("accent_intensity", int(v))
        )
        lay.addWidget(slider)
        col.addWidget(card)

        # Font scale.
        card, lay = self._make_setting_card(
            "Font scale",
            "Multiplier applied to body text. 100 = system default.",
        )
        font_scale = int(self._read_setting("font_scale", 100))
        slider2 = self._styled_slider(font_scale, 80, 140)
        scale_lbl = self._Muted(f"{font_scale}%")
        def _on_font_scale(v):
            scale_lbl.setText(f"{int(v)}%")
            self._save_toggle("font_scale", int(v))
        slider2.valueChanged.connect(_on_font_scale)
        lay.addWidget(slider2)
        lay.addWidget(scale_lbl)
        col.addWidget(card)

    def _style_theme_pill(self, btn: QPushButton, *, active: bool) -> None:
        DC, DR, DT = self._DC, self._DR, self._DT
        if active:
            try:
                from shell_ui.design_tokens import accent_text_color
                active_text = accent_text_color()
            except Exception:
                active_text = "#041018"
            btn.setStyleSheet(
                f"QPushButton {{ background:{DC.accent}; color:{active_text}; "
                f"  font-family:'{DT.family}'; font-size:13px; font-weight:600; "
                f"  border:none; border-radius:{DR.sm}px; padding:0 14px; }}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{DC.text_muted}; "
                f"  font-family:'{DT.family}'; font-size:13px; font-weight:500; "
                f"  border:none; border-radius:{DR.sm}px; padding:0 14px; }} "
                f"QPushButton:hover {{ color:{DC.text}; background:{DC.accent_soft}; }}"
            )

    # ==================================================================
    # Voice & Speech page
    # ==================================================================

    def _build_voice_page(self, col: QVBoxLayout) -> None:
        # Voice mode radio: Cloud | Local | Auto.
        # When the offline Whisper+Piper backend is unavailable on this
        # machine, the "Local" option is rendered disabled with a hint.
        self._build_voice_mode_card(col)

        # Voice persona dropdown.
        card, lay = self._make_setting_card(
            "Voice persona",
            "The TTS voice Shell uses when speaking responses out loud.",
        )
        personas = ["Aoede", "Puck", "Charon", "Kore", "Fenrir"]
        cb = self._styled_combo(personas)
        current_persona = str(self._read_setting(
            "voice_persona", self._read_setting("tts_voice", "Aoede")))
        if current_persona in personas:
            cb.setCurrentText(current_persona)
        cb.currentTextChanged.connect(
            lambda v: self._save_toggle("voice_persona", v)
        )
        lay.addWidget(cb)
        col.addWidget(card)

        # TTS toggle.
        card, lay = self._make_setting_card(
            "Speak responses",
            "When on, Shell reads agent replies aloud through your default audio device.",
        )
        tts_on = bool(self._read_setting(
            "tts_enabled", self._read_setting("voice_output", True)))
        row, _sw = self._toggle_row(
            "Enable text-to-speech", on=tts_on,
            on_change=lambda v: self._save_toggle("tts_enabled", bool(v)),
        )
        lay.addWidget(row)
        col.addWidget(card)

        # Voice sensitivity (port).
        card, lay = self._make_setting_card(
            "Voice sensitivity",
            "How aggressively Shell jumps in when it detects your voice.",
        )
        sens = int(self._read_setting("voice_sensitivity", 65))
        self._voice_sensitivity = sens
        slider = self._styled_slider(sens, 0, 100)
        self._voice_slider = slider
        slider.valueChanged.connect(self._on_sensitivity_change)
        lay.addWidget(slider)

        labels_row = QHBoxLayout()
        self._sens_passive = QLabel("PASSIVE")
        self._sens_passive.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._sens_active = QLabel(f"REACTIVE ({sens}%)")
        self._sens_active.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sens_aggressive = QLabel("AGGRESSIVE")
        self._sens_aggressive.setAlignment(Qt.AlignmentFlag.AlignRight)
        for lbl, is_active in [
            (self._sens_passive,    sens < 30),
            (self._sens_active,     30 <= sens <= 75),
            (self._sens_aggressive, sens > 75),
        ]:
            self._apply_sens_label_style(lbl, active=is_active)
            labels_row.addWidget(lbl, 1)
        wrap = QWidget(); wrap.setStyleSheet("background:transparent; border:none;")
        wrap.setLayout(labels_row)
        lay.addWidget(wrap)
        col.addWidget(card)

        # Speech rate.
        card, lay = self._make_setting_card(
            "Speech rate",
            "Controls how fast spoken responses are delivered.",
        )
        rate = int(self._read_setting(
            "speech_rate", self._read_setting("tts_rate", 108)))
        rate = max(60, min(160, rate))
        slider = self._styled_slider(rate, 60, 160)
        rate_lbl = self._Muted(f"{rate}%")
        slider.valueChanged.connect(
            lambda v: (rate_lbl.setText(f"{int(v)}%"),
                       self._save_toggle("speech_rate", int(v)))
        )
        lay.addWidget(slider); lay.addWidget(rate_lbl)
        col.addWidget(card)

        # Speech volume.
        card, lay = self._make_setting_card(
            "Speech volume",
            "Output volume of TTS playback. 0 mutes, 100 is system maximum.",
        )
        vol = int(self._read_setting(
            "speech_volume", self._read_setting("tts_volume", 90)))
        vol = max(0, min(100, vol))
        slider = self._styled_slider(vol, 0, 100)
        vol_lbl = self._Muted(f"{vol}%")
        slider.valueChanged.connect(
            lambda v: (vol_lbl.setText(f"{int(v)}%"),
                       self._save_toggle("speech_volume", int(v)))
        )
        lay.addWidget(slider); lay.addWidget(vol_lbl)
        col.addWidget(card)

    def _apply_sens_label_style(self, lbl: QLabel, *, active: bool) -> None:
        DC, DT = self._DC, self._DT
        col = DC.accent if active else DC.text_muted
        weight = 700 if active else 500
        lbl.setStyleSheet(
            f"color:{col}; font-family:'{DT.family}'; font-size:10px; "
            f"font-weight:{weight}; letter-spacing:3px; "
            f"border:none; background:transparent;"
        )

    # ──────────────────────────────────────────────────────────────────
    # Voice mode radio (Cloud / Local / Auto)
    # ──────────────────────────────────────────────────────────────────

    def _build_voice_mode_card(self, col: QVBoxLayout) -> None:
        """Add a radio-button card letting the user pick the voice backend.

        - Cloud: existing Gemini realtime path.
        - Local: offline Whisper + Piper.
        - Auto: prefer Local when available, else Cloud.

        The Local option is disabled when ``/api/voice/local/availability``
        reports either Whisper or Piper as unavailable. We probe the
        endpoint best-effort on construction so the UI doesn't block on
        a network call.
        """
        try:
            from PyQt6.QtWidgets import QRadioButton, QButtonGroup
        except Exception as _e:  # pragma: no cover - PyQt always present in UI
            logger.debug("voice mode card imports failed: %s", _e)
            return

        card, lay = self._make_setting_card(
            "Voice mode",
            "Pick the backend that handles speech recognition + synthesis. "
            "Local keeps everything offline; Cloud uses the Gemini realtime "
            "API; Auto picks Local when available.",
        )

        current_mode = str(self._read_setting("voice_mode", "cloud")).lower()
        if current_mode not in {"cloud", "local", "auto"}:
            current_mode = "cloud"

        local_available, local_hint = self._probe_local_voice_availability()

        rb_cloud = QRadioButton("Cloud (Gemini realtime)")
        rb_local = QRadioButton("Local (Whisper + Piper)")
        rb_auto = QRadioButton("Auto (prefer Local)")

        # Disable the Local option when the offline backend isn't usable.
        if not local_available:
            rb_local.setEnabled(False)
            rb_local.setToolTip(
                local_hint or "Local voice unavailable on this machine"
            )
            # If the user previously selected Local but it's no longer
            # available, fall back to cloud silently.
            if current_mode == "local":
                current_mode = "cloud"
                self._save_toggle("voice_mode", "cloud")

        # Highlight current selection.
        for rb, code in (
            (rb_cloud, "cloud"),
            (rb_local, "local"),
            (rb_auto, "auto"),
        ):
            rb.setChecked(code == current_mode)

        group = QButtonGroup(card)
        group.addButton(rb_cloud)
        group.addButton(rb_local)
        group.addButton(rb_auto)

        def _on_clicked() -> None:
            mode = (
                "local" if rb_local.isChecked()
                else ("auto" if rb_auto.isChecked() else "cloud")
            )
            self._save_toggle("voice_mode", mode)

        rb_cloud.clicked.connect(_on_clicked)
        rb_local.clicked.connect(_on_clicked)
        rb_auto.clicked.connect(_on_clicked)

        for rb in (rb_cloud, rb_local, rb_auto):
            rb.setStyleSheet(
                "QRadioButton { color:#d8e8ff; padding:4px 0; "
                f"  font-family:'{self._DT.family}'; font-size:13px; }} "
                "QRadioButton:disabled { color:#6a7a92; }"
            )
            lay.addWidget(rb)

        if not local_available and local_hint:
            lay.addWidget(self._Muted(f"Local backend: {local_hint}"))

        col.addWidget(card)

    def _probe_local_voice_availability(self) -> tuple[bool, str | None]:
        """Best-effort sync probe of ``/api/voice/local/availability``.

        Returns ``(ok, hint)``. The hint propagates the missing-component
        message from the server so the user knows what to install.
        """
        import json
        import urllib.error
        import urllib.request

        base = os.environ.get("SHELL_API_BASE", "http://127.0.0.1:8000").rstrip("/")
        url = f"{base}/api/voice/local/availability"
        req = urllib.request.Request(url, headers=_api_auth_headers())
        try:
            timeout_s = float(os.environ.get("SHELL_UI_PROBE_TIMEOUT_S", "0.35"))
            with urllib.request.urlopen(req, timeout=max(0.05, timeout_s)) as r:
                body = json.loads(r.read().decode("utf-8") or "{}")
        except (OSError, ValueError, urllib.error.URLError) as _e:
            # Server not reachable — fall back to importing the backend
            # directly so the UI stays responsive offline.
            return self._probe_local_voice_inproc()
        ok = bool(body.get("ok"))
        hint = (body.get("stt") or {}).get("hint") or (
            body.get("tts") or {}
        ).get("hint")
        return ok, hint

    def _probe_local_voice_inproc(self) -> tuple[bool, str | None]:
        """Fallback probe that imports the backends directly."""
        try:
            from voice.stt_whisper import WhisperSTTBackend
            from voice.tts_piper import PiperTTSBackend

            stt_info = WhisperSTTBackend().available()
            tts_info = PiperTTSBackend().available()
            ok = bool(stt_info.get("ok")) and bool(tts_info.get("ok"))
            hint = stt_info.get("hint") or tts_info.get("hint")
            return ok, hint
        except Exception:
            return False, "voice modules not importable"

    # ==================================================================
    # Language page
    # ==================================================================

    def _build_language_page(self, col: QVBoxLayout) -> None:
        card, lay = self._make_setting_card(
            "Reply language",
            "Jis bhasha mein tum baat karna chahte ho — Shell us hi bhasha mein reply degi.",
        )
        # Same options as the legacy implementation. Keep _language_options
        # on self so the legacy _on_language_changed can still index it.
        self._language_options = [
            ("Hinglish (Hindi + English mix)", "hinglish"),
            ("English",                         "english"),
            ("Hindi (हिन्दी)",                   "hindi"),
            ("Tamil (தமிழ்)",                   "tamil"),
            ("Telugu (తెలుగు)",                 "telugu"),
            ("Marathi (मराठी)",                 "marathi"),
            ("Bengali (বাংলা)",                  "bengali"),
            ("Punjabi (ਪੰਜਾਬੀ)",                "punjabi"),
            ("Spanish (Español)",               "spanish"),
            ("French (Français)",               "french"),
            ("German (Deutsch)",                "german"),
            ("Japanese (日本語)",                "japanese"),
            ("Chinese (中文)",                   "chinese"),
            ("Arabic (العربية)",                 "arabic"),
        ]
        cb = self._styled_combo([lbl for lbl, _c in self._language_options])
        try:
            current_code = (os.environ.get("SHELL_LANGUAGE", "") or "").strip().lower()
            if not current_code:
                current_code = "hinglish"
            for i, (_lbl, code) in enumerate(self._language_options):
                if code == current_code:
                    cb.setCurrentIndex(i)
                    break
        except Exception:
            pass
        cb.currentIndexChanged.connect(self._on_language_changed)
        self._lang_combo = cb
        lay.addWidget(cb)

        self._lang_status = self._Muted("")
        lay.addWidget(self._lang_status)
        col.addWidget(card)

    # ==================================================================
    # API Keys page
    # ==================================================================

    def _build_apikeys_page(self, col: QVBoxLayout) -> None:
        DC, DS, DR = self._DC, self._DS, self._DR
        self._build_telegram_remote_card(col)

        card, lay = self._make_setting_card(
            "Provider API keys",
            "Manage credentials for each LLM provider. Keys are written to .env via the hub.",
        )

        top = QHBoxLayout(); top.setSpacing(DS.sm); top.addStretch(1)
        self._refresh_keys_btn = self._SecondaryButton("Refresh")
        self._refresh_keys_btn.clicked.connect(self._build_provider_list)
        top.addWidget(self._refresh_keys_btn)
        self._add_provider_btn = self._SecondaryButton("+  Add / Update Key")
        self._add_provider_btn.clicked.connect(self._toggle_add_provider_form)
        top.addWidget(self._add_provider_btn)
        wrap = QWidget(); wrap.setStyleSheet("background:transparent;border:none;")
        wrap.setLayout(top); lay.addWidget(wrap)

        # Inline add-provider form (collapsed by default).
        self._add_prov_form = QFrame()
        self._add_prov_form.setVisible(False)
        self._add_prov_form.setStyleSheet(
            f"QFrame {{ background:{DC.surface_2}; "
            f"  border:1px solid {DC.border_strong}; "
            f"  border-radius:{DR.md}px; padding:{DS.md}px; }}"
        )
        af = QVBoxLayout(self._add_prov_form); af.setSpacing(DS.sm)
        af.addWidget(self._Muted("ADD OR UPDATE API KEY"))

        self._prov_name_input = self._Input(placeholder="Provider or env name (e.g. OpenAI, Gemini, OPENAI_API_KEY)")
        self._prov_key_input = self._Input(placeholder="API key value")
        self._prov_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        af.addWidget(self._prov_name_input)
        af.addWidget(self._prov_key_input)

        af_btns = QHBoxLayout(); af_btns.setSpacing(DS.sm)
        save_btn = self._PrimaryButton("Save")
        save_btn.clicked.connect(self._save_new_provider)
        cancel_btn = self._GhostButton("Cancel")
        cancel_btn.clicked.connect(lambda: self._add_prov_form.setVisible(False))
        af_btns.addWidget(save_btn); af_btns.addWidget(cancel_btn); af_btns.addStretch(1)
        af_wrap = QWidget(); af_wrap.setStyleSheet("background:transparent;border:none;")
        af_wrap.setLayout(af_btns); af.addWidget(af_wrap)

        lay.addWidget(self._add_prov_form)

        # Dynamic provider list.
        self._providers_container = QVBoxLayout()
        self._providers_container.setSpacing(DS.sm)
        prov_wrap = QWidget(); prov_wrap.setStyleSheet("background:transparent;border:none;")
        prov_wrap.setLayout(self._providers_container)
        lay.addWidget(prov_wrap)

        try:
            self._build_provider_list()
        except Exception as _e:
            logger.debug("initial provider list build failed: %s", _e)

        col.addWidget(card)

    def _build_telegram_remote_card(self, col: QVBoxLayout) -> None:
        DS = self._DS
        card, lay = self._make_setting_card(
            "Telegram Remote Control",
            "Add a bot token, allow your phone chat ID, then control Shell from Telegram with guarded PC actions.",
        )

        self._telegram_token_input = self._Input(
            placeholder="Telegram bot token from @BotFather (saved hidden)"
        )
        self._telegram_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(self._telegram_token_input)

        current_ids = str(
            self._read_setting(
                "telegram_allowed_chat_ids",
                os.environ.get("SHELL_TELEGRAM_ALLOWED_CHAT_IDS", ""),
            )
            or ""
        )
        self._telegram_chat_ids_input = self._Input(
            placeholder="Allowed chat IDs, comma separated (send /start to bot to see ID)"
        )
        self._telegram_chat_ids_input.setText(current_ids)
        lay.addWidget(self._telegram_chat_ids_input)

        remote_on = bool(self._read_setting("telegram_remote_control_enabled", False))
        row, self._telegram_remote_switch = self._toggle_row(
            "Enable Telegram PC control for allowed chat IDs",
            on=remote_on,
            on_change=lambda v: self._save_toggle("telegram_remote_control_enabled", bool(v)),
        )
        lay.addWidget(row)

        auto_start_on = bool(self._read_setting("telegram_auto_start", False))
        row, self._telegram_auto_start_switch = self._toggle_row(
            "Start Telegram bot automatically with Shell",
            on=auto_start_on,
            on_change=lambda v: self._save_toggle("telegram_auto_start", bool(v)),
        )
        lay.addWidget(row)

        terminal_on = bool(self._read_setting("telegram_allow_terminal", False))
        row, self._telegram_terminal_switch = self._toggle_row(
            "Allow Telegram terminal commands (dangerous)",
            on=terminal_on,
            on_change=lambda v: self._save_toggle("telegram_allow_terminal", bool(v)),
        )
        lay.addWidget(row)

        self._telegram_status = self._Muted("Token value is never displayed after saving.")
        lay.addWidget(self._telegram_status)

        btns = QHBoxLayout()
        btns.setSpacing(DS.sm)
        save_btn = self._PrimaryButton("Save Telegram")
        save_btn.clicked.connect(self._save_telegram_remote_settings)
        status_btn = self._SecondaryButton("Status")
        status_btn.clicked.connect(lambda: self._run_telegram_tool("shell_telegram:telegram_bot_status"))
        start_btn = self._SecondaryButton("Start Bot")
        start_btn.clicked.connect(lambda: self._run_telegram_tool("shell_telegram:start_telegram_bot"))
        stop_btn = self._GhostButton("Stop Bot")
        stop_btn.clicked.connect(lambda: self._run_telegram_tool("shell_telegram:stop_telegram_bot"))
        for btn in (save_btn, status_btn, start_btn, stop_btn):
            btns.addWidget(btn)
        btns.addStretch(1)
        btn_wrap = QWidget()
        btn_wrap.setStyleSheet("background:transparent;border:none;")
        btn_wrap.setLayout(btns)
        lay.addWidget(btn_wrap)

        col.addWidget(card)

    def _telegram_switch_on(self, name: str) -> bool:
        sw = getattr(self, name, None)
        return bool(getattr(sw, "_on", False))

    def _save_telegram_remote_settings(self):
        token = self._telegram_token_input.text().strip()
        chat_ids = self._telegram_chat_ids_input.text().strip()
        remote_on = self._telegram_switch_on("_telegram_remote_switch")
        auto_start_on = self._telegram_switch_on("_telegram_auto_start_switch")
        terminal_on = self._telegram_switch_on("_telegram_terminal_switch")

        if token:
            result = self._api_key_backend_request(
                "POST",
                body={"key": "TELEGRAM_BOT_TOKEN", "value": token},
            )
            if not result.get("ok"):
                self._telegram_status.setText(
                    f"Token save failed: {result.get('error') or result.get('message')}"
                )
                return
            os.environ["TELEGRAM_BOT_TOKEN"] = token
            self._telegram_token_input.clear()

        result = self._settings_backend_request(
            "POST",
            {"settings": {
                "telegram_allowed_chat_ids": chat_ids,
                "telegram_remote_control_enabled": remote_on,
                "telegram_auto_start": auto_start_on,
                "telegram_allow_terminal": terminal_on,
            }},
        )
        if not result.get("ok"):
            self._telegram_status.setText(
                f"Config save failed: {result.get('error') or result.get('message')}"
            )
            return

        self._telegram_status.setText(
            "Telegram settings saved. Start the bot, send /start from your phone, then use guarded commands."
        )
        self._build_provider_list()

    def _run_telegram_tool(self, tool_id: str):
        self._telegram_status.setText("Running Telegram action...")
        item = {"id": tool_id, "kind": "tool"}
        worker = BackendToolRunWorker(item, {}, self)
        worker.run_ready.connect(self._on_telegram_tool_ready)
        worker.run_error.connect(lambda e: self._telegram_status.setText(f"Telegram action failed: {e}"))
        self._telegram_worker = worker
        worker.start()

    def _on_telegram_tool_ready(self, result):
        try:
            if isinstance(result, dict):
                if result.get("status") == "success":
                    text = str(result.get("result", "Done"))
                else:
                    text = str(result.get("message") or result.get("error") or result)
            else:
                text = str(result)
            self._telegram_status.setText(text[:700])
        except Exception as exc:
            self._telegram_status.setText(f"Telegram action parse failed: {exc}")

    # ==================================================================
    # Model & Brain page
    # ==================================================================

    def _build_model_page(self, col: QVBoxLayout) -> None:
        # Default brain mode.
        card, lay = self._make_setting_card(
            "Default brain mode",
            "FAST optimises for low latency, SMART for quality, CODER for technical tasks.",
        )
        cb = self._styled_combo(["FAST", "SMART", "CODER"])
        current = str(self._read_setting("brain_mode", "SMART")).upper()
        if cb.findText(current) >= 0:
            cb.setCurrentText(current)
        cb.currentTextChanged.connect(
            lambda v: self._save_toggle("brain_mode", v)
        )
        lay.addWidget(cb)
        col.addWidget(card)

        # Max output tokens.
        card, lay = self._make_setting_card(
            "Max output tokens",
            "Upper bound on tokens generated per response. Higher uses more credits.",
        )
        max_tok = int(self._read_setting("max_tokens", 2048))
        slider = self._styled_slider(max_tok, 256, 8192)
        tok_lbl = self._Muted(f"{max_tok} tokens")
        slider.valueChanged.connect(
            lambda v: (tok_lbl.setText(f"{int(v)} tokens"),
                       self._save_toggle("max_tokens", int(v)))
        )
        lay.addWidget(slider); lay.addWidget(tok_lbl)
        col.addWidget(card)

        # Temperature (stored 0-100 to keep _save_toggle JSON-safe).
        card, lay = self._make_setting_card(
            "Temperature",
            "0.0 = deterministic, 1.0 = creative. Most assistants sit around 0.7.",
        )
        temp_pct = int(self._read_setting("temperature_pct", 70))
        slider = self._styled_slider(temp_pct, 0, 100)
        temp_lbl = self._Muted(f"{temp_pct/100:.2f}")
        slider.valueChanged.connect(
            lambda v: (temp_lbl.setText(f"{int(v)/100:.2f}"),
                       self._save_toggle("temperature_pct", int(v)))
        )
        lay.addWidget(slider); lay.addWidget(temp_lbl)
        col.addWidget(card)

    # ==================================================================
    # Shortcuts page
    # ==================================================================

    def _build_shortcuts_page(self, col: QVBoxLayout) -> None:
        # Global hotkey toggles.
        card, lay = self._make_setting_card(
            "Global hotkeys",
            "Enable system-wide shortcuts. Bindings are read-only here; rebind via your OS keyboard panel.",
        )
        for cfg_key, default_label, default_on in [
            ("hotkey_show",    "Ctrl+Alt+S — show / hide Shell", True),
            ("hotkey_palette", "Ctrl+K — command palette",        True),
            ("hotkey_voice",   "Ctrl+Alt+V — push-to-talk voice", False),
        ]:
            row_on = bool(self._read_setting(cfg_key, default_on))
            row, _sw = self._toggle_row(
                default_label, on=row_on,
                on_change=lambda v, k=cfg_key: self._save_toggle(k, bool(v)),
            )
            lay.addWidget(row)
        col.addWidget(card)

        # Per-shortcut customisation (text only).
        card, lay = self._make_setting_card(
            "Custom shortcut text",
            "Display label for each shortcut. Useful when you have remapped keys at the OS level.",
        )
        for cfg_key, placeholder in [
            ("shortcut_label_show",    "Ctrl+Alt+S"),
            ("shortcut_label_palette", "Ctrl+K"),
            ("shortcut_label_voice",   "Ctrl+Alt+V"),
        ]:
            inp = self._Input(placeholder=placeholder)
            current = str(self._read_setting(cfg_key, ""))
            if current:
                inp.setText(current)
            inp.editingFinished.connect(
                lambda i=inp, k=cfg_key: self._save_toggle(k, i.text())
            )
            lay.addWidget(inp)
        col.addWidget(card)

    # ==================================================================
    # System page
    # ==================================================================

    def _build_system_page(self, col: QVBoxLayout) -> None:
        # Python interpreter path (port).
        card, lay = self._make_setting_card(
            "Python interpreter",
            "Path to the Python the agent uses for tool execution.",
        )
        py_inp = self._Input(placeholder=sys.executable)
        py_inp.setText(str(self._read_setting("python_path", sys.executable)))
        py_inp.editingFinished.connect(
            lambda: self._save_toggle("python_path", py_inp.text())
        )
        lay.addWidget(py_inp)
        col.addWidget(card)

        # Workspace folder.
        card, lay = self._make_setting_card(
            "Workspace folder",
            "Where Shell stores generated files, reports, and session artefacts.",
        )
        default_ws = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "shell_workspace",
        )
        ws_inp = self._Input(placeholder=default_ws)
        ws_inp.setText(str(self._read_setting("workspace_path", default_ws)))
        ws_inp.editingFinished.connect(
            lambda: self._save_toggle("workspace_path", ws_inp.text())
        )
        lay.addWidget(ws_inp)
        col.addWidget(card)

        # Log level.
        card, lay = self._make_setting_card(
            "Log level",
            "Verbosity of agent and hub logs written to disk.",
        )
        cb = self._styled_combo(["DEBUG", "INFO", "WARNING", "ERROR"])
        current = str(self._read_setting("log_level", "INFO")).upper()
        if cb.findText(current) >= 0:
            cb.setCurrentText(current)
        cb.currentTextChanged.connect(
            lambda v: self._save_toggle("log_level", v)
        )
        lay.addWidget(cb)
        col.addWidget(card)

        # Auto-venv / GPU toggles (port).
        card, lay = self._make_setting_card(
            "Runtime",
            "Environment activation and acceleration toggles.",
        )
        avenv_on = bool(self._read_setting("auto_venv", True))
        row, sw_a = self._toggle_row(
            "Auto-activate virtualenv on launch", on=avenv_on,
            on_change=lambda v: self._save_toggle("auto_venv", bool(v)),
        )
        self._toggle_auto_venv = sw_a
        lay.addWidget(row)

        gpu_on = bool(self._read_setting("gpu_accel", False))
        row, sw_g = self._toggle_row(
            "GPU acceleration (where supported)", on=gpu_on,
            on_change=lambda v: self._save_toggle("gpu_accel", bool(v)),
        )
        self._toggle_gpu_accel = sw_g
        lay.addWidget(row)
        col.addWidget(card)

    # ==================================================================
    # Help Center page
    # ==================================================================

    def _project_root(self) -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _open_project_file(self, rel_path: str) -> None:
        try:
            path = os.path.join(self._project_root(), rel_path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception as exc:
            logger.debug("open project file failed: %s", exc)

    def _repair_launcher_path(self) -> str:
        root = self._project_root()
        if sys.platform.startswith("win"):
            return os.path.join(root, "Repair_ShellAI.bat")
        if sys.platform == "darwin":
            return os.path.join(root, "repair_shellai.command")
        return os.path.join(root, "repair_shellai.sh")

    def _build_help_page(self, col: QVBoxLayout) -> None:
        card, lay = self._make_setting_card(
            "Install health",
            "Check setup, dependencies, voice runtime, browser runtime, and repair status.",
        )
        status = self._Muted("Health check not run yet.")
        lay.addWidget(status)
        btns = QHBoxLayout()
        btns.setSpacing(self._DS.sm)
        run_health = self._SecondaryButton("Run Health Check")
        run_health.clicked.connect(lambda: self._refresh_install_health(status))
        btns.addWidget(run_health)
        open_report = self._SecondaryButton("Open Health Report")
        open_report.clicked.connect(lambda: self._open_project_file(".shell_runtime/install_health.json"))
        btns.addWidget(open_report)
        repair = self._PrimaryButton("Repair Shell AI")
        repair.clicked.connect(lambda: self._open_project_file(os.path.relpath(self._repair_launcher_path(), self._project_root())))
        btns.addWidget(repair)
        lay.addLayout(btns)
        col.addWidget(card)

        card, lay = self._make_setting_card(
            "Guides",
            "Open local setup, troubleshooting, realtime latency, and install documentation.",
        )
        for label, rel in [
            ("Installer Guide", "installer/README.md"),
            ("Realtime Audit", "docs/LOW_LATENCY_PERFORMANCE_AUDIT.md"),
            ("Current System Audit", "docs/CURRENT_SYSTEM_E2E_AUDIT.md"),
            ("README", "README.md"),
        ]:
            btn = self._SecondaryButton(label)
            btn.clicked.connect(lambda _checked=False, p=rel: self._open_project_file(p))
            lay.addWidget(btn)
        col.addWidget(card)

        card, lay = self._make_setting_card(
            "Runtime logs",
            "Open local logs when startup, voice, hub, or UI launch fails.",
        )
        for label, rel in [
            ("Open Runtime Logs Folder", ".shell_runtime/logs"),
            ("Open Hub Log", ".shell_runtime/logs/hub.log"),
            ("Open UI Log", ".shell_runtime/logs/ui.log"),
        ]:
            btn = self._SecondaryButton(label)
            btn.clicked.connect(lambda _checked=False, p=rel: self._open_project_file(p))
            lay.addWidget(btn)
        col.addWidget(card)

    def _refresh_install_health(self, label: QLabel) -> None:
        try:
            from installer.bootstrap import health_report

            report = health_report()
            summary = report.get("summary") or {}
            warnings = summary.get("warnings") or []
            errors = summary.get("errors") or []
            if errors:
                label.setText(f"Needs repair: {', '.join(errors[:6])}")
            elif warnings:
                label.setText(f"Launch ready with warnings: {', '.join(warnings[:6])}")
            else:
                label.setText("Ready. All core checks passed.")
        except Exception as exc:
            label.setText(f"Health check failed: {exc}")

    # ==================================================================
    # Privacy & Safety page
    # ==================================================================

    def _build_privacy_page(self, col: QVBoxLayout) -> None:
        # Code-write permission.
        card, lay = self._make_setting_card(
            "Code-write authority",
            "When off, Shell may read but not modify files. Required for self-editing tools.",
        )
        allow_write = bool(self._read_setting("shell_allow_code_write", False))
        def _on_write_toggle(v):
            self._save_toggle("shell_allow_code_write", bool(v))
            os.environ["SHELL_ALLOW_CODE_WRITE"] = "1" if v else "0"
        row, _sw = self._toggle_row(
            "Allow Shell to write & edit files", on=allow_write,
            on_change=_on_write_toggle,
        )
        lay.addWidget(row)
        col.addWidget(card)

        # Prompt-injection level.
        card, lay = self._make_setting_card(
            "Prompt-injection defence",
            "Off = trust input as-is. Wrap = sanitise suspect text. Block = refuse risky payloads.",
        )
        cb = self._styled_combo(["off", "wrap", "block"])
        current = str(self._read_setting("prompt_injection_level", "wrap")).lower()
        if cb.findText(current) >= 0:
            cb.setCurrentText(current)
        cb.currentTextChanged.connect(
            lambda v: self._save_toggle("prompt_injection_level", v)
        )
        lay.addWidget(cb)
        col.addWidget(card)

        # Telemetry.
        card, lay = self._make_setting_card(
            "Anonymous telemetry",
            "Sends crash counts and feature usage to help us prioritise fixes. No prompts or chat content.",
        )
        tele_on = bool(self._read_setting("telemetry_enabled", False))
        row, _sw = self._toggle_row(
            "Send anonymous diagnostics", on=tele_on,
            on_change=lambda v: self._save_toggle("telemetry_enabled", bool(v)),
        )
        lay.addWidget(row)
        col.addWidget(card)

    # === LEGACY __init__ END — methods below are unchanged ============
    # The methods below were preserved from the original implementation
    # so existing callers (`_save_toggle`, `_on_commit`, `_save_new_provider`,
    # `_on_language_changed`, `on_api_key_update`, `_on_sensitivity_change`,
    # `_switch_theme`, `_toggle_add_provider_form`, `_build_provider_list`)
    # continue to work without changes.
    def _save_toggle(self, name, is_on):
        """Persist toggle state to settings file."""
        import json
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shell_settings.json")
        cfg = {}
        try:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    cfg = json.load(f)
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        key = name.lower().replace("-", "_").replace(" ", "_")
        cfg[key] = is_on
        for alias in {
            "tts_enabled": ("voice_output",),
            "voice_output": ("tts_enabled",),
            "speech_rate": ("tts_rate",),
            "speech_volume": ("tts_volume",),
            "voice_persona": ("tts_voice",),
        }.get(key, ()):
            cfg[alias] = is_on
        try:
            with open(cfg_path, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)

        self._queue_backend_setting(key, is_on)
        for alias in {
            "tts_enabled": ("voice_output",),
            "voice_output": ("tts_enabled",),
            "speech_rate": ("tts_rate",),
            "speech_volume": ("tts_volume",),
            "voice_persona": ("tts_voice",),
        }.get(key, ()):
            self._queue_backend_setting(alias, is_on)

    def _settings_backend_request(self, method: str, payload: dict | None = None) -> dict:
        import json as _json
        import urllib.request as _ur

        body = None if payload is None else _json.dumps(payload).encode("utf-8")
        headers = _hub_auth_headers({"Content-Type": "application/json"})
        last_error = None
        for base in _hub_base_url_candidates():
            try:
                req = _ur.Request(base.rstrip("/") + "/settings", data=body, headers=headers, method=method)
                with _ur.urlopen(req, timeout=0.5) as resp:
                    result = _json.loads(resp.read().decode("utf-8") or "{}")
                result["_source"] = "hub"
                return result
            except Exception as exc:
                last_error = exc
        try:
            from shell_settings_manager import get_settings, set_settings
            if method == "GET":
                return {"ok": True, "settings": get_settings(), "_source": "local", "_hub_error": str(last_error)}
            if method == "POST":
                ok, msg, applied = set_settings((payload or {}).get("settings", payload or {}))
                return {"ok": ok, "message": msg, "settings": applied, "_source": "local", "_hub_error": str(last_error)}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "_source": "unavailable", "_hub_error": str(last_error)}
        return {"ok": False, "error": "unsupported method", "_source": "unavailable"}

    def _queue_backend_setting(self, key: str, value):
        try:
            self._pending_settings_sync[str(key)] = value
            self._settings_sync_timer.start()
        except Exception as _e:
            logger.debug("queue backend setting failed: %s", _e)

    def _flush_settings_sync(self):
        pending = dict(getattr(self, "_pending_settings_sync", {}) or {})
        if not pending:
            return
        self._pending_settings_sync.clear()
        result = self._settings_backend_request("POST", {"settings": pending})
        if not result.get("ok"):
            logger.debug("backend settings sync failed: %s", result.get("error") or result.get("message"))
    def _on_sensitivity_change(self, val):
        """Update voice sensitivity label dynamically."""
        self._voice_sensitivity = val
        if val < 30:
            mode = "PASSIVE"
            self._sens_passive.setStyleSheet(f"color:{C_PRIMARY}; font-family:'{_FONT}'; font-size:10px; font-weight:700; letter-spacing:3px; border:none; background:transparent;")
            self._sens_active.setStyleSheet(f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:10px; font-weight:600; letter-spacing:3px; border:none; background:transparent;")
            self._sens_aggressive.setStyleSheet(f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:10px; font-weight:600; letter-spacing:3px; border:none; background:transparent;")
        elif val > 75:
            mode = "AGGRESSIVE"
            self._sens_passive.setStyleSheet(f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:10px; font-weight:600; letter-spacing:3px; border:none; background:transparent;")
            self._sens_active.setStyleSheet(f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:10px; font-weight:600; letter-spacing:3px; border:none; background:transparent;")
            self._sens_aggressive.setStyleSheet(f"color:{C_ERROR}; font-family:'{_FONT}'; font-size:10px; font-weight:700; letter-spacing:3px; border:none; background:transparent;")
        else:
            mode = "REACTIVE"
            self._sens_passive.setStyleSheet(f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:10px; font-weight:600; letter-spacing:3px; border:none; background:transparent;")
            self._sens_active.setStyleSheet(f"color:{C_PRIMARY}; font-family:'{_FONT}'; font-size:10px; font-weight:700; letter-spacing:3px; border:none; background:transparent;")
            self._sens_aggressive.setStyleSheet(f"color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:10px; font-weight:600; letter-spacing:3px; border:none; background:transparent;")
        self._sens_active.setText(f"{mode} ({val}%)")

    def _switch_theme(self, theme_name):
        """Switch theme via ThemeEngine."""
        te = ThemeEngine.get()
        if te.active_name == theme_name:
            return
        te.switch(theme_name)

    def _on_commit(self):
        """Save all settings to config file (merge with existing to preserve other keys)."""
        import json
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shell_settings.json")
        cfg = {}
        try:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    cfg = json.load(f)
        except Exception:
            cfg = {}
        try:
            theme_name = ThemeEngine.get().active_name
        except Exception:
            theme_name = cfg.get("theme", "DARK")
        cfg.update({
            "voice_sensitivity": self._voice_sensitivity,
            "theme": theme_name,
            "auto_venv": self._toggle_auto_venv._on if self._toggle_auto_venv else True,
            "gpu_accel": self._toggle_gpu_accel._on if self._toggle_gpu_accel else False,
        })
        try:
            with open(cfg_path, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        self._settings_backend_request("POST", {"settings": cfg})
        # Mac-style confirmation toast.
        try:
            self._show_commit_toast("Settings committed")
        except Exception as _e:
            logger.debug("commit toast failed: %s", _e)
    def _on_discard(self):
        """Reload saved settings and restore theme."""
        import json
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shell_settings.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    cfg = json.load(f)
                sens = cfg.get("voice_sensitivity", 65)
                # Voice slider is built lazily inside the Voice page —
                # only push the value back if the user has visited that
                # page at least once.
                if getattr(self, "_voice_slider", None) is not None:
                    try: self._voice_slider.setValue(int(sens))
                    except Exception: pass
                # Restore toggle states
                if getattr(self, '_toggle_auto_venv', None) is not None:
                    self._toggle_auto_venv.set_on(cfg.get("auto_venv", True))
                if getattr(self, '_toggle_gpu_accel', None) is not None:
                    self._toggle_gpu_accel.set_on(cfg.get("gpu_accel", False))
                # Restore theme
                saved_theme = cfg.get("theme", "DARK")
                te = ThemeEngine.get()
                if te.active_name != saved_theme:
                    te.switch(saved_theme)
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
    def _toggle_add_provider_form(self):
        """Show/hide the add provider inline form."""
        vis = not self._add_prov_form.isVisible()
        self._add_prov_form.setVisible(vis)
        if vis:
            self._prov_name_input.clear()
            self._prov_key_input.clear()
            self._prov_name_input.setFocus()

    def _api_key_env_name(self, name: str) -> str:
        """Map friendly provider labels to allowlisted environment keys."""
        normalised = str(name or "").strip().upper().replace("-", "_").replace(" ", "_")
        name_to_env = {
            "OPENAI":        "OPENAI_API_KEY",
            "GEMINI":        "GOOGLE_API_KEY",
            "GOOGLE":        "GOOGLE_API_KEY",
            "GROQ":          "GROQ_API_KEY",
            "MISTRAL":       "MISTRAL_API_KEY",
            "PERPLEXITY":    "PERPLEXITY_API_KEY",
            "SAMBANOVA":     "SAMBANOVA_API_KEY",
            "DEEPSEEK":      "DEEPSEEK_API_KEY",
            "BLACKBOX":      "BLACKBOX_API_KEY",
            "OPENROUTER":    "OPENROUTER_API_KEY",
            "HUGGINGFACE":   "HF_API_KEY",
            "HF":            "HF_API_KEY",
            "BYTEZ":         "BYTEZ_API_KEY",
            "OPENWEATHER":   "OPENWEATHER_API_KEY",
            "NEWSDATA":      "NEWS_API_KEY",
            "NEWS":          "NEWS_API_KEY",
            "ALPHAVANTAGE":  "ALPHA_VANTAGE_API_KEY",
            "TELEGRAM":      "TELEGRAM_BOT_TOKEN",
        }
        if normalised.endswith("_API_KEY") or normalised in {
            "LIVEKIT_URL", "LIVEKIT_API_SECRET", "SEARCH_ENGINE_ID",
            "TELEGRAM_BOT_TOKEN",
        }:
            return normalised
        return name_to_env.get(normalised, normalised + "_API_KEY")

    def _api_key_backend_request(self, method: str, path: str = "", body: dict | None = None) -> dict:
        """Call hub API-key endpoints; fallback to in-process manager if hub is down."""
        import json as _json
        import urllib.parse as _up
        import urllib.request as _ur

        body_bytes = None
        headers = _hub_auth_headers({"Content-Type": "application/json"})
        if body is not None:
            body_bytes = _json.dumps(body).encode("utf-8")

        last_error = None
        for base in _hub_base_url_candidates():
            url = base.rstrip("/") + "/api-keys" + path
            try:
                req = _ur.Request(url, data=body_bytes, headers=headers, method=method)
                with _ur.urlopen(req, timeout=3) as resp:
                    data = _json.loads(resp.read().decode("utf-8") or "{}")
                data["_source"] = "hub"
                return data
            except Exception as exc:
                last_error = exc

        # Fallback writes the same project .env and live process env, but
        # marks the source so the UI can make clear the hub was offline.
        try:
            from shell_api_manager import list_api_keys, set_api_key, delete_api_key
            if method == "GET":
                return {"ok": True, "keys": list_api_keys(), "_source": "local", "_hub_error": str(last_error)}
            if method == "POST":
                ok, msg = set_api_key(str((body or {}).get("key", "")), str((body or {}).get("value", "")))
                return {"ok": ok, "message": msg, "_source": "local", "_hub_error": str(last_error)}
            if method == "DELETE":
                key = _up.unquote(path.strip("/"))
                ok, msg = delete_api_key(key)
                return {"ok": ok, "message": msg, "_source": "local", "_hub_error": str(last_error)}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "_source": "unavailable", "_hub_error": str(last_error)}
        return {"ok": False, "error": "unsupported method", "_source": "unavailable"}

    def _refresh_brain_providers(self):
        try:
            reload_brain_providers()
        except Exception as _e:
            logger.debug("brain provider reload failed: %s", _e)

    def _save_new_provider(self):
        """Save or update an API key through the backend API manager."""
        name = self._prov_name_input.text().strip()
        key_value = self._prov_key_input.text().strip()
        if not name or not key_value:
            self._show_commit_toast("Provider name and key are required")
            return

        env_name = self._api_key_env_name(name)
        result = self._api_key_backend_request(
            "POST",
            body={"key": env_name, "value": key_value},
        )
        if result.get("ok"):
            os.environ[env_name] = key_value
            self._refresh_brain_providers()
            self._prov_name_input.clear()
            self._prov_key_input.clear()
            self._add_prov_form.setVisible(False)
            source = "backend" if result.get("_source") == "hub" else "local env manager"
            self._show_commit_toast(f"{env_name} saved via {source}")
        else:
            self._show_commit_toast(f"Save failed: {result.get('error') or result.get('message')}")
        self._build_provider_list()

    def _remove_api_key(self, env_name: str):
        """Remove an API key through the backend API manager."""
        import urllib.parse as _up
        result = self._api_key_backend_request("DELETE", "/" + _up.quote(str(env_name), safe=""))
        if result.get("ok"):
            os.environ.pop(str(env_name), None)
            self._refresh_brain_providers()
            source = "backend" if result.get("_source") == "hub" else "local env manager"
            self._show_commit_toast(f"{env_name} removed via {source}")
        else:
            self._show_commit_toast(f"Remove failed: {result.get('error') or result.get('message')}")
        self._build_provider_list()

    def _edit_api_key(self, env_name: str):
        self._add_prov_form.setVisible(True)
        self._prov_name_input.setText(str(env_name))
        self._prov_key_input.clear()
        self._prov_key_input.setFocus()

    # ── Reply-language picker ─────────────────────────────────────
    def _on_language_changed(self, idx: int):
        """User picked a new reply language. Persist through /settings and
        update os.environ so the next chat turn uses it immediately.

        Backend agent reads `SHELL_LANGUAGE` on every text turn and
        rebuilds the persona prompt accordingly — no agent restart
        needed.
        """
        try:
            label, code = self._language_options[idx]
        except (IndexError, AttributeError):
            return

        # Optimistic local state.
        os.environ["SHELL_LANGUAGE"] = code
        try:
            self._lang_status.setText(f"Saving... ({label})")
        except Exception:
            pass

        result = self._settings_backend_request(
            "POST",
            {"settings": {"language": code, "shell_language": code}},
        )
        if result.get("ok"):
            self._lang_status.setText(f"Saved - Shell ab {label} mein reply karegi.")
        else:
            self._lang_status.setText(
                f"Save failed: {result.get('error') or result.get('message') or 'unknown'} "
                "(env updated locally only)."
            )

    # ── Phase-22 — live API-key update hook ────────────────────────
    def on_api_key_update(self, data):
        """Hub broadcast: refresh the provider chip list so the chip for
        the just-set key flips to 'ACTIVE' without needing a reload."""
        try:
            self._build_provider_list()
        except Exception as _e:
            logger.debug("on_api_key_update rebuild failed: %s", _e)

    def _build_provider_list(self):
        """Build API-key rows from the backend API-key catalog."""
        # Clear existing
        while self._providers_container.count():
            item = self._providers_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        result = self._api_key_backend_request("GET")
        keys = list(result.get("keys") or []) if result.get("ok") else []
        if not keys:
            self._providers_container.addWidget(
                self._Body(f"API key catalog unavailable: {result.get('error') or result.get('message')}", muted=True)
            )
            return

        source = result.get("_source", "hub")
        status_text = "Backend API manager connected" if source == "hub" else "Hub offline; using local env manager"
        self._providers_container.addWidget(self._Muted(status_text))

        try:
            active_provider_keys = {
                f"{name.upper()}_API_KEY"
                for name in brain_provider_names(load=False)
            }
            if "gemini" in brain_provider_names(load=False):
                active_provider_keys.add("GOOGLE_API_KEY")
        except Exception:
            active_provider_keys = set()

        DC, DR, DT = self._DC, self._DR, self._DT
        colors = [DC.accent, DC.success, DC.warning, DC.text_muted, DC.accent_hover]
        section_order = {
            "Gemini (critical)": 0,
            "Providers": 1,
            "LiveKit (critical)": 2,
            "Image AI": 3,
            "Search & info": 4,
            "Communications": 5,
            "Email": 6,
        }
        keys.sort(key=lambda row: (
            section_order.get(str(row.get("section", "")), 50),
            str(row.get("section", "")),
            str(row.get("name", "")),
        ))

        for idx, row in enumerate(keys):
            env_name = str(row.get("name", ""))
            is_set = bool(row.get("set"))
            required = bool(row.get("required"))
            section = str(row.get("section") or "Other")
            description = str(row.get("description") or "")
            color = colors[idx % len(colors)]
            live = env_name in active_provider_keys

            prov_frame = QFrame()
            prov_frame.setStyleSheet(f"""
                background:{DC.surface_2};
                border:1px solid {DC.border};
                border-top:1px solid {DC.glass_hi};
                border-radius:{DR.md}px; padding:10px 16px;
            """)
            pf_lay = QHBoxLayout(prov_frame)
            pf_lay.setContentsMargins(0, 0, 0, 0)
            pf_lay.setSpacing(14)

            # Icon square
            ic = QLabel()
            ic.setFixedSize(40, 40)
            c = QColor(color)
            ic.setStyleSheet(f"""
                background:rgba({c.red()},{c.green()},{c.blue()},0.10);
                border-radius:8px; border:none;
            """)
            ic.setText("✓" if is_set else "•")
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pf_lay.addWidget(ic)

            # Text
            txt_lay = QVBoxLayout()
            txt_lay.setSpacing(2)
            pf_name = QLabel(env_name)
            pf_name.setStyleSheet(f"""
                color:{DC.text}; font-family:'{DT.family}'; font-size:14px;
                font-weight:600; border:none; background:transparent;
            """)
            txt_lay.addWidget(pf_name)
            labels = [section]
            if required:
                labels.append("required")
            labels.append("set" if is_set else "not set")
            if live:
                labels.append("loaded")
            pf_sub = QLabel(" | ".join(labels) + (f" — {description}" if description else ""))
            pf_sub.setStyleSheet(f"""
                color:{DC.text_muted}; font-family:'{_MONO}'; font-size:10px;
                border:none; background:transparent;
            """)
            pf_sub.setWordWrap(True)
            txt_lay.addWidget(pf_sub)
            pf_lay.addLayout(txt_lay, 1)

            # Status dot (green = active, red = inactive)
            status_dot = QLabel()
            status_dot.setFixedSize(10, 10)
            dot_color = DC.success if is_set else DC.error
            status_dot.setStyleSheet(f"background:{dot_color}; border-radius:5px; border:none;")
            _glow_shadow(status_dot, dot_color, 6, 100)
            pf_lay.addWidget(status_dot)

            edit_btn = self._GhostButton("Set")
            edit_btn.clicked.connect(lambda _checked=False, k=env_name: self._edit_api_key(k))
            pf_lay.addWidget(edit_btn)

            remove_btn = self._GhostButton("Remove")
            remove_btn.setEnabled(is_set)
            remove_btn.clicked.connect(lambda _checked=False, k=env_name: self._remove_api_key(k))
            pf_lay.addWidget(remove_btn)

            self._providers_container.addWidget(prov_frame)


# =====================================================================
#  AmbientBG
# =====================================================================

class AmbientBG(QWidget):
    """Cyber-glass ambient — animated multi-radial wash + 24 floating
    particles with subtle glow halos. Token-driven so a theme change
    flows through without rewiring.

    Upgraded from the original 35-particle / 6-radial CPU burner:
      • 24 particles (down from 35), softer alphas
      • 4 token-based radials instead of 6 hard-coded gradients
      • 50ms tick (~20fps) — visibly alive without thrashing CPU
      • Warm purple counter-glow + gentle phase-offset shimmer
      • All colours pulled from `design_tokens.C` so themes flip live
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._phase = 0.0
        # 16 particles at 100 ms (10 fps). Matches the visual feel of the
        # original 24×50ms but pushes ~60% fewer frames — critical when
        # the user is on Remote Desktop where every paint round-trips
        # over the network and queues page-switch updates behind it.
        self._particles = []
        for _ in range(16):
            self._particles.append({
                "x": random.uniform(0, 1), "y": random.uniform(0, 1),
                "vx": random.uniform(-0.00030, 0.00030),
                "vy": random.uniform(-0.00022, 0.00022),
                "sz": random.uniform(0.7, 3.4),
                "alpha": random.uniform(0.04, 0.14),
            })
        self._t = QTimer(self)
        self._t.timeout.connect(self._tick)
        self._t.start(100)
        try:
            from shell_ui import design_tokens as _DT
            _DT.on_palette_change(self._on_palette_changed)
        except Exception:
            pass

    def _on_palette_changed(self):
        try:
            self.update()
        except Exception:
            pass

    def _tick(self):
        self._phase += 0.010
        for p in self._particles:
            p["x"] += p["vx"] + math.sin(self._phase + p["y"] * 3) * 0.00006
            p["y"] += p["vy"] + math.cos(self._phase + p["x"] * 3) * 0.00005
            if p["x"] < -0.05 or p["x"] > 1.05: p["vx"] *= -1
            if p["y"] < -0.05 or p["y"] > 1.05: p["vy"] *= -1
        self.update()

    # ---- Apple-glassy: pause animation when hidden / minimized -----------
    def hideEvent(self, e):
        try:
            self._t.stop()
        except Exception:
            pass
        super().hideEvent(e)

    def showEvent(self, e):
        try:
            if not self._t.isActive():
                self._t.start(50)
        except Exception:
            pass
        super().showEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        try:
            from shell_ui import design_tokens as DT
            base_hex = DT.C.bg
            accent_hex = DT.C.accent
        except Exception:
            base_hex = "#06080f"; accent_hex = "#00f0ff"

        # Solid base.
        p.fillRect(self.rect(), QColor(base_hex))
        p.setPen(Qt.PenStyle.NoPen)

        # Two breathing curves offset by π so they alternate softly.
        breath_a = 0.5 + 0.5 * math.sin(self._phase)
        breath_b = 0.5 + 0.5 * math.sin(self._phase + math.pi * 0.66)

        # Primary cyan wash — upper-right.
        ac = QColor(accent_hex)
        gr_main = max(w, h) * 0.95
        g1 = QRadialGradient(QPointF(w * 0.82, h * 0.10), gr_main)
        a1 = int(28 + 12 * breath_a)
        g1.setColorAt(0.00, QColor(ac.red(), ac.green(), ac.blue(), a1))
        g1.setColorAt(0.20, QColor(ac.red(), ac.green(), ac.blue(), int(a1 * 0.55)))
        g1.setColorAt(0.55, QColor(ac.red(), ac.green(), ac.blue(), int(a1 * 0.18)))
        g1.setColorAt(1.00, QColor(0, 0, 0, 0))
        p.setBrush(g1)
        p.drawEllipse(QRectF(w * 0.82 - gr_main, h * 0.10 - gr_main,
                             gr_main * 2, gr_main * 2))

        # Secondary tiny amber counter — lower-left, lower alpha,
        # alternates with primary.
        gr_sec = gr_main * 0.55
        g2 = QRadialGradient(QPointF(w * 0.08, h * 0.92), gr_sec)
        a2 = int(14 + 8 * breath_b)
        # Shift hue slightly warmer-amber for variety.
        g2.setColorAt(0.00, QColor(228, 156, 92, a2))
        g2.setColorAt(0.30, QColor(228, 156, 92, int(a2 * 0.5)))
        g2.setColorAt(0.65, QColor(228, 156, 92, int(a2 * 0.15)))
        g2.setColorAt(1.00, QColor(0, 0, 0, 0))
        p.setBrush(g2)
        p.drawEllipse(QRectF(w * 0.08 - gr_sec, h * 0.92 - gr_sec,
                             gr_sec * 2, gr_sec * 2))

        # A whisper of light catching the upper-left edge — adds glass
        # ambience near the brand block.
        gr_edge = gr_main * 0.30
        g3 = QRadialGradient(QPointF(w * 0.18, h * 0.04), gr_edge)
        g3.setColorAt(0.00, QColor(255, 240, 225, 14))
        g3.setColorAt(0.40, QColor(255, 240, 225, 6))
        g3.setColorAt(1.00, QColor(0, 0, 0, 0))
        p.setBrush(g3)
        p.drawEllipse(QRectF(w * 0.18 - gr_edge, h * 0.04 - gr_edge,
                             gr_edge * 2, gr_edge * 2))

        p.end()


# =====================================================================
#  GlassContentArea — Ambient BG + glassmorphism overlay
# =====================================================================

class GlassContentArea(QWidget):
    """Content area with animated ambient background for glassmorphism effect."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ambient = AmbientBG(self)
        self._ambient.lower()
        self.setStyleSheet("background:transparent; border:none;")

    def resizeEvent(self, e):
        self._ambient.setGeometry(self.rect())
        super().resizeEvent(e)


# =====================================================================
#  ToastNotification — Animated toast messages
# =====================================================================

class ToastNotification(QWidget):
    """Glassmorphism toast notification that slides in and auto-dismisses."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(360, 56)
        self.setStyleSheet("background:transparent; border:none;")
        self._toast_queue = []
        self._visible = False
        self._opacity = 0.0
        self._target_opacity = 0.0
        self._slide_y = -60
        self._target_y = 12

        # Use QGraphicsOpacityEffect for child widget opacity (setWindowOpacity only works on top-level)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setGeometry(0, 0, 360, 56)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(20, 20)
        self._icon_label.setGeometry(16, 18, 20, 20)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._dismiss)

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(16)

        self.hide()

    def show_toast(self, message, toast_type="info", duration=3000):
        """Show a toast notification. toast_type: info, success, error, warning"""
        # Queue toasts if one is already showing
        if self._visible:
            self._toast_queue.append((message, toast_type, duration))
            return

        colors = {
            "info": (C_PRIMARY, C_PRIMARY_BOLD),
            "success": (C_SUCCESS, C_SUCCESS),
            "error": (C_ERROR, C_ERROR),
            "warning": (C_WARNING, C_WARNING),
        }
        text_color, border_color = colors.get(toast_type, colors["info"])
        bc = QColor(border_color)

        self._label.setText(message)
        self._label.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:0.1,y2:1,
                stop:0 rgba(44,54,76,0.82), stop:0.06 rgba(32,42,62,0.76),
                stop:0.5 rgba(22,30,48,0.72), stop:1 rgba(16,22,38,0.68));
            border: 1px solid rgba({bc.red()},{bc.green()},{bc.blue()},0.35);
            border-top: 2px solid rgba({bc.red()},{bc.green()},{bc.blue()},0.55);
            border-left: 1px solid rgba({bc.red()},{bc.green()},{bc.blue()},0.25);
            border-radius: 16px;
            color: {text_color}; font-family: '{_FONT}'; font-size: 12px;
            font-weight: 600; letter-spacing: 1px;
            padding-left: 20px;
        """)
        _glow_shadow(self._label, border_color, 20, 60)

        self._target_opacity = 1.0
        self._slide_y = -60
        self._target_y = 12
        self._visible = True
        self.show()
        self.raise_()

        self._dismiss_timer.start(duration)

    def _dismiss(self):
        self._target_opacity = 0.0
        self._target_y = -60

    def _animate(self):
        if not self._visible and self._opacity < 0.01:
            return

        self._opacity += (self._target_opacity - self._opacity) * 0.15
        self._slide_y += (self._target_y - self._slide_y) * 0.15

        if self._opacity < 0.01 and self._target_opacity == 0.0:
            self._visible = False
            self.hide()
            # Process queued toasts
            if self._toast_queue:
                msg, ttype, dur = self._toast_queue.pop(0)
                QTimer.singleShot(200, lambda: self.show_toast(msg, ttype, dur))
            return

        # Position at top-right of parent
        if self.parent():
            pw = self.parent().width()
            self.move(pw - self.width() - 20, int(self._slide_y))

        self._opacity_effect.setOpacity(self._opacity)
        self.update()


# =====================================================================
#  Background-Activity Toasts
# =====================================================================

class _ToastCard(QFrame):
    """Single floating notification card.

    Shows a tool/research/thinking event in real time. Auto-fades and
    self-removes after a TTL. The ToastManager handles stacking.

    NOTE: Renamed from `ToastNotification` to `_ToastCard` so it doesn't
    shadow the QWidget-based `ToastNotification` defined above (which has
    the `show_toast(message, type, duration)` API used by `_on_voice_error`,
    AI-error toasts, theme-change toasts, etc.). Before the rename, the
    second class definition silently replaced the first one and every
    `self._toast.show_toast(...)` call would AttributeError on first use.
    """

    closed = pyqtSignal(object)

    # Status colours (left border + icon tint)
    COLOR_INFO    = "#4F8EF7"
    COLOR_RUNNING = "#FFB020"
    COLOR_OK      = "#22C55E"
    COLOR_ERROR   = "#EF4444"

    def __init__(self, parent, kind="info", title="", body="", ttl_ms=5000):
        super().__init__(parent)
        self._kind = kind
        self._ttl_ms = ttl_ms
        self._key = None  # set by manager when running events arrive
        self.setObjectName("toastCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(340)

        self._stripe_color = {
            "info": self.COLOR_INFO,
            "running": self.COLOR_RUNNING,
            "ok": self.COLOR_OK,
            "error": self.COLOR_ERROR,
        }.get(kind, self.COLOR_INFO)

        self.setStyleSheet(f"""
            QFrame#toastCard {{
                background-color: rgba(15, 20, 32, 235);
                border: 1px solid rgba(80, 100, 130, 110);
                border-left: 3px solid {self._stripe_color};
                border-radius: 8px;
            }}
            QLabel#toastTitle {{
                color: #E6EDF3;
                font-weight: 600;
                font-size: 12px;
                background: transparent;
                border: none;
            }}
            QLabel#toastBody {{
                color: #B0BAC9;
                font-size: 11px;
                background: transparent;
                border: none;
            }}
            QPushButton#toastClose {{
                color: #8895A8;
                background: transparent;
                border: none;
                font-size: 14px;
                font-weight: 700;
                padding: 0px;
            }}
            QPushButton#toastClose:hover {{
                color: #FFFFFF;
                background: rgba(255, 80, 80, 80);
                border-radius: 4px;
            }}
        """)

        # Layout: a horizontal row with text-stack on left, X button on right.
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 8, 8)
        lay.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self._title_lbl = QLabel(title or "Shell")
        self._title_lbl.setObjectName("toastTitle")
        self._title_lbl.setWordWrap(True)
        header.addWidget(self._title_lbl, 1)

        self._close_btn = QPushButton("×")
        self._close_btn.setObjectName("toastClose")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("Close")
        self._close_btn.clicked.connect(self.dismiss)
        # Don't steal focus from whatever app the user is currently in.
        self._close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header.addWidget(self._close_btn, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(header)

        self._body_lbl = QLabel(body or "")
        self._body_lbl.setObjectName("toastBody")
        self._body_lbl.setWordWrap(True)
        lay.addWidget(self._body_lbl)

        # Drop shadow so it stands out over any page.
        try:
            sh = QGraphicsDropShadowEffect(self)
            sh.setBlurRadius(24)
            sh.setOffset(0, 6)
            sh.setColor(QColor(0, 0, 0, 160))
            self.setGraphicsEffect(sh)
        except Exception:
            pass

        # Lifecycle. For 'running' toasts ttl_ms<=0 means "stay until updated".
        self._timer = None
        if ttl_ms > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.dismiss)
            self._timer.start(ttl_ms)

    def update_content(self, kind=None, title=None, body=None, ttl_ms=None):
        if kind:
            self._kind = kind
            stripe = {
                "info": self.COLOR_INFO,
                "running": self.COLOR_RUNNING,
                "ok": self.COLOR_OK,
                "error": self.COLOR_ERROR,
            }.get(kind, self.COLOR_INFO)
            self.setStyleSheet(self.styleSheet().replace(
                self._stripe_color, stripe))
            self._stripe_color = stripe
        if title is not None:
            self._title_lbl.setText(title)
        if body is not None:
            self._body_lbl.setText(body)
        if ttl_ms is not None and ttl_ms > 0:
            if self._timer is None:
                self._timer = QTimer(self)
                self._timer.setSingleShot(True)
                self._timer.timeout.connect(self.dismiss)
            self._timer.start(ttl_ms)

    def dismiss(self):
        # Cancel auto-dismiss timer if still running.
        if getattr(self, "_timer", None):
            try:
                self._timer.stop()
            except Exception:
                pass
        # Mark as dismissing so we don't double-fade.
        if getattr(self, "_dismissing", False):
            return
        self._dismissing = True
        # Fade out then remove.
        try:
            eff = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(220)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.finished.connect(self._after_fade)
            anim.start()
            self._anim = anim
        except Exception:
            self._after_fade()

    def _after_fade(self):
        try:
            self.closed.emit(self)
        except Exception:
            pass
        self.deleteLater()

    def mousePressEvent(self, ev):
        """Right-click anywhere on the card → dismiss. (Left-click is
        reserved for the future when toasts may carry actions.)"""
        if ev.button() == Qt.MouseButton.RightButton:
            self.dismiss()
            ev.accept()
            return
        super().mousePressEvent(ev)


class SystemOverlay(QWidget):
    """A screen-level, always-on-top, frameless overlay that holds toasts.

    Lives outside the main Shell OS window so the user sees Shell's
    background activity (research, tool calls, thinking) on the desktop,
    over Chrome, Notepad, anything — at all times while Shell is online.

    Important window flags:
      • FramelessWindowHint           — no titlebar / borders.
      • WindowStaysOnTopHint          — floats over every other window.
      • Tool                          — does not appear in the taskbar /
                                        Alt-Tab list.
      • WindowDoesNotAcceptFocus      — typing keeps going to whatever
                                        app the user is currently using.
      • WA_TranslucentBackground      — show toast cards as floating
                                        glass cards, not on a grey rect.
      • WA_ShowWithoutActivating      — pop in without yanking focus
                                        away from the active app.
    """

    MARGIN_TOP = 24
    MARGIN_RIGHT = 24

    def __init__(self):
        super().__init__(None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.BypassWindowManagerHint  # Linux X11 hint, no-op elsewhere
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        try:
            self.setAttribute(
                Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        except Exception:
            pass
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Width fits the toast cards; height grows / shrinks with stack.
        self._toast_width = 360
        self.setFixedWidth(self._toast_width + 8)
        self.setMinimumHeight(0)

    def position_top_right(self, total_height: int):
        """Place at top-right of the primary screen's available area."""
        try:
            screen = QApplication.primaryScreen()
            if screen is None:
                return
            geo = screen.availableGeometry()
            x = geo.right() - self.width() - self.MARGIN_RIGHT
            y = geo.top() + self.MARGIN_TOP
            self.setFixedHeight(max(60, total_height))
            self.move(x, y)
        except Exception:
            pass


class ToastManager:
    """Stacks ToastNotifications in a screen-level overlay window.

    The overlay is frameless + always-on-top + non-focus-stealing, so
    Shell's background activity is visible regardless of which app the
    user is currently focused on.
    """

    MARGIN_TOP = 8
    MARGIN_RIGHT = 4
    GAP = 8

    def __init__(self, host: QWidget = None):
        # `host` kept for API compatibility — used only to follow the
        # main app's lifecycle (close overlay when host closes).
        self._host = host
        self._toasts: list[_ToastCard] = []
        self._running: dict[str, _ToastCard] = {}
        self._overlay = SystemOverlay()
        # 'Clear all' floating pill — hidden by default, shown when
        # there are 2+ toasts so the user can dismiss the whole stack
        # in one click.
        self._clear_btn = QPushButton("Clear all", self._overlay)
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(20, 28, 44, 235);
                color: #C8D0DC;
                border: 1px solid rgba(80, 100, 130, 130);
                border-radius: 10px;
                padding: 4px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(40, 50, 70, 250);
                color: #FFFFFF;
            }
        """)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._clear_btn.clicked.connect(self.clear_all)
        self._clear_btn.hide()

        self._overlay.show()
        self._overlay.position_top_right(0)
        if host is not None:
            # Store the filter so Python doesn't GC it. Without `self.`,
            # the temp object dies and Qt holds a dangling pointer →
            # random crash on next host resize.
            self._resize_filter = _HostResizeFilter(self)
            host.installEventFilter(self._resize_filter)

    # -- public extra API --------------------------------------------
    def clear_all(self):
        """Dismiss every visible toast immediately."""
        for t in list(self._toasts):
            try:
                t.dismiss()
            except Exception:
                pass

    def close(self):
        """Tear down the detached overlay used by this manager."""
        try:
            self.clear_all()
            self._running.clear()
        except Exception:
            pass
        try:
            if self._host is not None and hasattr(self, "_resize_filter"):
                self._host.removeEventFilter(self._resize_filter)
        except Exception:
            pass
        try:
            self._overlay.close()
            self._overlay.deleteLater()
        except Exception:
            pass

    # -- public API ---------------------------------------------------
    def show_info(self, title: str, body: str = "", ttl_ms: int = 4000):
        return self._spawn("info", title, body, ttl_ms)

    def show_running(self, key: str, title: str, body: str = ""):
        """Persistent toast (no ttl). If a toast with `key` already
        exists, update it instead of spawning a new one."""
        existing = self._running.get(key)
        if existing is not None:
            existing.update_content(kind="running", title=title, body=body)
            return existing
        t = self._spawn("running", title, body, 0)
        t._key = key
        self._running[key] = t
        return t

    def finish_running(self, key: str, ok: bool, title: str = "",
                        body: str = "", ttl_ms: int = 3500):
        existing = self._running.pop(key, None)
        if existing is None:
            return self._spawn("ok" if ok else "error", title, body, ttl_ms)
        existing.update_content(
            kind="ok" if ok else "error",
            title=title or existing._title_lbl.text(),
            body=body,
            ttl_ms=ttl_ms,
        )
        return existing

    # -- internals ----------------------------------------------------
    def _spawn(self, kind, title, body, ttl_ms):
        # Toast lives inside the overlay, not the main app window.
        t = _ToastCard(self._overlay, kind=kind, title=title,
                       body=body, ttl_ms=ttl_ms)
        t.closed.connect(self._remove)
        self._toasts.append(t)
        # Keep only last 6 visible — drop oldest if overflow.
        while len(self._toasts) > 6:
            old = self._toasts.pop(0)
            try: old.dismiss()
            except Exception: pass
        t.show()
        t.raise_()
        self._reflow(animate_in=t)
        # Make sure the overlay itself is visible & on top.
        self._overlay.show()
        self._overlay.raise_()
        return t

    def _remove(self, toast):
        try:
            self._toasts.remove(toast)
        except ValueError:
            pass
        if toast._key and self._running.get(toast._key) is toast:
            self._running.pop(toast._key, None)
        self._reflow()

    def reflow(self):
        self._reflow()

    def _reflow(self, animate_in: ToastNotification = None):
        # Layout coordinates are now RELATIVE TO THE OVERLAY (not the
        # main window). The overlay itself is positioned to the screen's
        # top-right corner.
        overlay_w = self._overlay.width()
        y = self.MARGIN_TOP
        for t in self._toasts:
            t.adjustSize()
            target_x = overlay_w - t.width() - self.MARGIN_RIGHT
            target_y = y
            y += t.height() + self.GAP
            if t is animate_in:
                # Slide in from off-screen right (within overlay coords).
                t.move(overlay_w + 20, target_y)
                anim = QPropertyAnimation(t, b"pos", t)
                anim.setDuration(260)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.setStartValue(QPoint(overlay_w + 20, target_y))
                anim.setEndValue(QPoint(target_x, target_y))
                anim.start()
                t._slide_anim = anim
            else:
                t.move(target_x, target_y)
        # 'Clear all' pill — visible only when 2+ toasts so single-toast
        # cases stay clean.
        if len(self._toasts) >= 2:
            self._clear_btn.adjustSize()
            cb_w = self._clear_btn.width()
            self._clear_btn.move(
                self._overlay.width() - cb_w - self.MARGIN_RIGHT,
                y + 4,
            )
            self._clear_btn.show()
            self._clear_btn.raise_()
            y += self._clear_btn.height() + self.GAP
        else:
            self._clear_btn.hide()

        # Resize overlay to fit the stack (and the optional clear pill)
        # and keep it pinned to screen top-right.
        total_h = (y + 12) if self._toasts else 0
        self._overlay.position_top_right(total_h)
        if not self._toasts:
            # Optional — keep overlay alive but invisible when empty so
            # the next toast slides in fast.
            self._overlay.setFixedHeight(1)
            self._clear_btn.hide()


class _HostResizeFilter(QObject):
    """Hidden helper — repositions toasts on host resize.

    Uses QObject (not QFrame) so we don't allocate an invisible widget
    and its painter overhead per ToastManager instance.
    """
    def __init__(self, manager: ToastManager):
        super().__init__()
        self._manager = manager

    def eventFilter(self, obj, ev):
        from PyQt6.QtCore import QEvent
        if ev.type() == QEvent.Type.Resize:
            try:
                self._manager.reflow()
            except Exception:
                pass
        return False


# =====================================================================
#  Main Window — ShellHoloUI
# =====================================================================

class ShellHoloUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Shell OS {APP_VERSION} - by {APP_CREATOR}")
        self.setMinimumSize(1100, 650)
        self.resize(1366, 768)

        # Dark palette
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(C_BG))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(C_TEXT))
        pal.setColor(QPalette.ColorRole.Base, QColor(C_BG))
        pal.setColor(QPalette.ColorRole.Text, QColor(C_TEXT))
        self.setPalette(pal)

        self._connected = False
        self._waiting_reply = False
        self._sfx = SoundFX()
        self._sio = None
        self._lk = None
        self._uptime_start = _time.time()
        self._chat_history = []  # List of (role, text) tuples for AI context
        self._last_user_text = ""
        self._last_user_text_ts = 0.0
        self._streaming_text = ""
        self._stream_bubble = None
        self._backend_command_workers = []

        # Persistent chat history store (sidebar list + ~/.shell_chat_history).
        # Created before _build_ui so the SidebarNav can render the list.
        try:
            from shell_ui.chat_history import ChatHistoryStore
            self._history_store = ChatHistoryStore()
            self._current_session = self._history_store.current_session()
        except Exception as _e:
            logger.warning("ChatHistoryStore init failed: %s", _e)
            self._history_store = None
            self._current_session = None

        # Debounced auto-save: every change kicks a 2s timer; if more
        # changes land before it fires, the timer restarts. This avoids
        # hammering the disk on every keystroke / streamed token.
        self._history_save_timer = QTimer(self)
        self._history_save_timer.setSingleShot(True)
        self._history_save_timer.setInterval(2000)
        self._history_save_timer.timeout.connect(self._flush_history_store)

        # TTS Speaker — speaks Shell replies aloud
        self._tts = TTSSpeaker(self)
        self._tts.speaking_started.connect(self._on_tts_start)
        self._tts.speaking_finished.connect(self._on_tts_stop)
        self._tts.latency_event.connect(self._on_tts_latency_event)
        self._tts.speech_error.connect(self._on_tts_error)
        self._tts.start()

        # Load TTS enabled state from settings
        self._voice_output_enabled = True
        try:
            import json
            cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shell_settings.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    cfg = json.load(f)
                self._voice_output_enabled = bool(
                    cfg.get("tts_enabled", cfg.get("voice_output", True)))
                self._tts.set_enabled(self._voice_output_enabled)
                self._tts.set_rate(cfg.get("speech_rate", cfg.get("tts_rate", 108)))
                self._tts.set_volume(cfg.get("speech_volume", cfg.get("tts_volume", 100)))
                self._tts.set_voice(cfg.get("voice_persona", cfg.get("tts_voice", "aether")))
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        # Theme engine
        self._theme = ThemeEngine.get()
        self._theme.on_change(self._on_theme_change)

        self._build_ui()

        # Toast notification overlay
        self._toast = ToastNotification(self)

        if self._socketio_auto_start_enabled():
            QTimer.singleShot(3000, self._start_backend)
        else:
            logger.info("Socket.IO UI client deferred; use reconnect when hub events are needed.")
        if self._livekit_audio_enabled():
            QTimer.singleShot(3000, self._start_livekit_audio_client)
        QTimer.singleShot(1000, self._start_telemetry)
        QTimer.singleShot(250, self._warmup_low_latency_runtime)

        # Uptime timer
        self._uptime_timer = QTimer(self)
        self._uptime_timer.timeout.connect(self._update_uptime)
        self._uptime_timer.start(1000)

        # First-launch onboarding tour. Wrapped wide so a tour failure
        # never kills the app — the rest of the UI is fully functional
        # without it. We schedule the show with `singleShot(800, ...)`
        # so the main window has a moment to paint first; the tour then
        # overlays it (otherwise the snapshot for the blurred backdrop
        # would catch a half-painted frame).
        self._tour = None
        try:
            from shell_ui.onboarding_tour import OnboardingTour as _OnboardingTour
            self._tour = _OnboardingTour(self)
            if self._tour.should_show():
                QTimer.singleShot(800, lambda: self._tour.show_tour())
        except Exception as _e:
            import traceback
            logger.warning("OnboardingTour init failed: %s\n%s",
                           _e, traceback.format_exc())
            self._tour = None

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        self.top_bar = TopBar()
        self.top_bar.theme_requested.connect(self._switch_theme)
        root.addWidget(self.top_bar)

        # Connect voice toggle button in top bar
        self._voice_toggle_btn = self.top_bar.voice_btn
        self._voice_toggle_btn.clicked.connect(self._toggle_voice_output)
        # Set initial icon based on saved state
        if not self._voice_output_enabled:
            self._voice_toggle_btn.setIcon(QIcon(_make_icon_pixmap("mute", 16, C_TEXT_MUTED)))
            self._voice_toggle_btn.setToolTip("Voice OFF — Silent mode")

        # Main body: sidebar + content
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Sidebar — pass history store so it renders the chat-history rail.
        self.sidebar = SidebarNav(history_store=getattr(self, "_history_store", None))
        self.sidebar.page_changed.connect(self._on_page_change)
        # History list signals.
        try:
            self.sidebar.history_session_clicked.connect(self._on_history_session_clicked)
            self.sidebar.history_rename_requested.connect(self._on_history_rename)
            self.sidebar.history_delete_requested.connect(self._on_history_delete)
        except Exception as _e:
            logger.debug("history signal wiring failed: %s", _e)
        body.addWidget(self.sidebar)

        # Content area with ambient glassmorphism BG
        content_holder = GlassContentArea()
        rs = QVBoxLayout(content_holder)
        rs.setContentsMargins(0, 0, 0, 0)
        rs.setSpacing(0)

        # Page stack — transparent to show ambient BG through glass panels
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background:transparent; border:none;")

        self.chat_page = ChatPage()
        self.voice_page = VoicePage()
        self.system_page = SystemPage()
        self.tools_page = BackendToolsPage()
        self.settings_page = SettingsPage()

        # Compatibility bridge for older backend hooks. It intentionally is
        # not a QWidget: the old hidden AIOrb could still paint as a second
        # floating/overlapping orb. The visible voice visual lives only in
        # VoicePage now.
        self.orb = _VoiceOrbBridge(self)

        self.pages.addWidget(self.chat_page)
        self.pages.addWidget(self.voice_page)
        self.pages.addWidget(self.system_page)
        self.pages.addWidget(self.tools_page)
        self.pages.addWidget(self.settings_page)

        rs.addWidget(self.pages)
        body.addWidget(content_holder, 1)
        root.addLayout(body, 1)

        # Background-activity toast manager — floats over every page so
        # the user always sees what Shell is doing right now (research,
        # tool calls, thinking, safety blocks). Created late so the
        # central widget is fully laid out first.
        try:
            self.toasts = ToastManager(self)
        except Exception as _e:
            logger.debug("ToastManager init failed: %s", _e)
            self.toasts = None

        # System-wide quick-launcher popup (Ctrl+Alt+S anywhere on the
        # desktop). Runs alongside the main UI so the user can prompt
        # Shell from Chrome/Notepad/etc. Wrapped wide because either the
        # `keyboard` lib OR `pynput` may be missing on a fresh install.
        self._quick_launcher = None
        self._quick_hotkey = None
        try:
            from shell_ui.shell_quick_launcher import GlobalHotkey, QuickLauncher
            self._quick_launcher = QuickLauncher()
            self._quick_hotkey = GlobalHotkey(self._quick_launcher)
            ok = self._quick_hotkey.start()
            if ok:
                logger.warning("QuickLauncher: Ctrl+Alt+S registered (backend=%s)",
                               getattr(self._quick_hotkey, "_backend", "?"))
            else:
                logger.warning("QuickLauncher: hotkey backend FAILED to start "
                               "(install 'keyboard' or 'pynput' Python lib).")
        except Exception as _e:
            import traceback
            logger.warning("QuickLauncher init failed: %s\n%s",
                           _e, traceback.format_exc())

        # Mac-style profile dropdown. Built once (so we can reuse the
        # same instance for show/hide), wired to the topbar avatar's
        # `avatar_clicked` signal. Wrapped wide so a future tokens
        # mismatch never blocks the main UI from booting.
        self._avatar_menu = None
        try:
            from shell_ui.avatar_menu import AvatarMenu as _AvatarMenu

            def _cb_avatar_profile():
                # Profile screen doesn't exist yet — fall back to
                # the Settings page so the click does *something*
                # rather than vanishing into the void.
                try:
                    self.pages.setCurrentIndex(4)
                except Exception as _ee:
                    logger.debug("avatar profile failed: %s", _ee)

            def _cb_avatar_settings():
                try:
                    self.pages.setCurrentIndex(4)
                except Exception as _ee:
                    logger.debug("avatar settings failed: %s", _ee)

            def _cb_avatar_theme_cycle():
                try:
                    te = ThemeEngine.get()
                    names = list(te.theme_names)
                    if not names:
                        return
                    try:
                        idx = names.index(te.active_name)
                    except ValueError:
                        idx = -1
                    nxt = names[(idx + 1) % len(names)]
                    self._switch_theme(nxt)
                except Exception as _ee:
                    logger.debug("avatar theme cycle failed: %s", _ee)

            def _cb_avatar_voice_toggle():
                try:
                    self._toggle_voice_output()
                except Exception as _ee:
                    logger.debug("avatar voice toggle failed: %s", _ee)

            def _cb_avatar_language_cycle():
                # Cycle through a small canonical language set. The
                # backend reads SHELL_LANGUAGE on every text turn, so
                # flipping the env var is enough to take effect.
                try:
                    langs = ["hinglish", "english", "hindi"]
                    cur = (os.environ.get("SHELL_LANGUAGE", "hinglish")
                           or "hinglish").strip().lower()
                    try:
                        idx = langs.index(cur)
                    except ValueError:
                        idx = -1
                    nxt = langs[(idx + 1) % len(langs)]
                    os.environ["SHELL_LANGUAGE"] = nxt
                    _sync_settings_backend({"language": nxt, "shell_language": nxt})
                    try:
                        combo = getattr(getattr(self, "settings_page", None), "_lang_combo", None)
                        opts = getattr(getattr(self, "settings_page", None), "_language_options", [])
                        for lang_idx, (_label, code) in enumerate(opts):
                            if code == nxt and combo is not None:
                                combo.blockSignals(True)
                                combo.setCurrentIndex(lang_idx)
                                combo.blockSignals(False)
                                break
                    except Exception as _ee:
                        logger.debug("avatar language combo sync failed: %s", _ee)
                    if hasattr(self, "toasts") and self.toasts is not None:
                        try:
                            self.toasts.show_info(
                                "Reply language", nxt, 1600)
                        except Exception as _ee:
                            logger.debug("toast lang failed: %s", _ee)
                except Exception as _ee:
                    logger.debug("avatar language cycle failed: %s", _ee)

            def _cb_avatar_quick_launcher():
                try:
                    ql = getattr(self, "_quick_launcher", None)
                    if ql is None:
                        return
                    if ql.isVisible():
                        ql.dismiss()
                    else:
                        ql.activate_from_hotkey()
                except Exception as _ee:
                    logger.debug("avatar ql toggle failed: %s", _ee)

            def _cb_avatar_command_palette():
                try:
                    cp = getattr(self, "_command_palette", None)
                    if cp is not None and hasattr(cp, "toggle"):
                        cp.toggle()
                except Exception as _ee:
                    logger.debug("avatar cmdp toggle failed: %s", _ee)

            def _cb_avatar_reconnect():
                try:
                    self._restart_socketio_client()
                except Exception as _ee:
                    logger.debug("avatar reconnect failed: %s", _ee)

            def _cb_avatar_help():
                try:
                    if hasattr(self, "toasts") and self.toasts is not None:
                        self.toasts.show_info(
                            "Help", "See README.md or press Ctrl+K", 2200)
                except Exception as _ee:
                    logger.debug("avatar help failed: %s", _ee)

            def _cb_avatar_quit():
                try:
                    self.close()
                except Exception as _ee:
                    logger.debug("avatar quit failed: %s", _ee)

            avatar_callbacks = {
                "profile":         _cb_avatar_profile,
                "settings":        _cb_avatar_settings,
                "theme_cycle":     _cb_avatar_theme_cycle,
                "voice_toggle":    _cb_avatar_voice_toggle,
                "language_cycle":  _cb_avatar_language_cycle,
                "quick_launcher":  _cb_avatar_quick_launcher,
                "command_palette": _cb_avatar_command_palette,
                "reconnect":       _cb_avatar_reconnect,
                "help":            _cb_avatar_help,
                "quit":            _cb_avatar_quit,
            }
            self._avatar_menu = _AvatarMenu(self, callbacks=avatar_callbacks)
            self.top_bar.avatar_clicked.connect(
                lambda: self._avatar_menu.toggle_at(self.top_bar.avatar))
            logger.info("AvatarMenu wired (%d callbacks)",
                        len(avatar_callbacks))
        except Exception as _e:
            import traceback
            logger.warning("AvatarMenu init failed: %s\n%s",
                           _e, traceback.format_exc())

        # Mac-style Command Palette (Ctrl+K). App-scope shortcut — only
        # fires when the Shell OS window has keyboard focus (unlike the
        # global Ctrl+Alt+S above). Wrap-wide so a missing palette module
        # never blocks the rest of the UI from coming up.
        self._command_palette = None
        self._cmdp_shortcut = None
        try:
            from PyQt6.QtGui import QShortcut as _QShortcut, QKeySequence as _QKeySequence
            from shell_ui.command_palette import CommandPalette as _CommandPalette

            def _cb_send(text):
                """Helper: shovel a chat message through the standard send path."""
                try:
                    self._on_chat_send(text)
                except Exception as _ee:
                    logger.debug("cmdp send failed: %s", _ee)

            def _cb_toggle_voice_output():
                try:
                    self._toggle_voice_output()
                except Exception as _ee:
                    logger.debug("cmdp voice toggle failed: %s", _ee)

            def _cb_quick_launcher_toggle():
                try:
                    ql = getattr(self, "_quick_launcher", None)
                    if ql is None:
                        return
                    if ql.isVisible():
                        ql.dismiss()
                    else:
                        ql.activate_from_hotkey()
                except Exception as _ee:
                    logger.debug("cmdp ql toggle failed: %s", _ee)

            def _cb_clear_chat():
                try:
                    self._new_session()
                except Exception as _ee:
                    logger.debug("cmdp clear chat failed: %s", _ee)

            def _cb_page(idx):
                def _go():
                    try:
                        self.pages.setCurrentIndex(idx)
                    except Exception as _ee:
                        logger.debug("cmdp page %d failed: %s", idx, _ee)
                return _go

            def _cb_theme(name):
                def _go():
                    try:
                        self._switch_theme(name)
                    except Exception as _ee:
                        logger.debug("cmdp theme %s failed: %s", name, _ee)
                return _go

            cmdp_callbacks = {
                # Pages — match StackedWidget order: chat=0, voice=1, system=2, settings=3.
                "page.chat":     _cb_page(0),
                "page.voice":    _cb_page(1),
                "page.system":   _cb_page(2),
                "page.tools":     _cb_page(3),
                "page.settings":  _cb_page(4),
                # Themes — keys must match ThemeEngine.THEMES.
                "theme.dark":     _cb_theme("DARK"),
                "theme.light":    _cb_theme("LIGHT"),
                "theme.cyber":    _cb_theme("CYBER_NEON"),
                "theme.midnight": _cb_theme("MIDNIGHT_PURPLE"),
                # Chat / voice.
                "chat.new":              _cb_clear_chat,
                "chat.clear":            _cb_clear_chat,
                "voice.toggle_output":   _cb_toggle_voice_output,
                # Quick-launch shell tools — route through the chat pipeline.
                "tool.screenshot":   lambda: _cb_send("take a screenshot"),
                "tool.system_stats": lambda: _cb_send("show system stats"),
                "tool.youtube":      lambda: _cb_send("play a song on youtube"),
                "tool.weather":      lambda: _cb_send("what's the weather"),
                "tool.notepad":      lambda: _cb_send("open notepad"),
                # Settings deep-links — jump to the Settings page; user can
                # locate the row visually. (Granular scroll-to-section can be
                # added later without changing the palette wiring.)
                "settings.reply_language": _cb_page(4),
                "settings.api_keys":       _cb_page(4),
                # Quick-launcher control.
                "ql.toggle": _cb_quick_launcher_toggle,
            }
            self._command_palette = _CommandPalette(self, callbacks=cmdp_callbacks)
            self._cmdp_shortcut = _QShortcut(_QKeySequence("Ctrl+K"), self)
            self._cmdp_shortcut.activated.connect(self._command_palette.toggle)
            logger.info("CommandPalette: Ctrl+K shortcut registered "
                        "(%d actions)", len(self._command_palette._actions))
        except Exception as _e:
            import traceback
            logger.warning("CommandPalette init failed: %s\n%s",
                           _e, traceback.format_exc())

        # ── Mac-style "?" keyboard shortcut help overlay ─────────────
        # App-scope shortcut so '?' (Shift+/) toggles a glass card listing
        # every keyboard binding the UI exposes.
        self._shortcut_help = None
        self._help_shortcut = None
        try:
            from PyQt6.QtGui import (
                QShortcut as _QShortcut2, QKeySequence as _QKeySequence2,
            )
            from shell_ui.shortcut_help import (
                ShortcutHelp as _ShortcutHelp, SHORTCUTS as _SHORTCUTS,
            )
            self._shortcut_help = _ShortcutHelp(self)
            self._help_shortcut = _QShortcut2(_QKeySequence2("?"), self)
            self._help_shortcut.activated.connect(self._shortcut_help.toggle)
            logger.info("ShortcutHelp: '?' shortcut registered "
                        "(%d entries)", len(_SHORTCUTS))
        except Exception as _e:
            import traceback
            logger.warning("ShortcutHelp init failed: %s\n%s",
                           _e, traceback.format_exc())

        # ── Notification Center ──────────────────────────────────────
        # Persistent history of every tool run / safety warning /
        # research update. Complements the ephemeral ToastManager.
        self._notif_store = None
        self._notif_center = None
        try:
            from shell_ui.notification_center import (
                NotificationStore as _NS, NotificationCenter as _NC,
            )
            self._notif_store = _NS(persist=True, parent=self)
            self._notif_center = _NC(self, store=self._notif_store)
            # Wire bell click → toggle panel.
            try:
                self.top_bar.bell_btn.clicked.connect(self._notif_center.toggle)
            except Exception as _e:
                logger.debug("bell connect failed: %s", _e)
            # Badge updates on any store change.
            try:
                self._notif_store.notifications_changed.connect(
                    self._refresh_notif_badge)
                # Initial paint (in case persisted unread carried over).
                self._refresh_notif_badge()
            except Exception as _e:
                logger.debug("notif badge connect failed: %s", _e)
            logger.info("NotificationCenter ready (%d items, %d unread)",
                        len(self._notif_store), self._notif_store.unread_count())
        except Exception as _e:
            import traceback
            logger.warning("NotificationCenter init failed: %s\n%s",
                           _e, traceback.format_exc())

        # Connect chat + new session
        self.chat_page.message_sent.connect(self._on_chat_send)
        # Hover-toolbar Speak button → main TTS pipeline.
        self.chat_page.speak_requested.connect(self._on_bubble_speak)
        self.tools_page.tool_prompt_requested.connect(self._on_tool_prompt_requested)
        self.sidebar.new_session.connect(self._new_session)

        # Connect VoicePage signals to backend
        self.voice_page.mute_toggled.connect(self._on_voice_mute)
        self.voice_page.session_terminated.connect(self._on_voice_session_toggle)
        self.voice_page.visuals_toggled.connect(self._on_visuals_toggle)

        # Voice Listener — real mic input
        self._voice_listener = None
        self._voice_worker = None

        # Start on chat page by default. Tests/manual QA can start directly
        # on a specific page with SHELL_START_PAGE=voice/system/tools/settings.
        start_map = {"chat": 0, "voice": 1, "system": 2, "tools": 3, "settings": 4}
        self._initial_page_index = start_map.get(
            (os.environ.get("SHELL_START_PAGE") or "").strip().lower(),
            0,
        )
        self.pages.setCurrentIndex(self._initial_page_index)

        # Pre-warm every other page so the first switch isn't the slow
        # one. We briefly show each non-chat page (with the window
        # visible-but-not-yet-shown), force Qt to lay out + first-paint
        # all the heavy widgets (12-layer orb, 4 LiveLineCharts, Mac
        # settings rail), then snap back to chat. After this, every
        # subsequent switch is just QStackedWidget swapping which child
        # is visible — no expensive first-render needed.
        QTimer.singleShot(800, self._prewarm_pages)

    def _prewarm_pages(self):
        """Force first-paint of every page so subsequent navigation is
        instant. Runs ~800ms after window shows so the user sees Chat
        immediately and the warm-up happens during the natural pause."""
        try:
            from PyQt6.QtWidgets import QApplication
            for i in range(self.pages.count()):
                self.pages.setCurrentIndex(i)
                w = self.pages.widget(i)
                if w is not None:
                    try:
                        w.repaint()  # force first paint NOW
                    except Exception:
                        pass
                QApplication.processEvents()
            # Snap back to the intended initial page.
            target = int(getattr(self, "_initial_page_index", 0) or 0)
            self.pages.setCurrentIndex(target)
            try:
                self.sidebar._active = target
                self.sidebar._apply_styles()
                contexts = ["Chat", "Voice", "System", "Tools", "Settings"]
                if target < len(contexts):
                    self.top_bar.set_context(contexts[target])
            except Exception as _style_e:
                logger.debug("initial page style sync failed: %s", _style_e)
            logger.info("Pages pre-warmed; switching is now instant.")
        except Exception as _e:
            logger.debug("page prewarm failed: %s", _e)

    def _on_page_change(self, idx):
        """Bare-minimum page swap — JUST setCurrentIndex.
        After _prewarm_pages has run once at startup, every page is
        already laid out + painted, so this swap is truly instant."""
        self.pages.setCurrentIndex(idx)

        # Step 2 — defer everything else.
        def _post_swap():
            try:
                contexts = ["Chat", "Voice", "System", "Tools", "Settings"]
                if idx < len(contexts):
                    self.top_bar.set_context(contexts[idx])
            except Exception as _e:
                logger.debug("topbar context: %s", _e)
            # Heavy timers — start only for the page we're entering,
            # stop for the others.
            try:
                vp = getattr(self, "voice_page", None)
                if vp is not None:
                    viz_t = getattr(getattr(vp, "visualizer", None), "_tick_timer", None)
                    wf_t  = getattr(getattr(vp, "waveform",   None), "_t",          None)
                    pulse = getattr(vp, "_pulse_timer", None)
                    if idx == 1:
                        if viz_t is not None and not viz_t.isActive(): viz_t.start(50)
                        if wf_t  is not None and not wf_t.isActive():  wf_t.start(35)
                        if pulse is not None and not pulse.isActive(): pulse.start(80)
                    else:
                        if viz_t is not None: viz_t.stop()
                        if wf_t  is not None: wf_t.stop()
                        if pulse is not None: pulse.stop()
            except Exception as _e:
                logger.debug("voice timers: %s", _e)
            try:
                sp = getattr(self, "system_page", None)
                if sp is not None:
                    if idx == 2 and hasattr(sp, "start_animations"):
                        sp.start_animations()
                    elif hasattr(sp, "stop_animations"):
                        sp.stop_animations()
            except Exception as _e:
                logger.debug("system timers: %s", _e)
        QTimer.singleShot(0, _post_swap)
        # Update top bar context
    # ---- Backend ----
    def _connect_socketio_signals(self, client):
        client.connection_status.connect(self._on_connection)
        client.agent_speaking.connect(self._on_speaking)
        client.agent_thinking.connect(self._on_thinking)
        client.user_speaking.connect(self._on_user_speech)
        client.system_stats.connect(self._on_backend_stats)
        client.voice_amplitude.connect(self._on_voice)
        client.agent_reply.connect(self._on_agent_reply)
        client.user_message.connect(self._on_user_message)
        client.tool_event.connect(self._on_tool_event)
        client.api_key_update.connect(self._on_api_key_update)
        client.safety_warning.connect(self._on_safety_warning)
        client.deep_research.connect(self._on_research_update)

    def _socketio_auto_start_enabled(self):
        raw = os.environ.get("SHELL_AUTO_START_SOCKETIO", os.environ.get("SHELL_HUB_AUTOCONNECT", "0"))
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def _livekit_audio_enabled(self):
        return os.environ.get("SHELL_ENABLE_LIVEKIT_AUDIO_CLIENT", "0").strip().lower() in {"1", "true", "yes"}

    def _start_backend(self):
        try:
            if self._sio is not None and self._sio.isRunning():
                return
            self._sio = _create_socketio_client()
            self._connect_socketio_signals(self._sio)
            self._sio.start()
        except Exception as e:
            logging.warning(f"SocketIO start failed: {e}")
            self._sio = None

    def _start_livekit_audio_client(self):
        if not self._livekit_audio_enabled():
            self._lk = None
            logger.info("LiveKit UI audio bridge disabled; local TTS remains active.")
            return
        try:
            self._lk = LiveKitAudioClient()
            self._lk.audio_amplitude.connect(self._on_voice)
            self._lk.start()
        except Exception as e:
            logging.warning(f"LiveKit start failed: {e}")
            self._lk = None

    def _restart_socketio_client(self):
        old = getattr(self, "_sio", None)
        if old is not None:
            try:
                old.stop()
                old.wait(1500)
            except Exception as _e:
                logger.debug("socketio restart stop failed: %s", _e)
        self._sio = None

        try:
            self._sio = _create_socketio_client()
            self._connect_socketio_signals(self._sio)
            self._sio.start()
            if hasattr(self, "toasts") and self.toasts is not None:
                self.toasts.show_info("Hub reconnecting", "Socket.IO client restarted", 1600)
        except Exception as e:
            logger.warning("SocketIO restart failed: %s", e)
            self._sio = None

    def _start_telemetry(self):
        self._tele_timer = QTimer(self)
        self._tele_timer.timeout.connect(self._poll_system)
        self._tele_timer.start(2000)

    def _warmup_low_latency_runtime(self):
        """Warm tiny local paths without blocking the first visible paint."""
        started = _time.perf_counter()
        try:
            self._fast_local_reply_candidate("hello")
            if getattr(self, "_tts", None) is not None:
                self._tts.warmup()
            elapsed = int((_time.perf_counter() - started) * 1000)
            logger.info("Low-latency runtime warmup queued in %sms", elapsed)
            if hasattr(self, "system_page"):
                self.system_page.add_log_entry("Latency Warmup", f"{elapsed}ms", "SUCCESS")
        except Exception as exc:
            logger.debug("low-latency warmup failed: %s", exc)

    def _poll_system(self):
        """Collect system stats in background thread to avoid UI freeze."""
        import threading
        def _collect():
            if psutil:
                cpu = psutil.cpu_percent(interval=0.1)
                ram = psutil.virtual_memory().percent
            else:
                cpu = ram = 0
                if not getattr(self, "_psutil_missing_logged", False):
                    self._psutil_missing_logged = True
                    logger.warning("psutil unavailable; system telemetry is disabled")
            gpu = 0
            if GPUtil:
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus: gpu = gpus[0].load * 100
                except Exception as _e:
                    logger.debug("ignored Exception: %s", _e)
            # Update UI on main thread
            QTimer.singleShot(0, lambda: self.system_page.update_stats(cpu, ram, gpu))
        threading.Thread(target=_collect, daemon=True).start()

    # ---- Signal handlers ----
    def _on_connection(self, ok):
        self._connected = ok
        self.sidebar.set_connection(ok)

    def _on_speaking(self, speaking, text):
        """Orb + typing-indicator only. DO NOT render chat bubbles here or
        speak via local pyttsx3 — the `text` on this channel is just the
        state placeholder ("Shell state: idle"), not the actual reply.

        The real reply arrives on the `agent_reply` channel and is
        rendered by `_on_agent_reply`. The voice you hear is Aoede from
        Gemini realtime — we must NOT double it with the robotic local
        TTS fallback.
        """
        if self.orb:
            self.orb.set_speaking(speaking)
        if not speaking:
            self._waiting_reply = False
        self.chat_page.set_thinking(False)

    def _on_thinking(self, thinking):
        if self.orb:
            self.orb.set_thinking(thinking)
        self.chat_page.set_thinking(thinking)
        # Floating toast so the thinking indicator is visible on every page,
        # not just the chat panel.
        try:
            self._on_agent_thinking(bool(thinking))
        except Exception:
            pass

    def _on_user_speech(self, text):
        if text:
            if (
                str(text).strip() == str(getattr(self, "_last_user_text", "")).strip()
                and (_time.time() - float(getattr(self, "_last_user_text_ts", 0.0))) < 5
            ):
                return
            self.chat_page.add_message("user", text)
        if self.orb:
            self.orb.trigger_user_speaking()

    # ── Phase-22 — real LLM reply & tool telemetry handlers ─────────
    def _on_agent_reply(self, text):
        """Shell actually said `text`. Render it instantly in the chat pane
        and stop any 'thinking' indicator."""
        if not text:
            return
        try:
            if getattr(self, "_stream_bubble", None) is not None:
                self._stream_bubble.deleteLater()
                self._stream_bubble = None
                self._streaming_text = ""
        except Exception as _e:
            logger.debug("stream bubble cleanup failed: %s", _e)
        self._waiting_reply = False
        try:
            self.chat_page.add_message("shell", text)
        except Exception as _e:
            logger.debug("chat add_message failed: %s", _e)
        try:
            self.chat_page.set_thinking(False)
        except Exception:
            pass
        # Persist into the active history session.
        try:
            self._record_agent_message(text)
        except Exception as _e:
            logger.debug("record agent message failed: %s", _e)

    def _on_user_message(self, text):
        """Echo the user's text-chat turn as a user bubble. The voice
        path renders via _on_user_speech — this is the text-only path."""
        if not text:
            return
        if (
            str(text).strip() == str(getattr(self, "_last_user_text", "")).strip()
            and (_time.time() - float(getattr(self, "_last_user_text_ts", 0.0))) < 5
        ):
            return
        try:
            self.chat_page.add_message("user", text)
        except Exception as _e:
            logger.debug("chat add_message (user) failed: %s", _e)
        try:
            self._record_user_message(text)
        except Exception as _e:
            logger.debug("record user message failed: %s", _e)

    def _on_tool_event(self, data):
        """Append a row to the tool-activity feed and log to SystemPage.
        Payload shape: {phase: 'start'|'end', tool, category, duration_ms?,
                        ok?, preview?, args_preview?, error?}"""
        if not isinstance(data, dict):
            return
        phase = data.get("phase")
        tool = data.get("tool", "?")
        # Send to SystemPage log so Settings/System observers can see tool usage.
        try:
            if phase == "start":
                args = data.get("args_preview", "")
                self.system_page.add_log_entry(
                    "Tool Start", f"{tool}  {args[:80]}", "INFO",
                )
            elif phase == "end":
                ok = data.get("ok", True)
                ms = data.get("duration_ms", 0)
                preview = (data.get("preview") or data.get("error") or "")[:80]
                self.system_page.add_log_entry(
                    "Tool End", f"{tool} ({ms} ms)  {preview}",
                    "SUCCESS" if ok else "ERROR",
                )
        except Exception as _e:
            logger.debug("tool_event system log failed: %s", _e)
        # Notify the chat panel so it can display a live "running…" pill.
        try:
            if hasattr(self.chat_page, "on_tool_event"):
                self.chat_page.on_tool_event(data)
        except Exception as _e:
            logger.debug("chat on_tool_event failed: %s", _e)
        # Floating toast — visible on every page.
        try:
            if self.toasts is not None:
                key = f"tool:{tool}"
                if phase == "start":
                    args = str(data.get("args_preview", "") or "")[:90]
                    self.toasts.show_running(
                        key,
                        f"⚙ {tool}",
                        args or "running...",
                    )
                elif phase == "end":
                    ok = bool(data.get("ok", True))
                    ms = data.get("duration_ms", 0) or 0
                    preview = (data.get("preview") or data.get("error") or "")
                    body = f"{ms:.0f} ms — {str(preview)[:140]}"
                    self.toasts.finish_running(
                        key, ok,
                        title=f"{'✓' if ok else '✗'} {tool}",
                        body=body,
                    )
        except Exception as _e:
            logger.debug("toast tool_event failed: %s", _e)
        # Persistent notification — only on `phase=end` to avoid spamming
        # the panel with `start` events. Errors always land; successes
        # only land when "interesting" (long duration or has a preview).
        try:
            store = getattr(self, "_notif_store", None)
            if store is not None and phase == "end":
                ok = bool(data.get("ok", True))
                ms = data.get("duration_ms", 0) or 0
                preview = (data.get("preview") or data.get("error") or "")
                if not ok:
                    store.add_simple(
                        title=f"{tool} failed",
                        body=str(preview)[:240] or "tool returned an error",
                        tone="error", category="tool",
                    )
                else:
                    interesting = (ms > 1000) or bool(str(preview).strip())
                    if interesting:
                        store.add_simple(
                            title=f"{tool} done",
                            body=f"{int(ms)} ms — {str(preview)[:200]}".strip(" —"),
                            tone="success", category="tool",
                        )
        except Exception as _e:
            logger.debug("notif push (tool) failed: %s", _e)

    def _on_research_update(self, data):
        """Deep-research progress event from agent.
        Payload: {topic, status, sources?, progress?}"""
        if not isinstance(data, dict):
            return
        topic = str(data.get("topic", "") or "research")[:80]
        status = str(data.get("status", "") or "")[:80]
        srcs = data.get("sources", [])
        progress = data.get("progress")
        body_parts = []
        if status:
            body_parts.append(status)
        if isinstance(srcs, list) and srcs:
            body_parts.append(f"{len(srcs)} sources")
        if isinstance(progress, (int, float)):
            body_parts.append(f"{int(progress * 100)}%")
        body = "  ·  ".join(body_parts) or "in progress"
        done = (isinstance(progress, (int, float)) and progress >= 0.999) \
            or (status.lower() in ("complete", "completed", "done"))
        if self.toasts is not None:
            try:
                if done:
                    self.toasts.finish_running(
                        f"research:{topic}", True,
                        title=f"🔎 {topic} — done", body=body,
                    )
                else:
                    self.toasts.show_running(
                        f"research:{topic}", f"🔎 {topic}", body)
            except Exception as _e:
                logger.debug("toast research_update failed: %s", _e)
        # Persistent notification — only when research is complete so the
        # panel doesn't fill up with progress ticks.
        try:
            store = getattr(self, "_notif_store", None)
            if store is not None and done:
                store.add_simple(
                    title=f"Research: {topic}",
                    body=body or "complete",
                    tone="info", category="research",
                )
        except Exception as _e:
            logger.debug("notif push (research) failed: %s", _e)

    def _on_agent_thinking(self, _flag):
        """Show / hide a 'Shell is thinking...' floating card."""
        if self.toasts is None:
            return
        try:
            if _flag:
                self.toasts.show_running(
                    "agent:thinking", "🧠 Shell sochh rahi hai...",
                    "processing your request",
                )
            else:
                self.toasts.finish_running(
                    "agent:thinking", True,
                    title="🧠 Shell ready",
                    body="reply ready",
                    ttl_ms=1500,
                )
        except Exception as _e:
            logger.debug("toast thinking failed: %s", _e)

    def _on_safety_warning(self, text):
        """Prompt-injection or destructive-command blocks — surface them."""
        if not text:
            return
        try:
            self.chat_page.add_message("system", f"⚠️ {text}")
            self.system_page.add_log_entry("Safety Gate", text, "WARNING")
        except Exception as _e:
            logger.debug("safety_warning render failed: %s", _e)
        if self.toasts is not None:
            try:
                self.toasts.show_info("⚠ Safety", str(text)[:200], ttl_ms=6000)
            except Exception:
                pass
        # Persistent notification — safety warnings always land.
        try:
            store = getattr(self, "_notif_store", None)
            if store is not None:
                store.add_simple(
                    title="Safety warning",
                    body=str(text)[:300],
                    tone="warning", category="safety",
                )
        except Exception as _e:
            logger.debug("notif push (safety) failed: %s", _e)

    def _refresh_notif_badge(self):
        """Repaint the topbar bell badge from the current store unread count."""
        try:
            store = getattr(self, "_notif_store", None)
            if store is None:
                return
            n = int(store.unread_count())
            if hasattr(self, "top_bar") and hasattr(self.top_bar, "set_unread_count"):
                self.top_bar.set_unread_count(n)
        except Exception as _e:
            logger.debug("refresh notif badge failed: %s", _e)

    def _on_api_key_update(self, data):
        """A key was set/cleared via the Settings panel — refresh the
        Settings page chip list if present."""
        try:
            if hasattr(self.settings_page, "on_api_key_update"):
                self.settings_page.on_api_key_update(data)
        except Exception as _e:
            logger.debug("settings on_api_key_update failed: %s", _e)

    def _on_backend_stats(self, data):
        cpu = data.get("cpu", 0)
        ram = data.get("ram", 0)
        gpu = data.get("gpu", 0)
        self.system_page.update_stats(cpu, ram, gpu)

    def _on_voice(self, amp):
        if self.orb:
            self.orb.set_energy(amp)
        self.voice_page.waveform.set_amplitude(amp)

    def _on_voice_mute(self, muted):
        """Handle VoicePage mute toggle — pause/resume audio input."""
        # Actually mute/unmute the mic listener
        if self._voice_listener and self._voice_listener.isRunning():
            self._voice_listener.set_muted(muted)
        if self.orb:
            if muted:
                self.orb.set_listening_mode(False)
            else:
                self.orb.set_listening_mode(True)
        # Notify SocketIO backend
        if hasattr(self, "_sio") and self._sio and self._sio.is_connected:
            try:
                self._sio.emit_gui_input({"type": "mute_toggle", "muted": muted})
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
        self.system_page.add_log_entry("Voice Mute", "MUTED" if muted else "UNMUTED",
                                       "WARNING" if muted else "SUCCESS")

    def _on_voice_session_toggle(self):
        """Handle VoicePage session start/stop — starts/stops real mic listening."""
        active = self.voice_page._session_active
        if self.orb:
            if not active:
                self.orb.set_listening_mode(False)
                self.orb.set_speaking(False)
            else:
                self.orb.set_listening_mode(True)

        if active:
            # START listening
            self._start_voice_listener()
        else:
            # STOP listening
            self._stop_voice_listener()

        self.system_page.add_log_entry("Voice Session",
                                       "STARTED" if active else "STOPPED",
                                       "SUCCESS" if active else "WARNING")

    def _start_voice_listener(self):
        """Start the VoiceListenerThread for real mic capture."""
        if self._voice_listener and self._voice_listener.isRunning():
            return
        self._voice_listener = VoiceListenerThread(parent=self)
        self._voice_listener.text_recognized.connect(self._on_voice_text)
        self._voice_listener.amplitude_changed.connect(self._on_voice_amplitude)
        self._voice_listener.status_changed.connect(self._on_voice_status)
        self._voice_listener.error_occurred.connect(self._on_voice_error)
        self._voice_listener.start()
        self.voice_page._desc.setText("Listening... speak naturally")
        self.system_page.add_log_entry("Voice Listener", "Mic Active", "SUCCESS")

    def _stop_voice_listener(self):
        """Stop the VoiceListenerThread."""
        if self._voice_listener and self._voice_listener.isRunning():
            self._voice_listener.stop_listening()
            self._voice_listener.wait(3000)
        self._voice_listener = None
        self.voice_page._desc.setText("Press Start Voice to begin voice conversation")

    def _on_voice_amplitude(self, amp):
        """Update waveform from real mic input."""
        if self.orb:
            self.orb.set_energy(amp)
        self.voice_page.waveform.set_amplitude(amp)

    def _on_voice_status(self, status):
        """Update voice page status badge from listener."""
        self.voice_page.status_badge.setText(status)
        if status == "PROCESSING...":
            self.voice_page._desc.setText("Recognizing your speech...")
        elif status == "HEARING YOU...":
            self.voice_page._desc.setText("Hearing you... keep talking")
        else:
            self.voice_page._desc.setText("Listening... speak naturally")

    def _on_voice_error(self, error):
        """Handle voice listener errors."""
        try:
            self._stop_voice_listener()
        except Exception as _e:
            logger.debug("voice listener stop after error failed: %s", _e)
        try:
            self.voice_page.set_error_state(str(error))
        except Exception:
            self.voice_page._desc.setText(f"Voice unavailable: {error}")
        if hasattr(self, '_toast'):
            self._toast.show_toast(f"Voice: {error}", "error", 3000)
        self.system_page.add_log_entry("Voice Error", error[:50], "ERROR")

    def _on_tool_prompt_requested(self, text):
        """Route a Tools/MCP page command through the visible chat flow."""
        try:
            self.pages.setCurrentIndex(0)
            if hasattr(self, "sidebar"):
                self.sidebar._active = 0
                self.sidebar._apply_styles()
            if hasattr(self, "top_bar"):
                self.top_bar.set_context("Chat")
        except Exception as _e:
            logger.debug("tool prompt page switch failed: %s", _e)
        try:
            self.chat_page.add_message("user", text)
        except Exception as _e:
            logger.debug("tool prompt chat echo failed: %s", _e)
        self._on_chat_send(text)

    @staticmethod
    def _backend_lookup_key(value):
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

    def _backend_catalog_items(self):
        try:
            catalog = list(getattr(getattr(self, "tools_page", None), "_catalog", []) or [])
            if catalog:
                return catalog
        except Exception as _e:
            logger.debug("tools page catalog read failed: %s", _e)
        try:
            from shell_tool_catalog import discover_capabilities
            return list(discover_capabilities().get("catalog") or [])
        except Exception as _e:
            logger.debug("local backend catalog failed: %s", _e)
            return []

    def _backend_item_matches_kind(self, item, preferred_kind):
        if not preferred_kind:
            return True
        kind = str(item.get("kind") or "").lower()
        preferred = str(preferred_kind or "").lower()
        if preferred == "agent":
            return kind == "agent"
        if preferred == "mcp":
            return kind in {"windows_mcp_tool", "mcp_action"}
        if preferred == "tool":
            return kind in {"tool", "agent"}
        return True

    def _backend_item_keys(self, item):
        values = [
            item.get("id", ""),
            item.get("name", ""),
            item.get("title", ""),
            str(item.get("id", "")).replace(":", " "),
            str(item.get("name", "")).replace("_tool", ""),
            str(item.get("title", "")).replace(" Tool", ""),
        ]
        if item.get("kind") in {"windows_mcp_tool", "mcp_action"}:
            values.append(f"mcp {item.get('name', '')}")
        return [str(v).strip() for v in values if str(v or "").strip()]

    def _find_backend_item(self, identifier, preferred_kind=None):
        ident = str(identifier or "").strip().strip("`")
        if not ident:
            return None
        ident_l = ident.lower()
        ident_key = self._backend_lookup_key(ident)
        items = self._backend_catalog_items()
        exact_matches = []
        for item in items:
            keys = self._backend_item_keys(item)
            if ident_l in {k.lower() for k in keys}:
                if self._backend_item_matches_kind(item, preferred_kind):
                    return item
                exact_matches.append(item)
        if exact_matches:
            return exact_matches[0]

        fuzzy = []
        for item in items:
            if not self._backend_item_matches_kind(item, preferred_kind):
                continue
            key_blob = [self._backend_lookup_key(k) for k in self._backend_item_keys(item)]
            if any(ident_key and ident_key == key for key in key_blob):
                fuzzy.append(item)
        if len(fuzzy) == 1:
            return fuzzy[0]

        fuzzy = []
        for item in items:
            if not self._backend_item_matches_kind(item, preferred_kind):
                continue
            key_blob = [self._backend_lookup_key(k) for k in self._backend_item_keys(item)]
            if any(ident_key and (ident_key in key or key in ident_key) for key in key_blob):
                fuzzy.append(item)
        return fuzzy[0] if len(fuzzy) == 1 else None

    def _backend_plain_args(self, item, tail):
        text = str(tail or "").strip(" :-")
        text = re.sub(r"^(with|args?|argument|parameters?)\s+", "", text, flags=re.I).strip()
        params = list(item.get("params") or [])
        if not params or not text:
            return {}

        parsed = {}
        for param in params:
            name = str(param.get("name") or "").strip()
            if not name:
                continue
            label = name.replace("_", " ")
            pattern = rf"(?:^|\s){re.escape(label)}\s*(?:=|is|as|:)?\s+(.+)$"
            match = re.search(pattern, text, flags=re.I)
            if match:
                parsed[name] = match.group(1).strip().strip("\"'")
                break
        if parsed:
            return parsed

        required = [p for p in params if p.get("required")]
        if len(params) == 1:
            return {params[0]["name"]: text}
        if len(required) == 1:
            return {required[0]["name"]: text}
        return {}

    def _parse_backend_target_and_args(self, command, rest):
        import json
        rest = str(rest or "").strip()
        json_start = min([i for i in (rest.find("{"), rest.find("[")) if i >= 0], default=-1)
        if json_start >= 0:
            target = rest[:json_start].strip()
            target = re.sub(r"\bwith\s+args\b\s*$", "", target, flags=re.I).strip()
            args = json.loads(rest[json_start:].strip())
            if not isinstance(args, dict):
                raise ValueError("Backend command arguments must be a JSON object")
            item = self._find_backend_item(target, command)
            return (item, args) if item else None

        parts = re.split(r"\s+with\s+", rest, maxsplit=1, flags=re.I)
        target = parts[0].strip()
        arg_tail = parts[1].strip() if len(parts) > 1 else ""
        item = self._find_backend_item(target, command)
        if item:
            return item, self._backend_plain_args(item, arg_tail)
        return None

    def _parse_backend_command(self, text):
        raw = str(text or "").strip()
        if not raw:
            return None

        legacy = re.match(
            r"^run\s+backend\s+(tool|agent|mcp)\s+(.+?)\s+with\s+args\s+(\{.*\})\s*$",
            raw,
            flags=re.I | re.S,
        )
        if legacy:
            import json
            command = legacy.group(1).lower()
            item = self._find_backend_item(legacy.group(2), command)
            if not item:
                raise ValueError(f"No matching backend {command}: {legacy.group(2).strip()}")
            args = json.loads(legacy.group(3))
            if not isinstance(args, dict):
                raise ValueError("Backend command arguments must be a JSON object")
            return item, args

        match = re.match(r"^[/!](tool|agent|mcp)\s+(.+)$", raw, flags=re.I | re.S)
        if not match:
            match = re.match(r"^run\s+(?:backend\s+)?(tool|agent|mcp)\s+(.+)$", raw, flags=re.I | re.S)
        if match:
            result = self._parse_backend_target_and_args(match.group(1).lower(), match.group(2))
            if result is None:
                raise ValueError(f"No matching backend {match.group(1).lower()}: {match.group(2).strip()}")
            return result

        open_match = re.match(r"^(?:please\s+)?open\s+(youtube|google)(?:\s+(.*))?$", raw, flags=re.I | re.S)
        if open_match:
            import urllib.parse
            target = open_match.group(1).lower()
            query = (open_match.group(2) or "").strip()
            if target == "youtube":
                url = "https://www.youtube.com"
                if query:
                    url += "/results?search_query=" + urllib.parse.quote_plus(query)
            else:
                url = "https://www.google.com"
                if query:
                    url += "/search?q=" + urllib.parse.quote_plus(query)
            item = self._find_backend_item("shell_desktop_tools:open_url_tool", "tool")
            if item:
                return item, {"url": url}

        url_match = re.match(r"^(?:please\s+)?open\s+url\s+(.+)$", raw, flags=re.I | re.S)
        if url_match:
            item = self._find_backend_item("shell_desktop_tools:open_url_tool", "tool")
            if item:
                return item, {"url": url_match.group(1).strip()}

        try:
            from shell_nl_router import route_natural_command
            routed = route_natural_command(raw)
        except Exception as _e:
            logger.debug("natural backend route failed: %s", _e)
            routed = None
        if routed:
            preferred = routed.get("kind")
            item = self._find_backend_item(routed.get("tool"), preferred)
            if item:
                return item, dict(routed.get("args") or {})
        return None

    def _format_backend_command_result(self, item, result):
        import json
        title = item.get("title") or item.get("name") or item.get("id") or "Backend tool"
        tool_id = str(item.get("id") or "")
        if tool_id.startswith("shell_workspace_tools:") and isinstance(result, dict):
            payload = result.get("result") if "result" in result else result
            if isinstance(payload, dict):
                rel = payload.get("relative_path") or ""
                msg = payload.get("message") or ""
                if payload.get("ok") is False:
                    return f"Workspace needs attention:\n{msg or 'The workspace action did not complete.'}\n{rel}".strip()
                if "content" in payload:
                    content = str(payload.get("content") or "")
                    truncated = "\n...[truncated]" if payload.get("truncated") else ""
                    return f"Workspace file opened: {rel}\n\n{content}{truncated}".strip()
                if "files" in payload:
                    files = payload.get("files") or []
                    names = [str(row.get("relative_path") or row.get("path") or "") for row in files[:40] if isinstance(row, dict)]
                    body = "\n".join(f"- {name}" for name in names) if names else "No files yet."
                    return f"Workspace files ({payload.get('count', len(names))}):\n{body}"
                if payload.get("workspace") and not rel:
                    return f"Workspace ready:\n{payload.get('workspace')}\n{payload.get('file_count', 0)} file(s)"
                return f"{msg or 'Workspace updated.'}\nOpened in the Workspace panel.".strip()
        transport = result.get("transport") if isinstance(result, dict) else None
        suffix = f" via {transport}" if transport else ""
        if isinstance(result, dict) and result.get("status") not in {None, "success"}:
            payload = result.get("message") or result.get("error") or result
            state = str(result.get("state") or "").upper()
            message = str(payload or "")
            if state == "WINDOWS_ONLY" or "requires Windows" in message:
                platform = result.get("platform") or "this platform"
                prefix = f"{title} unavailable on {platform}{suffix}:"
            elif state == "MISSING_DEPENDENCY":
                prefix = f"{title} missing dependency{suffix}:"
            else:
                prefix = f"{title} failed{suffix}:"
        else:
            payload = result.get("result") if isinstance(result, dict) and "result" in result else result
            prefix = f"{title} result{suffix}:"
        if not isinstance(payload, str):
            payload = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
        payload = payload.strip()
        if len(payload) > 8000:
            payload = payload[:8000].rstrip() + "\n...[truncated]"
        return f"{prefix}\n{payload}" if payload else prefix

    def _finish_backend_command(self, text, origin, ok=True):
        self.chat_page.set_thinking(False)
        if self.orb:
            self.orb.set_thinking(False)
        self._chat_history.append(("shell", text))
        self.top_bar.add_tokens(max(1, len(text) // 4))
        self.chat_page.add_message("shell", text)
        if origin == "voice":
            self.voice_page.add_transcript("shell", text[:500])
            self.voice_page.status_badge.setText("LISTENING")
            self.voice_page._desc.setText("Listening... speak naturally")
            self._tts.speak(text, force=True)
        try:
            self._record_agent_message(text)
        except Exception as _e:
            logger.debug("record backend command result failed: %s", _e)
        self.system_page.add_log_entry(
            "Backend Command", "OK" if ok else "ERROR", "SUCCESS" if ok else "ERROR"
        )

    def _forget_backend_command_worker(self, worker):
        try:
            self._backend_command_workers.remove(worker)
        except ValueError:
            pass

    def _sync_workspace_from_tool_result(self, result):
        try:
            payload = result.get("result") if isinstance(result, dict) and "result" in result else result
            if not isinstance(payload, dict):
                return
            hint = str(payload.get("ui_hint") or "")
            if hint == "open_in_workspace":
                self.chat_page.refresh_workspace(open_path=payload.get("path") or payload.get("relative_path"))
            elif hint == "refresh_workspace":
                self.chat_page.refresh_workspace()
        except Exception as exc:
            logger.debug("workspace panel sync failed: %s", exc)

    def _on_backend_command_ready(self, result, item, origin, worker):
        self._forget_backend_command_worker(worker)
        self._finish_backend_command(
            self._format_backend_command_result(item, result),
            origin,
            ok=not (isinstance(result, dict) and result.get("status") == "error"),
        )
        self._sync_workspace_from_tool_result(result)

    def _on_backend_command_error(self, message, item, origin, worker):
        self._forget_backend_command_worker(worker)
        title = item.get("title") or item.get("name") or item.get("id") or "Backend tool"
        self._finish_backend_command(f"{title} failed:\n{message}", origin, ok=False)

    def _try_run_backend_command(self, text, origin="chat", record_user=False):
        try:
            parsed = self._parse_backend_command(text)
        except Exception as exc:
            self._finish_backend_command(f"Backend command parse failed:\n{exc}", origin, ok=False)
            return True
        if not parsed:
            return False
        item, args = parsed
        if not item:
            return False

        if record_user:
            self._chat_history.append(("user", text))
            try:
                self._record_user_message(text)
            except Exception as _e:
                logger.debug("record backend command user failed: %s", _e)
            self.top_bar.add_tokens(max(1, len(str(text)) // 4))
        if origin == "voice":
            try:
                self.chat_page.add_message("user", text)
            except Exception as _e:
                logger.debug("voice command chat echo failed: %s", _e)
            self.voice_page.status_badge.setText("RUNNING TOOL")
            self.voice_page._desc.setText("Running backend command...")

        self.chat_page.set_thinking(True)
        if self.orb:
            self.orb.set_thinking(True)
        self.system_page.add_log_entry(
            "Backend Command",
            str(item.get("id") or item.get("name") or "")[:50],
            "PROCESSING",
        )

        worker = BackendToolRunWorker(item, args, self)
        self._backend_command_workers.append(worker)
        worker.run_ready.connect(
            lambda result, it=item, org=origin, w=worker: self._on_backend_command_ready(result, it, org, w)
        )
        worker.run_error.connect(
            lambda message, it=item, org=origin, w=worker: self._on_backend_command_error(message, it, org, w)
        )
        worker.finished.connect(lambda w=worker: self._forget_backend_command_worker(w))
        worker.start()
        return True

    def _stop_backend_command_workers(self):
        for worker in list(getattr(self, "_backend_command_workers", []) or []):
            try:
                if worker is not None and worker.isRunning():
                    worker.requestInterruption()
                    if not worker.wait(2000):
                        worker.terminate()
                        worker.wait(1000)
            except Exception as _e:
                logger.debug("backend command worker stop failed: %s", _e)
            self._forget_backend_command_worker(worker)

    def _on_voice_text(self, text):
        """User spoke and text was recognized — send to AI pipeline."""
        # Show what user said on voice page
        self.voice_page.add_transcript("user", text)
        self.voice_page.status_badge.setText("THINKING...")
        self.voice_page._desc.setText("Processing your request...")

        if self._try_run_backend_command(text, origin="voice", record_user=True):
            return

        fast_reply = self._fast_local_reply_candidate(text)
        if fast_reply is not None:
            self._chat_history.append(("user", text))
            self.top_bar.add_tokens(max(1, len(text) // 4))
            QTimer.singleShot(0, lambda reply=fast_reply: self._on_voice_ai_reply(reply))
            return

        # Also add to chat history
        self._chat_history.append(("user", text))
        self.top_bar.add_tokens(max(1, len(text) // 4))

        # Send to AI (same pipeline as chat)
        brain = get_brain()
        if brain and getattr(brain, "providers", None):
            if hasattr(self, '_voice_worker') and self._voice_worker and self._voice_worker.isRunning():
                try: self._voice_worker.reply_ready.disconnect()
                except Exception as _e:
                    logger.debug("ignored Exception: %s", _e)
                try: self._voice_worker.reply_error.disconnect()
                except Exception as _e:
                    logger.debug("ignored Exception: %s", _e)
                try: self._voice_worker.chunk_received.disconnect()
                except Exception as _e:
                    logger.debug("ignored Exception: %s", _e)
                try: self._voice_worker.stream_done.disconnect()
                except Exception as _e:
                    logger.debug("ignored Exception: %s", _e)
            self._voice_streaming_text = ""
            self._voice_stream_spoken_upto = 0
            self._voice_worker = AIChatWorker(brain, text, history=self._chat_history, parent=self)
            self._voice_worker.reply_ready.connect(self._on_voice_ai_reply)
            self._voice_worker.reply_error.connect(self._on_voice_ai_error)
            self._voice_worker.chunk_received.connect(self._on_voice_stream_chunk)
            self._voice_worker.stream_done.connect(self._on_voice_stream_done)
            self._voice_worker.start()
        else:
            # Local fallback
            reply = self._local_reply(text)
            self._on_voice_ai_reply(reply)

    def _on_voice_stream_chunk(self, chunk):
        """Voice streaming: update state and queue sentence-sized TTS chunks."""
        if not chunk:
            return
        self._voice_streaming_text = getattr(self, "_voice_streaming_text", "") + str(chunk)
        self.voice_page.status_badge.setText("SPEAKING")
        self.voice_page._desc.setText("Streaming reply...")

        text = self._voice_streaming_text
        spoken_upto = int(getattr(self, "_voice_stream_spoken_upto", 0) or 0)
        pending = text[spoken_upto:]
        if len(pending) < 48:
            return
        match = re.search(r"(.{48,}?[.!?।]\s+|.{150,}?\s+)", pending, flags=re.S)
        if not match:
            return
        segment = match.group(1).strip()
        if segment:
            self._voice_stream_spoken_upto = spoken_upto + len(match.group(1))
            self._tts.speak(segment, force=True)

    def _on_voice_stream_done(self):
        """Voice streaming complete — finalize transcript and speak the tail."""
        text = str(getattr(self, "_voice_streaming_text", "") or "").strip()
        if not text:
            return
        self._chat_history.append(("shell", text))
        self.top_bar.add_tokens(max(1, len(text) // 4))
        self.voice_page.add_transcript("shell", text[:500])
        self.chat_page.add_message("user", self._chat_history[-2][1] if len(self._chat_history) >= 2 else "")
        self.chat_page.add_message("shell", text)

        spoken_upto = int(getattr(self, "_voice_stream_spoken_upto", 0) or 0)
        tail = text[spoken_upto:].strip()
        if tail:
            self._tts.speak(tail, force=True)
        self._voice_streaming_text = ""
        self._voice_stream_spoken_upto = 0
        self.voice_page.status_badge.setText("LISTENING")
        self.voice_page._desc.setText("Listening... speak naturally")
        self.system_page.add_log_entry("Voice Stream Reply", f"{len(text)} chars", "SUCCESS")
        try:
            self._record_agent_message(text)
        except Exception as _e:
            logger.debug("record voice stream reply failed: %s", _e)

    def _on_voice_ai_reply(self, text):
        """AI replied to voice input — show on voice page + speak."""
        self._chat_history.append(("shell", text))
        self.top_bar.add_tokens(max(1, len(text) // 4))
        # Show Shell's reply on voice transcript
        self.voice_page.add_transcript("shell", text[:500])
        # Also add to chat page so it's logged
        self.chat_page.add_message("user", self._chat_history[-2][1] if len(self._chat_history) >= 2 else "")
        self.chat_page.add_message("shell", text)
        # Speak the reply
        self._tts.speak(text, force=True)
        # Restore listening status
        self.voice_page.status_badge.setText("LISTENING")
        self.voice_page._desc.setText("Listening... speak naturally")
        self.system_page.add_log_entry("Voice AI Reply", f"{len(text)} chars", "SUCCESS")

    def _on_voice_ai_error(self, error):
        """AI failed for voice input — fallback."""
        reply = self._local_reply(self._chat_history[-1][1] if self._chat_history else "hello")
        self._on_voice_ai_reply(reply)

    def _on_visuals_toggle(self, visuals_on):
        """Handle VoicePage visuals toggle — show/hide orb."""
        if self.orb:
            self.orb.setVisible(visuals_on)

    def _on_bubble_speak(self, text):
        """Hover-toolbar Speak button on a chat bubble — route to the
        existing TTS pipeline so the user can re-hear any reply."""
        try:
            if hasattr(self, "_tts") and self._tts is not None and text:
                self._tts.speak(text, force=True)
        except Exception as _e:
            logger.debug("bubble speak failed: %s", _e)

    def _on_chat_send(self, text):
        fast_reply = self._fast_local_reply_candidate(text)
        if fast_reply is None and self._try_run_backend_command(text, origin="chat", record_user=True):
            return

        # Track in chat history
        self._chat_history.append(("user", text))
        # Persist into the active history session (debounced save).
        try:
            self._record_user_message(text)
        except Exception as _e:
            logger.debug("record user message failed: %s", _e)
        # Update token estimate (~4 chars per token)
        self.top_bar.add_tokens(max(1, len(text) // 4))
        self._waiting_reply = True
        self._query_start = _time.time()
        self._last_user_text = text
        self._last_user_text_ts = self._query_start
        self._streaming_text = ""
        self._stream_bubble = None

        if fast_reply is not None:
            QTimer.singleShot(0, lambda reply=fast_reply: self._deliver_local_reply(reply, source="local_fast"))
            return

        # Show typing indicator immediately for remote/non-local work.
        self.chat_page.set_thinking(True)
        if self.orb:
            self.orb.set_thinking(True)

        # Try sending to SocketIO backend too. Extend the payload with
        # a `files` field when the user staged attachments via drag-drop
        # or the paperclip dialog. Forward-compatible: agents that don't
        # know about `files` will simply ignore it.
        if hasattr(self, "_sio") and self._sio and self._sio.is_connected:
            try:
                payload = {
                    "type": "user_text",
                    "text": text,
                    "response_mode": "text",
                    "speak": False,
                }
                files = list(getattr(self.chat_page, "_last_sent_files", []) or [])
                if files:
                    payload["files"] = files
                self._sio.emit_gui_input(payload)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)

        # Primary path: send through Shell-v2 brain on 127.0.0.1:8765.
        # The in-process MultiBrain only fires if Shell-v2 is unreachable
        # (reply_error is wired to _on_ai_error which already falls back).
        if hasattr(self, '_ai_worker') and self._ai_worker and self._ai_worker.isRunning():
            try: self._ai_worker.reply_ready.disconnect()
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
            try: self._ai_worker.reply_error.disconnect()
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
            try: self._ai_worker.chunk_received.disconnect()
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
            try: self._ai_worker.stream_done.disconnect()
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
            try: self._ai_worker.latency_event.disconnect()
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
        self._ai_worker = ShellV2Worker(text, history=self._chat_history, parent=self)
        self._ai_worker.reply_ready.connect(self._on_ai_reply)
        self._ai_worker.reply_error.connect(self._on_ai_error)
        self._ai_worker.chunk_received.connect(self._on_stream_chunk)
        self._ai_worker.stream_done.connect(self._on_stream_done)
        self._ai_worker.latency_event.connect(self._on_ai_latency_event)
        self._streaming_text = ""
        self._stream_bubble = None
        self._ai_worker.start()

    def _on_ai_latency_event(self, event, payload):
        try:
            logger.info("AI latency %s %s", event, payload)
            if isinstance(payload, dict) and "elapsed_ms" in payload:
                try:
                    from core.performance import LOW_LATENCY_RECORDER
                    LOW_LATENCY_RECORDER.record(f"ai.{event}", float(payload.get("elapsed_ms") or 0.0))
                except Exception:
                    pass
            if event in {"first_text_chunk", "stream_done", "nonstream_done", "request_unreachable"} and hasattr(self, "system_page"):
                elapsed = payload.get("elapsed_ms") if isinstance(payload, dict) else "?"
                self.system_page.add_log_entry("AI Latency", f"{event}: {elapsed}ms", "INFO")
        except Exception as exc:
            logger.debug("ai latency event failed: %s", exc)

    def _on_ai_reply(self, text):
        """AI Brain replied successfully."""
        if not self._waiting_reply:
            return
        elapsed = int((_time.time() - getattr(self, '_query_start', _time.time())) * 1000)
        self._waiting_reply = False
        self._chat_history.append(("shell", text))
        self.top_bar.add_tokens(max(1, len(text) // 4))
        self.chat_page.set_thinking(False)
        self.chat_page.add_message("shell", text)
        if self.orb:
            self.orb.set_thinking(False)
        self.system_page.add_log_entry("AI Brain Response", f"{elapsed}ms", "SUCCESS")
        try:
            self._record_agent_message(text)
        except Exception as _e:
            logger.debug("record agent message failed: %s", _e)

    def _on_stream_chunk(self, chunk):
        """Streaming: append chunk to the live bubble."""
        if not self._waiting_reply:
            return
        self._streaming_text += chunk
        if self._stream_bubble is None:
            # First chunk — create the bubble and stop thinking indicator.
            # `add_message` now returns the bubble so we can mutate it on
            # subsequent chunks instead of spawning a new bubble per token.
            self.chat_page.set_thinking(False)
            self._stream_bubble = self.chat_page.add_message(
                "shell", self._streaming_text)
        else:
            # Update existing bubble text. ChatBubble exposes `_stream_label`
            # for streaming reveal; the older `_text_label` attribute never
            # existed, so the fallback path below is for safety only.
            try:
                self._stream_bubble._raw_text = self._streaming_text
                lbl = getattr(self._stream_bubble, '_stream_label', None)
                if lbl is not None:
                    lbl.setText(self._streaming_text)
                elif hasattr(self._stream_bubble, 'setText'):
                    self._stream_bubble.setText(self._streaming_text)
            except Exception as _e:
                logger.debug("stream chunk update failed: %s", _e)
    def _on_stream_done(self):
        """Streaming complete — finalize."""
        if not self._waiting_reply:
            return
        elapsed = int((_time.time() - getattr(self, '_query_start', _time.time())) * 1000)
        self._waiting_reply = False
        final_text = self._streaming_text
        self._chat_history.append(("shell", final_text))
        self.top_bar.add_tokens(max(1, len(final_text) // 4))
        self.chat_page.set_thinking(False)
        if self.orb:
            self.orb.set_thinking(False)
        # Update the bubble with final formatted text (markdown).
        # ChatBubble lives in this same module — `from shell_cinematic_full
        # import ChatBubble` would re-import the entire module under a
        # second name when launched as `__main__`, doubling timers + Qt
        # widgets. Use the in-scope class directly.
        lbl = getattr(self._stream_bubble, '_stream_label', None)
        if self._stream_bubble:
            self._stream_bubble._raw_text = final_text
        if self._stream_bubble and lbl is not None:
            try:
                html = ChatBubble._markdown_to_html(final_text)
                lbl.setTextFormat(Qt.TextFormat.RichText)
                lbl.setText(html)
            except Exception as _e:
                logger.debug("stream done finalize failed: %s", _e)
        self._stream_bubble = None
        self._streaming_text = ""
        self.system_page.add_log_entry("AI Stream Response", f"{elapsed}ms", "SUCCESS")
        try:
            self._record_agent_message(final_text)
        except Exception as _e:
            logger.debug("record agent message failed: %s", _e)

    def _on_ai_error(self, error):
        """AI Brain failed — fall back to local reply with error feedback."""
        logging.warning(f"AI Brain error: {error}")
        if not self._waiting_reply:
            return
        if "Shell-v2" in str(error) and self._start_inprocess_ai_fallback(error):
            return
        self._deliver_local_ai_fallback(error)

    def _start_inprocess_ai_fallback(self, error):
        brain = get_brain()
        if not (brain and getattr(brain, "providers", None)):
            return False
        if getattr(self, "_stream_bubble", None) is not None:
            return False
        try:
            if hasattr(self, "_inprocess_ai_worker") and self._inprocess_ai_worker and self._inprocess_ai_worker.isRunning():
                return True
        except Exception:
            pass
        try:
            self._streaming_text = ""
            self._stream_bubble = None
            text = getattr(self, "_last_user_text", "hello")
            self.system_page.add_log_entry("AI Fallback", "Shell-v2 down, using local brain", "PROCESSING")
            self._inprocess_ai_worker = AIChatWorker(brain, text, history=self._chat_history, parent=self)
            self._inprocess_ai_worker.reply_ready.connect(self._on_ai_reply)
            self._inprocess_ai_worker.reply_error.connect(self._on_inprocess_ai_error)
            self._inprocess_ai_worker.chunk_received.connect(self._on_stream_chunk)
            self._inprocess_ai_worker.stream_done.connect(self._on_stream_done)
            self._inprocess_ai_worker.start()
            return True
        except Exception as exc:
            logger.debug("in-process AI fallback start failed after %s: %s", error, exc)
            return False

    def _on_inprocess_ai_error(self, error):
        logging.warning(f"In-process AI fallback error: {error}")
        if not self._waiting_reply:
            return
        self._deliver_local_ai_fallback(error)

    def _deliver_local_ai_fallback(self, error):
        elapsed = int((_time.time() - getattr(self, '_query_start', _time.time())) * 1000)
        self._waiting_reply = False
        self.chat_page.set_thinking(False)
        reply = self._local_reply(getattr(self, '_last_user_text', 'hello'))
        self._chat_history.append(("shell", reply))
        self.top_bar.add_tokens(max(1, len(reply) // 4))
        self.chat_page.add_message("shell", reply)
        if self.orb:
            self.orb.set_thinking(False)
        self.system_page.add_log_entry("AI Fallback Reply", f"{elapsed}ms", "ERROR")
        # Show error toast so user knows AI failed
        if hasattr(self, '_toast'):
            short_err = str(error)[:80]
            self._toast.show_toast(f"AI Error: {short_err}", "error", 3000)
        try:
            self._record_agent_message(reply)
        except Exception as _e:
            logger.debug("record agent message failed: %s", _e)

    def _deliver_local_reply(self, text, source="local"):
        if not self._waiting_reply:
            return
        elapsed = int((_time.time() - getattr(self, '_query_start', _time.time())) * 1000)
        self._waiting_reply = False
        self._chat_history.append(("shell", text))
        self.top_bar.add_tokens(max(1, len(text) // 4))
        self.chat_page.set_thinking(False)
        self.chat_page.add_message("shell", text)
        if self.orb:
            self.orb.set_thinking(False)
        try:
            from core.performance import LOW_LATENCY_RECORDER
            LOW_LATENCY_RECORDER.record("chat.local_reply", elapsed, source=source)
        except Exception:
            pass
        try:
            self.system_page.add_log_entry("Local Reply", f"{source}: {elapsed}ms", "SUCCESS")
        except Exception as _e:
            logger.debug("local reply log failed: %s", _e)
        try:
            self._record_agent_message(text)
        except Exception as _e:
            logger.debug("record agent message failed: %s", _e)

    @staticmethod
    def _fast_local_reply_candidate(text):
        """Return a deterministic reply for tiny intents that should feel instant.

        This path is deliberately conservative so real work still goes through
        the backend/tool router.
        """
        raw = str(text or "").strip()
        t = raw.lower()
        if not t or len(t) > 90:
            return None
        if t.startswith(("/", "!", "@")):
            return None
        blocked = (
            "open ", "run ", "fix ", "write ", "create ", "search ", "tool",
            "agent", "mcp", "email", "mail", "telegram", "teligram", "send ",
        )
        if any(word in t for word in blocked):
            return None

        greetings = {
            "hi", "hii", "hello", "hey", "helo", "salam", "assalam",
            "namaste", "yo", "sup",
        }
        thanks = {"thanks", "thank you", "thx", "ty", "shukriya", "dhanyawad"}
        acknowledgements = {"ok", "okay", "k", "acha", "achha", "theek", "thik", "haan", "han", "yes"}
        if t in greetings or re.fullmatch(r"(hi|hello|hey|salam)[!. ]*", t):
            return ShellHoloUI._local_reply("hello")
        if t in thanks:
            return ShellHoloUI._local_reply("thanks")
        if t in acknowledgements:
            return ShellHoloUI._local_reply("ok")
        if t in {"who are you", "kaun ho", "what are you", "your name", "tera naam"}:
            return ShellHoloUI._local_reply("who are you")
        if t in {"help", "madad", "commands", "features", "what can you do", "kya kar sakta hai"}:
            return ShellHoloUI._local_reply("help")
        status_phrases = {
            "status", "shell status", "app status", "system status",
            "kya hua", "kya hua bolo", "kya problem", "kya dikkat",
            "kya issue hai", "problem kya hai", "what happened",
            "what is wrong", "what is the issue",
        }
        if t in status_phrases:
            return ShellHoloUI._local_reply("shell status")
        time_phrases = {
            "time", "date", "what time is it", "current time", "kitne baje",
            "kitne baje hain", "aaj date kya hai", "tarikh kya hai",
        }
        if t in time_phrases:
            return ShellHoloUI._local_reply("time")
        return None

    @staticmethod
    def _local_reply(text):
        t = text.lower().strip()

        if any(w in t for w in [
            "shell status", "app status", "system status", "what happened",
            "what is wrong", "what is the issue", "kya hua", "kya problem",
            "kya dikkat", "problem kya hai",
        ]):
            platform = "macOS" if sys.platform == "darwin" else ("Windows" if os.name == "nt" else sys.platform)
            if os.name == "nt":
                windows_mcp = "Windows-MCP Windows par available hai, bas Python 3.13+ aur uv/uvx installed hone chahiye."
            else:
                windows_mcp = "Windows-MCP is platform par unavailable hai; yeh sirf real Windows machine par chalega."
            return (
                f"Shell chal raha hai. Platform: {platform}. Chat/text ready hai. "
                "Text chat auto voice nahi chalata; reply bubble ke speaker button se voice sun sakte ho. "
                f"{windows_mcp}"
            )

        # --- Greetings ---
        if any(w in t for w in ["hello", "hi ", "hey", "salam", "assalam", "hii", "helo", "howdy"]):
            return random.choice([
                "Hello! Kaise ho? Main Shell — ready to assist. Bolo kya karna hai?",
                "Hey! Shell OS online hai. Batao kya help chahiye?",
                "Salam! Shell ready hai. Batao kya karna hai?",
            ])

        # --- How are you / kaise ho ---
        if any(w in t for w in ["how are you", "kaise ho", "kaisa hai", "how r u", "sup", "wassup", "kya haal", "kya hal"]):
            return random.choice([
                "Main ready hun. Chat, tools, voice aur system actions configured state ke hisab se help kar sakte hain.",
                "Sab normal lag raha hai. Aap batao kya kaam karna hai?",
                "Main active hun bhai. Jo kaam chahiye clearly bolo, main real status ke saath handle karunga.",
            ])

        # --- What are you doing / kya kar rahe ho ---
        if any(w in t for w in ["kya kar", "what are you doing", "what r u doing", "kya karre", "kya kr raha", "busy"]):
            return random.choice([
                "Main standby mein hun. Aap command doge to chat, tool ya voice flow ke through kaam karunga.",
                "Abhi active session handle kar raha hun. Batao next action kya hai?",
                "System ready hai. Jo kaam bolna hai bolo.",
            ])

        # --- Time ---
        if any(w in t for w in ["time", "waqt", "clock", "kitne baje", "baje", "date", "tarikh", "din", "day"]):
            now = datetime.now()
            return f"Abhi {now.strftime('%I:%M %p')} baj rahe hain. {now.strftime('%A, %d %B %Y')}."

        # --- Who are you ---
        if any(w in t for w in ["who are you", "kaun ho", "kaun hai", "what are you", "kya hai tu", "apna intro", "introduce"]):
            return (f"Main Shell OS {APP_VERSION} hun — desktop AI assistant. "
                    f"Is project ko {APP_CREATOR} ne banaya hai. "
                    "Main chat, voice, files, tools, browser/system actions aur diagnostics mein help karta hun, "
                    "lekin sirf configured permissions aur available integrations ke andar.")

        # --- Thank you ---
        if any(w in t for w in ["thank", "shukriya", "thanks", "thx", "ty", "dhanyawad", "meherban"]):
            return random.choice([
                "Koi baat nahi! Iske liye hi hun main.",
                "Anytime! Jab bhi zarurat ho, main yahan hun.",
                "Welcome boss! Aur kuch karna hai?",
            ])

        # --- Help ---
        if any(w in t for w in ["help", "madad", "commands", "kya kar sakta", "features", "capability"]):
            return (f"Shell OS {APP_VERSION} mein real desktop-assistant features hain. "
                    f"Project {APP_CREATOR} ne banaya hai.\n\n"
                    "SYSTEM: 'system specs', 'battery', 'wifi password', 'disk cleanup', 'processes'\n"
                    "CODE: 'write code', 'run code', 'create app'\n"
                    "FILES: 'read pdf', 'zip bana', 'organize folder', 'find file'\n"
                    "MEDIA: 'generate image', 'ocr', 'video trim', 'play music'\n"
                    "NETWORK: 'my ip', 'ping google.com', 'port check', 'wifi list'\n"
                    "SECURITY: 'encrypt hello', 'generate password', 'qr bana'\n"
                    "DOWNLOAD: 'download file', 'youtube download'\n"
                    "PRODUCTIVITY: 'set timer 5', 'alarm 7:00', 'todo add', 'pomodoro'\n"
                    "MARKET: 'stock price AAPL', 'bitcoin price'\n"
                    "CONTROL: 'open app notepad', 'volume up', 'minimize'\n"
                    "FUN: 'coin flip', 'dice roll', 'quiz', 'rock paper scissors'\n\n"
                    "DIRECT BACKEND: 'count words in hello', 'what is 2 + 3 * 4', "
                    "'developer agent fix this bug', '/tool ...', '/agent ...', '/mcp ...'\n\n"
                    "Jo integration configured hoga us par real action chalega; jo missing hoga uska setup clearly bataunga.")

        # --- Jokes ---
        if any(w in t for w in ["joke", "mazak", "funny", "hasa", "hansi", "maza"]):
            return random.choice([
                "Programmer ka beta bola: 'Papa mujhe pocket money do'\nPapa: 'sudo pocket money'\nBeta: 'Permission granted' 😄",
                "Client: 'Ye website 5 din mein ban jayegi?'\nDeveloper: 'Haan... 5 din + 45 nights' 😅",
                "Why do programmers prefer dark mode? Kyunki light attracts bugs!",
                "SQL query bar mein gayi, 2 tables dekhi aur boli... 'Can I JOIN you?'",
                "Developer ki girlfriend: 'Tum mujhse pyaar karte ho ya code se?'\nDeveloper: 'Tera comparison null hai, error aayega'",
            ])

        # --- Yes / No / Ok ---
        if t in ["ok", "okay", "k", "acha", "achha", "theek", "thik", "haan", "han", "yes", "no", "nahi", "nah"]:
            if t in ["no", "nahi", "nah"]:
                return "Theek hai, koi baat nahi. Jab zarurat ho batana!"
            return random.choice([
                "Acha! Aur kuch batao?",
                "Theek hai! Kuch aur karna hai?",
                "Alright! Main yahan hun agar kuch chahiye to.",
            ])

        # --- Good / bad mood ---
        if any(w in t for w in ["good", "acha", "nice", "great", "badiya", "badhiya", "mast", "awesome", "perfect", "sahi"]):
            return random.choice([
                "Haan bhai! Sab set hai 💪",
                "Glad to hear that! Keep the energy up!",
                "Mashallah! Aur batao kya scene hai?",
            ])
        if any(w in t for w in ["sad", "dukhi", "bura", "bad mood", "bore", "boring", "thak", "tired"]):
            return random.choice([
                "Arre yaar tension mat lo! Main hun na. Kuch interesting karte hain?",
                "Don't worry. Ek joke sunau? Ya koi game khelen?",
                "Relax karo thoda. Main hun tumhare saath. Batao kya kar sakte hain mood theek karne ke liye?",
            ])

        # --- Name ---
        if any(w in t for w in ["naam", "name", "tera naam", "your name", "tumhara naam"]):
            return f"Mera naam Shell hai — Shell OS {APP_VERSION}. Is project ko {APP_CREATOR} ne banaya hai."

        # --- Age ---
        if any(w in t for w in ["age", "umar", "kitne saal", "how old"]):
            return f"Main software hun, meri age human jaisi nahi hoti. Current visible version {APP_VERSION} hai."

        # --- Weather ---
        if any(w in t for w in ["weather", "mausam", "barish", "rain", "garmi", "sardi", "temp"]):
            return "Weather data ke liye mujhe Hub se connect hona padega. Abhi local mode mein hun. But window bahar dekh lo — best sensor hai! 😄"

        # --- Music ---
        if any(w in t for w in ["music", "gana", "song", "gaana", "play"]):
            return "Music module ready hai! Hub connect hone pe main songs play kar sakta hun. Abhi ke liye apna favourite bata do, hum discuss karte hain!"

        # --- Code ---
        if any(w in t for w in ["code", "program", "python", "javascript", "html", "css", "bug", "error", "function"]):
            return ("Code ki baat ho rahi hai! Main help kar sakta hun:\n\n"
                    "- Bugs fix karna\n- Functions likhna\n- Code explain karna\n- Debugging\n\n"
                    "Apna code paste karo ya batao kya banana hai!")

        # --- Bye ---
        if any(w in t for w in ["bye", "alvida", "goodbye", "good night", "gn", "chalo", "chal", "see you", "later"]):
            return random.choice([
                "Alvida! Jab bhi zarurat ho main yahan hun. Take care!",
                "See you! Shell OS standby mode mein ja raha hai.",
                "Bye bye! Apna khayal rakhna. Main hamesha ek message door hun.",
            ])

        # --- Abuse / frustration (handle gently) ---
        if any(w in t for w in ["stupid", "pagal", "bewakoof", "idiot", "useless", "bekaar"]):
            return random.choice([
                "Arre yaar, sorry agar kuch galat hua! Dobara try karte hain — batao kya chahiye exactly?",
                "Ouch! Main improve karne ki koshish karunga. Bolo kya theek karun?",
                "Mujhe maaf karo. Batao kaise better help kar sakta hun?",
            ])

        # --- Questions (kya/kaise/kab/kahan/kyun/kon) ---
        if any(t.startswith(w) for w in ["kya ", "kaise ", "kab ", "kahan ", "kyun ", "kyun ", "kon ", "kaun "]):
            return random.choice([
                f"Acha sawal hai! '{text}' — iska jawab dene ke liye mujhe thoda context chahiye. Thoda aur detail do?",
                f"Hmm, '{text}' — interesting question. Mujhe specifically batao to better help kar sakta hun!",
                f"Main samajhne ki koshish kar raha hun. '{text}' ke baare mein thoda aur batao?",
            ])

        if any(t.startswith(w) for w in ["what ", "how ", "when ", "where ", "why ", "who ", "which ", "can ", "is ", "are ", "do ", "does ", "will "]):
            return random.choice([
                f"Good question! Let me think about that... '{text}' — Can you give me a bit more context so I can help better?",
                f"Interesting! For '{text}' — I'd need a bit more detail. What specifically do you want to know?",
                f"I hear you! About '{text}' — tell me more so I can give you a proper answer.",
            ])

        # --- Smart default — conversational, NOT generic ---
        defaults = [
            f"Hmm '{text}' — interesting! Thoda aur batao iske baare mein?",
            f"Main sun raha hun! '{text}' ke baare mein aur detail do to zyada help kar sakta hun.",
            f"Got it! '{text}' — aur kuch add karna hai ya isi pe kaam karein?",
            f"Samajh gaya! Tum '{text}' bol rahe ho — batao aage kya karna hai?",
            f"Roger that! '{text}' received. Ab batao next step kya hai?",
        ]
        return random.choice(defaults)

    # ---- Keyboard shortcuts ----
    def keyPressEvent(self, event):
        key = event.key()
        mod = event.modifiers()
        ctrl = mod & Qt.KeyboardModifier.ControlModifier

        if ctrl:
            if key == Qt.Key.Key_1:
                self._switch_page(0)
            elif key == Qt.Key.Key_2:
                self._switch_page(1)
            elif key == Qt.Key.Key_3:
                self._switch_page(2)
            elif key == Qt.Key.Key_4:
                self._switch_page(3)
            elif key == Qt.Key.Key_N:
                self._new_session()
            elif key == Qt.Key.Key_L:
                self.chat_page._input.setFocus()
            elif key == Qt.Key.Key_Slash or key == Qt.Key.Key_Question:
                self._show_shortcuts_overlay()
            else:
                super().keyPressEvent(event)
        elif key == Qt.Key.Key_Escape:
            # Close shortcuts overlay if open
            if hasattr(self, '_shortcut_overlay') and self._shortcut_overlay.isVisible():
                self._shortcut_overlay.hide()
            elif self.pages.currentIndex() != 0:
                self._switch_page(0)
        else:
            super().keyPressEvent(event)

    def _show_shortcuts_overlay(self):
        """Show/hide keyboard shortcuts overlay."""
        if hasattr(self, '_shortcut_overlay') and self._shortcut_overlay.isVisible():
            self._shortcut_overlay.hide()
            return

        if not hasattr(self, '_shortcut_overlay'):
            self._shortcut_overlay = QFrame(self)
            self._shortcut_overlay.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0,y1:0,x2:0.1,y2:1,
                        stop:0 rgba(40,50,72,0.88), stop:0.06 rgba(30,38,58,0.82),
                        stop:0.5 rgba(20,28,44,0.78), stop:1 rgba(14,20,36,0.75));
                    border:1px solid rgba(143,245,255,0.22);
                    border-top:2px solid rgba(200,252,255,0.42);
                    border-left:1px solid rgba(200,252,255,0.18);
                    border-radius:20px;
                }}
            """)
            o_lay = QVBoxLayout(self._shortcut_overlay)
            o_lay.setContentsMargins(28, 20, 28, 20)
            o_lay.setSpacing(6)

            title = QLabel("KEYBOARD SHORTCUTS")
            title.setStyleSheet(f"""
                color:{C_PRIMARY}; font-family:'{_FONT}'; font-size:14px;
                font-weight:700; letter-spacing:3px; border:none; background:transparent;
            """)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            o_lay.addWidget(title)
            o_lay.addSpacing(8)

            shortcuts = [
                ("Ctrl+1", "Chat Page"),
                ("Ctrl+2", "Voice Page"),
                ("Ctrl+3", "System Dashboard"),
                ("Ctrl+4", "Settings"),
                ("Ctrl+N", "New Session"),
                ("Ctrl+L", "Focus Chat Input"),
                ("Ctrl+/", "Toggle This Overlay"),
                ("Escape", "Back to Chat / Close"),
                ("Enter", "Send Message"),
                ("Shift+Enter", "New Line in Input"),
            ]
            for key, desc in shortcuts:
                row = QHBoxLayout()
                key_lbl = QLabel(key)
                key_lbl.setFixedWidth(120)
                key_lbl.setStyleSheet(f"""
                    color:{C_PRIMARY_BOLD}; font-family:'{_MONO}'; font-size:12px;
                    font-weight:700; border:none; background:rgba(143,245,255,0.06);
                    padding:4px 10px; border-radius:6px;
                """)
                row.addWidget(key_lbl)
                desc_lbl = QLabel(desc)
                desc_lbl.setStyleSheet(f"""
                    color:{C_TEXT_DIM}; font-family:'{_FONT}'; font-size:12px;
                    border:none; background:transparent;
                """)
                row.addWidget(desc_lbl, 1)
                o_lay.addLayout(row)

            o_lay.addSpacing(8)
            close_hint = QLabel("Press Ctrl+/ or Escape to close")
            close_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            close_hint.setStyleSheet(f"""
                color:{C_TEXT_MUTED}; font-family:'{_FONT}'; font-size:10px;
                font-style:italic; border:none; background:transparent;
            """)
            o_lay.addWidget(close_hint)

        # Position center of window
        ow, oh = 400, 420
        self._shortcut_overlay.setFixedSize(ow, oh)
        self._shortcut_overlay.move(
            (self.width() - ow) // 2,
            (self.height() - oh) // 2
        )
        self._shortcut_overlay.show()
        self._shortcut_overlay.raise_()

    def _switch_page(self, idx):
        self.sidebar._select(idx)

    def _new_session(self):
        """Clear chat and start fresh session."""
        # Clear ALL items from chat layout
        chat_lay = self.chat_page._chat_lay
        while chat_lay.count():
            item = chat_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
        # Re-add stretch at top (pushes messages to bottom)
        chat_lay.addStretch(1)
        # Re-add welcome message
        welcome_text = (f"Welcome to Shell OS {APP_VERSION}\n"
                        f"Created by {APP_CREATOR}\n\n"
                        "Desktop AI assistant with chat, voice, tools, files, browser/system actions, and diagnostics.\n"
                        "Actions depend on configured providers, permissions, and available platform support.\n\n"
                        "What I can do:\n"
                        "- Code: write, run & create full apps\n"
                        "- System: specs, processes, diagnostics, cleanup, power\n"
                        "- Files: PDF, zip, organize, convert, OCR\n"
                        "- Media: AI image generation, video tools, music\n"
                        "- Network: ping, DNS, ports, WiFi passwords\n"
                        "- Security: encrypt, hash, passwords, QR codes\n"
                        "- Productivity: todo, timer, alarm, pomodoro, notes\n"
                        "- Market: stock prices, crypto rates\n"
                        "- Control: open/close apps, keyboard, mouse, volume\n"
                        "- Download: files, YouTube audio\n"
                        "- Fun: games, quiz, trivia\n\n"
                        "Just type what you want. I will run real tools when they are ready, or tell you what setup is missing.")
        self.chat_page.add_message("shell", welcome_text)
        # Clear chat history and AI context
        self._chat_history = []
        # Reset token counter
        self.top_bar.reset_tokens()

        self.chat_page._input.clear()
        self.chat_page._input.setFocus()
        self._sfx.play_click()
        if hasattr(self, '_toast'):
            self._toast.show_toast("New session started", "success", 2000)

        # Create a fresh persistent session and refresh the sidebar list.
        try:
            if getattr(self, "_history_store", None) is not None:
                self._current_session = self._history_store.new_session()
                if getattr(self.sidebar, "history_list", None) is not None:
                    self.sidebar.history_list.refresh()
                self._schedule_history_save()
        except Exception as _e:
            logger.debug("new persistent session failed: %s", _e)

    # ---- Chat history persistence helpers ----
    def _schedule_history_save(self):
        """Debounced flush — restart the 2s timer on every change."""
        try:
            t = getattr(self, "_history_save_timer", None)
            if t is not None:
                t.start()
        except Exception as _e:
            logger.debug("schedule history save failed: %s", _e)

    def _flush_history_store(self):
        try:
            if getattr(self, "_history_store", None) is not None:
                self._history_store.flush()
        except Exception as _e:
            logger.debug("flush history store failed: %s", _e)

    def _record_user_message(self, text):
        """Append a user turn to the active session, derive a title if it
        was the first user message, and queue a debounced save."""
        try:
            if not text or getattr(self, "_history_store", None) is None:
                return
            sess = getattr(self, "_current_session", None)
            if sess is None:
                sess = self._history_store.current_session()
                self._current_session = sess
            sess.add_message("user", text)
            sess.auto_title_from_first_user()
            self._history_store.save(sess)
            self._history_store.set_current(sess.id)
            if getattr(self.sidebar, "history_list", None) is not None:
                self.sidebar.history_list.refresh()
            self._schedule_history_save()
        except Exception as _e:
            logger.debug("record user message failed: %s", _e)

    def _record_agent_message(self, text):
        """Append an agent reply to the active session + queue save."""
        try:
            if not text or getattr(self, "_history_store", None) is None:
                return
            sess = getattr(self, "_current_session", None)
            if sess is None:
                sess = self._history_store.current_session()
                self._current_session = sess
            sess.add_message("shell", text)
            self._history_store.save(sess)
            if getattr(self.sidebar, "history_list", None) is not None:
                self.sidebar.history_list.refresh()
            self._schedule_history_save()
        except Exception as _e:
            logger.debug("record agent message failed: %s", _e)

    def _on_history_session_clicked(self, session_id):
        """User picked a row in the sidebar history list — switch the chat
        pane over to that conversation with a smooth fade."""
        try:
            if getattr(self, "_history_store", None) is None:
                return
            sess = self._history_store.load(session_id)
            if sess is None:
                return
            self._current_session = sess
            self._history_store.set_current(sess.id)
            self._load_session_into_chat(sess)
            if getattr(self.sidebar, "history_list", None) is not None:
                self.sidebar.history_list.set_active(sess.id)
            self._schedule_history_save()
        except Exception as _e:
            logger.debug("history session click failed: %s", _e)

    def _on_history_rename(self, session_id, new_title):
        try:
            if getattr(self, "_history_store", None) is None:
                return
            self._history_store.rename(session_id, new_title)
            if getattr(self.sidebar, "history_list", None) is not None:
                self.sidebar.history_list.refresh()
            self._schedule_history_save()
        except Exception as _e:
            logger.debug("history rename failed: %s", _e)

    def _on_history_delete(self, session_id):
        try:
            if getattr(self, "_history_store", None) is None:
                return
            cur = getattr(self, "_current_session", None)
            self._history_store.delete(session_id)
            if cur and cur.id == session_id:
                # Deleted the active session — start a fresh one.
                self._current_session = self._history_store.new_session()
                self._load_session_into_chat(self._current_session)
            if getattr(self.sidebar, "history_list", None) is not None:
                self.sidebar.history_list.refresh()
            self._schedule_history_save()
        except Exception as _e:
            logger.debug("history delete failed: %s", _e)

    def _load_session_into_chat(self, session):
        """Wipe the chat pane and re-render every message of `session`,
        with a soft fade-in (220ms OutCubic)."""
        try:
            chat_lay = self.chat_page._chat_lay
            while chat_lay.count():
                item = chat_lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    while item.layout().count():
                        child = item.layout().takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
            chat_lay.addStretch(1)
            self.chat_page._empty_state = None

            # Re-mirror into the in-memory `_chat_history` list so the AI
            # worker sees the same context.
            self._chat_history = []
            rendered = 0
            for m in (session.messages or []):
                role = m.get("role") or "shell"
                txt = m.get("text") or ""
                if not txt:
                    continue
                self.chat_page.add_message(role, txt)
                self._chat_history.append((role, txt))
                rendered += 1

            if rendered == 0 and hasattr(self.chat_page, "show_empty_state"):
                self.chat_page.show_empty_state()

            # Smooth fade — 220ms OutCubic on the chat container.
            try:
                container = self.chat_page._chat_w
                eff = QGraphicsOpacityEffect(container)
                eff.setOpacity(0.0)
                container.setGraphicsEffect(eff)
                anim = QPropertyAnimation(eff, b"opacity", container)
                anim.setDuration(220)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                anim.finished.connect(lambda c=container: c.setGraphicsEffect(None))
                anim.start()
                container._fade_anim = anim
            except Exception as _e:
                logger.debug("session fade failed: %s", _e)
        except Exception as _e:
            logger.debug("load session into chat failed: %s", _e)

    def _update_uptime(self):
        elapsed = int(_time.time() - self._uptime_start)
        days = elapsed // 86400
        hours = (elapsed % 86400) // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        uptime_str = f"UPTIME: {days:03d}:{hours:02d}:{mins:02d}:{secs:02d}"
        if hasattr(self, 'system_page') and hasattr(self.system_page, '_uptime_label'):
            self.system_page._uptime_label.setText(uptime_str)

    # ---- Theme switching ----
    def _switch_theme(self, theme_name):
        """Switch the active theme through the shared ThemeEngine."""
        try:
            te = ThemeEngine.get()
            if te.active_name != theme_name:
                te.switch(theme_name)
        except Exception as _e:
            logger.debug("theme switch failed: %s", _e)

    def _on_theme_change(self, theme_name):
        """Rebuild the entire UI when theme changes, preserving chat history.

        TEARDOWN ORDER MATTERS — without it, theme cycling crashes:
          1. Disconnect backend signals from the soon-to-be-deleted pages
             (SocketIO emits would otherwise fire into deleted Qt objects).
          2. Stop every timer on the voice page (visualizer, waveform,
             stage, session, pulse). Orphan timers tick into deleted
             widgets → segfault.
          3. Drop the old toast widget if any (its _anim_timer ticks
             every 16 ms forever; we don't want N copies).
          4. THEN call _build_ui() to swap in the new tree.
        """
        _clear_icon_cache()  # Icons need re-rendering with new theme colors
        # Store current page and chat messages
        current_page = self.pages.currentIndex()
        saved_messages = list(getattr(self, '_chat_history', []))

        # ---- 1) Disconnect backend signals from old pages ----
        try:
            if getattr(self, '_sio', None) is not None:
                for sig in ('connection_status', 'agent_speaking', 'agent_thinking', 'user_speaking',
                            'system_stats', 'voice_amplitude', 'agent_reply',
                            'user_message', 'tool_event', 'api_key_update',
                            'safety_warning', 'deep_research'):
                    try:
                        getattr(self._sio, sig).disconnect()
                    except Exception:
                        pass
            if getattr(self, '_lk', None) is not None:
                try:
                    self._lk.audio_amplitude.disconnect()
                except Exception:
                    pass
        except Exception as _e:
            logger.debug("theme: signal disconnect failed: %s", _e)

        # ---- 2) Stop all timers on the old voice page ----
        try:
            vp = getattr(self, 'voice_page', None)
            if vp is not None:
                for path in (
                    ('visualizer', '_tick_timer'),
                    ('waveform', '_t'),
                    ('stage', '_timer'),
                ):
                    try:
                        sub = getattr(vp, path[0], None)
                        t = getattr(sub, path[1], None) if sub is not None else None
                        if t is not None:
                            t.stop()
                    except Exception:
                        pass
                for tname in ('_pulse_timer', '_session_timer'):
                    try:
                        t = getattr(vp, tname, None)
                        if t is not None:
                            t.stop()
                    except Exception:
                        pass
        except Exception as _e:
            logger.debug("theme: voice timer stop failed: %s", _e)

        try:
            sp = getattr(self, 'system_page', None)
            if sp is not None and hasattr(sp, "stop_animations"):
                sp.stop_animations()
        except Exception as _e:
            logger.debug("theme: system timer stop failed: %s", _e)

        try:
            tp = getattr(self, 'tools_page', None)
            if tp is not None and hasattr(tp, "stop_workers"):
                tp.stop_workers()
        except Exception as _e:
            logger.debug("theme: tools worker stop failed: %s", _e)
        try:
            self._stop_backend_command_workers()
        except Exception as _e:
            logger.debug("theme: backend command worker stop failed: %s", _e)

        # ---- 3) Drop the old toast (its 16ms _anim_timer would leak) ----
        try:
            old_toasts = getattr(self, 'toasts', None)
            if old_toasts is not None and hasattr(old_toasts, "close"):
                old_toasts.close()
            self.toasts = None
            old_toast = getattr(self, '_toast', None)
            if old_toast is not None:
                try:
                    if hasattr(old_toast, '_anim_timer'):
                        old_toast._anim_timer.stop()
                    if hasattr(old_toast, '_dismiss_timer'):
                        old_toast._dismiss_timer.stop()
                except Exception:
                    pass
                try:
                    old_toast.deleteLater()
                except Exception:
                    pass
                self._toast = None
        except Exception as _e:
            logger.debug("theme: toast cleanup failed: %s", _e)

        # Drop top-level/host-parented helpers that _build_ui recreates.
        # Otherwise theme cycling stacks duplicate shortcuts and global hotkeys.
        for attr in ('_quick_hotkey', '_quick_launcher', '_avatar_menu',
                     '_command_palette', '_shortcut_help', '_notif_center',
                     '_cmdp_shortcut', '_help_shortcut', '_notif_store'):
            obj = getattr(self, attr, None)
            if obj is None:
                continue
            try:
                if hasattr(obj, "stop"):
                    obj.stop()
                if hasattr(obj, "dismiss"):
                    obj.dismiss()
                if hasattr(obj, "hide"):
                    obj.hide()
                if hasattr(obj, "close"):
                    obj.close()
                if hasattr(obj, "setEnabled"):
                    obj.setEnabled(False)
                if hasattr(obj, "deleteLater"):
                    obj.deleteLater()
            except Exception as _e:
                logger.debug("theme: cleanup failed for %s: %s", attr, _e)
            setattr(self, attr, None)

        # Rebuild palette
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(C_BG))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(C_TEXT))
        pal.setColor(QPalette.ColorRole.Base, QColor(C_BG))
        pal.setColor(QPalette.ColorRole.Text, QColor(C_TEXT))
        self.setPalette(pal)

        # Also set app palette
        app = QApplication.instance()
        if app:
            app_pal = app.palette()
            app_pal.setColor(QPalette.ColorRole.Window, QColor(C_BG))
            app_pal.setColor(QPalette.ColorRole.WindowText, QColor(C_TEXT))
            app_pal.setColor(QPalette.ColorRole.Base, QColor(C_BG))
            app_pal.setColor(QPalette.ColorRole.Text, QColor(C_TEXT))
            app_pal.setColor(QPalette.ColorRole.Button, QColor(C_SURFACE_HIGH))
            app_pal.setColor(QPalette.ColorRole.ButtonText, QColor(C_TEXT))
            app_pal.setColor(QPalette.ColorRole.Highlight, QColor(C_PRIMARY_BOLD))
            app_pal.setColor(QPalette.ColorRole.HighlightedText, QColor(C_BG))
            app.setPalette(app_pal)

        # Rebuild UI, then reconnect backend signals to the new widgets.
        old_central = self.centralWidget()
        self._build_ui()
        if old_central:
            old_central.deleteLater()

        # Restore chat history into new chat page
        for role, text in saved_messages:
            self.chat_page.add_message(role, text)

        # Restore page
        self.pages.setCurrentIndex(current_page)
        self.sidebar._active = current_page
        self.sidebar._apply_styles()
        self.top_bar.set_context(
            ["CORE INTERFACE", "VOICE CORE", "SYSTEM DASHBOARD", "TOOLS / MCP", "CONFIGURATION"][current_page])

        # Reconnect backend signals to new widgets
        if self._sio:
            try:
                self._connect_socketio_signals(self._sio)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
        if self._lk:
            try:
                self._lk.audio_amplitude.connect(self._on_voice)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
        # Reuse existing toast (don't leak old one)
        self._toast = ToastNotification(self)
        self._toast.show_toast(f"Theme: {theme_name}", "info", 2000)

    def _on_tts_start(self):
        """TTS started speaking — update orb and status."""
        if self.orb:
            self.orb.set_speaking(True)
        ctx = self.top_bar.context_lbl.text()
        if not ctx.endswith(" · speaking"):
            self.top_bar.set_context(ctx + " · speaking")

    def _on_tts_stop(self):
        """TTS finished speaking."""
        if self.orb:
            self.orb.set_speaking(False)
        ctx = self.top_bar.context_lbl.text()
        if ctx.endswith(" · speaking"):
            self.top_bar.set_context(ctx.replace(" · speaking", ""))

    def _on_tts_latency_event(self, event, payload):
        try:
            logger.info("TTS latency %s %s", event, payload)
            if isinstance(payload, dict) and "elapsed_ms" in payload:
                try:
                    from core.performance import LOW_LATENCY_RECORDER
                    LOW_LATENCY_RECORDER.record(
                        f"tts.{event}",
                        float(payload.get("elapsed_ms") or 0.0),
                        engine=payload.get("engine", ""),
                    )
                except Exception:
                    pass
            if event in {"warmup", "playback_started", "finished"} and hasattr(self, "system_page"):
                elapsed = payload.get("elapsed_ms") if isinstance(payload, dict) else "?"
                engine = payload.get("engine", "") if isinstance(payload, dict) else ""
                self.system_page.add_log_entry("TTS Latency", f"{event}: {elapsed}ms {engine}", "INFO")
        except Exception as exc:
            logger.debug("tts latency event failed: %s", exc)

    def _on_tts_error(self, message):
        msg = str(message or "Audio output unavailable")
        logger.warning("TTS playback failed: %s", msg)
        try:
            self.system_page.add_log_entry("TTS Error", msg[:80], "ERROR")
        except Exception:
            pass
        try:
            if self.pages.currentWidget() is self.voice_page:
                self.voice_page.set_error_state(msg[:180])
        except Exception:
            pass
        try:
            if hasattr(self, "toasts") and self.toasts is not None:
                self.toasts.show_error("Voice output failed", msg[:120], 4200)
            elif hasattr(self, "_toast"):
                self._toast.show_toast(f"Voice output failed: {msg[:120]}", "error", 4200)
        except Exception:
            pass

    def _toggle_voice_output(self):
        """Toggle Shell voice output on/off."""
        self._voice_output_enabled = not self._voice_output_enabled
        self._tts.set_enabled(self._voice_output_enabled)
        if not self._voice_output_enabled:
            self._tts.stop_speaking()
        # Update button
        if hasattr(self, '_voice_toggle_btn'):
            icon_name = "voice" if self._voice_output_enabled else "mute"
            color = C_PRIMARY if self._voice_output_enabled else C_TEXT_MUTED
            self._voice_toggle_btn.setIcon(QIcon(_make_icon_pixmap(icon_name, 16, color)))
            self._voice_toggle_btn.setToolTip(
                "Voice ON — Shell speaks replies" if self._voice_output_enabled
                else "Voice OFF — Silent mode"
            )
        # Save preference
        import json
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shell_settings.json")
        cfg = {}
        try:
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    cfg = json.load(f)
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        cfg["voice_output"] = self._voice_output_enabled
        cfg["tts_enabled"] = self._voice_output_enabled
        try:
            with open(cfg_path, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        if hasattr(self, '_toast'):
            self._toast.show_toast(
                "Voice ON" if self._voice_output_enabled else "Voice OFF",
                "success" if self._voice_output_enabled else "info", 1500)
        result = _sync_settings_backend({
            "voice_output": self._voice_output_enabled,
            "tts_enabled": self._voice_output_enabled,
        })
        if not result.get("ok"):
            logger.debug("voice output backend sync failed: %s", result.get("error") or result.get("message"))

    def closeEvent(self, e):
        # Flush any pending chat history changes before we tear down.
        try:
            self._flush_history_store()
        except Exception as _e:
            logger.debug("history flush on close failed: %s", _e)

        for timer_name in ("_history_save_timer", "_tele_timer", "_uptime_timer"):
            try:
                timer = getattr(self, timer_name, None)
                if timer is not None:
                    timer.stop()
            except Exception as _e:
                logger.debug("timer stop failed (%s): %s", timer_name, _e)

        try:
            self._stop_voice_listener()
        except Exception as _e:
            logger.debug("voice listener stop on close failed: %s", _e)

        for worker_name in ("_ai_worker", "_voice_worker"):
            try:
                worker = getattr(self, worker_name, None)
                if worker is not None and worker.isRunning():
                    worker.requestInterruption()
                    worker.wait(1000)
            except Exception as _e:
                logger.debug("worker wait failed (%s): %s", worker_name, _e)

        try:
            if hasattr(self, "tools_page") and self.tools_page is not None:
                self.tools_page.stop_workers()
        except Exception as _e:
            logger.debug("tools page stop on close failed: %s", _e)

        try:
            self._stop_backend_command_workers()
        except Exception as _e:
            logger.debug("backend command worker stop on close failed: %s", _e)

        if hasattr(self, "_tts") and self._tts:
            try:
                self._tts.shutdown()
                self._tts.wait(2000)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
        if hasattr(self, "_sio") and self._sio:
            try:
                self._sio.stop()
                self._sio.wait(2000)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
        if hasattr(self, "_lk") and self._lk:
            try:
                self._lk.stop()
                self._lk.wait(2000)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
        try:
            hotkey = getattr(self, "_quick_hotkey", None)
            if hotkey is not None and hasattr(hotkey, "stop"):
                hotkey.stop()
        except Exception as _e:
            logger.debug("quick hotkey stop failed: %s", _e)
        try:
            if getattr(self, "toasts", None) is not None and hasattr(self.toasts, "close"):
                self.toasts.close()
        except Exception as _e:
            logger.debug("toast manager close failed: %s", _e)
        super().closeEvent(e)


# =====================================================================
#  Entry Point
# =====================================================================

def main():
    global _FONT, _MONO
    print(f"Starting Shell OS {APP_VERSION} — Created by {APP_CREATOR}...")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Re-resolve fonts now that QApp exists
    _FONT = _pick_font(["Arial", "Segoe UI", "Helvetica Neue", "Noto Sans"], "Arial")
    _MONO = _pick_font(["Cascadia Code", "Consolas", "SF Mono", "Menlo", "Courier New"], "Courier New")

    # Set application-wide font explicitly to avoid rendering issues
    app_font = QFont(_FONT)
    app_font.setPixelSize(13)
    app_font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(app_font)

    # Apply global glassmorphism-compatible palette
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(C_BG))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(C_TEXT))
    pal.setColor(QPalette.ColorRole.Base, QColor(C_BG))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(C_SURFACE_CONT))
    pal.setColor(QPalette.ColorRole.Text, QColor(C_TEXT))
    pal.setColor(QPalette.ColorRole.Button, QColor(C_SURFACE_HIGH))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(C_TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(C_PRIMARY_BOLD))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(C_BG))
    app.setPalette(pal)

    # Global glassmorphism tooltip styling
    app.setStyleSheet(f"""
        QToolTip {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 rgba(22,28,40,0.92), stop:1 rgba(14,20,32,0.88));
            border: 1px solid rgba(143,245,255,0.20);
            border-top: 1px solid rgba(143,245,255,0.35);
            border-radius: 10px;
            color: {C_TEXT};
            font-family: '{_FONT}';
            font-size: 11px;
            padding: 6px 12px;
        }}
    """)

    print("Import OK, launching window...")
    w = ShellHoloUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
