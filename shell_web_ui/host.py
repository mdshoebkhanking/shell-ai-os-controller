from __future__ import annotations

import json
import base64
import hashlib
import mimetypes
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

_ONLINE_CACHE_TIME = 0.0
_ONLINE_CACHE_VAL = False

def is_network_online() -> bool:
    import os
    if os.environ.get("SHELL_TEST_FORCE_OFFLINE") == "1":
        return False
    if os.environ.get("SHELL_TEST_FORCE_ONLINE") == "1":
        return True
    global _ONLINE_CACHE_TIME, _ONLINE_CACHE_VAL
    now = time.monotonic()
    if now - _ONLINE_CACHE_TIME < 5.0:
        return _ONLINE_CACHE_VAL
    
    online = False
    for host, port in [("8.8.8.8", 53), ("1.1.1.1", 53), ("www.google.com", 80)]:
        try:
            with socket.create_connection((host, port), timeout=0.8):
                online = True
                break
        except OSError:
            continue
    _ONLINE_CACHE_TIME = now
    _ONLINE_CACHE_VAL = online
    return online

try:
    from shell_offline_tts import offline_tts_status, prewarm_offline_tts, prime_offline_tts_cache, speak_offline_tts
except Exception:  # pragma: no cover - fallback keeps the host importable
    def offline_tts_status() -> dict[str, Any]:
        return {
            "success": True,
            "available": False,
            "engine": "kokoro",
            "reason": "Offline TTS service could not be imported.",
            "candidates": [],
        }

    def speak_offline_tts(_text: str) -> dict[str, Any]:
        return {
            "success": False,
            "available": False,
            "engine": "fallback",
            "message": "Offline TTS service could not be imported.",
        }

    def prewarm_offline_tts() -> dict[str, Any]:
        return {
            "success": False,
            "prewarmed": False,
            "engine": "fallback",
            "message": "Offline TTS service could not be imported.",
        }

    def prime_offline_tts_cache(_phrases: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
        return {
            "success": False,
            "primed": 0,
            "engine": "fallback",
            "message": "Offline TTS service could not be imported.",
        }

try:
    from shell_voice_runtime import TTSSpeaker
except Exception:  # pragma: no cover - cloud voice is optional in the host
    TTSSpeaker = None  # type: ignore

try:
    from shell_offline_llm import generate_offline_coding_reply, generate_offline_reply, offline_coding_llm_status, offline_llm_status
except Exception:  # pragma: no cover - fallback keeps the host importable
    def offline_llm_status() -> dict[str, Any]:
        return {
            "success": True,
            "available": False,
            "status": "fallback",
            "engine": "fallback",
            "reason": "Offline LLM service could not be imported.",
            "candidates": [],
        }

    def generate_offline_reply(_text: str, **_kwargs: Any) -> Any:
        class _FallbackResult:
            success = False
            reply = ""
            reason = "Offline LLM service could not be imported."

            def as_dict(self) -> dict[str, Any]:
                return {"success": False, "reply": "", "reason": self.reason}

        return _FallbackResult()

    def offline_coding_llm_status() -> dict[str, Any]:
        return {
            "success": True,
            "available": False,
            "status": "fallback",
            "engine": "fallback",
            "category": "coding",
            "reason": "Offline coding LLM service could not be imported.",
            "candidates": [],
        }

    def generate_offline_coding_reply(_text: str, **_kwargs: Any) -> Any:
        return generate_offline_reply(_text, **_kwargs)

try:
    from shell_offline_model_catalog import (
        CHAT_MODEL_CATEGORY,
        CODING_MODEL_CATEGORY,
        catalog_payload as offline_llm_catalog_payload,
        get_model_option as get_offline_model_option,
        model_install_dir as offline_model_install_dir,
        write_model_metadata as write_offline_model_metadata,
    )
except Exception:  # pragma: no cover - fallback keeps the host importable
    def offline_llm_catalog_payload(category: str = "chat") -> dict[str, Any]:
        return {
            "success": False,
            "category": category,
            "runtimeDownloads": True,
            "options": [],
            "installedModels": [],
            "reason": "Offline model catalog could not be imported.",
        }

    def get_offline_model_option(_model_id: str, category: str | None = None) -> Any:
        return None

    def offline_model_install_dir(model_id: str) -> Path:
        return PROJECT_ROOT / ".shell_runtime" / "models" / "llm" / str(model_id)

    def write_offline_model_metadata(_option: Any, *, model_path: Path, category: str | None = None) -> None:
        return None

    CHAT_MODEL_CATEGORY = "chat"
    CODING_MODEL_CATEGORY = "coding"


def _project_root() -> Path:
    for env_name in ("SHELL_APP_ROOT", "SHELL_INSTALL_ROOT"):
        configured = os.environ.get(env_name, "").strip()
        if not configured:
            continue
        candidate = Path(configured).resolve()
        if (candidate / "shell_web_ui").exists() and (candidate / "shell_tool_catalog.py").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = _project_root()
WEB_UI_ROOT = Path(__file__).resolve().parent
WEB_DIST_INDEX = WEB_UI_ROOT / "dist" / "index.html"
HISTORY_PATH = PROJECT_ROOT / ".shell_runtime" / "web_ui_history.json"
NOTES_PATH = PROJECT_ROOT / ".shell_runtime" / "web_ui_notes.json"
GALLERY_DIR = Path.home() / "Pictures" / "Shell_Generated"
GALLERY_META_PATH = PROJECT_ROOT / ".shell_runtime" / "web_ui_gallery.json"
GALLERY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
UPLOADS_DIR = PROJECT_ROOT / ".shell_runtime" / "uploads"
UPDATES_DIR = PROJECT_ROOT / ".shell_runtime" / "updates"
UPDATE_STATE_PATH = UPDATES_DIR / "update_state.json"
DEFAULT_UPDATE_REPO = "mdshoebkhanking/shell-ai-os-controller"
CRITICAL_OFFLINE_TTS_PHRASES = ("Command center ready.",)
ALLOWED_SHELL_LANGUAGES = {"hinglish", "english", "hindi"}
CHAT_PROVIDER_SECRET_GROUPS = (
    ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    ("OPENAI_API_KEY",),
    ("ANTHROPIC_API_KEY",),
    ("OPENROUTER_API_KEY",),
    ("GROQ_API_KEY",),
    ("MISTRAL_API_KEY",),
    ("TOGETHER_API_KEY",),
    ("HF_API_KEY", "HUGGINGFACE_API_KEY"),
)
CHAT_PROVIDER_PROBE_HOSTS = {
    "GOOGLE_API_KEY": "generativelanguage.googleapis.com",
    "GEMINI_API_KEY": "generativelanguage.googleapis.com",
    "OPENAI_API_KEY": "api.openai.com",
    "ANTHROPIC_API_KEY": "api.anthropic.com",
    "OPENROUTER_API_KEY": "openrouter.ai",
    "GROQ_API_KEY": "api.groq.com",
    "MISTRAL_API_KEY": "api.mistral.ai",
    "TOGETHER_API_KEY": "api.together.xyz",
    "HF_API_KEY": "huggingface.co",
    "HUGGINGFACE_API_KEY": "huggingface.co",
}
STALE_PROVIDER_FALLBACK_MARKERS = (
    "ai provider abhi available nahi hai",
    "ai provider not available",
    "ai provider is not available",
    "api key set karoge",
    "api key set karoge to main",
    "provider is not available",
    "provider not available",
    "provider unavailable",
    "no ai provider",
    "no provider available",
    "all brains failed",
    "set an api key",
    "missing api key",
    "api key missing",
)


def _shell_language() -> str:
    language = os.environ.get("SHELL_LANGUAGE", "").strip().lower()
    if language in ALLOWED_SHELL_LANGUAGES:
        return language
    try:
        from shell_settings_manager import get_settings

        stored = str(
            get_settings().get("shell_language") or get_settings().get("language") or ""
        ).strip().lower()
        if stored in ALLOWED_SHELL_LANGUAGES:
            return stored
    except Exception:
        pass
    return "hinglish"


def _shell_language_instruction() -> str:
    language = _shell_language()
    if language == "english":
        return "Reply in clear English only."
    if language == "hindi":
        return "Reply in simple Hindi. Use readable Hindi and keep it concise."
    return "Reply in natural Hinglish: Hindi and English mixed casually."


def _brand_icon_path() -> Path | None:
    for candidate in (
        WEB_UI_ROOT / "dist" / "shell-logo.png",
        WEB_UI_ROOT / "src" / "public" / "shell-logo.png",
        PROJECT_ROOT / "shell_ui" / "shell_logo.png",
        PROJECT_ROOT / "assets" / "brand" / "shell-official-logo.png",
    ):
        if candidate.exists():
            return candidate
    return None


def _json_response(data: Any = None, *, ok: bool = True, error: str = "") -> str:
    return json.dumps({"ok": ok, "data": data, "error": error}, ensure_ascii=False)


class ShellBackendBridge:
    """Pure Python backend bridge used by Electron and tests."""

    def __init__(self, parent: Any | None = None) -> None:
        self._parent = parent
        self._event_listeners: list[Callable[[str, Any], None]] = []
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._voice_listener = None
        self._voice_input_unavailable_state = False
        self._last_voice_amp_event = 0.0
        self._speech_process: subprocess.Popen[Any] | None = None
        self._speech_job_lock = threading.Lock()
        self._speech_job_id = 0
        self._chat_job_lock = threading.Lock()
        self._chat_job_id = 0
        self._history_lock = threading.RLock()
        self._cloud_tts_speaker: Any | None = None
        self._cloud_tts_fallback_text = ""
        self._chat_provider_network_cache: tuple[float, str, bool] = (0.0, "", False)
        self._offline_llm_download_lock = threading.Lock()
        self._offline_llm_downloads: dict[str, dict[str, Any]] = {}
        self._last_app_context: dict[str, Any] = {}
        self._offline_tts_critical_prime_ready = threading.Event()
        self._maybe_prewarm_offline_tts()

    def add_event_listener(self, listener: Callable[[str, Any], None]) -> None:
        if callable(listener) and listener not in self._event_listeners:
            self._event_listeners.append(listener)

    def _maybe_prewarm_offline_tts(self) -> None:
        if not self._env_flag_enabled("SHELL_OFFLINE_TTS_PREWARM", default=True):
            self._offline_tts_critical_prime_ready.set()
            return

        def run() -> None:
            try:
                prewarm_offline_tts()
                if self._env_flag_enabled("SHELL_OFFLINE_TTS_PRECACHE", default=True):
                    prime_offline_tts_cache(CRITICAL_OFFLINE_TTS_PHRASES)
                    self._offline_tts_critical_prime_ready.set()
                    prime_offline_tts_cache()
                else:
                    self._offline_tts_critical_prime_ready.set()
            except Exception:
                self._offline_tts_critical_prime_ready.set()

        self._start_background_task("ShellOfflineTTSPrewarm", run)

    def call(self, channel: str, payload: str = "[]") -> str:
        try:
            args = json.loads(payload or "[]")
            if not isinstance(args, list):
                args = [args]
            result = self._dispatch(str(channel or ""), args)
            return _json_response(result)
        except Exception as exc:
            return _json_response(None, ok=False, error=f"{exc}\n{traceback.format_exc()}")

    def emit_event(self, channel: str, payload: Any) -> None:
        for listener in list(self._event_listeners):
            try:
                listener(channel, payload)
            except Exception:
                pass

    def _next_speech_job_id(self) -> int:
        with self._speech_job_lock:
            self._speech_job_id += 1
            return self._speech_job_id

    def _current_speech_job_id(self) -> int:
        with self._speech_job_lock:
            return self._speech_job_id

    def _next_chat_job_id(self) -> str:
        with self._chat_job_lock:
            self._chat_job_id += 1
            return f"offline-chat-{int(time.time() * 1000)}-{self._chat_job_id}"

    def _invalidate_speech_jobs(self) -> None:
        with self._speech_job_lock:
            self._speech_job_id += 1

    def _start_background_task(self, name: str, target: Any) -> None:
        threading.Thread(target=target, name=name, daemon=True).start()

    def _dispatch(self, channel: str, args: list[Any]) -> Any:
        handlers = {
            "get-system-stats": self._system_stats,
            "get-installed-apps": self._installed_apps,
            "get-running-apps": self._running_apps,
            "get-history": self._get_history,
            "clear-history": self._clear_history,
            "add-message": self._add_message,
            "secure-get-keys": self._secure_keys,
            "secure-save-keys": self._secure_save_keys,
            "list-api-keys": self._list_api_keys,
            "get-settings": self._get_settings,
            "set-settings": self._set_settings,
            "get-personality": self._get_personality,
            "save-personality": self._save_personality,
            "set-personality": self._save_personality,
            "get-app-version": self._get_app_version,
            "check-vault-status": lambda _args: {"faceCount": 0, "pinConfigured": False},
            "verify-vault-pin": lambda _args: False,
            "setup-vault-pin": lambda _args: {"success": True},
            "setup-vault-face": lambda _args: {"success": True},
            "verify-vault-face": lambda _args: False,
            "check-for-updates": self._check_for_updates,
            "download-update": self._download_update,
            "install-update": self._install_update,
            "open-app": self._open_app,
            "close-app": self._close_app,
            "google-search": self._google_search,
            "execute-command": self._execute_command,
            "chat-message": self._chat_message,
            "offline-tts-status": self._offline_tts_status,
            "offline-llm-status": self._offline_llm_status,
            "offline-llm-catalog": self._offline_llm_catalog,
            "offline-llm-download": self._offline_llm_download,
            "offline-llm-select": self._offline_llm_select,
            "offline-coding-llm-status": self._offline_coding_llm_status,
            "offline-coding-llm-catalog": self._offline_coding_llm_catalog,
            "offline-coding-llm-download": self._offline_coding_llm_download,
            "offline-coding-llm-select": self._offline_coding_llm_select,
            "probe-voice-amplitude": self._probe_voice_amplitude,
            "speak-text": self._speak_text,
            "stop-speech": self._stop_speech,
            "start-voice": self._start_voice,
            "stop-voice": self._stop_voice,
            "set-voice-muted": self._set_voice_muted,
            "get-screen-source": lambda _args: None,
            "capture-app-context": self._capture_app_context,
            "adb-get-history": lambda _args: [],
            "adb-get-notifications": lambda _args: [],
            "adb-connect": lambda _args: {"success": False, "message": "ADB bridge is not connected."},
            "adb-disconnect": lambda _args: {"success": True, "message": "ADB disconnected."},
            "adb-quick-action": lambda _args: {"success": False, "message": "ADB bridge is not connected."},
            "adb-telemetry": lambda _args: {"success": False, "message": "ADB bridge is not connected."},
            "adb-screenshot": lambda _args: {"success": False, "message": "ADB bridge is not connected."},
            "search-memory": self._search_memory,
            "get-capabilities": self._get_capabilities,
            "execute-tool": self._execute_tool,
            "get-notes": self._get_notes,
            "save-note": self._save_note,
            "delete-note": self._delete_note,
            "get-gallery": self._get_gallery_images,
            "get-gallery-images": self._get_gallery_images,
            "save-image-to-gallery": self._save_image_to_gallery,
            "delete-image": self._delete_image,
            "open-image-location": self._open_image_location,
            "save-image-external": self._save_image_external,
            "toggle-overlay": lambda _args: {"success": True},
            "social-media-status": self._social_media_status,
            "social-media-connect": self._social_media_connect,
            "social-media-disconnect": self._social_media_disconnect,
        }
        handler = handlers.get(channel)
        if handler is None:
            return {"success": False, "message": f"Unhandled Shell UI channel: {channel}"}
        return handler(args)

    def _social_media_status(self, _args: list[Any]) -> dict[str, Any]:
        try:
            from shell_social_connector import social_connector
            
            statuses = {}
            for platform in ["whatsapp", "telegram", "instagram", "gmail"]:
                statuses[platform] = social_connector.get_status(platform)
            
            return {"success": True, "statuses": statuses}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _social_media_connect(self, args: list[Any]) -> dict[str, Any]:
        payload = args[0] if args and isinstance(args[0], dict) else {}
        platform = str(payload.get("platform") or "").lower().strip()
        if not platform:
            return {"success": False, "error": "Platform required"}
        
        from shell_social_connector import social_connector
        
        try:
            if platform == "whatsapp":
                phone = payload.get("phone_number")
                success, msg = social_connector.connect_whatsapp(phone)
                return {"success": success, "message": msg}
            elif platform == "telegram":
                token = payload.get("bot_token")
                success, msg = social_connector.connect_telegram(bot_token=token)
                return {"success": success, "message": msg}
            elif platform in ("instagram", "gmail"):
                # Run browser session capture in background thread to avoid freezing UI
                import threading
                
                def run_background_connect():
                    try:
                        if platform == "instagram":
                            success, msg = social_connector.connect_instagram()
                        else:
                            success, msg = social_connector.connect_gmail()
                        logger.info(f"Background connection for {platform} finished: {success}, {msg}")
                    except Exception as exc:
                        logger.error(f"Background connection for {platform} failed: {exc}")
                
                t = threading.Thread(target=run_background_connect, daemon=True)
                t.start()
                
                return {
                    "success": True,
                    "message": "Browser session launched. Please log in on the official site in Chrome."
                }
            else:
                return {"success": False, "error": f"Unknown platform: {platform}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _social_media_disconnect(self, args: list[Any]) -> dict[str, Any]:
        payload = args[0] if args and isinstance(args[0], dict) else {}
        platform = str(payload.get("platform") or "").lower().strip()
        if not platform:
            return {"success": False, "error": "Platform required"}
        
        from shell_social_connector import social_connector
        
        try:
            success = social_connector.disconnect(platform)
            return {"success": success, "message": f"{platform.title()} disconnected successfully!" if success else f"Failed to disconnect {platform}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_app_version(self, _args: list[Any] | None = None) -> str:
        try:
            return (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip() or "1.0.0"
        except Exception:
            return "1.0.0"

    @staticmethod
    def _version_parts(value: str) -> tuple[int, ...]:
        cleaned = str(value or "").strip().lstrip("vV")
        parts: list[int] = []
        for chunk in re.split(r"[^0-9]+", cleaned):
            if chunk == "":
                continue
            try:
                parts.append(int(chunk))
            except Exception:
                parts.append(0)
        return tuple(parts or [0])

    @classmethod
    def _version_newer(cls, remote: str, current: str) -> bool:
        left = list(cls._version_parts(remote))
        right = list(cls._version_parts(current))
        size = max(len(left), len(right))
        left.extend([0] * (size - len(left)))
        right.extend([0] * (size - len(right)))
        return tuple(left) > tuple(right)

    def _read_update_state(self) -> dict[str, Any]:
        try:
            data = json.loads(UPDATE_STATE_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_update_state(self, data: dict[str, Any]) -> None:
        UPDATES_DIR.mkdir(parents=True, exist_ok=True)
        UPDATE_STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _asset_download_url(asset: dict[str, Any]) -> str:
        return str(
            asset.get("download_url")
            or asset.get("browser_download_url")
            or asset.get("url")
            or ""
        ).strip()

    @classmethod
    def _best_windows_installer_asset(cls, assets: list[Any]) -> dict[str, Any]:
        candidates = [item for item in assets if isinstance(item, dict)]

        def score(asset: dict[str, Any]) -> int:
            name = str(asset.get("name") or asset.get("filename") or cls._asset_download_url(asset)).lower()
            value = 0
            if name.endswith(".exe"):
                value += 100
            if "setup" in name or "installer" in name:
                value += 50
            if "windows" in name or "win" in name:
                value += 30
            if "shell" in name:
                value += 10
            if name.endswith(".zip"):
                value -= 50
            return value

        scored = sorted(candidates, key=score, reverse=True)
        return scored[0] if scored and score(scored[0]) > 0 else {}

    @classmethod
    def _normalize_update_payload(cls, payload: dict[str, Any], source_url: str) -> dict[str, Any]:
        if "tag_name" in payload or "assets" in payload:
            asset = cls._best_windows_installer_asset(list(payload.get("assets") or []))
            version = str(payload.get("tag_name") or payload.get("name") or "").lstrip("vV")
            return {
                "version": version,
                "releaseNotes": str(payload.get("body") or payload.get("releaseNotes") or "").strip(),
                "downloadUrl": cls._asset_download_url(asset),
                "assetName": str(asset.get("name") or "").strip(),
                "sha256": str(asset.get("sha256") or payload.get("sha256") or "").strip(),
                "sourceUrl": source_url,
            }
        return {
            "version": str(payload.get("version") or payload.get("tag") or "").lstrip("vV"),
            "releaseNotes": str(payload.get("releaseNotes") or payload.get("notes") or "").strip(),
            "downloadUrl": str(payload.get("installer_url") or payload.get("downloadUrl") or payload.get("download_url") or "").strip(),
            "assetName": str(payload.get("assetName") or payload.get("filename") or "").strip(),
            "sha256": str(payload.get("sha256") or "").strip(),
            "sourceUrl": source_url,
        }

    def _update_feed_url(self) -> str:
        configured = os.environ.get("SHELL_UPDATE_MANIFEST_URL", "").strip()
        if configured:
            return configured
        repo = os.environ.get("SHELL_UPDATE_REPO", DEFAULT_UPDATE_REPO).strip()
        return f"https://api.github.com/repos/{repo}/releases/latest" if repo else ""

    def _fetch_update_payload(self, url: str) -> dict[str, Any]:
        if not url:
            raise RuntimeError("Update feed is not configured.")
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "ShellAI-Updater/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(2 * 1024 * 1024)
        data = json.loads(raw.decode("utf-8", errors="replace"))
        if not isinstance(data, dict):
            raise RuntimeError("Update feed returned invalid JSON.")
        return data

    def _check_for_updates(self, _args: list[Any]) -> dict[str, Any]:
        self.emit_event("updater-event", {"status": "checking", "data": {}})
        current = self._get_app_version()
        url = self._update_feed_url()
        try:
            payload = self._fetch_update_payload(url)
            update = self._normalize_update_payload(payload, url)
            latest = str(update.get("version") or "").strip()
            if latest and self._version_newer(latest, current):
                update.update(
                    {
                        "currentVersion": current,
                        "status": "available",
                        "canDownload": bool(update.get("downloadUrl")),
                    }
                )
                self._write_update_state(update)
                self.emit_event("updater-event", {"status": "available", "data": update})
                return {"success": True, **update}
            state = {
                "status": "idle",
                "currentVersion": current,
                "version": latest or current,
                "message": "System is up to date.",
                "sourceUrl": url,
            }
            self._write_update_state(state)
            self.emit_event("updater-event", {"status": "not-available", "data": state})
            return {"success": True, **state}
        except Exception as exc:
            message = f"Update check failed: {exc}"
            self.emit_event("updater-event", {"status": "error", "error": message})
            return {"success": False, "status": "error", "message": message, "currentVersion": current}

    @staticmethod
    def _safe_update_filename(url: str, version: str) -> str:
        name = Path(urllib.parse.urlparse(url).path).name
        if not name.lower().endswith(".exe"):
            name = f"ShellAI_Setup_{version or 'latest'}.exe"
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "ShellAI_Setup_latest.exe"
        return name

    @staticmethod
    def _sha256(path: Path) -> str:
        import hashlib

        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _download_update(self, _args: list[Any]) -> dict[str, Any]:
        state = self._read_update_state()
        url = str(state.get("downloadUrl") or "").strip()
        version = str(state.get("version") or "latest").strip()
        if not url:
            message = "No update installer URL is available. Check for updates first."
            self.emit_event("updater-event", {"status": "error", "error": message})
            return {"success": False, "status": "error", "message": message}
        if not urllib.parse.urlparse(url).path.lower().endswith(".exe"):
            message = "Latest release does not include a Windows .exe installer asset yet."
            self.emit_event("updater-event", {"status": "error", "error": message})
            return {"success": False, "status": "error", "message": message}

        UPDATES_DIR.mkdir(parents=True, exist_ok=True)
        target = UPDATES_DIR / self._safe_update_filename(url, version)
        temp_target = target.with_suffix(target.suffix + ".download")
        self.emit_event("updater-event", {"status": "downloading", "data": {"percent": 0}})
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ShellAI-Updater/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response, temp_target.open("wb") as fh:
                total = int(response.headers.get("Content-Length") or "0")
                received = 0
                while True:
                    chunk = response.read(1024 * 512)
                    if not chunk:
                        break
                    fh.write(chunk)
                    received += len(chunk)
                    if total > 0:
                        percent = max(1, min(99, round((received / total) * 100)))
                        self.emit_event("updater-event", {"status": "downloading", "data": {"percent": percent}})
            temp_target.replace(target)
            expected = str(state.get("sha256") or "").strip().lower()
            if expected and self._sha256(target).lower() != expected:
                target.unlink(missing_ok=True)
                raise RuntimeError("Downloaded installer checksum did not match the update manifest.")
            state.update({"status": "downloaded", "downloadedPath": str(target), "downloadedAt": time.time()})
            self._write_update_state(state)
            self.emit_event("updater-event", {"status": "downloaded", "data": {**state, "percent": 100}})
            return {"success": True, **state}
        except Exception as exc:
            try:
                temp_target.unlink(missing_ok=True)
            except Exception:
                pass
            message = f"Update download failed: {exc}"
            self.emit_event("updater-event", {"status": "error", "error": message})
            return {"success": False, "status": "error", "message": message}

    @staticmethod
    def _path_inside(child: Path, parent: Path) -> bool:
        try:
            child.resolve().relative_to(parent.resolve())
            return True
        except Exception:
            return False

    def _install_update(self, _args: list[Any]) -> dict[str, Any]:
        state = self._read_update_state()
        path = Path(str(state.get("downloadedPath") or ""))
        if not path.exists() or not path.suffix.lower() == ".exe":
            return {"success": False, "status": "error", "message": "Downloaded update installer was not found."}
        if not self._path_inside(path, UPDATES_DIR):
            return {"success": False, "status": "error", "message": "Refusing to launch installer outside Shell update cache."}
        if platform.system().lower() != "windows":
            return {
                "success": False,
                "status": "error",
                "message": "Update installer is ready, but launching .exe updates is only supported on Windows.",
                "downloadedPath": str(path),
            }
        try:
            subprocess.Popen([str(path)], cwd=str(PROJECT_ROOT), close_fds=True)
            return {"success": True, "status": "installing", "message": "Update installer launched.", "downloadedPath": str(path)}
        except Exception as exc:
            return {"success": False, "status": "error", "message": f"Could not launch update installer: {exc}"}

    def _system_stats(self, _args: list[Any]) -> dict[str, Any]:
        try:
            import psutil

            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=0.0)
            uptime_seconds = max(0, int(time.time() - psutil.boot_time()))
            uptime = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m"
            return {
                "cpu": f"{cpu:.0f}",
                "memory": {
                    "total": f"{memory.total / (1024 ** 3):.1f} GB",
                    "free": f"{memory.available / (1024 ** 3):.1f} GB",
                    "usedPercentage": f"{memory.percent:.0f}",
                },
                "temperature": self._temperature(),
                "os": {"type": platform.system() or sys.platform, "uptime": uptime},
            }
        except Exception:
            return {
                "cpu": "0",
                "memory": {"total": "0 GB", "free": "0 GB", "usedPercentage": "0"},
                "temperature": 0,
                "os": {"type": platform.system() or sys.platform, "uptime": "Unknown"},
            }

    def _temperature(self) -> int:
        try:
            import psutil

            temps = psutil.sensors_temperatures(fahrenheit=False)
            for entries in temps.values():
                for entry in entries:
                    if entry.current:
                        return int(entry.current)
        except Exception:
            pass
        return 42

    def _installed_apps(self, _args: list[Any]) -> list[dict[str, str]]:
        apps: list[str] = []
        if sys.platform == "darwin":
            for folder in (Path("/Applications"), Path.home() / "Applications"):
                if folder.exists():
                    apps.extend(p.stem for p in folder.glob("*.app"))
        elif sys.platform.startswith("linux"):
            desktop_dir = Path("/usr/share/applications")
            if desktop_dir.exists():
                apps.extend(p.stem.replace("-", " ").title() for p in desktop_dir.glob("*.desktop"))
        elif sys.platform == "win32":
            for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
                root = os.environ.get(key)
                if root and Path(root).exists():
                    apps.extend(p.name for p in Path(root).iterdir() if p.is_dir())
        if not apps:
            apps = ["Terminal", "Browser", "File Explorer", "System Settings", "Code Editor"]
        unique = sorted(dict.fromkeys(apps), key=str.lower)
        return [{"id": name.lower().replace(" ", "-"), "name": name} for name in unique[:250]]

    def _running_apps(self, _args: list[Any]) -> list[str]:
        try:
            import psutil

            names = []
            for proc in psutil.process_iter(["name"]):
                name = (proc.info.get("name") or "").strip()
                if name:
                    names.append(name)
            return sorted(dict.fromkeys(names), key=str.lower)[:80]
        except Exception:
            return ["Shell AI"]

    def _read_history_file(self) -> list[Any]:
        with self._history_lock:
            try:
                return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            except Exception:
                return []

    def _write_history_file(self, messages: list[Any]) -> None:
        with self._history_lock:
            HISTORY_PATH.write_text(
                json.dumps(self._visible_history_messages(messages)[-80:], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _get_history(self, _args: list[Any]) -> list[Any]:
        return self._visible_history_messages(self._read_history_file())

    def _clear_history(self, _args: list[Any]) -> dict[str, Any]:
        self._write_history_file([])
        self.emit_event("history-cleared", {"success": True})
        return {"success": True, "cleared": True}

    def _add_message(self, args: list[Any]) -> bool:
        messages = self._read_history_file()
        messages.append(args[0] if args else {})
        self._write_history_file(messages)
        return True

    def _secure_keys(self, _args: list[Any]) -> dict[str, str]:
        try:
            from shell_api_manager import get_configured_secret_value
        except Exception:
            def get_configured_secret_value(*keys: str) -> str:
                for key in keys:
                    value = os.environ.get(key, "")
                    if value:
                        return value
                return ""

        return {
            "geminiKey": get_configured_secret_value("GOOGLE_API_KEY", "GEMINI_API_KEY"),
            "groqKey": os.environ.get("GROQ_API_KEY", ""),
            "hfKey": get_configured_secret_value("HF_API_KEY", "HUGGINGFACE_API_KEY"),
            "tavilyKey": os.environ.get("TAVILY_API_KEY", ""),
            "livekitKey": os.environ.get("LIVEKIT_API_KEY", ""),
            "livekitSecret": os.environ.get("LIVEKIT_API_SECRET", ""),
            "livekitUrl": os.environ.get("LIVEKIT_URL", ""),
            "openaiKey": os.environ.get("OPENAI_API_KEY", ""),
            "openrouterKey": os.environ.get("OPENROUTER_API_KEY", ""),
            "mistralKey": os.environ.get("MISTRAL_API_KEY", ""),
            "googleSearchKey": os.environ.get("GOOGLE_SEARCH_API_KEY", ""),
            "searchEngineId": os.environ.get("SEARCH_ENGINE_ID", ""),
            "weatherKey": os.environ.get("OPENWEATHER_API_KEY", ""),
            "telegramToken": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            "telegramAllowedChatIds": os.environ.get("SHELL_TELEGRAM_ALLOWED_CHAT_IDS", ""),
            "telegramRemoteControlEnabled": os.environ.get("SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED", ""),
            "telegramAllowTerminal": os.environ.get("SHELL_TELEGRAM_ALLOW_TERMINAL", ""),
        }

    def _secure_save_keys(self, args: list[Any]) -> dict[str, Any]:
        keys = args[0] if args and isinstance(args[0], dict) else {}
        key_map = {
            "geminiKey": "GOOGLE_API_KEY",
            "groqKey": "GROQ_API_KEY",
            "hfKey": "HF_API_KEY",
            "tavilyKey": "TAVILY_API_KEY",
            "livekitKey": "LIVEKIT_API_KEY",
            "livekitSecret": "LIVEKIT_API_SECRET",
            "livekitUrl": "LIVEKIT_URL",
            "openaiKey": "OPENAI_API_KEY",
            "openrouterKey": "OPENROUTER_API_KEY",
            "mistralKey": "MISTRAL_API_KEY",
            "googleSearchKey": "GOOGLE_SEARCH_API_KEY",
            "searchEngineId": "SEARCH_ENGINE_ID",
            "weatherKey": "OPENWEATHER_API_KEY",
            "telegramToken": "TELEGRAM_BOT_TOKEN",
            "telegramAllowedChatIds": "SHELL_TELEGRAM_ALLOWED_CHAT_IDS",
            "telegramRemoteControlEnabled": "SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED",
            "telegramAllowTerminal": "SHELL_TELEGRAM_ALLOW_TERMINAL",
        }
        saved: list[str] = []
        skipped: list[str] = []
        rejected: dict[str, str] = {}
        try:
            from shell_api_manager import set_api_key
        except Exception as exc:
            return {"success": False, "saved": [], "error": str(exc)}

        for ui_key, env_key in key_map.items():
            value = str(keys.get(ui_key) or keys.get(env_key) or "").strip()
            if not value:
                skipped.append(env_key)
                continue
            ok, message = set_api_key(env_key, value)
            if ok:
                saved.append(env_key)
            else:
                rejected[env_key] = message
        return {"success": not rejected, "saved": saved, "skipped": skipped, "rejected": rejected}

    def _list_api_keys(self, _args: list[Any]) -> dict[str, Any]:
        try:
            from shell_api_manager import list_api_keys

            return {"success": True, "keys": list_api_keys()}
        except Exception as exc:
            return {"success": False, "keys": [], "error": str(exc)}

    def _get_settings(self, _args: list[Any]) -> dict[str, Any]:
        try:
            from shell_settings_manager import get_settings

            return get_settings()
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _set_settings(self, args: list[Any]) -> dict[str, Any]:
        try:
            from shell_settings_manager import set_settings

            payload = args[0] if args and isinstance(args[0], dict) else {}
            ok, message, applied = set_settings(payload)
            return {"success": ok, "message": message, "applied": applied}
        except Exception as exc:
            return {"success": False, "message": str(exc), "applied": {}}

    def _get_personality(self, _args: list[Any]) -> str:
        return os.environ.get("SHELL_PERSONALITY", "")

    def _save_personality(self, args: list[Any]) -> bool:
        value = str(args[0] if args else "")
        settings_path = PROJECT_ROOT / ".shell_runtime" / "web_ui_personality.txt"
        settings_path.write_text(value, encoding="utf-8")
        return True

    def _open_app(self, args: list[Any]) -> dict[str, Any]:
        app_name = str(args[0] if args else "").strip()
        if not app_name:
            return {"success": False, "error": "Missing app name"}
        try:
            from shell_tool_gateway import execute_tool_sync

            result = execute_tool_sync("shell_window_CTRL:open_app", {"app_title": app_name})
            return {"success": True, "result": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _close_app(self, args: list[Any]) -> dict[str, Any]:
        app_name = str(args[0] if args else "").strip()
        if not app_name:
            return {"success": False, "error": "Missing app name"}
        try:
            from shell_tool_gateway import execute_tool_sync

            result = execute_tool_sync("shell_window_CTRL:close_app", {"window_title": app_name})
            return {"success": True, "result": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _google_search(self, args: list[Any]) -> dict[str, Any]:
        query = str(args[0] if args else "").strip()
        if not query:
            return {"success": False, "error": "Missing query"}
        try:
            import webbrowser

            webbrowser.open(f"https://www.google.com/search?q={query}")
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _execute_command(self, args: list[Any]) -> dict[str, Any]:
        command = str(args[0] if args else "").strip()
        if not command:
            return {"success": False, "error": "Missing command"}
        try:
            from shell_tool_gateway import execute_tool_sync

            result = execute_tool_sync("shell_terminal:run_command_tool", {"command": command})
            return {"success": True, "result": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _capture_app_context(self, _args: list[Any] | None = None) -> dict[str, Any]:
        try:
            from shell_app_context import capture_app_context

            context = capture_app_context()
        except Exception as exc:
            context = {
                "app_type": "generic",
                "adapter": "generic",
                "app_name": "Unknown app",
                "title": "",
                "metadata": {"error": str(exc)[:240]},
                "captured_at": time.time(),
            }
        self._last_app_context = context if isinstance(context, dict) else {}
        return {"success": True, "context": self._last_app_context}

    @staticmethod
    def _fresh_app_context(context: Any) -> dict[str, Any]:
        if not isinstance(context, dict):
            return {}
        captured_at = float(context.get("captured_at") or 0)
        if captured_at and time.time() - captured_at > 180:
            return {}
        return context

    def _chat_message(self, args: list[Any]) -> dict[str, Any]:
        text = str(args[0] if args else "").strip()
        meta = args[1] if len(args) > 1 and isinstance(args[1], dict) else {}
        source = str(meta.get("source") or "text").strip().lower()
        entry = str(meta.get("entry") or "").strip().lower()
        if source not in {"text", "voice"}:
            source = "text"
        if not text:
            attachments_probe = meta.get("attachments") if isinstance(meta, dict) else None
            if not attachments_probe:
                return {"success": False, "reply": "Message empty hai.", "error": "Missing message"}

        previous_messages = self._read_history_file()
        attachments = self._prepare_chat_attachments(meta.get("attachments"))
        attachment_context = self._attachment_context(attachments)
        app_context = self._fresh_app_context(meta.get("app_context") or meta.get("appContext") or self._last_app_context)
        app_context_block = ""
        if app_context:
            try:
                from shell_app_context import context_prompt_block

                app_context_block = context_prompt_block(app_context)
            except Exception:
                app_context_block = ""
        processing_text = f"{text}\n\n{attachment_context}".strip() if attachment_context else text
        processing_text = f"{processing_text}\n\n{app_context_block}".strip() if app_context_block else processing_text
        display_text = text or "Attached file"
        if attachments:
            display_text = (
                f"{display_text}\n\nAttached: "
                + ", ".join(str(item.get("name") or "file") for item in attachments[:4])
            ).strip()
        messages = list(previous_messages)
        messages.append({"role": "user", "parts": [{"text": display_text}]})

        route: dict[str, Any] | None = None
        image_prompt = ""
        image_generation_started = False
        activity_descriptor: dict[str, Any] | None = None
        result: Any = None
        success = True
        ui_actions: list[dict[str, Any]] = []
        pending_permission: dict[str, Any] | None = None
        async_pending = False
        pending_chat_id = ""
        deferred_prompt = ""
        deferred_previous_messages: list[Any] | None = None
        try:
            identity_reply = self._creator_identity_reply(text, source=source)
            if identity_reply:
                reply = identity_reply
            else:
                self_identity_reply = self._self_identity_reply(text)
                if self_identity_reply:
                    reply = self_identity_reply
                else:
                    recall_reply = self._conversation_recall_reply(text, previous_messages)
                    if recall_reply:
                        reply = recall_reply
                    elif self._is_telemetry_chart_prompt(text, entry=entry):
                        reply = self._chart_summary_reply(text)
                    else:
                        direct_route = self._direct_tool_route(text)
                        if direct_route and direct_route.get("errorReply"):
                            reply = str(direct_route.get("errorReply") or "").strip()
                        else:
                            route = direct_route if direct_route and direct_route.get("tool") else None
                            approval_route = self._approval_route_from_history(text, previous_messages)
                            route = approval_route or route
                            if not route:
                                from shell_nl_router import route_natural_command

                                route = route_natural_command(text)
                            research_disabled_reply = ""
                            if self._is_research_route(route):
                                if not self._internet_research_allowed():
                                    research_disabled_reply = self._internet_research_disabled_reply()
                                else:
                                    route = self._prepare_internet_research_route(route, text)
                            elif not (route and route.get("tool")) and self._internet_research_needed(text):
                                if not self._internet_research_allowed():
                                    research_disabled_reply = self._internet_research_disabled_reply()
                                else:
                                    route = self._prepare_internet_research_route(self._web_research_route(text), text)
                            if research_disabled_reply:
                                reply = research_disabled_reply
                                result = {
                                    "status": "offline_research_disabled",
                                    "message": reply,
                                }
                                success = True
                                activity_descriptor = None
                            elif not (route and route.get("tool")):
                                image_prompt = self._extract_image_generation_prompt(text)
                                if image_prompt:
                                    route = self._image_generation_route(image_prompt)
                            if not research_disabled_reply and not (route and route.get("tool")) and self._has_command_intent(text):
                                route = self._orchestration_route(text)
                            if not research_disabled_reply and route and route.get("tool"):
                                if str(route.get("tool")) == "shell_image_ai:generate_image_tool":
                                    image_prompt = (
                                        self._clean_image_prompt(self._route_image_prompt(route))
                                        or self._extract_image_generation_prompt(text)
                                        or text
                                    )
                                    route_args = dict(route.get("args") or {})
                                    route_args["description"] = image_prompt
                                    route_args.setdefault("use_cache", False)
                                    route_args.setdefault("force_fresh", True)
                                    route = {**route, "args": route_args}
                                    image_generation_started = True
                                    self.emit_event(
                                        "image-gen",
                                        {
                                            "prompt": image_prompt,
                                            "loading": True,
                                            "url": "",
                                            "source": source,
                                            "entry": entry,
                                        },
                                    )
                                else:
                                    route = self._prepare_artifact_route(route, previous_messages=previous_messages)
                                    route = self._prepare_code_build_route(route)
                                if self._route_needs_user_permission(route):
                                    permission_prompt = self._permission_prompt_for_route(route)
                                    reply = str(permission_prompt.get("user_message") or "").strip()
                                    ui_actions = list(permission_prompt.get("ui_actions") or [])
                                    pending_permission = permission_prompt.get("pending_permission") if isinstance(permission_prompt.get("pending_permission"), dict) else None
                                    result = {"status": "permission_required", "message": reply}
                                    success = True
                                    activity_descriptor = None
                                    image_generation_started = False
                                    route = {**route, "mode": "permission-required", "modeLabel": "Permission required"}
                                else:
                                    mode_decision = None if self._is_research_route(route) else self._mode_decision_for_route(processing_text, route)
                                    if mode_decision and mode_decision.get("mode") == "local-basic-offered":
                                        route = {
                                            **route,
                                            "mode": "local-basic-offered",
                                            "modeLabel": "Local basic available",
                                            "modeDecision": mode_decision,
                                        }
                                        reply = str(mode_decision.get("message") or "").strip()
                                        result = {
                                            "status": "basic_offline_offered",
                                            "message": reply,
                                            "reason": mode_decision.get("reason", ""),
                                        }
                                        success = True
                                        activity_descriptor = None
                                        image_generation_started = False
                                    else:
                                        if mode_decision:
                                            route = {
                                                **route,
                                                "mode": str(mode_decision.get("mode") or "local"),
                                                "modeLabel": str(mode_decision.get("modeLabel") or "Local"),
                                                "modeDecision": mode_decision,
                                            }
                                        activity_descriptor = self._activity_descriptor(
                                            text,
                                            route,
                                            image_prompt=image_prompt,
                                        )
                                        self._emit_activity(
                                            activity_descriptor,
                                            status="running",
                                            progress=34 if image_generation_started else 22,
                                            source=source,
                                            entry=entry,
                                        )
                                        if isinstance(route, dict):
                                            route = {**route, "request": text}
                                        result = self._execute_routed_tool(route)
                                        self._emit_activity(
                                            activity_descriptor,
                                            status="running",
                                            message="FORMATTING RESULT",
                                            progress=82,
                                            source=source,
                                            entry=entry,
                                        )
                                        formatted_result = self._format_chat_result_payload(route, result)
                                        reply = str(formatted_result.get("user_message") or "").strip()
                                        ui_actions = list(formatted_result.get("ui_actions") or [])
                                        pending_permission = formatted_result.get("pending_permission") if isinstance(formatted_result.get("pending_permission"), dict) else None
                                        tool_success = self._activity_result_success(route, result, reply)
                                        self._emit_activity(
                                            activity_descriptor,
                                            status="done" if tool_success else "error",
                                            message="TASK COMPLETE" if tool_success else "TASK FAILED",
                                            progress=100,
                                            source=source,
                                            entry=entry,
                                        )
                            elif not research_disabled_reply:
                                if self._should_defer_offline_brain_reply():
                                    pending_chat_id = self._next_chat_job_id()
                                    async_pending = True
                                    deferred_prompt = processing_text
                                    deferred_previous_messages = previous_messages
                                    reply = "Local brain loading hai. Main answer background mein bana raha hoon..."
                                else:
                                    reply = self._brain_chat_fallback(processing_text, previous_messages=previous_messages)
            if entry == "chart":
                reply = self._compact_chat_reply(reply, limit=360)
        except Exception as exc:
            success = False
            reply = f"Shell backend error: {exc}"
            if image_generation_started:
                self.emit_event(
                    "image-gen",
                    {
                        "prompt": image_prompt or text,
                        "loading": False,
                        "url": "",
                        "error": True,
                        "errorMessage": str(exc),
                        "source": source,
                    },
                )
            self._emit_activity(
                activity_descriptor,
                status="error",
                message=str(exc),
                progress=100,
                source=source,
                entry=entry,
            )

        if success and self._is_stale_provider_fallback_reply(reply):
            reply = self._local_chat_answer(processing_text or text)

        model_message = {"role": "model", "parts": [{"text": reply}]}
        if route and isinstance(route, dict):
            mode_label = str(route.get("modeLabel") or "").strip()
            mode_value = str(route.get("mode") or "").strip()
            if mode_label:
                model_message["modeLabel"] = mode_label
            if mode_value:
                model_message["mode"] = mode_value
        if async_pending and pending_chat_id:
            model_message["pendingOfflineChatId"] = pending_chat_id
        if ui_actions:
            model_message["uiActions"] = ui_actions
        if pending_permission:
            model_message["pendingPermission"] = pending_permission
        messages.append(model_message)
        self._write_history_file(messages)
        self.emit_event(
            "chat-updated",
            {
                "reply": reply,
                "route": route,
                "success": success,
                "source": source,
                "voice": source == "voice" and not async_pending,
                "pending": async_pending,
                "ui_actions": ui_actions,
            },
        )
        if async_pending and pending_chat_id:
            self._start_background_task(
                "ShellOfflineChat",
                lambda prompt=deferred_prompt, previous=deferred_previous_messages, pending_id=pending_chat_id: (
                    self._finish_deferred_offline_brain_reply(
                        prompt,
                        previous_messages=previous,
                        pending_chat_id=pending_id,
                        source=source,
                        entry=entry,
                    )
                ),
            )
        return {
            "success": success,
            "reply": reply,
            "route": route,
            "result": result,
            "source": source,
            "pending": async_pending,
            "ui_actions": ui_actions,
        }

    def _should_defer_offline_brain_reply(self) -> bool:
        mode = os.environ.get("SHELL_OFFLINE_LLM_ASYNC_UI", "auto").strip().lower()
        if mode in {"0", "off", "false", "no", "disabled"}:
            return False
        if mode in {"1", "on", "true", "yes", "force"}:
            enabled = True
        else:
            enabled = (
                platform.system().lower().startswith("win")
                or getattr(sys, "frozen", False)
                or os.environ.get("SHELL_DESKTOP_BUNDLED", "").strip() == "1"
            )
        if not enabled or self._should_try_provider_chat():
            return False
        try:
            status = offline_llm_status()
        except Exception:
            return False
        return bool(isinstance(status, dict) and status.get("available") is True)

    def _finish_deferred_offline_brain_reply(
        self,
        prompt: str,
        *,
        previous_messages: list[Any] | None,
        pending_chat_id: str,
        source: str,
        entry: str,
    ) -> None:
        try:
            reply = self._brain_chat_fallback(prompt, previous_messages=previous_messages)
            if entry == "chart":
                reply = self._compact_chat_reply(reply, limit=360)
            if self._is_stale_provider_fallback_reply(reply):
                reply = self._local_chat_answer(prompt)
            if not str(reply or "").strip():
                reply = self._local_chat_answer(prompt)
        except Exception as exc:
            reply = f"Local brain error: {exc}"

        reply = str(reply or "").strip()
        self._replace_pending_offline_chat_reply(pending_chat_id, reply)
        self.emit_event(
            "chat-updated",
            {
                "reply": reply,
                "route": None,
                "success": not reply.lower().startswith("local brain error:"),
                "source": source,
                "voice": source == "voice",
                "pending": False,
            },
        )

    def _replace_pending_offline_chat_reply(self, pending_chat_id: str, reply: str) -> None:
        if not pending_chat_id:
            return
        with self._history_lock:
            messages = self._read_history_file()
            replaced = False
            for message in reversed(messages):
                if not isinstance(message, dict):
                    continue
                if str(message.get("pendingOfflineChatId") or "") != pending_chat_id:
                    continue
                message["parts"] = [{"text": reply}]
                message.pop("pendingOfflineChatId", None)
                replaced = True
                break
            if not replaced:
                messages.append({"role": "model", "parts": [{"text": reply}]})
            self._write_history_file(messages)

    def _execute_routed_tool(self, route: dict[str, Any]) -> Any:
        from shell_tool_gateway import execute_tool_sync

        return execute_tool_sync(str(route["tool"]), route.get("args") or {})

    @classmethod
    def _direct_tool_route(cls, text: str) -> dict[str, Any] | None:
        raw = " ".join(str(text or "").split()).strip()
        if not raw:
            return None

        tool_id_pattern = r"([A-Za-z0-9_.-]+(?::[A-Za-z_][A-Za-z0-9_]*)?)"
        direct_match = re.match(
            rf"^/(tool|agent)\s+{tool_id_pattern}(?:\s+(.*))?$",
            raw,
            flags=re.I | re.S,
        )
        if not direct_match:
            direct_match = re.match(
                rf"^(?:run|use|call|execute)\s+(?:shell\s+)?(tool|agent)\s+"
                rf"{tool_id_pattern}(?:\s+(.*))?$",
                raw,
                flags=re.I | re.S,
            )
        if not direct_match:
            direct_match = re.match(
                rf"^(?:ask)\s+(?:shell\s+)?(agent)\s+{tool_id_pattern}(?:\s+(.*))?$",
                raw,
                flags=re.I | re.S,
            )
        if not direct_match:
            return None

        command_kind = str(direct_match.group(1) or "tool").strip().lower()
        requested_tool_id = str(direct_match.group(2) or "").strip()
        raw_args = str(direct_match.group(3) or "").strip()
        item, error = cls._catalog_item_for_direct_tool(requested_tool_id)
        if error:
            return {"errorReply": error, "source": "chat-direct-command"}
        if not item:
            return None

        parsed_args, args_error = cls._parse_direct_tool_args(item, raw_args, command_kind=command_kind)
        if args_error:
            return {"errorReply": args_error, "source": "chat-direct-command"}

        tool_id = str(item.get("id") or requested_tool_id)
        return {
            "tool": tool_id,
            "args": parsed_args,
            "kind": "agent" if command_kind == "agent" else str(item.get("kind") or "tool"),
            "confidence": 0.99,
            "source": "chat-direct-command",
            "direct": True,
        }

    @staticmethod
    def _catalog_item_for_direct_tool(tool_id: str) -> tuple[dict[str, Any] | None, str]:
        requested = str(tool_id or "").strip()
        if not requested:
            return None, "Tool id missing hai. Format: /tool module:function {\"arg\": \"value\"}"
        try:
            from shell_tool_catalog import discover_tool_catalog

            tools = discover_tool_catalog(PROJECT_ROOT)
        except Exception as exc:
            return None, f"Shell tool catalog load nahi hua: {exc}"

        by_id = {str(item.get("id") or ""): item for item in tools}
        if requested in by_id:
            return by_id[requested], ""

        matches = [item for item in tools if str(item.get("name") or "") == requested]
        if len(matches) == 1:
            return matches[0], ""
        if len(matches) > 1:
            ids = ", ".join(str(item.get("id") or "") for item in matches[:6])
            return None, f"'{requested}' ambiguous hai. Exact tool id use karo: {ids}"
        return None, f"Unknown Shell tool/agent id: {requested}. Use exact catalog id, jaise /tool shell_calculator:calculate_tool {{\"expression\":\"5*9\"}}"

    @staticmethod
    def _parse_direct_tool_args(
        item: dict[str, Any],
        raw_args: str,
        *,
        command_kind: str = "tool",
    ) -> tuple[dict[str, Any], str]:
        text = str(raw_args or "").strip()
        text = re.sub(r"^(?:with|using|args|arguments)\b\s*[:=-]?\s*", "", text, flags=re.I).strip()
        if command_kind == "agent":
            text = re.sub(r"^(?:to|for)\b\s*", "", text, flags=re.I).strip()

        params = [param for param in item.get("params") or [] if isinstance(param, dict)]
        required = [param for param in params if param.get("required")]
        tool_id = str(item.get("id") or "")

        if not text:
            if required:
                names = ", ".join(str(param.get("name") or "") for param in required)
                first = str(required[0].get("name") or "arg")
                return {}, f"Missing required argument(s) for {tool_id}: {names}. Example: /tool {tool_id} {{\"{first}\": \"...\"}}"
            return {}, ""

        if text[0] in "{[":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                return {}, f"Tool args valid JSON object nahi hai: {exc.msg}"
            if not isinstance(payload, dict):
                return {}, "Tool args JSON object hone chahiye, array/string nahi."
            return payload, ""

        string_required = [
            param for param in required if "str" in str(param.get("annotation") or "").lower()
        ]
        if len(string_required) == 1:
            return {str(string_required[0].get("name") or "input"): text}, ""
        if len(params) == 1 and "str" in str(params[0].get("annotation") or "").lower():
            return {str(params[0].get("name") or "input"): text}, ""
        if not required:
            return {}, ""

        names = ", ".join(str(param.get("name") or "") for param in required)
        return {}, f"{tool_id} ke liye JSON args chahiye. Required: {names}"

    @staticmethod
    def _orchestration_route(text: str) -> dict[str, Any]:
        return {
            "tool": "shell_agent_orchestrator:orchestrate_shell_goal_tool",
            "args": {"goal": str(text or "").strip(), "execute": True, "approved": False},
            "kind": "agent",
            "confidence": 0.7,
            "source": "web-ui-command-orchestrator",
        }

    @staticmethod
    def _compact_chat_reply(reply: str, *, limit: int = 360) -> str:
        text = " ".join(str(reply or "").split()).strip()
        if limit <= 0:
            return text
        if len(text) <= limit:
            return text
        return f"{text[:limit].rsplit(' ', 1)[0]}..."

    @staticmethod
    def _chat_response_depth(text: str) -> str:
        lower = " ".join(str(text or "").lower().split())
        if re.search(r"\b(full|complete|start\s+to\s+end|end\s+to\s+end|multi[- ]?page|all\s+code|entire)\b", lower) and re.search(
            r"\b(script|screenplay|movie|document|report|website|app|code|story)\b", lower
        ):
            return "artifact"
        if re.search(r"\b(write|build|generate|create|make|draft|produce)\b", lower) and re.search(
            r"\b(script|screenplay|movie|document|pdf|report|website|app|code|html|story)\b", lower
        ):
            return "artifact"
        if re.search(r"\b(explain|design|plan|architecture|how|why|compare|tradeoff|decide|decides|strategy)\b", lower):
            return "medium"
        return "short"

    @classmethod
    def _chat_reply_limit(cls, text: str, *, entry: str = "") -> int:
        if entry == "chart":
            return 360
        depth = cls._chat_response_depth(text)
        if depth == "artifact":
            return 8000
        if depth == "medium":
            return 1600
        return 520

    @classmethod
    def _chat_depth_instruction(cls, text: str) -> str:
        depth = cls._chat_response_depth(text)
        if depth == "artifact":
            return (
                "The user is asking for an artifact or large generated output. Provide the requested artifact fully when practical. "
                "If the full artifact is too long, say that clearly and offer an outline plus the first useful part, or split it into parts."
            )
        if depth == "medium":
            return "The user is asking for design, planning, or explanation. Use a medium-length structured answer with headings or bullets when helpful."
        return "The user is asking a simple or factual question. Answer directly in 1-3 concise sentences."

    @staticmethod
    def _internet_research_allowed() -> bool:
        raw = os.environ.get("SHELL_ALLOW_INTERNET_RESEARCH", "").strip().lower()
        # Agar user ne explicitly disable kiya hai, toh respect karo
        if raw in {"0", "false", "no", "off", "disabled"}:
            return False
        # Agar explicitly enabled hai, allow karo
        if raw in {"1", "true", "yes", "on", "allow", "enabled"}:
            return True
        # Default: auto-enable jab internet online hai
        return is_network_online()

    @staticmethod
    def _internet_research_disabled_reply() -> str:
        return "I’m in offline mode and can’t access the internet. I can still give a generic/offline answer or you can enable online research."

    @staticmethod
    def _internet_research_needed(text: str) -> bool:
        lower = " ".join(str(text or "").lower().split())
        if not lower:
            return False
        explicit_research = bool(
            re.search(r"\b(research|recerch|reserch|deep\s+research|deep\s+reserch|fact\s*check|web\s+search|internet|online)\b", lower)
        )
        current_info = bool(
            re.search(
                r"\b(latest|current|up[- ]?to[- ]?date|today|news|2026|trends?|compare|comparison|apis?|prices?|release|versions?)\b",
                lower,
            )
        )
        external_subject = bool(
            re.search(r"\b(ai\s+apis?|web\s+design|market|competitors?|companies|models?|laws?|weather|stock|crypto)\b", lower)
        )
        return explicit_research or (current_info and external_subject)

    @staticmethod
    def _web_research_route(text: str) -> dict[str, Any]:
        return {
            "tool": "shell_agents:research_agent_tool",
            "args": {"task": str(text or "").strip()},
            "kind": "agent",
            "confidence": 0.78,
            "source": "web-ui-internet-research-policy",
        }

    @staticmethod
    def _approval_intent(text: str) -> bool:
        lower = " ".join(str(text or "").lower().split())
        return bool(re.search(r"\b(yes|allow|approve|go ahead|execute|run it|do it|karo|haan|han|yes once)\b", lower))

    @staticmethod
    def _downloads_cleanup_route(*, dry_run: bool, source: str = "real-os-agent-downloads-cleanup") -> dict[str, Any]:
        return {
            "tool": "shell_windows_workflows:organize_downloads_setups_pdfs_tool",
            "args": {"zip_folder": "Setups", "pdf_folder": "PDFs", "dry_run": bool(dry_run)},
            "kind": "tool",
            "confidence": 0.94,
            "source": source,
            "mode": "local",
            "modeLabel": "Local",
        }

    @classmethod
    def _approval_route_from_history(cls, text: str, previous_messages: list[Any]) -> dict[str, Any] | None:
        if not cls._approval_intent(text):
            return None
        for message in reversed(previous_messages[-8:]):
            if not isinstance(message, dict) or str(message.get("role") or "").lower() == "user":
                continue
            pending = message.get("pendingPermission")
            if not isinstance(pending, dict):
                continue
            if pending.get("action") == "downloads_cleanup":
                return cls._downloads_cleanup_route(dry_run=False, source="real-os-agent-downloads-cleanup-approved")
            route = pending.get("route")
            if isinstance(route, dict) and route.get("tool"):
                return {
                    **route,
                    "source": str(route.get("source") or "approved-pending-action"),
                    "approved": True,
                }
        return None

    @staticmethod
    def _route_needs_user_permission(route: dict[str, Any] | None) -> bool:
        if not isinstance(route, dict):
            return False
        if route.get("approved") is True:
            return False
        args = route.get("args") if isinstance(route.get("args"), dict) else {}
        if args.get("requires_approval") is True or route.get("requiresApproval") is True:
            return True
        return str(route.get("tool") or "") == "shell_terminal:run_command_tool" and str(route.get("source") or "").startswith("dev-workflow")

    @classmethod
    def _permission_prompt_for_route(cls, route: dict[str, Any]) -> dict[str, Any]:
        tool = str(route.get("tool") or "")
        args = dict(route.get("args") or {})
        if tool == "shell_terminal:run_command_tool":
            command = str(args.get("command") or "").strip()
            scope = str(args.get("permission_scope") or "this project").strip()
            approved_args = dict(args)
            approved_args.pop("requires_approval", None)
            approved_args.pop("permission_scope", None)
            approved_route = {**route, "args": approved_args, "approved": True, "source": "approved-dev-command"}
            return {
                "user_message": (
                    f"I want to run `{command}` in {scope}. Allow this action? "
                    "Say “yes” to run it once, or cancel to leave it untouched."
                ),
                "ui_actions": [
                    {"type": "APPROVE_ACTION", "label": "Yes, run once", "message": "yes"},
                    {"type": "CANCEL_ACTION", "label": "Cancel"},
                ],
                "pending_permission": {
                    "action": "run_command",
                    "summary": f"Run `{command}` in {scope}.",
                    "route": approved_route,
                },
            }
        return {
            "user_message": "This action needs permission before I run it. Say “yes” to allow it once, or cancel.",
            "ui_actions": [{"type": "APPROVE_ACTION", "label": "Yes, allow", "message": "yes"}],
            "pending_permission": {"action": "generic", "route": {**route, "approved": True}},
        }

    @staticmethod
    def _is_research_route(route: dict[str, Any] | None) -> bool:
        return bool(route and "research_agent" in str(route.get("tool") or "").lower())

    def _web_research_summary(self, query: str) -> str:
        if not self._internet_research_allowed():
            return ""
        api_key = os.environ.get("GOOGLE_SEARCH_API_KEY", "").strip()
        search_engine_id = os.environ.get("SEARCH_ENGINE_ID", "").strip()
        if not api_key or not search_engine_id:
            return ""
        try:
            params = urllib.parse.urlencode(
                {
                    "key": api_key,
                    "cx": search_engine_id,
                    "q": str(query or "").strip(),
                    "num": 3,
                }
            )
            request = urllib.request.Request(
                f"https://www.googleapis.com/customsearch/v1?{params}",
                headers={"User-Agent": "ShellAIResearch/1.0"},
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8", errors="ignore"))
            rows: list[str] = []
            for item in payload.get("items", [])[:3]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "Untitled").strip()
                link = str(item.get("link") or "").strip()
                snippet = str(item.get("snippet") or "").strip()
                excerpt = self._fetch_web_page_excerpt(link) if link else ""
                parts = [f"Title: {title}"]
                if link:
                    parts.append(f"URL: {link}")
                if snippet:
                    parts.append(f"Search snippet: {snippet}")
                if excerpt:
                    parts.append(f"Page excerpt: {excerpt}")
                rows.append("\n".join(parts))
            return "\n\n".join(rows)
        except Exception:
            return ""

    @staticmethod
    def _fetch_web_page_excerpt(url: str) -> str:
        if not re.match(r"^https?://", str(url or ""), flags=re.I):
            return ""
        try:
            request = urllib.request.Request(str(url), headers={"User-Agent": "ShellAIResearch/1.0"})
            with urllib.request.urlopen(request, timeout=5) as response:
                content_type = str(response.headers.get("content-type") or "").lower()
                if "text/html" not in content_type and "text/plain" not in content_type:
                    return ""
                raw = response.read(200_000).decode("utf-8", errors="ignore")
            raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
            raw = re.sub(r"(?s)<[^>]+>", " ", raw)
            raw = re.sub(r"\s+", " ", raw).strip()
            return raw[:900]
        except Exception:
            return ""

    def _prepare_internet_research_route(self, route: dict[str, Any], text: str) -> dict[str, Any]:
        route_args = dict(route.get("args") or {})
        original_task = str(route_args.get("task") or text or "").strip()
        research_context = self._web_research_summary(original_task)
        if research_context:
            route_args["task"] = (
                f"{original_task}\n\n"
                "Use this fetched web research context. Clearly base the answer on it and include source URLs when useful.\n"
                f"{research_context}"
            )
            return {**route, "args": route_args, "mode": "online-research", "modeLabel": "Online research"}
        return {**route, "args": route_args, "mode": "online-research", "modeLabel": "Online research"}

    @staticmethod
    def _has_command_intent(text: str) -> bool:
        return bool(
            re.search(
                r"\b(open|close|run|start|stop|launch|kill|type|write|search|google|download|install|delete|remove|move|copy|send|create|make|build|fix|scan|execute|control|volume|brightness|screenshot|terminal|calculator)\b",
                text,
                re.IGNORECASE,
            )
        )

    @classmethod
    def _is_telemetry_chart_prompt(cls, text: str, *, entry: str = "") -> bool:
        raw = str(text or "").strip()
        if not raw or cls._has_command_intent(raw):
            return False
        lower = raw.lower()
        has_chart_word = bool(re.search(r"\b(chart|graph|telemetry|metric|metrics)\b", lower))
        if has_chart_word:
            return True
        if re.search(r"\b(what|why|how|explain|define|meaning|tell me|who|when|where|kya|kaise|kyun)\b", lower):
            return False
        has_telemetry_word = bool(
            re.search(r"\b(cpu|processor|ram|memory|network|latency|ping|packet|tx|rx|temp|temperature|heat|load|usage)\b", lower)
        )
        return entry == "chart" and has_telemetry_word and len(raw.split()) <= 12

    def _chart_summary_reply(self, text: str) -> str:
        stats = self._system_stats([])
        cpu = int(float(stats.get("cpu") or 0))
        memory = int(float((stats.get("memory") or {}).get("usedPercentage") or 0))
        temp = int(float(stats.get("temperature") or 0))
        lower = str(text or "").lower()
        if "network" in lower or "latency" in lower or "ping" in lower:
            return "Chart: network telemetry ready. Local bridge is active; live packet values update in the Dashboard."
        if "memory" in lower or "ram" in lower:
            state = "high" if memory >= 80 else "moderate" if memory >= 60 else "normal"
            return f"Chart: RAM {memory}% used, {state}."
        if "temp" in lower or "heat" in lower or "temperature" in lower:
            state = "hot" if temp >= 80 else "warm" if temp >= 65 else "normal"
            return f"Chart: temperature {temp}C, {state}."
        state = "high" if cpu >= 80 else "moderate" if cpu >= 55 else "normal"
        return f"Chart: CPU {cpu}%, {state}. RAM {memory}%, temp {temp}C."

    @staticmethod
    def _clean_image_prompt(prompt: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(prompt or "")).strip(" :.-")
        cleaned = re.sub(
            r"^(?:(?:of|for|about|ki|ka|ke|karke|kar\s+ke|kar\s+do|do|de\s+do|dijiye|please|mere\s+liye|mujhe|mojhe|koi|ek|a|an)\s+)+",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        if re.fullmatch(
            r"(?:image|photo|picture|pic|wallpaper|art|tasveer|chitra|generate|genrate|ganerate|ganarete|ganarate|create|make|draw|design|banao|bana|banado|banaao|karo|karke|kar\s+ke|kar\s+do|do|de\s+do|dijiye|please|\s)+",
            cleaned,
            flags=re.I,
        ):
            return ""
        return cleaned

    @classmethod
    def _extract_image_generation_prompt(cls, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""

        image_word = r"(?:image|photo|picture|pic|wallpaper|art|tasveer|chitra)"
        action_word = r"(?:generate|genrate|ganerate|ganarete|ganarate|create|make|draw|design|banao|bana|banado|banaao|karo|kar\s+do)"
        polite_tail = r"(?:karo|kar\s+do|karke\s+do|karke\s+de\s+do|de\s+do|do)?(?:\s+ok)?"
        connector = r"(?:(?:of|for|about|ki|ka|ke)\b|:)"
        if not re.search(rf"\b{image_word}\b", raw, flags=re.I) or not re.search(
            rf"\b{action_word}\b",
            raw,
            flags=re.I,
        ):
            return ""

        patterns = (
            rf"^(?:please\s+)?(?:generate|genrate|ganerate|ganarete|ganarate|create|make|draw|design)\s+"
            rf"(?:an?\s+|ek\s+|achhi\s+|acchi\s+|high\s+quality\s+)*"
            rf"{image_word}\s*{connector}?\s*(.*)$",
            rf"^(?:please\s+)?{image_word}\s+{action_word}\s*{connector}?\s*(.*)$",
            rf"^(?:please\s+)?{action_word}\s+"
            rf"(?:an?\s+|ek\s+|achhi\s+|acchi\s+|high\s+quality\s+)*"
            rf"{image_word}\s*{connector}?\s*(.*)$",
            rf"^(.+?)\s+(?:(?:ki|ka|ke)\b\s*)?{image_word}\s+{action_word}\s*{polite_tail}\s*$",
        )
        for pattern in patterns:
            match = re.match(pattern, raw, flags=re.I | re.S)
            if not match:
                continue
            prompt = cls._clean_image_prompt(match.group(1) if match.groups() else "")
            if prompt:
                return prompt

        return "high quality original Shell AI concept image"

    @staticmethod
    def _image_generation_route(prompt: str) -> dict[str, Any]:
        return {
            "tool": "shell_image_ai:generate_image_tool",
            "args": {
                "description": prompt,
                "device_type": "pc",
                "style": "photorealistic",
                "quality": "excellent",
                "use_ai_enhancement": True,
                "use_cache": False,
                "force_fresh": True,
            },
            "confidence": 0.9,
            "source": "web-ui-image-intent",
        }

    @staticmethod
    def _route_image_prompt(route: dict[str, Any]) -> str:
        args = route.get("args") if isinstance(route, dict) else {}
        if not isinstance(args, dict):
            return ""
        return str(args.get("description") or args.get("prompt") or "").strip()

    @staticmethod
    def _artifact_topic_from_request(request: str) -> str:
        text = re.sub(
            r"\b(?:write|create|make|generate|banao|bana|banado|banaao|kar\s+do|pdf|document|file|"
            r"polished|original|concise|structured|report|movie|film|script|screenplay|about|ke\s+bare\s+mein|"
            r"ka|ki|ke|ek|a|an)\b",
            " ",
            str(request or ""),
            flags=re.I,
        )
        return " ".join(text.split()).strip(" .:-") or "Shell AI"

    @staticmethod
    def _escape_html_text(text: str) -> str:
        return (
            str(text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    @classmethod
    def _local_html_artifact_content(cls, request: str) -> str:
        normalized = " ".join(str(request or "").split()).strip()
        lower = normalized.lower()
        is_login = bool(re.search(r"\b(login|signin|sign\s*in|auth|authentication)\b", lower))
        if not is_login:
            title = cls._escape_html_text(cls._artifact_topic_from_request(normalized).title())
            return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light dark; --bg:#f6f7f2; --ink:#17211b; --panel:#ffffff; --accent:#0f766e; --line:#d8ded6; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; min-height:100vh; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:var(--bg); color:var(--ink); }}
    main {{ width:min(920px, calc(100% - 32px)); margin:0 auto; padding:64px 0; }}
    h1 {{ font-size:clamp(2rem, 6vw, 4.5rem); line-height:1; margin:0 0 18px; }}
    p {{ font-size:1.05rem; line-height:1.7; max-width:680px; }}
    .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:24px; margin-top:28px; }}
    .button {{ display:inline-block; margin-top:16px; padding:12px 16px; border-radius:6px; background:var(--accent); color:white; text-decoration:none; font-weight:700; }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p>This standalone HTML page was generated by Shell AI and is ready to edit.</p>
    <section class="panel">
      <h2>Useful Section</h2>
      <p>Add your real content, links, and contact details here.</p>
      <a class="button" href="#">Get Started</a>
    </section>
  </main>
</body>
</html>"""

        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shell Login</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #eef2ec;
      --ink: #14201a;
      --muted: #5f6f65;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-strong: #0b4f49;
      --line: #d8e0d7;
      --error: #b42318;
      --success: #137333;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        linear-gradient(135deg, rgba(15,118,110,.14), transparent 36%),
        linear-gradient(315deg, rgba(20,32,26,.10), transparent 34%),
        var(--bg);
      color: var(--ink);
    }
    .login-shell {
      width: min(960px, 100%);
      min-height: 560px;
      display: grid;
      grid-template-columns: 1fr 420px;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: var(--panel);
      box-shadow: 0 24px 70px rgba(20, 32, 26, .16);
    }
    .brand-panel {
      padding: 48px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      background: #10231e;
      color: white;
    }
    .brand-mark {
      width: 48px;
      height: 48px;
      display: grid;
      place-items: center;
      border: 1px solid rgba(255,255,255,.22);
      border-radius: 8px;
      font-weight: 800;
      background: rgba(255,255,255,.08);
    }
    .brand-panel h1 {
      margin: 0;
      max-width: 460px;
      font-size: clamp(2.2rem, 6vw, 4.6rem);
      line-height: .95;
      letter-spacing: 0;
    }
    .brand-panel p { color: rgba(255,255,255,.72); line-height: 1.7; max-width: 460px; }
    .form-panel { padding: 48px; display: flex; flex-direction: column; justify-content: center; }
    .form-panel h2 { margin: 0 0 8px; font-size: 1.65rem; }
    .form-panel > p { margin: 0 0 28px; color: var(--muted); line-height: 1.6; }
    label { display: block; margin: 16px 0 8px; font-weight: 700; font-size: .92rem; }
    input {
      width: 100%;
      min-height: 48px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 14px;
      font: inherit;
      color: var(--ink);
      background: color-mix(in srgb, var(--panel) 92%, var(--bg));
    }
    input:focus { outline: 3px solid rgba(15,118,110,.18); border-color: var(--accent); }
    .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 16px 0 22px; }
    .check { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: .92rem; }
    .check input { width: 16px; min-height: 16px; }
    a { color: var(--accent-strong); font-weight: 700; text-decoration: none; }
    button {
      width: 100%;
      min-height: 50px;
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
    }
    button:hover { background: var(--accent-strong); }
    .message { min-height: 24px; margin-top: 16px; font-weight: 700; }
    .message.error { color: var(--error); }
    .message.success { color: var(--success); }
    @media (max-width: 780px) {
      body { padding: 0; place-items: stretch; }
      .login-shell { min-height: 100vh; grid-template-columns: 1fr; border: 0; border-radius: 0; }
      .brand-panel { min-height: 280px; padding: 32px; }
      .form-panel { padding: 32px; }
    }
  </style>
</head>
<body>
  <main class="login-shell">
    <section class="brand-panel" aria-label="Product">
      <div class="brand-mark">S</div>
      <div>
        <h1>Secure Shell Access</h1>
        <p>Sign in to continue to your workspace. This page is fully offline and validates the form in your browser.</p>
      </div>
    </section>
    <section class="form-panel" aria-label="Login form">
      <h2>Welcome Back</h2>
      <p>Use any valid email and a password with at least 6 characters to test the working login state.</p>
      <form id="loginForm" novalidate>
        <label for="email">Email address</label>
        <input id="email" name="email" type="email" autocomplete="email" placeholder="you@example.com" required>
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" placeholder="Minimum 6 characters" required minlength="6">
        <div class="row">
          <label class="check"><input type="checkbox" name="remember"> Remember me</label>
          <a href="#" aria-label="Reset password">Forgot?</a>
        </div>
        <button type="submit">Sign In</button>
        <p id="message" class="message" role="status" aria-live="polite"></p>
      </form>
    </section>
  </main>
  <script>
    const form = document.getElementById('loginForm');
    const message = document.getElementById('message');
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const email = form.email.value.trim();
      const password = form.password.value;
      const validEmail = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email);
      message.className = 'message';
      if (!validEmail) {
        message.textContent = 'Please enter a valid email address.';
        message.classList.add('error');
        form.email.focus();
        return;
      }
      if (password.length < 6) {
        message.textContent = 'Password must be at least 6 characters.';
        message.classList.add('error');
        form.password.focus();
        return;
      }
      message.textContent = 'Login demo successful. Your form is working.';
      message.classList.add('success');
    });
  </script>
</body>
</html>"""

    @staticmethod
    def _extract_html_document(text: str) -> str:
        raw = str(text or "").strip()
        fence = re.search(r"```(?:html)?\s*(.*?)```", raw, flags=re.I | re.S)
        if fence:
            raw = fence.group(1).strip()
        start = raw.lower().find("<!doctype html")
        if start < 0:
            start = raw.lower().find("<html")
        if start > 0:
            raw = raw[start:].strip()
        return raw

    @staticmethod
    def _looks_like_standalone_html(text: str, *, require_form: bool = False) -> bool:
        lower = str(text or "").lower()
        if "<html" not in lower or "</html>" not in lower:
            return False
        if "<body" not in lower or "</body>" not in lower:
            return False
        if require_form and ("<form" not in lower or "type=\"password\"" not in lower and "type='password'" not in lower):
            return False
        return True

    @classmethod
    def _local_artifact_content(cls, request: str, *, file_type: str = "") -> str:
        normalized = " ".join(str(request or "").split()).strip()
        topic = cls._artifact_topic_from_request(normalized)
        lower = normalized.lower()
        if str(file_type or "").lower() in {"html", "htm"}:
            return cls._local_html_artifact_content(normalized)
        if re.search(r"\b(movie|film|short film|script|screenplay|scene|dialogue|dialog)\b", lower):
            title = topic.title()
            if re.search(r"\b(full|complete|start\s+to\s+end|end\s+to\s+end|entire|acts?\s*1\s*[-to]+\s*3)\b", lower):
                return (
                    f"{title}\n\n"
                    "Format: Feature screenplay draft\n"
                    "Genre: Mystery thriller\n\n"
                    "ACT STRUCTURE\n"
                    "Act 1: Ayaan discovers a file from tomorrow, follows the first clue, and learns the warning is real.\n"
                    "Act 2: Ayaan, Meera, and Rafiq trace the signal to an abandoned cinema where projected scenes alter real events.\n"
                    "Act 3: Ayaan must decide whether to destroy the projector or use it once, risking his own future to stop a city-wide disaster.\n\n"
                    "CAST\n"
                    "AYAAN MALIK - 29, systems technician, careful under pressure but haunted by one past mistake.\n"
                    "MEERA SINGH - 31, investigative reporter, direct, skeptical, and hard to intimidate.\n"
                    "RAFIQ ANSARI - 28, Ayaan's oldest friend, street-smart and loyal even when terrified.\n"
                    "THE PROJECTIONIST - unseen at first, leaving warnings through film reels and corrupted files.\n\n"
                    "FADE IN:\n\n"
                    "INT. AYAAN'S APARTMENT - NIGHT\n\n"
                    "Rain needles the windows of a cramped Mumbai apartment. Ayaan sits before three monitors, repairing a municipal server dump. "
                    "The room is quiet except for a ceiling fan and the soft click of keys.\n\n"
                    "On the center monitor, a folder appears by itself: TOMORROW_00_17.\n\n"
                    "Ayaan stops typing.\n\n"
                    "AYAAN\n"
                    "I did not mount that drive.\n\n"
                    "He checks the logs. Nothing. The folder opens. Inside is a video file named: DO_NOT_GO_TO_SLEEP.mp4.\n\n"
                    "Ayaan hesitates, then clicks.\n\n"
                    "ON SCREEN: A shaky phone video of Ayaan's own apartment. Same rain. Same fan. A digital clock reads 12:17 AM. "
                    "In the video, Ayaan is asleep on the couch. The front door unlocks from outside.\n\n"
                    "Ayaan looks toward his real front door.\n\n"
                    "The video cuts to black. Text appears: FIND THE TICKET BEFORE MIDNIGHT.\n\n"
                    "CUT TO:\n\n"
                    "EXT. AYAAN'S BUILDING - NIGHT\n\n"
                    "Ayaan steps into the rain with his laptop bag under his jacket. He calls Meera. She answers on the third ring.\n\n"
                    "MEERA (V.O.)\n"
                    "If this is about your router again, I am hanging up.\n\n"
                    "AYAAN\n"
                    "Someone sent me a video from tomorrow.\n\n"
                    "MEERA (V.O.)\n"
                    "That is not a sentence serious people say.\n\n"
                    "AYAAN\n"
                    "I need you to be unserious for ten minutes.\n\n"
                    "Across the street, a small object waits beneath the flickering bus-stop light: an old cinema ticket sealed in plastic.\n\n"
                    "CUT TO:\n\n"
                    "INT. MEERA'S NEWSROOM - NIGHT\n\n"
                    "Half the office is dark. Meera watches the video on Ayaan's laptop. Her skepticism fades when she sees tomorrow's timestamp embedded in raw metadata.\n\n"
                    "MEERA\n"
                    "Metadata can be forged.\n\n"
                    "AYAAN\n"
                    "Yes.\n\n"
                    "MEERA\n"
                    "This was not forged by anyone normal.\n\n"
                    "She turns the cinema ticket over. On the back, a handwritten address has bled in the rain: REGAL ECHO, SCREEN 3.\n\n"
                    "MEERA\n"
                    "This theatre burned down twelve years ago.\n\n"
                    "AYAAN\n"
                    "Then why is there a showtime for tonight?\n\n"
                    "A desk phone rings though no line is connected. Meera and Ayaan stare at it.\n\n"
                    "Meera answers.\n\n"
                    "THE PROJECTIONIST (V.O.)\n"
                    "Bring the ticket. Leave the reporter.\n\n"
                    "The line dies.\n\n"
                    "CUT TO:\n\n"
                    "EXT. OLD CITY MARKET - NIGHT\n\n"
                    "Rafiq hurries through closing stalls, clutching a second ticket. Ayaan and Meera meet him beneath a blue tarp snapping in the wind.\n\n"
                    "RAFIQ\n"
                    "Tell me both of you got one too.\n\n"
                    "MEERA\n"
                    "How did you get this?\n\n"
                    "RAFIQ\n"
                    "It was in my taxi. On the seat. Passenger never existed on the dashcam.\n\n"
                    "Ayaan compares the tickets. Three seats. Same show. Same time: 11:47 PM.\n\n"
                    "The market lights go out one row at a time, moving toward them.\n\n"
                    "AYAAN\n"
                    "Walk. Do not run.\n\n"
                    "They walk. Behind them, a projector beam slices through the rain from somewhere above the market. Wherever the beam touches, people freeze for one second, then continue as if nothing happened.\n\n"
                    "Meera sees it and finally stops pretending not to be afraid.\n\n"
                    "MEERA\n"
                    "Ayaan.\n\n"
                    "AYAAN\n"
                    "I saw it.\n\n"
                    "CUT TO:\n\n"
                    "INT. ABANDONED REGAL ECHO THEATRE - LOBBY - NIGHT\n\n"
                    "The theatre is blackened from an old fire, but the ticket booth glows with warm light. No one sits inside. Three tickets slide out beneath the glass.\n\n"
                    "Ayaan does not take them.\n\n"
                    "RAFIQ\n"
                    "Good. We leave. Excellent investigation.\n\n"
                    "The lobby speakers crackle.\n\n"
                    "THE PROJECTIONIST (V.O.)\n"
                    "The film starts whether you watch or not.\n\n"
                    "A low mechanical rumble begins beyond the auditorium doors.\n\n"
                    "MEERA\n"
                    "If it can show tomorrow, it can show who is doing this.\n\n"
                    "AYAAN\n"
                    "Or it shows us exactly what it wants us to do.\n\n"
                    "He takes the tickets.\n\n"
                    "INT. REGAL ECHO - SCREEN 3 - CONTINUOUS\n\n"
                    "The auditorium is empty except for three clean seats in the center row. The screen flickers alive. The image is the market outside, live, from above.\n\n"
                    "On screen, a bus loses control at the corner they crossed minutes ago.\n\n"
                    "Ayaan checks his phone. The time is 11:46 PM.\n\n"
                    "The screen cuts to a title card: ONE MINUTE.\n\n"
                    "MEERA\n"
                    "That corner is full of people.\n\n"
                    "RAFIQ\n"
                    "We cannot get there in one minute.\n\n"
                    "Ayaan looks up at the projection booth. A second reel spins beside the first, labeled: CHANGE.\n\n"
                    "AYAAN\n"
                    "Maybe we do not have to get there.\n\n"
                    "He runs toward the booth stairs.\n\n"
                    "END OF PART 1 - NATURAL BREAK\n\n"
                    "I've written until Ayaan reaches the projection booth stairs at the end of Act 1's first major turn; I can continue with the next part if you ask."
                )
            return (
                f"{title}\n\n"
                "Genre: Drama / Thriller\n"
                "Logline: A focused protagonist faces one urgent choice that changes the direction of their life.\n\n"
                "Characters:\n"
                "- Ayaan: determined, observant, and carrying a quiet pressure.\n"
                "- Meera: practical, sharp, and willing to challenge easy answers.\n"
                "- Rafiq: the friend who notices danger before anyone else.\n\n"
                "Scene 1 - Interior, late evening\n"
                "Ayaan studies a flickering laptop screen while rain taps the window. A file opens with a timestamp he does not recognize.\n\n"
                "AYAAN\n"
                "This was created tomorrow.\n\n"
                "MEERA\n"
                "Then someone is warning you before it happens.\n\n"
                "Scene 2 - Street outside the old cinema\n"
                "The city lights blur in the rain. Rafiq arrives breathless, holding a torn ticket with the same timestamp.\n\n"
                "RAFIQ\n"
                "You need to leave before midnight. They already know you saw it.\n\n"
                "Scene 3 - Final choice\n"
                "Ayaan stands at the cinema door. Behind it is the evidence; outside is safety. He turns back to Meera.\n\n"
                "AYAAN\n"
                "If we run, this happens to someone else.\n\n"
                "Meera nods. Together, they open the door.\n\n"
                "Ending note: The story closes on the projector starting by itself, revealing the first frame of tomorrow."
            )
        if re.search(r"\b(report|analysis|summary|essay|article)\b", lower) or file_type == "pdf":
            return (
                f"{topic.title()}\n\n"
                f"Overview\n{topic} par yeh short document clear points mein useful context deta hai.\n\n"
                "Key Points\n"
                "1. Main idea ko simple language mein define karo.\n"
                "2. Practical examples add karo jisse reader ko topic immediately samajh aaye.\n"
                "3. Risks, benefits, aur next steps ko separate sections mein rakho.\n\n"
                "Practical Use\n"
                "Is content ko presentation, notes, ya quick reference document ke base ke roop mein use kiya ja sakta hai.\n\n"
                "Conclusion\n"
                f"{topic} ko samajhne ke liye best approach hai: clear definition, real examples, aur actionable next steps."
            )
        return (
            f"{topic.title()}\n\n"
            f"Yeh document {topic} ke liye Shell AI ne local mode mein draft kiya hai.\n\n"
            "Main points:\n"
            "- Topic ko clear objective ke saath start karo.\n"
            "- Important details ko short sections mein divide karo.\n"
            "- End mein next steps ya conclusion add karo."
        )

    def _generated_artifact_content(self, request: str, *, file_type: str = "", previous_messages: list[Any] | None = None) -> str:
        task = " ".join(str(request or "").split()).strip()
        if not task:
            return ""
        normalized_file_type = str(file_type or "").strip().lower()
        if normalized_file_type in {"html", "htm"}:
            require_form = bool(re.search(r"\b(login|signin|sign\s*in|auth|authentication)\b", task, flags=re.I))
            system_prompt = (
                "You are Shell AI's coding brain. Return a complete standalone HTML document only. "
                "Use inline CSS. Use inline JavaScript when interaction is requested. "
                "Do not return markdown, explanation, placeholders, or a generic document."
            )
            candidates: list[str] = []
            if self._should_try_provider_chat():
                candidates.append(self._provider_chat_reply(task, system_prompt, limit=8000))
            try:
                result = generate_offline_coding_reply(task, system_prompt=system_prompt, previous_messages=previous_messages)
                if getattr(result, "success", False) and getattr(result, "reply", ""):
                    candidates.append(str(result.reply))
            except Exception:
                pass
            try:
                result = generate_offline_reply(task, system_prompt=system_prompt, previous_messages=previous_messages)
                if getattr(result, "success", False) and getattr(result, "reply", ""):
                    candidates.append(str(result.reply))
            except Exception:
                pass
            for candidate in candidates:
                html_doc = self._extract_html_document(candidate)
                if self._looks_like_standalone_html(html_doc, require_form=require_form):
                    return html_doc
            return self._local_artifact_content(task, file_type=normalized_file_type)
        if normalized_file_type == "pdf" and re.search(r"\b(summary|summarize|summarise|saransh|recap)\b", task, re.I):
            try:
                from shell_make_modes import cloud_make_pdf, local_make_pdf
                from shell_task_mode import online_full_version_ready

                title = self._artifact_topic_from_request(task).title() or "Shell Summary"
                if online_full_version_ready() and self._should_try_provider_chat():
                    return cloud_make_pdf(title, task, self._provider_chat_reply, summary=True)
                return local_make_pdf(title, task, summary=True)
            except Exception:
                return self._local_artifact_content(task, file_type=file_type)
        system_prompt = (
            "You are Shell AI writing finished artifact content for a file/PDF. "
            f"{_shell_language_instruction()} "
            "Return only the actual content that should be saved. Do not describe that you are creating it. "
            "Never echo the user's request as the whole answer. Include useful sections and concrete details."
        )
        try:
            from shell_task_mode import online_mode_enabled
        except Exception:
            online_mode_enabled = lambda: False  # type: ignore[assignment]
        if online_mode_enabled() and self._should_try_provider_chat():
            provider_reply = self._provider_chat_reply(task, system_prompt, limit=self._chat_reply_limit(task))
            if provider_reply and not self._is_stale_provider_fallback_reply(provider_reply):
                return provider_reply
        offline_reply = self._offline_chat_reply(task, system_prompt, previous_messages, limit=self._chat_reply_limit(task))
        if offline_reply:
            return offline_reply
        return self._local_artifact_content(task, file_type=file_type)

    def _prepare_artifact_route(self, route: dict[str, Any], *, previous_messages: list[Any] | None = None) -> dict[str, Any]:
        tool = str(route.get("tool") or "")
        args = route.get("args") if isinstance(route.get("args"), dict) else {}
        if tool != "shell_workspace_tools:create_user_file_tool" or not isinstance(args, dict):
            return route
        content_request = str(args.get("content_request") or "").strip()
        if not content_request:
            return route
        file_type = str(args.get("file_type") or "").strip().lower()
        generated = self._generated_artifact_content(content_request, file_type=file_type, previous_messages=previous_messages)
        if not generated:
            return route
        next_args = dict(args)
        next_args["content"] = generated
        next_args.pop("content_request", None)
        next_args.pop("raw_request", None)
        return {**route, "args": next_args}

    @classmethod
    def _local_build_brief(cls, request: str) -> str:
        raw = " ".join(str(request or "").split()).strip()
        lower = raw.lower()
        kind = "website" if re.search(r"\b(website|webpage|web page|landing page|site)\b", lower) else "app"
        subject = re.sub(
            r"\b(?:please|pls|make|create|build|generate|design|scaffold|develop|code|website|webpage|web\s+page|"
            r"landing\s+page|site|app|application|software|dashboard|tool|banao|bana|banado|banaao|bana\s+do|"
            r"kar\s+do|with|for|ke\s+liye|ka|ki|ek|a|an)\b",
            " ",
            raw,
            flags=re.I,
        )
        subject = " ".join(subject.split()).strip(" .:-") or ("business" if kind == "website" else "productivity")
        if kind == "website":
            return (
                f"Build a polished responsive website for {subject}. Include a strong hero, value proposition, "
                "feature/service sections, proof or highlights, and a contact/CTA section. Do not echo the request text as page copy."
            )
        return (
            f"Build a full-stack app for {subject}. Include a useful dashboard, create/read/update flows, persistent backend data, "
            "responsive UI, and clear empty/error states. Do not echo the request text as page copy."
        )

    def _prepare_code_build_route(self, route: dict[str, Any]) -> dict[str, Any]:
        tool = str(route.get("tool") or "")
        args = route.get("args") if isinstance(route.get("args"), dict) else {}
        if tool != "shell_code_engine:create_fullstack_app_tool" or not isinstance(args, dict):
            return route
        app_type = str(args.get("app_type") or "").strip()
        if not app_type:
            return route
        if re.search(r"\b(?:banao|bana|banado|banaao|kar\s+do)\b", app_type, re.I) or re.match(
            r"^\s*(?:website|webpage|landing\s+page|site|app)\b",
            app_type,
            re.I,
        ):
            next_args = dict(args)
            next_args["app_type"] = self._local_build_brief(app_type)
            return {**route, "args": next_args}
        return route

    def _mode_decision_for_route(self, text: str, route: dict[str, Any]) -> dict[str, Any] | None:
        tool = str(route.get("tool") or "")
        args = route.get("args") if isinstance(route.get("args"), dict) else {}
        prompt = " ".join(
            item
            for item in (
                str(text or ""),
                str(args.get("app_type") or ""),
                str(args.get("task") or ""),
                str(args.get("query") or ""),
            )
            if item
        )
        try:
            from shell_task_mode import classify_task_mode, online_full_version_message, online_mode_enabled

            decision = classify_task_mode(prompt, route_tool=tool)
        except Exception:
            return None
        if not decision.requires_online:
            return {
                **decision.to_dict(),
                "mode": "local",
                "modeLabel": "Local",
                "message": "Using Level 1 Local mode.",
            }
        if online_mode_enabled() and self._should_try_provider_chat():
            return {
                **decision.to_dict(),
                "mode": "online-api",
                "modeLabel": "Online (API)",
                "message": "Using Level 2 Online (API) mode. File writes and execution remain local.",
            }
        return {
            **decision.to_dict(),
            "mode": "local-basic-offered",
            "modeLabel": "Local basic available",
            "reason": decision.reason,
            "message": online_full_version_message(decision.reason),
        }

    @staticmethod
    def _safe_upload_filename(name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._ -]+", "_", str(name or "upload")).strip(" ._-")
        return cleaned[:120] or "upload"

    def _prepare_chat_attachments(self, attachments: Any) -> list[dict[str, Any]]:
        if not isinstance(attachments, list):
            return []
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        prepared: list[dict[str, Any]] = []
        for index, item in enumerate(attachments[:4]):
            if not isinstance(item, dict):
                continue
            name = self._safe_upload_filename(str(item.get("name") or f"attachment_{index + 1}"))
            file_type = str(item.get("type") or mimetypes.guess_type(name)[0] or "application/octet-stream")
            size = int(float(item.get("size") or 0))
            text = str(item.get("text") or "")[:26000]
            saved_path = ""
            data_url = str(item.get("dataUrl") or "")
            if data_url.startswith("data:") and "," in data_url:
                try:
                    header, encoded = data_url.split(",", 1)
                    binary = base64.b64decode(encoded, validate=False)
                    if len(binary) <= 5 * 1024 * 1024:
                        suffix = Path(name).suffix or mimetypes.guess_extension(file_type) or ".bin"
                        stem = Path(name).stem[:80] or "attachment"
                        path = UPLOADS_DIR / f"{int(time.time() * 1000)}_{index}_{stem}{suffix}"
                        path.write_bytes(binary)
                        saved_path = str(path)
                        if not size:
                            size = len(binary)
                        if not file_type or file_type == "application/octet-stream":
                            guessed = header[5:].split(";", 1)[0].strip()
                            file_type = guessed or file_type
                except Exception:
                    saved_path = ""
            prepared.append(
                {
                    "name": name,
                    "type": file_type,
                    "size": size,
                    "path": saved_path,
                    "text": text,
                    "error": str(item.get("error") or "")[:200],
                }
            )
        return prepared

    @staticmethod
    def _attachment_context(attachments: list[dict[str, Any]]) -> str:
        if not attachments:
            return ""
        rows = ["Attached files for this Shell request:"]
        for index, item in enumerate(attachments, start=1):
            rows.append(
                f"{index}. {item.get('name')} ({item.get('type')}, {item.get('size')} bytes)"
                + (f" saved at {item.get('path')}" if item.get("path") else "")
                + (f" error: {item.get('error')}" if item.get("error") else "")
            )
            text = str(item.get("text") or "").strip()
            if text:
                rows.append(f"Content excerpt:\n{text[:6000]}")
        return "\n".join(rows)

    @staticmethod
    def _activity_descriptor(text: str, route: dict[str, Any] | None, *, image_prompt: str = "") -> dict[str, Any] | None:
        if not route or not route.get("tool"):
            return None
        tool = str(route.get("tool") or "")
        args = route.get("args") if isinstance(route.get("args"), dict) else {}
        prompt = (
            image_prompt
            or str(args.get("description") or args.get("task") or args.get("query") or args.get("goal") or args.get("app_type") or "")
            or str(text or "")
        ).strip()
        lower_tool = tool.lower()
        lower_text = str(text or "").lower()
        if tool == "shell_image_ai:generate_image_tool":
            kind = "image"
            title = "IMAGE GENERATION"
            message = "GENERATING VISUAL"
        elif "research_agent" in lower_tool or re.search(r"\b(deep\s*(?:research|recerch)|research|recerch|fact\s*check)\b", lower_text):
            kind = "research"
            title = "DEEP RESEARCH"
            message = "SEARCHING AND VERIFYING"
        elif any(token in lower_tool for token in ("code_engine", "game_builder", "website_builder", "app_builder")):
            kind = "build"
            title = "BUILD TASK"
            message = "BUILDING OUTPUT"
        elif any(token in lower_tool for token in ("browser", "search", "open_url", "youtube")):
            kind = "search"
            title = "LIVE SEARCH"
            message = "FETCHING RESULT"
        else:
            kind = "tool"
            title = "SHELL ACTION"
            message = "RUNNING TOOL"
        return {
            "id": f"{kind}-{int(time.time() * 1000)}",
            "kind": kind,
            "title": title,
            "prompt": prompt[:220],
            "tool": tool,
            "message": message,
        }

    def _emit_activity(
        self,
        descriptor: dict[str, Any] | None,
        *,
        status: str,
        message: str = "",
        progress: int = 18,
        source: str = "text",
        entry: str = "",
    ) -> None:
        if not descriptor:
            return
        payload = dict(descriptor)
        payload.update(
            {
                "status": status,
                "message": str(message or descriptor.get("message") or "WORKING")[:220],
                "progress": max(0, min(100, int(progress))),
                "source": source,
                "entry": entry,
                "ts": time.time(),
            }
        )
        self.emit_event("activity-updated", payload)

    @staticmethod
    def _activity_result_success(route: dict[str, Any], result: Any, reply: str) -> bool:
        tool = str(route.get("tool") or "")
        lower_reply = str(reply or "").lower()
        if "[blocked]" in lower_reply or "blocked" in lower_reply or "failed" in lower_reply:
            return False
        if tool == "shell_image_ai:generate_image_tool":
            return "gallery mein save ho gayi" in lower_reply or "saved to gallery" in lower_reply
        if isinstance(result, dict):
            payload = result.get("result")
            payload_dict = ShellBackendBridge._coerce_tool_payload(payload)
            if payload_dict.get("ok") is False or payload_dict.get("error"):
                return False
            if result.get("status") == "success":
                return True
            if result.get("success") is True:
                return True
            if result.get("error"):
                return False
            if result.get("status") in {"error", "failed", "blocked"}:
                return False
        return True

    @staticmethod
    def _history_text(message: Any) -> str:
        if not isinstance(message, dict):
            return ""
        parts = message.get("parts")
        if isinstance(parts, list) and parts:
            first = parts[0]
            if isinstance(first, dict):
                return str(first.get("text") or "").strip()
        return str(message.get("content") or message.get("text") or "").strip()

    @classmethod
    def _conversation_recall_reply(cls, text: str, previous_messages: list[Any]) -> str:
        raw = str(text or "").strip()
        if cls._direct_tool_route(raw):
            return ""
        lower = raw.lower()
        recall_intent = any(
            token in lower
            for token in (
                "yaad",
                "remember",
                "recall",
                "pichla",
                "pichle",
                "previous",
                "last task",
                "last command",
                "abhi kya",
                "kya kaam",
                "what did i ask",
                "what was my last",
            )
        )
        if not recall_intent:
            return ""

        previous_user_texts: list[str] = []
        for message in previous_messages:
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            item = cls._history_text(message)
            if not item:
                continue
            normalized = item[7:].strip() if item.lower().startswith("chart: ") else item
            if normalized and normalized.lower() != lower:
                previous_user_texts.append(normalized)

        if not previous_user_texts:
            return "Haan bhai, lekin is session mein abhi koi pehla chart ya command task saved nahi mila."

        last_task = previous_user_texts[-1]
        return f"Haan bhai, yaad hai. Tumne pichla kaam bola tha: \"{last_task}\"."

    @staticmethod
    def _creator_identity_reply(text: str, *, source: str = "text") -> str:
        normalized = " ".join(str(text or "").lower().split())
        if not normalized:
            return ""

        who_intent = bool(re.search(r"\b(who\s+are\s+you|tum\s+kaun|tum\s+kon|tu\s+kaun|tu\s+kon|aap\s+kaun|aap\s+kon|kaun\s+ho|kon\s+ho)\b", normalized))
        explicit_creator_words = bool(
            re.search(
                r"\b("
                r"kis\s*ne|kisne|creator|maker|founder|owner|developer|made|created|built|developed|designed|"
                r"banaya|bana\s*ya|banaya\s*hai|banaya\s*ha|banaya\s*h|banane\s*wala|banane\s*waala|"
                r"banane\s*wale|create\s*kiya|develop\s*kiya"
                r")\b",
                normalized,
            )
        )
        if who_intent and not explicit_creator_words:
            return ""

        subject_intent = bool(
            re.search(r"\b(shell|shell ai|you|your|tum|tumhe|tumko|tujhe|tume|aap|aapko|apko|tere|tera|tu)\b", normalized)
        )
        creator_intent = bool(
            re.search(
                r"\b("
                r"kis\s*ne|kisne|which company|company|creator|maker|founder|owner|developer|"
                r"made|created|built|developed|designed|banaya|bana\s*ya|banaya\s*hai|banaya\s*ha|banaya\s*h|"
                r"banane\s*wala|banane\s*waala|banane\s*wale|create\s*kiya|develop\s*kiya"
                r")\b",
                normalized,
            )
        )
        explicit_creator_phrase = bool(
            re.search(r"\b(shell|shell ai|your|tumhara|tera|aapka)\s+(creator|maker|founder|owner|developer)\b", normalized)
            or re.search(r"\b(creator|maker|founder|owner|developer)\s+(kaun|kon|who|kisne|kis\s*ne)\b", normalized)
        )
        if not ((subject_intent and creator_intent) or explicit_creator_phrase):
            return ""

        return "Mujhe mdshoebking ne banaya hai."

    @classmethod
    def _is_unrequested_creator_identity_reply(cls, user_text: str, reply: str) -> bool:
        normalized_reply = " ".join(str(reply or "").lower().split())
        if "mdshoebking" not in normalized_reply:
            return False
        return not bool(cls._creator_identity_reply(user_text))

    @staticmethod
    def _self_identity_reply(text: str) -> str:
        normalized = " ".join(str(text or "").lower().split())
        if not normalized:
            return ""
        if not re.search(r"\b(who\s+are\s+you|tum\s+kaun|tum\s+kon|tu\s+kaun|tu\s+kon|aap\s+kaun|aap\s+kon|kaun\s+ho|kon\s+ho)\b", normalized):
            return ""
        return "Main Shell AI hoon, tumhara desktop OS controller aur assistant."

    def _history_context_snippet(self, previous_messages: list[Any], *, limit: int = 6) -> str:
        rows: list[str] = []
        for message in previous_messages[-limit:]:
            role = str(message.get("role") or "") if isinstance(message, dict) else ""
            text = self._history_text(message)
            if role == "model" and self._is_stale_provider_fallback_reply(text):
                continue
            if role and text:
                rows.append(f"{role}: {text[:220]}")
        return "\n".join(rows)

    @staticmethod
    def _is_stale_provider_fallback_reply(text: str) -> bool:
        normalized = " ".join(str(text or "").lower().split())
        return any(marker in normalized for marker in STALE_PROVIDER_FALLBACK_MARKERS)

    @classmethod
    def _visible_history_messages(cls, messages: list[Any]) -> list[Any]:
        clean: list[Any] = []
        for message in messages or []:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "").strip().lower()
            text = cls._history_text(message)
            if role == "model" and cls._is_stale_provider_fallback_reply(text):
                continue
            clean.append(message)
        return clean

    def _offline_llm_history(self, previous_messages: list[Any] | None) -> list[Any]:
        clean: list[Any] = []
        for message in previous_messages or []:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "").strip().lower()
            text = self._history_text(message)
            if role == "model" and self._is_stale_provider_fallback_reply(text):
                continue
            clean.append(message)
        return clean[-8:]

    @staticmethod
    def _env_flag_enabled(name: str, *, default: bool = True) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return str(raw).strip().lower() not in {"0", "false", "no", "off", "disabled"}

    def _memory_context_snippet(self, query: str, *, limit: int = 4) -> str:
        if not self._env_flag_enabled("SHELL_CHAT_MEMORY_CONTEXT", default=True):
            return ""
        rows: list[str] = []
        try:
            from shell_memory_v2 import memory_v2_enabled, recall_memory

            if memory_v2_enabled():
                result = recall_memory(query, limit=max(1, limit))
                for item in list(result.get("memories") or [])[:limit]:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("redacted_text") or item.get("text") or "").strip()
                    if text:
                        rows.append(f"- {text[:260]}")
        except Exception:
            rows = []

        if not rows:
            try:
                from shell_memory import load_memory

                memory = load_memory()
                query_tokens = {token for token in re.findall(r"[a-zA-Z0-9_]{3,}", query.lower())}
                broad_memory_query = bool(re.search(r"\b(memory|remember|yaad|meri|mera|mere|my)\b", query, flags=re.I))
                for category, items in (memory or {}).items():
                    if not isinstance(items, dict):
                        continue
                    for key, value in items.items():
                        haystack = f"{key} {value}".lower()
                        if broad_memory_query or any(token in haystack for token in query_tokens):
                            rows.append(f"- {category}.{key}: {str(value)[:220]}")
                        if len(rows) >= limit:
                            break
                    if len(rows) >= limit:
                        break
            except Exception:
                return ""
        if not rows:
            return ""
        return "\n".join(rows)[:1200]

    def _project_rag_context_snippet(self, query: str, *, limit: int = 3) -> str:
        if not self._env_flag_enabled("SHELL_CHAT_PROJECT_RAG_CONTEXT", default=True):
            return ""
        try:
            from shell_project_rag import index_project, project_rag_enabled, project_status, query_project

            if not project_rag_enabled():
                return ""
            status = project_status(str(PROJECT_ROOT))
            if int(status.get("indexed_chunks") or 0) <= 0 and self._env_flag_enabled(
                "SHELL_CHAT_PROJECT_RAG_AUTOINDEX",
                default=True,
            ):
                max_files = max(25, min(1000, int(float(os.environ.get("SHELL_CHAT_PROJECT_RAG_MAX_FILES", "250")))))
                index_project(str(PROJECT_ROOT), max_files=max_files)
            result = query_project(str(PROJECT_ROOT), query, limit=max(1, limit))
        except Exception:
            return ""

        rows: list[str] = []
        for item in list(result.get("matches") or [])[:limit] if isinstance(result, dict) else []:
            if not isinstance(item, dict):
                continue
            path = str(item.get("relative_path") or "").strip()
            start = item.get("start_line")
            end = item.get("end_line")
            preview = re.sub(r"\s+", " ", str(item.get("preview") or "")).strip()
            if path and preview:
                line_ref = f":{start}-{end}" if start and end else ""
                rows.append(f"- {path}{line_ref}: {preview[:360]}")
        return "\n".join(rows)[:1600]

    def _configured_chat_provider_keys(self) -> list[str]:
        try:
            from shell_api_manager import get_configured_secret_value
        except Exception:
            get_configured_secret_value = None  # type: ignore[assignment]

        configured: list[str] = []
        for group in CHAT_PROVIDER_SECRET_GROUPS:
            value = ""
            if get_configured_secret_value is not None:
                try:
                    value = str(get_configured_secret_value(*group) or "")
                except Exception:
                    value = ""
            if not value:
                value = next((os.environ.get(key, "") for key in group if self._looks_configured_secret(os.environ.get(key, ""))), "")
            if value:
                configured.append(group[0])
        return configured

    def _chat_provider_network_ready(self, configured_keys: list[str]) -> bool:
        if not is_network_online():
            return False
        if not configured_keys:
            return False
        if not self._env_flag_enabled("SHELL_CHAT_ONLINE_CHECK", default=True):
            return True
        cache_key = ",".join(sorted(configured_keys))
        now = time.monotonic()
        ttl = max(1.0, min(60.0, float(os.environ.get("SHELL_CHAT_ONLINE_CACHE_SECONDS", "20"))))
        cached_at, cached_key, cached_value = self._chat_provider_network_cache
        if cached_key == cache_key and now - cached_at <= ttl:
            return cached_value

        timeout = max(0.2, min(2.5, float(os.environ.get("SHELL_CHAT_ONLINE_TIMEOUT", "0.7"))))
        hosts = [CHAT_PROVIDER_PROBE_HOSTS.get(key, "") for key in configured_keys]
        hosts.append("www.google.com")
        for host in [item for item in dict.fromkeys(hosts) if item]:
            try:
                with socket.create_connection((host, 443), timeout=timeout):
                    self._chat_provider_network_cache = (now, cache_key, True)
                    return True
            except OSError:
                continue
        self._chat_provider_network_cache = (now, cache_key, False)
        return False


    def _should_try_provider_chat(self) -> bool:
        # Pehle explicit voice_mode/chat_mode lock check karo —
        # agar user ne manually "local"/"offline" set kiya hai, respect karo.
        voice_mode = os.environ.get("SHELL_VOICE_MODE", "").strip().lower()
        if voice_mode in {"local", "offline"}:
            return False

        mode = os.environ.get("SHELL_CHAT_MODE", "auto").strip().lower()
        if mode in {"local", "offline"}:
            return False

        configured_keys = self._configured_chat_provider_keys()
        if not configured_keys:
            return False

        # Keys configured hain aur mode lock nahi hai —
        # network probe karo aur result return karo.
        if self._chat_provider_network_ready(configured_keys):
            return True

        # Fallback: agar network probe fail hua but is_network_online() says
        # we're online, try once more through the probe.
        if is_network_online():
            return self._chat_provider_network_ready(configured_keys)

        return False

    def _provider_chat_reply(self, prompt: str, system_prompt: str, *, limit: int = 360) -> str:
        mock = os.environ.get("SHELL_TEST_MOCK_ONLINE_REPLY")
        if mock:
            return mock
        try:
            import concurrent.futures

            def _ask_brain() -> str:
                from brain.core import MultiAIBrain

                brain = MultiAIBrain.get_instance()
                return str(
                    brain.generate_response_sync(
                        prompt,
                        system_prompt=system_prompt,
                        mode="FAST",
                    )
                    or ""
                ).strip()

            timeout = max(4.0, float(os.environ.get("SHELL_WEB_CHAT_TIMEOUT", "8")))
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                reply = pool.submit(_ask_brain).result(timeout=timeout)
            if reply and not self._is_stale_provider_fallback_reply(reply):
                return self._compact_chat_reply(reply, limit=limit)
        except Exception:
            pass
        return ""

    def _offline_chat_reply(
        self,
        prompt: str,
        system_prompt: str,
        previous_messages: list[Any] | None = None,
        *,
        limit: int = 700,
    ) -> str:
        clean_previous_messages = self._offline_llm_history(previous_messages)
        try:
            result = generate_offline_reply(
                prompt,
                system_prompt=system_prompt,
                previous_messages=clean_previous_messages,
            )
            if getattr(result, "success", False) and getattr(result, "reply", ""):
                reply = self._compact_chat_reply(str(result.reply), limit=limit)
                if not self._is_stale_provider_fallback_reply(reply):
                    return reply
                if clean_previous_messages:
                    retry = generate_offline_reply(
                        prompt,
                        system_prompt=system_prompt,
                        previous_messages=[],
                    )
                    if getattr(retry, "success", False) and getattr(retry, "reply", ""):
                        retry_reply = self._compact_chat_reply(str(retry.reply), limit=limit)
                        if not self._is_stale_provider_fallback_reply(retry_reply):
                            return retry_reply
        except Exception:
            pass
        return ""

    def _offline_chat_reply_with_limit(
        self,
        prompt: str,
        system_prompt: str,
        previous_messages: list[Any] | None,
        *,
        limit: int,
    ) -> str:
        try:
            return self._offline_chat_reply(prompt, system_prompt, previous_messages, limit=limit)
        except TypeError:
            return self._offline_chat_reply(prompt, system_prompt, previous_messages)

    def _brain_chat_fallback(self, text: str, *, previous_messages: list[Any] | None = None) -> str:
        reply_limit = self._chat_reply_limit(text)
        history_context = self._history_context_snippet(previous_messages or [])
        memory_context = self._memory_context_snippet(text)
        rag_context = self._project_rag_context_snippet(text)
        context_sections: list[str] = []
        if history_context:
            context_sections.append(f"Recent conversation:\n{history_context}")
        if memory_context:
            context_sections.append(f"Relevant local memory:\n{memory_context}")
        if rag_context:
            context_sections.append(f"Relevant Project RAG:\n{rag_context}")
        system_prompt = (
            "You are Shell AI, a concise desktop OS assistant. "
            f"{_shell_language_instruction()} "
            "If the user asks who made, created, built, developed, owns, or created Shell AI, "
            "answer exactly: Mujhe mdshoebking ne banaya hai. Never say Meta, Google, OpenAI, Gemini, Qwen, llama.cpp, or any provider/model made you. "
            f"{self._chat_depth_instruction(text)} "
            "Do not claim you executed tools in this text-only fallback. "
            "Do not give generic capability refusals like 'I cannot make PDFs/images/open apps'; Shell has tools for files, PDFs, images, apps, and OS actions, so explain only the exact unavailable route or dependency if tool routing is unavailable. "
            "Use recent conversation, memory, and Project RAG context when relevant. Do not invent missing context."
        )
        context_block = "\n\n".join(context_sections)
        prompt = text if not context_block else f"{context_block}\n\nUser: {text}"
        if self._should_try_provider_chat():
            provider_reply = self._provider_chat_reply(prompt, system_prompt, limit=reply_limit)
            if provider_reply and not self._is_unrequested_creator_identity_reply(text, provider_reply):
                return provider_reply

        offline_reply = self._offline_chat_reply_with_limit(prompt, system_prompt, previous_messages, limit=reply_limit)
        if offline_reply and not self._is_unrequested_creator_identity_reply(text, offline_reply):
            return offline_reply
        if context_block:
            offline_reply = self._offline_chat_reply_with_limit(text, system_prompt, [], limit=reply_limit)
            if offline_reply and not self._is_unrequested_creator_identity_reply(text, offline_reply):
                return offline_reply

        return self._local_chat_answer(text)

    def _local_chat_answer(self, text: str) -> str:
        language = _shell_language()
        query = " ".join(str(text or "").lower().split())
        
        # Conversational Hinglish check-ins
        if re.search(r"\b(kaise\s+ho|how\s+are\s+you|how\s+r\s+u)\b", query):
            if language == "english":
                return "I'm doing well, thank you! How can I help you today?"
            if language == "hindi":
                return "मैं ठीक हूँ, धन्यवाद! आज आपकी क्या सेवा करूँ?"
            return "Main badhiya hoon bhai! Aap batao, aaj kya help chahiye?"
        if re.search(r"\b(kya\s+kar\s+rahe\s+ho|kya\s+kar\s+rahe|kya\s+kar\s+raha|what\s+are\s+you\s+doing|what\s+u\s+doing)\b", query):
            if language == "english":
                return "I am ready to help you run commands or research queries offline."
            if language == "hindi":
                return "मैं आपके ऑफलाइन कमांड और रिसर्च क्वेरी में मदद के लिए तैयार हूँ।"
            return "Kuch nahi bhai, aapki help karne ke liye ready baithi hoon offline mode mein."
        if re.search(r"\b(kya\s+chal\s+raha|kya\s+chal\s+raha\s+hai|whats\s+up|what's\s+up)\b", query):
            if language == "english":
                return "Everything is good! How can I assist you?"
            if language == "hindi":
                return "सब ठीक है! मैं आपकी क्या सहायता करूँ?"
            return "Sab badhiya chal raha hai bhai! Batao kya madad karu?"
        if re.search(r"\b(namaste|pranam|ram\s+ram)\b", query):
            return "Namaste bhai! Kaise ho? Kya help chahiye aaj?"

        if "capital of france" in query:
            if language == "english":
                return "The capital of France is Paris."
            if language == "hindi":
                return "France की राजधानी Paris है."
            return "France ki capital Paris hai."
        if "memory" in query and "python" in query:
            if language == "english":
                return "Python stores objects on the heap; reference counting and garbage collection clean up unused objects."
            if language == "hindi":
                return "Python objects को heap में रखता है; reference counting और garbage collector unused objects clean करते हैं."
            return "Python memory objects ko heap mein manage karta hai; reference counting aur garbage collector unused objects clean karte hain."
        if "network protocol" in query:
            if language == "english":
                return "A network protocol is a set of rules devices use to exchange data, such as TCP/IP, HTTP, and DNS."
            if language == "hindi":
                return "Network protocol rules का set होता है जिससे devices data exchange करते हैं, जैसे TCP/IP, HTTP और DNS."
            return "Network protocol rules ka set hota hai jisse devices data exchange karte hain, jaise TCP/IP, HTTP, DNS."
        if re.search(r"\b(who\s+are\s+you|tum\s+kaun|tum\s+kon|tu\s+kaun|tu\s+kon|aap\s+kaun|aap\s+kon|kaun\s+ho|kon\s+ho)\b", query):
            if language == "english":
                return "I am Shell AI, your desktop OS controller and assistant."
            if language == "hindi":
                return "मैं Shell AI हूँ, आपका desktop OS controller और assistant."
            return "Main Shell AI hoon, tumhara desktop OS controller aur assistant."
        if query in {"hi", "hello", "hey", "salam", "assalamualaikum"}:
            return "Haan bhai, bolo. Main sun rahi hoon."
        if "youtube" in query and re.search(r"\b(summarize|summary|main ideas|what.*about|watch this|video)\b", query):
            return (
                "I can see this is a YouTube/browser context, but I do not have a transcript in offline mode. "
                "I can summarize the page title/selected text I captured, or you can enable online research/transcript access for a fuller video summary."
            )
        if "active app context" in query and re.search(r"\b(what.*looking at|where am i|which app|context)\b", query):
            title_match = re.search(r'"title":\s*"([^"]+)"', str(text or ""))
            app_match = re.search(r'"app_name":\s*"([^"]+)"', str(text or ""))
            app = app_match.group(1) if app_match else "the active app"
            title = title_match.group(1) if title_match else ""
            suffix = f": {title}" if title else ""
            return f"You are currently in {app}{suffix}."
        if self._has_command_intent(query):
            return (
                "Shell action intent samajh aa gaya, lekin is request ka exact safe tool route nahi mila. "
                "Thoda specific command likho, jaise `PDF banao`, `image banao`, `open calculator`, ya `screenshot lo`."
            )
        if language == "english":
            return "I can answer locally, but this request needs more detail. Tell me the exact topic, format, or action you want."
        if language == "hindi":
            return "Main local mode mein jawab de sakti hoon, lekin is request ke liye thodi aur detail chahiye. Topic, format, ya action clear batao."
        return "Main local mode mein jawab de sakti hoon. Is request ke liye topic, format, ya exact action thoda clear batao."

    @classmethod
    def _format_agent_success_reply(cls, tool: str, rendered_text: str) -> str:
        if "orchestrate_shell_goal" in str(tool).lower():
            return cls._format_orchestration_reply(rendered_text)
        if "research_agent" in str(tool).lower():
            cleaned = re.sub(r"^\[ResearchAgent\]\s*\([^)]*\)\s*", "", rendered_text, flags=re.I | re.S).strip()
            cleaned = re.sub(r"\s*\[Tool Execution:\s*[^\]]+\]\s*$", "", cleaned, flags=re.I | re.S).strip()
            cleaned = re.sub(r"^\*\*(summary[^*]*):\*\*\s*", r"\1: ", cleaned, flags=re.I).strip()
            return f"Deep research complete: {cls._compact_chat_reply(cleaned or rendered_text, limit=900)}"
        text = str(rendered_text or "").strip()
        if not text or (text.startswith("{") and text.endswith("}")) or re.search(r"\bshell_[a-z0-9_:-]+\b", text, flags=re.I):
            return "Done. I completed that action."
        return cls._compact_chat_reply(text, limit=900)

    @staticmethod
    def _coerce_tool_payload(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("{") and text.endswith("}"):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    return {}
        return {}

    @classmethod
    def _tool_result_user_layer(cls, route: dict[str, Any], result: Any) -> dict[str, Any]:
        tool = str(route.get("tool") or "")
        route_args = route.get("args") if isinstance(route.get("args"), dict) else {}
        request_values = [
            route.get("request"),
            route.get("raw_request"),
            route.get("prompt"),
            route.get("goal"),
            route_args.get("raw_request"),
            route_args.get("task"),
            route_args.get("goal"),
        ]
        request_text = " ".join(str(value or "").lower() for value in request_values)
        outer = dict(result) if isinstance(result, dict) else {}
        raw_payload = outer.get("result") if "result" in outer else result
        payload = cls._coerce_tool_payload(raw_payload)
        if not payload and isinstance(raw_payload, dict):
            payload = dict(raw_payload)

        error_text = ""
        if isinstance(result, dict) and result.get("status") not in {None, "success"}:
            error_text = str(result.get("message") or result.get("error") or "").strip()
        if isinstance(result, dict) and result.get("error"):
            error_text = str(result.get("error") or result.get("message") or "").strip()
        if payload.get("ok") is False or payload.get("error"):
            error_text = str(payload.get("error") or payload.get("message") or "").strip()
        if error_text:
            return {
                "user_message": f"I couldn’t complete this action. Reason: {cls._compact_chat_reply(error_text, limit=220)}",
                "ui_actions": [],
            }

        is_file_create = tool == "shell_workspace_tools:create_user_file_tool"
        if is_file_create:
            filename = str(payload.get("filename") or route_args.get("filename") or "").strip()
            destination = str(payload.get("destination") or route_args.get("destination") or "").strip().lower()
            path = str(payload.get("path") or "").strip()
            if not filename and path:
                filename = Path(path).name
            if not destination:
                destination = "computer"
            user_message = f"I created {filename or 'the file'} on your {destination}."
            ui_actions: list[dict[str, Any]] = []
            if str(payload.get("ui_hint") or "").strip().lower() == "open_file_location" and path:
                ui_actions.append(
                    {
                        "type": "OPEN_FILE_LOCATION",
                        "label": "Open folder",
                        "path": path,
                    }
                )
            return {"user_message": user_message, "ui_actions": ui_actions}

        if tool == "shell_windows_workflows:open_recent_screenshots_slideshow_tool":
            return {"user_message": "I opened your Screenshots folder and Photos.", "ui_actions": []}

        if tool == "shell_windows_workflows:organize_downloads_setups_pdfs_tool":
            if "gmail" in request_text or "mail" in request_text or "email" in request_text:
                return {
                    "user_message": (
                        "Local tools only support organizing local Downloads into Setups and PDFs right now. "
                        "Gmail search and download is not implemented yet."
                    ),
                    "ui_actions": [],
                }
            zip_folder = str(payload.get("zip_folder") or route_args.get("zip_folder") or "Setups").strip()
            pdf_folder = str(payload.get("pdf_folder") or route_args.get("pdf_folder") or "PDFs").strip()
            moved_count = int(payload.get("moved_count") or 0)
            downloads_path = str(payload.get("downloads") or "").strip()
            dry_run = bool(payload.get("dry_run") or route_args.get("dry_run"))
            if dry_run:
                path_note = f" in `{downloads_path}`" if downloads_path else ""
                return {
                    "user_message": (
                        f"I audited your Downloads{path_note}. I found {moved_count} file(s) that can be safely organized: "
                        f"ZIP/MSI/EXE files into {zip_folder}, and PDFs into {pdf_folder}. "
                        "I have not moved anything yet. Say “yes” or “allow” if you want me to move them."
                    ),
                    "ui_actions": [
                        {
                            "type": "APPROVE_ACTION",
                            "label": "Yes, organize",
                            "message": "yes, organize my Downloads",
                        },
                        {"type": "CANCEL_ACTION", "label": "Cancel"},
                    ],
                    "pending_permission": {
                        "action": "downloads_cleanup",
                        "summary": f"Move {moved_count} Downloads file(s) into {zip_folder} and {pdf_folder}.",
                        "route": cls._downloads_cleanup_route(dry_run=False, source="real-os-agent-downloads-cleanup-approved"),
                    },
                }
            return {"user_message": f"I organized your Downloads into {zip_folder} and {pdf_folder}.", "ui_actions": []}

        if tool == "shell_workspace_tools:list_workspace_files_tool":
            count = payload.get("count") or payload.get("total") or payload.get("files_count")
            if count not in {None, ""}:
                return {"user_message": f"I found {count} files in your workspace.", "ui_actions": []}
            return {"user_message": "I listed the files in your workspace.", "ui_actions": []}

        if tool == "shell_terminal:run_command_tool":
            command = str(route_args.get("command") or "").strip()
            rendered = str(raw_payload or "").strip()
            lower_rendered = rendered.lower()
            if lower_rendered.startswith("blocked:"):
                reason = cls._compact_chat_reply(rendered.replace("BLOCKED:", "", 1).strip(), limit=260)
                return {"user_message": f"I didn’t run `{command}` because {reason}", "ui_actions": []}
            if lower_rendered.startswith("error") or "exit code:" in lower_rendered:
                short = cls._compact_chat_reply(rendered, limit=520)
                return {"user_message": f"I ran `{command}`, but it did not finish cleanly. {short}", "ui_actions": []}
            short = cls._compact_chat_reply(rendered.replace("Output:", "").strip(), limit=700)
            suffix = f" Result: {short}" if short else ""
            return {"user_message": f"I ran `{command}` successfully.{suffix}", "ui_actions": []}

        if tool == "shell_email_tool:email_setup_status_tool":
            rendered = str(raw_payload or "").strip()
            if "not configured" in rendered.lower() or "credentials missing" in rendered.lower():
                return {
                    "user_message": (
                        "Gmail/email integration is not configured yet. I can open Gmail in the browser, "
                        "but inbox reading, summaries, monitoring, and attachment downloads need a Gmail API setup first."
                    ),
                    "ui_actions": [
                        {
                            "type": "OPEN_URL",
                            "label": "Open Gmail",
                            "url": "https://mail.google.com/",
                        }
                    ],
                }
            return {"user_message": rendered, "ui_actions": []}

        return {"user_message": "", "ui_actions": []}

    @classmethod
    def _format_orchestration_reply(cls, rendered_text: str) -> str:
        try:
            plan = json.loads(str(rendered_text or "{}"))
        except Exception:
            return "I checked the request, but I couldn’t turn the planner output into a safe action."
        if not isinstance(plan, dict):
            return "I checked the request, but I couldn’t turn the planner output into a safe action."

        agent = str(plan.get("selected_agent_name") or plan.get("selected_agent_id") or "Planner Agent")
        status = str(plan.get("status") or "").strip() or "planned"
        execution_status = str(plan.get("execution_status") or "").strip()
        execution_allowed = plan.get("execution_allowed")
        execution_reason = str(plan.get("execution_reason") or "").strip()
        goal = str(plan.get("goal") or plan.get("task") or "").strip()
        low_level_tool = str(plan.get("low_level_tool_id") or "").strip()
        reasons = [str(reason) for reason in plan.get("reasons") or [] if str(reason).strip()]
        reason_text = cls._compact_chat_reply("; ".join(reasons), limit=260) if reasons else ""

        if execution_allowed is False or execution_status == "blocked" or status == "blocked":
            action = cls._planner_goal_action(goal)
            reason = cls._planner_block_reason(execution_reason or reason_text)
            return (
                f"I didn’t {action} because {reason}. "
                "Advanced users can change Shell’s policy/settings if they want to allow this."
            )
        if execution_status == "success":
            tool_text = f" via {low_level_tool}" if low_level_tool else ""
            return f"Shell agent executed: {agent}{tool_text}."
        if plan.get("requires_approval"):
            suffix = f" Reason: {reason_text}" if reason_text else ""
            return f"I can do this only after approval/safety settings allow it.{suffix}"
        if status == "needs_planning":
            suffix = f" Reason: {reason_text}" if reason_text else ""
            return f"I analyzed the task, but I don’t have a direct safe local tool for it yet.{suffix}"
        tool_text = f" Tool: {low_level_tool}." if low_level_tool else ""
        suffix = f" Reason: {reason_text}" if reason_text else ""
        return f"Shell agent route ready: {agent} selected hua.{tool_text}{suffix}"

    @staticmethod
    def _planner_goal_action(goal: str) -> str:
        lower = str(goal or "").lower()
        if re.search(r"\b(npm\s+test|pytest|test|command|run)\b", lower):
            command = re.sub(r"^\s*run\s+", "", str(goal or ""), flags=re.I).strip()
            return f"run `{command}`" if command else "run that command"
        if re.search(r"\b(screenshot|screen\s*capture|capture)\b", lower):
            return "capture a screenshot"
        if re.search(r"\b(open|launch)\b", lower):
            return f"open {goal}" if goal else "open that"
        if re.search(r"\b(organize|move|copy|delete|create|make|build|write)\b", lower):
            return goal or "complete that action"
        return goal or "complete that action"

    @staticmethod
    def _planner_block_reason(reason: str) -> str:
        lower = str(reason or "").lower()
        if "screen" in lower and ("capture" in lower or "screenshot" in lower):
            return "screen capture is disabled by policy"
        if "command" in lower or "execute" in lower or "capability execution" in lower:
            return "the current safety policy doesn’t allow Shell to execute this capability"
        if "policy" in lower:
            return str(reason).strip()
        return str(reason or "the current Shell safety policy does not allow it").strip()

    @staticmethod
    def _friendly_image_failure(rendered_text: str) -> str:
        text = str(rendered_text or "")
        if "image generation failed" not in text.lower() and "no provider returned" not in text.lower():
            return text[:700]
        return (
            "Image generate nahi ho payi kyunki koi real image provider ready nahi tha. "
            "Settings > API Keys mein OpenAI, Stability, Replicate, ya HuggingFace key add karo. "
            "Free Pollinations fallback bhi try hota hai; agar network/public API empty response de to Shell local preview fallback save karega."
        )

    def _format_chat_result_payload(self, route: dict[str, Any], result: Any) -> dict[str, Any]:
        tool = route.get("tool", "backend")
        is_image_tool = str(tool) == "shell_image_ai:generate_image_tool"
        image_prompt = self._route_image_prompt(route) if is_image_tool else ""
        user_layer = self._tool_result_user_layer(route, result)
        user_message = str(user_layer.get("user_message") or "").strip()
        ui_actions = list(user_layer.get("ui_actions") or [])
        pending_permission = user_layer.get("pending_permission") if isinstance(user_layer.get("pending_permission"), dict) else None
        if isinstance(result, dict):
            if result.get("status") == "success":
                payload = result.get("result")
                rendered = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
                rendered_text = str(rendered).strip()
                if is_image_tool:
                    image_path = self._extract_generated_image_path(rendered_text)
                    if image_path and image_path.exists():
                        item = self._gallery_item_for_file(image_path)
                        self.emit_event("gallery-updated", {"success": True, "image": item})
                        self.emit_event(
                            "image-gen",
                            {
                                "url": item["url"],
                                "prompt": image_prompt or item["displayName"],
                                "loading": False,
                                "error": False,
                                "saved": True,
                                "image": item,
                            },
                        )
                        return {"user_message": f"Image generated aur Gallery mein save ho gayi: {image_path.name}", "ui_actions": []}
                    lowered_image_result = rendered_text.lower()
                    if "image generation failed" in lowered_image_result or "critical error" in lowered_image_result:
                        error_text = self._friendly_image_failure(rendered_text)
                        self.emit_event(
                            "image-gen",
                            {
                                "url": "",
                                "prompt": image_prompt,
                                "loading": False,
                                "error": True,
                                "errorMessage": error_text,
                            },
                        )
                        return {"user_message": error_text, "ui_actions": []}
                    self.emit_event(
                        "image-gen",
                        {
                            "url": "",
                            "prompt": image_prompt,
                            "loading": False,
                            "error": True,
                            "errorMessage": "Image generation completed but no saved image path was returned.",
                        },
                    )
                    return {"user_message": self._compact_chat_reply(rendered_text, limit=520), "ui_actions": []}
                if user_message:
                    payload_result = {"user_message": user_message, "ui_actions": ui_actions}
                    if pending_permission:
                        payload_result["pending_permission"] = pending_permission
                    return payload_result
                if (
                    rendered_text.startswith("[BLOCKED]")
                    or "CODE WRITE BLOCKED" in rendered_text
                    or "Writing LLM-generated Python to disk is disabled" in rendered_text
                ):
                    reason = rendered_text.replace("[BLOCKED]", "", 1).strip()
                    message = (
                        "Code creation safety settings se blocked hai. "
                        "Website/app scaffold default allowed hai; agar SHELL_BLOCK_PROJECT_SCAFFOLD=1 set hai to remove karo. "
                        "Core code writes ke liye trusted session mein SHELL_ALLOW_CODE_WRITE=1 use karo. "
                        f"{reason[:620]}"
                    ).strip()
                    return {"user_message": message, "ui_actions": []}
                if "calculator" in str(tool).lower():
                    for line in rendered_text.splitlines():
                        if line.strip().lower().startswith("result:"):
                            return {"user_message": line.strip(), "ui_actions": []}
                return {"user_message": self._format_agent_success_reply(str(tool), rendered_text), "ui_actions": []}
            message = result.get("message") or result.get("error") or json.dumps(result, ensure_ascii=False)
            if is_image_tool:
                self.emit_event(
                    "image-gen",
                    {
                        "url": "",
                        "prompt": image_prompt,
                        "loading": False,
                        "error": True,
                        "errorMessage": str(message).strip()[:700],
                    },
                )
            if user_message:
                payload_result = {"user_message": user_message, "ui_actions": ui_actions}
                if pending_permission:
                    payload_result["pending_permission"] = pending_permission
                return payload_result
            short_message = self._compact_chat_reply(str(message).strip(), limit=220)
            return {"user_message": f"I couldn’t complete this action. Reason: {short_message}", "ui_actions": []}
        if is_image_tool:
            self.emit_event(
                "image-gen",
                {
                    "url": "",
                    "prompt": image_prompt,
                    "loading": False,
                    "error": True,
                    "errorMessage": str(result).strip()[:700],
                },
            )
        if user_message:
            payload_result = {"user_message": user_message, "ui_actions": ui_actions}
            if pending_permission:
                payload_result["pending_permission"] = pending_permission
            return payload_result
        return {"user_message": "Done. I completed that action.", "ui_actions": []}

    def _format_chat_result(self, route: dict[str, Any], result: Any) -> str:
        formatted = self._format_chat_result_payload(route, result)
        return str(formatted.get("user_message") or "").strip()

    @staticmethod
    def _extract_generated_image_path(text: str) -> Path | None:
        raw = str(text or "")
        candidates = re.findall(r"`([^`]+\.(?:png|jpg|jpeg|webp|gif))`", raw, flags=re.I)
        candidates.extend(re.findall(r"((?:/[^\s`]+|[A-Za-z]:\\[^\s`]+)\.(?:png|jpg|jpeg|webp|gif))", raw, flags=re.I))
        for candidate in candidates:
            try:
                path = Path(candidate).expanduser()
                if path.exists() and path.is_file():
                    return path
            except Exception:
                continue
        return None

    def _stop_speech_process(self) -> None:
        self._invalidate_speech_jobs()
        speaker = getattr(self, "_cloud_tts_speaker", None)
        if speaker is not None:
            try:
                speaker.stop_speaking()
            except Exception:
                pass
        proc = getattr(self, "_speech_process", None)
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=0.4)
                except Exception:
                    proc.kill()
        except Exception:
            pass
        self._speech_process = None

    def _start_os_tts(self, text: str, *, job_id: int | None = None) -> dict[str, Any]:
        job_id = job_id or self._next_speech_job_id()
        self.emit_event(
            "speech-status",
            {
                "state": "queued",
                "engine": "system",
                "source": "os-tts",
                "chars": len(text),
            },
        )

        def run() -> None:
            system = platform.system().lower()
            success = False
            engine_name = "System SAPI"
            
            if system == "windows":
                powershell = shutil.which("powershell") or shutil.which("powershell.exe")
                if powershell:
                    safe_text = text.replace("'", "''").replace('"', '`"')
                    script = (
                        "Add-Type -AssemblyName System.Speech; "
                        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        f"$synth.Speak('{safe_text}'); $synth.Dispose()"
                    )
                    try:
                        subprocess.run(
                            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=30,
                        )
                        success = True
                    except Exception:
                        pass
            elif system == "darwin":
                if shutil.which("say"):
                    try:
                        subprocess.run(["say", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                        success = True
                        engine_name = "macOS say"
                    except Exception:
                        pass
            else:
                for name in ("spd-say", "espeak-ng", "espeak"):
                    if shutil.which(name):
                        try:
                            subprocess.run([name, text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                            success = True
                            engine_name = name
                            break
                        except Exception:
                            pass
            
            if not success:
                try:
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                    engine.stop()
                    success = True
                    engine_name = "pyttsx3"
                except Exception:
                    pass

            if job_id != self._current_speech_job_id():
                return

            if success:
                self.emit_event(
                    "speech-status",
                    {
                        "state": "speaking",
                        "engine": "system",
                        "voice": engine_name,
                        "chars": len(text),
                    },
                )
            else:
                self.emit_event(
                    "speech-status",
                    {
                        "state": "error",
                        "engine": "system",
                        "message": "No local TTS engine available.",
                    },
                )

        self._start_background_task("ShellOSTTS", run)
        return {
            "success": True,
            "queued": True,
            "source": "os-tts",
            "engine": "system",
            "message": "System OS speech queued",
            "chars": len(text),
        }

    @staticmethod
    def _offline_tts_ready() -> tuple[bool, dict[str, Any]]:
        try:
            status = offline_tts_status()
        except Exception as exc:
            status = {"available": False, "engine": "fallback", "reason": str(exc)}
        return bool(status.get("available")), status

    def _queue_offline_tts(self, text: str, *, fallback_from: str = "") -> dict[str, Any]:
        job_id = self._next_speech_job_id()
        self.emit_event(
            "speech-status",
            {
                "state": "queued",
                "engine": "offline",
                "source": "offline-tts",
                "fallbackFrom": fallback_from or None,
                "chars": len(text),
            },
        )

        def run() -> None:
            critical_prime_wait_ms = 0.0
            if text in CRITICAL_OFFLINE_TTS_PHRASES and not self._offline_tts_critical_prime_ready.is_set():
                wait_started = time.perf_counter()
                wait_timeout_ms = max(0, int(os.environ.get("SHELL_OFFLINE_TTS_CRITICAL_WAIT_MS", "0") or "0"))
                self._offline_tts_critical_prime_ready.wait(timeout=wait_timeout_ms / 1000.0)
                critical_prime_wait_ms = (time.perf_counter() - wait_started) * 1000.0
            offline_result = speak_offline_tts(text)
            offline_process = offline_result.pop("_process", None) if isinstance(offline_result, dict) else None
            if job_id != self._current_speech_job_id():
                if offline_process is not None:
                    try:
                        offline_process.terminate()
                    except Exception:
                        pass
                return

            if isinstance(offline_result, dict) and offline_result.get("success"):
                if offline_process is not None:
                    self._speech_process = offline_process
                payload = self._speech_status_payload(
                    "speaking",
                    offline_result,
                    text=text,
                    criticalPrimeWaitMs=round(critical_prime_wait_ms, 2),
                )
                if fallback_from:
                    payload["fallbackFrom"] = fallback_from
                self.emit_event("speech-status", payload)
                return

            if isinstance(offline_result, dict) and offline_result.get("available"):
                self.emit_event(
                    "speech-status",
                    {
                        "state": "error",
                        "engine": offline_result.get("engine", "offline"),
                        "message": offline_result.get("message", "Kokoro offline voice failed."),
                    },
                )
                return
            message = (
                offline_result.get("message", "Kokoro offline voice is unavailable.")
                if isinstance(offline_result, dict)
                else "Kokoro offline voice is unavailable."
            )
            self.emit_event("speech-status", {"state": "error", "engine": "kokoro", "message": message})

        self._start_background_task("ShellOfflineTTS", run)
        return {
            "success": True,
            "queued": True,
            "source": "offline-tts",
            "engine": "offline",
            "message": "Offline natural speech queued",
            "chars": len(text),
        }

    @staticmethod
    def _looks_configured_secret(value: str) -> bool:
        low = str(value or "").strip().lower()
        return bool(low) and len(low) >= 20 and low not in {
            "your_google_api_key_here",
            "your_gemini_api_key_here",
            "your_google_api_key",
            "your_gemini_api_key",
        } and not low.startswith(("your_", "replace_"))

    def _configured_gemini_voice_key(self) -> str:
        direct = os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        if self._looks_configured_secret(direct):
            return direct
        try:
            from shell_api_manager import get_configured_secret_value

            value = str(get_configured_secret_value("GOOGLE_API_KEY", "GEMINI_API_KEY") or "")
        except Exception:
            value = ""
        if self._looks_configured_secret(value):
            return value
        return ""

    def _gemini_voice_configured(self) -> bool:
        return bool(self._configured_gemini_voice_key())

    def _cloud_voice_requested(self) -> bool:
        if is_network_online() and self._gemini_voice_configured():
            return True
        mode = os.environ.get("SHELL_VOICE_MODE", "").strip().lower()
        engine = os.environ.get("SHELL_TTS_ENGINE", "").strip().lower()
        if mode == "cloud":
            return True
        if engine in {"gemini", "gemini-live", "gemini-stream", "live", "live-pcm", "cloud"}:
            return True
        return mode == "auto" and self._gemini_voice_configured()

    def _cloud_tts_source(self) -> str:
        if not self._cloud_voice_requested():
            return ""
        gemini_key = self._configured_gemini_voice_key()
        if not gemini_key:
            return ""
        if TTSSpeaker is None:
            return ""
        if not os.environ.get("GOOGLE_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = gemini_key
        if not os.environ.get("GEMINI_API_KEY"):
            os.environ["GEMINI_API_KEY"] = gemini_key
        if not self._chat_provider_network_ready(["GOOGLE_API_KEY"]):
            return ""
        return "gemini-live"

    def _ensure_cloud_tts_speaker(self) -> Any | None:
        if TTSSpeaker is None:
            return None
        speaker = getattr(self, "_cloud_tts_speaker", None)
        if speaker is None:
            speaker = TTSSpeaker(self)
            speaker._engine = os.environ.get("SHELL_TTS_ENGINE", "gemini-live").strip().lower() or "gemini-live"
            if speaker._engine in {"auto", "fast", "system"}:
                speaker._engine = "gemini-live"
            try:
                speaker.speech_error.connect(self._on_cloud_tts_error)
                speaker.speaking_finished.connect(
                    lambda: self.emit_event("speech-status", {"state": "stopped", "engine": "gemini"})
                )
            except Exception:
                pass
            speaker.start()
            self._cloud_tts_speaker = speaker
        return speaker

    @staticmethod
    def _speech_status_payload(
        state: str,
        result: dict[str, Any] | None = None,
        *,
        engine: str = "",
        text: str = "",
        **extra: Any,
    ) -> dict[str, Any]:
        result = result if isinstance(result, dict) else {}
        payload: dict[str, Any] = {
            "state": state,
            "engine": engine or str(result.get("engine", "offline") or "offline"),
            "voice": result.get("voice", ""),
            "chars": result.get("chars", len(text)),
        }
        if text:
            payload["text"] = str(text)[:320]
        for key in (
            "durationMs",
            "amplitudeFrameMs",
            "amplitudeFrames",
            "playbackBackend",
            "cacheHit",
            "presetHit",
            "synthesisMs",
            "playbackStartMs",
            "totalMs",
        ):
            value = result.get(key)
            if value not in (None, ""):
                payload[key] = value
        payload.update({key: value for key, value in extra.items() if value not in (None, "")})
        return payload

    def _speak_cloud_tts(self, text: str) -> dict[str, Any]:
        source = self._cloud_tts_source()
        if not source:
            return {"success": False, "available": False, "engine": "gemini", "message": "Gemini cloud voice is not configured."}
        speaker = self._ensure_cloud_tts_speaker()
        if speaker is None:
            return {"success": False, "available": False, "engine": "gemini", "message": "Gemini voice runtime is unavailable."}
        try:
            gemini_key = self._configured_gemini_voice_key()
            if gemini_key and not os.environ.get("GOOGLE_API_KEY"):
                os.environ["GOOGLE_API_KEY"] = gemini_key
            if gemini_key and not os.environ.get("GEMINI_API_KEY"):
                os.environ["GEMINI_API_KEY"] = gemini_key
            speaker.set_voice(os.environ.get("VOICE_NAME") or os.environ.get("VOICE_PERSONA") or "Aoede")
            self._cloud_tts_fallback_text = text
            speaker.speak(text, force=True)
        except Exception as exc:
            self.emit_event("speech-status", {"state": "error", "engine": "gemini", "message": str(exc)})
            return {"success": False, "available": True, "engine": "gemini", "message": str(exc)}
        voice = ""
        try:
            voice = speaker.voice_identity_snapshot().get("gemini_voice", "")
        except Exception:
            voice = os.environ.get("VOICE_NAME", "Aoede")
        self.emit_event("speech-status", {"state": "speaking", "engine": "gemini", "voice": voice, "chars": len(text)})
        return {
            "success": True,
            "available": True,
            "engine": "gemini",
            "voice": voice,
            "chars": len(text),
            "message": "Gemini cloud speech queued",
            "source": source,
        }

    def _on_cloud_tts_error(self, message: str) -> None:
        text = str(getattr(self, "_cloud_tts_fallback_text", "") or "").strip()
        self.emit_event(
            "speech-status",
            {
                "state": "fallback",
                "engine": "gemini",
                "message": f"Gemini voice failed; using offline voice. {str(message)[:180]}",
            },
        )
        if not text:
            return
        offline_ready, _status = self._offline_tts_ready()
        if offline_ready:
            self._queue_offline_tts(text, fallback_from="gemini")
            return
        self.emit_event(
            "speech-status",
            {
                "state": "error",
                "engine": "kokoro",
                "message": "Gemini voice failed and Kokoro offline voice is unavailable.",
            },
        )

    def _tts_command(self, text: str) -> list[str] | None:
        return None

    def _offline_tts_status(self, _args: list[Any] | None = None) -> dict[str, Any]:
        return offline_tts_status()

    def _offline_llm_status(self, _args: list[Any] | None = None) -> dict[str, Any]:
        return offline_llm_status()

    def _offline_coding_llm_status(self, _args: list[Any] | None = None) -> dict[str, Any]:
        return offline_coding_llm_status()

    def _offline_llm_catalog(self, _args: list[Any] | None = None) -> dict[str, Any]:
        return self._offline_llm_catalog_for_category(CHAT_MODEL_CATEGORY)

    def _offline_coding_llm_catalog(self, _args: list[Any] | None = None) -> dict[str, Any]:
        return self._offline_llm_catalog_for_category(CODING_MODEL_CATEGORY)

    def _offline_llm_catalog_for_category(self, category: str) -> dict[str, Any]:
        status = offline_coding_llm_status() if category == CODING_MODEL_CATEGORY else offline_llm_status()
        catalog = offline_llm_catalog_payload(category)
        if isinstance(status, dict):
            catalog["status"] = status
            catalog["available"] = status.get("available") is True
            catalog["selectedModelId"] = status.get("selectedModelId") or catalog.get("selectedModelId") or ""
            catalog["selectedModelPath"] = status.get("modelPath") or catalog.get("selectedModelPath") or ""
        with self._offline_llm_download_lock:
            catalog["downloads"] = dict(self._offline_llm_downloads)
        return catalog

    def _offline_llm_download(self, args: list[Any]) -> dict[str, Any]:
        return self._offline_llm_download_for_category(args, CHAT_MODEL_CATEGORY)

    def _offline_coding_llm_download(self, args: list[Any]) -> dict[str, Any]:
        return self._offline_llm_download_for_category(args, CODING_MODEL_CATEGORY)

    def _offline_llm_download_for_category(self, args: list[Any], category: str) -> dict[str, Any]:
        payload = args[0] if args and isinstance(args[0], dict) else {}
        model_id = str(payload.get("modelId") or payload.get("id") or "").strip()
        option = get_offline_model_option(model_id, category)
        if option is None:
            return {"success": False, "message": "Unknown offline model option.", "modelId": model_id}

        target_dir = offline_model_install_dir(option.id)
        target_path = target_dir / option.filename
        if target_path.exists() and target_path.is_file():
            return self._offline_llm_select_for_category([{"modelId": option.id}], category)

        with self._offline_llm_download_lock:
            current = self._offline_llm_downloads.get(option.id)
            if current and current.get("status") in {"queued", "downloading", "verifying"}:
                return {"success": True, "status": current.get("status"), "modelId": option.id, "download": current}
            self._offline_llm_downloads[option.id] = {
                "status": "queued",
                "category": category,
                "percent": 0,
                "downloadedBytes": 0,
                "totalBytes": option.size_bytes,
                "message": "Queued",
            }

        self._start_background_task("ShellOfflineModelDownload", lambda: self._download_offline_llm_model(option, category=category))
        return {"success": True, "status": "queued", "modelId": option.id}

    def _offline_llm_select(self, args: list[Any]) -> dict[str, Any]:
        return self._offline_llm_select_for_category(args, CHAT_MODEL_CATEGORY)

    def _offline_coding_llm_select(self, args: list[Any]) -> dict[str, Any]:
        return self._offline_llm_select_for_category(args, CODING_MODEL_CATEGORY)

    def _offline_llm_select_for_category(self, args: list[Any], category: str) -> dict[str, Any]:
        payload = args[0] if args and isinstance(args[0], dict) else {}
        model_id = str(payload.get("modelId") or payload.get("id") or "").strip()
        option = get_offline_model_option(model_id, category)
        if option is None:
            return {"success": False, "message": "Unknown offline model option.", "modelId": model_id}

        target_path = offline_model_install_dir(option.id) / option.filename
        if not target_path.exists() or not target_path.is_file():
            label = "offline coding brain" if category == CODING_MODEL_CATEGORY else "offline brain"
            return {
                "success": False,
                "status": "missing",
                "message": f"Download this {label} before using it.",
                "modelId": option.id,
                "modelPath": str(target_path),
            }

        write_offline_model_metadata(option, model_path=target_path, category=category)
        try:
            from shell_offline_llm import _reset_cached_model_for_tests

            _reset_cached_model_for_tests()
        except Exception:
            pass
        catalog = self._offline_llm_catalog_for_category(category)
        return {
            "success": True,
            "status": "selected",
            "category": category,
            "modelId": option.id,
            "modelPath": str(target_path),
            "message": f"{option.name} is active",
            "catalog": catalog,
        }

    def _set_offline_llm_download_state(self, model_id: str, state: dict[str, Any]) -> None:
        with self._offline_llm_download_lock:
            current = dict(self._offline_llm_downloads.get(model_id) or {})
            current.update(state)
            self._offline_llm_downloads[model_id] = current
        self.emit_event("offline-llm-download-event", {"modelId": model_id, **current})

    def _download_offline_llm_model(self, option: Any, *, category: str = CHAT_MODEL_CATEGORY) -> None:
        target_dir = offline_model_install_dir(option.id)
        target_path = target_dir / option.filename
        partial_path = target_dir / f"{option.filename}.download"
        target_dir.mkdir(parents=True, exist_ok=True)
        parsed_url = urllib.parse.urlparse(option.download_url)
        if parsed_url.scheme != "https" or parsed_url.netloc.lower() != "huggingface.co":
            self._set_offline_llm_download_state(
                option.id,
                {"status": "error", "category": category, "message": "Offline model download host is not allowed.", "percent": 0},
            )
            return

        downloaded = 0
        digest = hashlib.sha256()
        self._set_offline_llm_download_state(
            option.id,
            {
                "status": "downloading",
                "category": category,
                "message": f"Downloading {option.name}",
                "percent": 0,
                "downloadedBytes": 0,
                "totalBytes": option.size_bytes,
            },
        )
        try:
            request = urllib.request.Request(
                option.download_url,
                headers={"User-Agent": f"ShellAI/{self._get_app_version()} offline-model-downloader"},
            )
            with urllib.request.urlopen(request, timeout=45) as response, partial_path.open("wb") as output:
                content_length = response.headers.get("Content-Length")
                total_bytes = int(content_length) if content_length and content_length.isdigit() else int(option.size_bytes)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)
                    percent = min(99, round((downloaded / max(1, total_bytes)) * 100))
                    self._set_offline_llm_download_state(
                        option.id,
                        {
                            "status": "downloading",
                            "category": category,
                            "message": f"Downloading {option.name}",
                            "percent": percent,
                            "downloadedBytes": downloaded,
                            "totalBytes": total_bytes,
                        },
                    )

            self._set_offline_llm_download_state(
                option.id,
                {
                    "status": "verifying",
                    "category": category,
                    "message": "Verifying model checksum",
                    "percent": 99,
                    "downloadedBytes": downloaded,
                    "totalBytes": option.size_bytes,
                },
            )
            actual_sha = digest.hexdigest().lower()
            if actual_sha != str(option.sha256).lower():
                try:
                    partial_path.unlink()
                except Exception:
                    pass
                self._set_offline_llm_download_state(
                    option.id,
                    {
                        "status": "error",
                        "category": category,
                        "message": "Model checksum failed. Download was discarded.",
                        "percent": 0,
                        "sha256": actual_sha,
                    },
                )
                return

            partial_path.replace(target_path)
            write_offline_model_metadata(option, model_path=target_path, category=category)
            try:
                from shell_offline_llm import _reset_cached_model_for_tests

                _reset_cached_model_for_tests()
            except Exception:
                pass
            self._set_offline_llm_download_state(
                option.id,
                {
                    "status": "installed",
                    "category": category,
                    "message": f"{option.name} installed",
                    "percent": 100,
                    "downloadedBytes": target_path.stat().st_size,
                    "totalBytes": option.size_bytes,
                    "modelPath": str(target_path),
                    "catalog": self._offline_llm_catalog_for_category(category),
                },
            )
        except Exception as exc:
            try:
                if partial_path.exists():
                    partial_path.unlink()
            except Exception:
                pass
            self._set_offline_llm_download_state(
                option.id,
                {"status": "error", "category": category, "message": f"Model download failed: {exc}", "percent": 0},
            )

    def _probe_voice_amplitude(self, args: list[Any]) -> dict[str, Any]:
        if os.environ.get("SHELL_UI_PROBE_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
            return {"success": False, "message": "UI probe channel is disabled."}
        payload = args[0] if args and isinstance(args[0], dict) else {}
        value = max(0.0, min(1.0, float(payload.get("value", 0.95) or 0.0)))
        speaking = bool(payload.get("speaking", True))
        self.emit_event("voice-status", {"state": "listening", "actualRuntime": False, "probe": True})
        if speaking:
            self.emit_event("speech-status", {"state": "speaking", "engine": "probe"})
        self.emit_event("voice-amplitude", {"value": value, "probe": True})
        return {"success": True, "value": value, "speaking": speaking}

    def _speak_text(self, args: list[Any]) -> dict[str, Any]:
        text = " ".join(str(args[0] if args else "").strip().split())
        if not text:
            return {"success": False, "message": "No speech text provided"}

        max_chars = int(os.environ.get("SHELL_TTS_MAX_CHARS", "320") or "320")
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0].strip() + "..."

        self._stop_speech_process()
        cloud_result = self._speak_cloud_tts(text)
        if cloud_result.get("success"):
            return cloud_result

        offline_ready, status = self._offline_tts_ready()
        if offline_ready:
            queued = self._queue_offline_tts(text)
            queued["engine"] = str(status.get("engine") or "offline")
            queued["label"] = status.get("label", "Offline natural voice")
            return queued

        # Agar offline model (Kokoro) unavailable hai, toh error return karo.
        # OS TTS fallback desktop EXE me focus steal karta hai, isliye yahan
        # silently use nahi karna.
        self.emit_event(
            "speech-status",
            {
                "state": "error",
                "engine": status.get("engine", "kokoro"),
                "message": status.get("reason") or "Offline voice model is unavailable.",
            },
        )
        return {
            "success": False,
            "source": "kokoro-unavailable",
            "engine": status.get("engine", "kokoro"),
            "message": status.get("reason") or "Offline voice model is unavailable.",
        }

    def _stop_speech(self, _args: list[Any]) -> dict[str, Any]:
        self._stop_speech_process()
        self.emit_event("speech-status", {"state": "stopped"})
        return {"success": True, "message": "Speech stopped"}

    def _start_voice(self, _args: list[Any]) -> dict[str, Any]:
        listener = getattr(self, "_voice_listener", None)
        if listener is not None:
            try:
                if listener.isRunning():
                    return {"success": True, "message": "Voice already listening", "actualRuntime": True}
            except Exception:
                self._voice_listener = None

        self.emit_event("voice-status", {"state": "starting", "actualRuntime": True})
        try:
            from shell_neural_voice import VOICE_COORDINATOR
            from shell_voice_listener_runtime import VoiceListenerThread

            self._voice_input_unavailable_state = False
            VOICE_COORDINATOR.start("shell-web-ui")
            listener = VoiceListenerThread(parent=self)
            listener.text_recognized.connect(self._on_voice_text)
            listener.amplitude_changed.connect(self._on_voice_amplitude)
            listener.status_changed.connect(self._on_voice_status)
            listener.error_occurred.connect(self._on_voice_error)
            listener.listening_started.connect(self._on_voice_started)
            listener.listening_stopped.connect(self._on_voice_stopped)
            listener.latency_event.connect(self._on_voice_latency)
            self._voice_listener = listener
            listener.start()
            return {"success": True, "message": "Voice listener starting", "actualRuntime": True}
        except Exception as exc:
            self._voice_listener = None
            self.emit_event("voice-status", {"state": "error", "error": str(exc), "actualRuntime": False})
            return {"success": False, "message": str(exc), "actualRuntime": False}

    def _stop_voice(self, _args: list[Any]) -> dict[str, Any]:
        self._voice_input_unavailable_state = False
        listener = getattr(self, "_voice_listener", None)
        if listener is not None:
            try:
                if listener.isRunning():
                    listener.stop_listening()
                    listener.wait(2500)
            except Exception:
                pass
        self._voice_listener = None
        try:
            from shell_neural_voice import VOICE_COORDINATOR

            VOICE_COORDINATOR.stop()
        except Exception:
            pass
        self.emit_event("voice-status", {"state": "stopped", "actualRuntime": True})
        return {"success": True, "message": "Voice stop requested"}

    def _set_voice_muted(self, args: list[Any]) -> dict[str, Any]:
        muted = bool(args[0]) if args else False
        listener = getattr(self, "_voice_listener", None)
        if listener is None:
            return {"success": True, "muted": muted, "message": "Voice listener inactive"}
        try:
            if hasattr(listener, "set_muted"):
                listener.set_muted(muted)
            elif hasattr(listener, "muted"):
                setattr(listener, "muted", muted)
            self.emit_event("voice-status", {"state": "muted" if muted else "listening", "actualRuntime": True})
            return {"success": True, "muted": muted}
        except Exception as exc:
            self.emit_event("voice-status", {"state": "error", "error": str(exc), "actualRuntime": True})
            return {"success": False, "muted": muted, "message": str(exc)}

    def _on_voice_started(self) -> None:
        self.emit_event("voice-status", {"state": "listening", "actualRuntime": True})

    def _on_voice_stopped(self) -> None:
        if self._voice_input_unavailable_state:
            self.emit_event(
                "voice-status",
                {
                    "state": "mic_missing",
                    "message": "Microphone unavailable. Shell can still speak; voice input is disabled.",
                    "actualRuntime": False,
                },
            )
            return
        self.emit_event("voice-status", {"state": "stopped", "actualRuntime": True})

    def _on_voice_status(self, status: str) -> None:
        self.emit_event("voice-status", {"state": str(status or "listening").lower(), "actualRuntime": True})

    def _on_voice_error(self, error: str) -> None:
        message = str(error or "Voice error")
        if self._is_voice_input_unavailable_error(message):
            self._voice_input_unavailable_state = True
            self.emit_event(
                "voice-status",
                {
                    "state": "mic_missing",
                    "error": message,
                    "message": f"{message}. Shell can still speak; voice input is disabled.",
                    "actualRuntime": False,
                },
            )
            return
        self.emit_event("voice-status", {"state": "error", "error": message, "actualRuntime": True})

    @staticmethod
    def _is_voice_input_unavailable_error(message: str) -> bool:
        lower = str(message or "").lower()
        input_markers = (
            "sounddevice",
            "microphone",
            "mic",
            "input device",
            "default input",
            "no input",
            "portaudio",
            "speechrecognition",
            "speech recognition",
        )
        return any(marker in lower for marker in input_markers)

    def _on_voice_amplitude(self, value: float) -> None:
        now = time.perf_counter()
        if now - self._last_voice_amp_event < 0.08:
            return
        self._last_voice_amp_event = now
        self.emit_event("voice-amplitude", {"value": max(0.0, min(1.0, float(value or 0.0)))})

    def _on_voice_latency(self, event: str, payload: object) -> None:
        self.emit_event("voice-latency", {"event": event, "payload": payload})

    def _on_voice_text(self, text: str) -> None:
        value = str(text or "").strip()
        if not value:
            return
        self.emit_event("voice-transcript", {"text": value})
        try:
            self._chat_message([value, {"source": "voice"}])
        except Exception as exc:
            self.emit_event("voice-status", {"state": "error", "error": str(exc), "actualRuntime": True})

    def _search_memory(self, args: list[Any]) -> dict[str, Any]:
        query = str(args[0] if args else "")
        try:
            from shell_memory_v2 import recall_memory

            return {"success": True, "items": recall_memory(query)}
        except Exception:
            return {"success": True, "items": []}

    def _get_capabilities(self, _args: list[Any]) -> dict[str, Any]:
        try:
            from shell_tool_catalog import discover_capabilities

            return discover_capabilities(PROJECT_ROOT)
        except Exception as exc:
            return {
                "status": "error",
                "summary": {},
                "catalog": [],
                "tools": [],
                "actions": [],
                "error": str(exc),
            }

    def _execute_tool(self, args: list[Any]) -> dict[str, Any]:
        tool_id = str(args[0] if args else "").strip()
        tool_args = args[1] if len(args) > 1 and isinstance(args[1], dict) else {}
        if not tool_id:
            return {"status": "error", "message": "Missing tool id"}
        try:
            from shell_tool_gateway import execute_tool_sync

            return execute_tool_sync(tool_id, tool_args)
        except Exception as exc:
            return {"status": "error", "tool": tool_id, "message": str(exc)}

    def _read_notes_file(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(NOTES_PATH.read_text(encoding="utf-8"))
            return [dict(item) for item in data if isinstance(item, dict)]
        except Exception:
            return []

    def _write_notes_file(self, notes: list[dict[str, Any]]) -> None:
        NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
        NOTES_PATH.write_text(json.dumps(notes[-200:], ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_notes(self, _args: list[Any]) -> list[Any]:
        return self._read_notes_file()

    def _save_note(self, args: list[Any]) -> bool:
        payload = args[0] if args and isinstance(args[0], dict) else {}
        title = str(payload.get("title") or "Untitled").strip() or "Untitled"
        content = str(payload.get("content") or "").strip()
        slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in title).strip("_") or "note"
        note = {
            "filename": f"{slug}_{int(time.time() * 1000)}.md",
            "title": title,
            "content": content,
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        notes = self._read_notes_file()
        notes.append(note)
        self._write_notes_file(notes)
        self.emit_event("note-saved", payload)
        return True

    def _delete_note(self, args: list[Any]) -> bool:
        filename = str(args[0] if args else "")
        if filename:
            notes = [note for note in self._read_notes_file() if note.get("filename") != filename]
            self._write_notes_file(notes)
        return True

    def _read_gallery_meta(self) -> dict[str, Any]:
        try:
            data = json.loads(GALLERY_META_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_gallery_meta(self, metadata: dict[str, Any]) -> None:
        GALLERY_META_PATH.parent.mkdir(parents=True, exist_ok=True)
        GALLERY_META_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _slug(text: str, fallback: str = "shell_image") -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")
        slug = re.sub(r"_+", "_", slug)[:54].strip("_")
        return slug or fallback

    @staticmethod
    def _safe_gallery_file(filename: str) -> Path | None:
        try:
            path = (GALLERY_DIR / Path(str(filename)).name).resolve()
            root = GALLERY_DIR.resolve()
            if path.parent != root:
                return None
            return path
        except Exception:
            return None

    def _gallery_item_for_file(self, path: Path, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        meta = metadata or self._read_gallery_meta()
        stat = path.stat()
        file_meta = meta.get(path.name) if isinstance(meta.get(path.name), dict) else {}
        title = str(file_meta.get("title") or "").strip()
        if not title:
            title = path.stem
            title = re.sub(r"^shell_ai_\d{8}_\d{6}_", "", title)
            title = re.sub(r"_[0-9]+x[0-9]+_[a-f0-9]{4,}$", "", title, flags=re.I)
            title = title.replace("_", " ").strip() or path.stem
        return {
            "filename": path.name,
            "displayName": title,
            "path": str(path),
            "url": path.resolve().as_uri(),
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
            "size": stat.st_size,
            "mime": mimetypes.guess_type(path.name)[0] or "image/png",
        }

    def _get_gallery_images(self, _args: list[Any]) -> list[Any]:
        try:
            GALLERY_DIR.mkdir(parents=True, exist_ok=True)
            metadata = self._read_gallery_meta()
            files = [
                item
                for item in GALLERY_DIR.iterdir()
                if item.is_file() and item.suffix.lower() in GALLERY_EXTENSIONS
            ]
            files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
            return [self._gallery_item_for_file(item, metadata) for item in files[:500]]
        except Exception:
            return []

    def _save_image_to_gallery(self, args: list[Any]) -> dict[str, Any]:
        payload = args[0] if args and isinstance(args[0], dict) else {}
        title = str(payload.get("title") or payload.get("prompt") or "Shell AI image").strip()
        data_url = str(payload.get("base64Data") or payload.get("dataUrl") or payload.get("image") or "").strip()
        if not data_url:
            return {"success": False, "message": "Missing image data."}

        mime = "image/png"
        encoded = data_url
        match = re.match(r"^data:(image/[a-z0-9.+-]+);base64,(.+)$", data_url, flags=re.I | re.S)
        if match:
            mime = match.group(1).lower()
            encoded = match.group(2)
        ext = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/png": ".png",
        }.get(mime, ".png")
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except Exception:
            return {"success": False, "message": "Invalid base64 image data."}
        if not image_bytes.startswith((b"\x89PNG", b"\xff\xd8", b"RIFF", b"GIF8")):
            return {"success": False, "message": "Image data is not a supported image file."}

        GALLERY_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"shell_ai_{time.strftime('%Y%m%d_%H%M%S')}_{self._slug(title)}{ext}"
        path = GALLERY_DIR / filename
        counter = 1
        while path.exists():
            path = GALLERY_DIR / f"{path.stem}_{counter}{ext}"
            counter += 1
        path.write_bytes(image_bytes)

        metadata = self._read_gallery_meta()
        metadata[path.name] = {"title": title, "source": "web-ui", "createdAt": time.time()}
        self._write_gallery_meta(metadata)
        item = self._gallery_item_for_file(path, metadata)
        self.emit_event("gallery-updated", {"success": True, "image": item})
        return {"success": True, "image": item, "path": str(path)}

    def _delete_image(self, args: list[Any]) -> dict[str, Any]:
        filename = str(args[0] if args else "").strip()
        path = self._safe_gallery_file(filename)
        if not path:
            return {"success": False, "message": "Invalid image filename."}
        try:
            if path.exists():
                path.unlink()
            metadata = self._read_gallery_meta()
            metadata.pop(path.name, None)
            self._write_gallery_meta(metadata)
            self.emit_event("gallery-updated", {"success": True, "deleted": path.name})
            return {"success": True}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    def _open_image_location(self, args: list[Any]) -> dict[str, Any]:
        raw_path = Path(str(args[0] if args else "")).expanduser()
        if not raw_path.exists():
            return {"success": False, "message": "Image file not found."}
        try:
            system = platform.system().lower()
            if system == "darwin":
                subprocess.Popen(["open", "-R", str(raw_path)])
            elif system == "windows":
                subprocess.Popen(["explorer", "/select,", str(raw_path)])
            else:
                subprocess.Popen(["xdg-open", str(raw_path.parent)])
            return {"success": True}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    def _save_image_external(self, args: list[Any]) -> dict[str, Any]:
        raw_path = Path(str(args[0] if args else "")).expanduser()
        if not raw_path.exists() or raw_path.suffix.lower() not in GALLERY_EXTENSIONS:
            return {"success": False, "message": "Image file not found."}
        try:
            target_dir = Path.home() / "Downloads" / "Shell_Generated"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / raw_path.name
            if target.exists():
                target = target_dir / f"{raw_path.stem}_{int(time.time())}{raw_path.suffix}"
            shutil.copy2(raw_path, target)
            return {"success": True, "path": str(target)}
        except Exception as exc:
            return {"success": False, "message": str(exc)}


class ShellWebUI:
    def __init__(self) -> None:
        raise RuntimeError("ShellWebUI Qt host is retired. Use the Electron launcher.")
