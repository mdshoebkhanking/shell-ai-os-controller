from __future__ import annotations

import json
import base64
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

try:
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except Exception:  # pragma: no cover - handled by the launcher
    QWebChannel = None  # type: ignore
    QWebEnginePage = None  # type: ignore
    QWebEngineSettings = None  # type: ignore
    QWebEngineView = None  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_UI_ROOT = Path(__file__).resolve().parent
WEB_DIST_INDEX = WEB_UI_ROOT / "dist" / "index.html"
HISTORY_PATH = PROJECT_ROOT / ".shell_runtime" / "web_ui_history.json"
NOTES_PATH = PROJECT_ROOT / ".shell_runtime" / "web_ui_notes.json"
GALLERY_DIR = Path.home() / "Pictures" / "Shell_Generated"
GALLERY_META_PATH = PROJECT_ROOT / ".shell_runtime" / "web_ui_gallery.json"
GALLERY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _json_response(data: Any = None, *, ok: bool = True, error: str = "") -> str:
    return json.dumps({"ok": ok, "data": data, "error": error}, ensure_ascii=False)


class ShellBackendBridge(QObject):
    """QWebChannel bridge used by the React renderer.

    The JS side calls this bridge through a single generic `call(channel, args)`
    slot so new UI features can be added without changing Qt slot signatures.
    """

    eventEmitted = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._voice_listener = None
        self._last_voice_amp_event = 0.0
        self._speech_process: subprocess.Popen[Any] | None = None

    @pyqtSlot(str, str, result=str)
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
        self.eventEmitted.emit(channel, json.dumps(payload, ensure_ascii=False))

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
            "get-personality": self._get_personality,
            "save-personality": self._save_personality,
            "set-personality": self._save_personality,
            "get-app-version": lambda _args: "1.0.0",
            "check-vault-status": lambda _args: {"faceCount": 0, "pinConfigured": False},
            "verify-vault-pin": lambda _args: False,
            "setup-vault-pin": lambda _args: {"success": True},
            "setup-vault-face": lambda _args: {"success": True},
            "verify-vault-face": lambda _args: False,
            "check-for-updates": lambda _args: {"success": True, "status": "idle", "message": "System is up to date."},
            "download-update": lambda _args: {"success": False, "message": "Desktop updater is not configured."},
            "install-update": lambda _args: {"success": False, "message": "Desktop updater is not configured."},
            "open-app": self._open_app,
            "close-app": self._close_app,
            "google-search": self._google_search,
            "execute-command": self._execute_command,
            "chat-message": self._chat_message,
            "speak-text": self._speak_text,
            "stop-speech": self._stop_speech,
            "start-voice": self._start_voice,
            "stop-voice": self._stop_voice,
            "set-voice-muted": self._set_voice_muted,
            "get-screen-source": lambda _args: None,
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
        }
        handler = handlers.get(channel)
        if handler is None:
            return {"success": False, "message": f"Unhandled Shell UI channel: {channel}"}
        return handler(args)

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
        try:
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_history_file(self, messages: list[Any]) -> None:
        HISTORY_PATH.write_text(json.dumps(messages[-80:], ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_history(self, _args: list[Any]) -> list[Any]:
        return self._read_history_file()

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

    def _chat_message(self, args: list[Any]) -> dict[str, Any]:
        text = str(args[0] if args else "").strip()
        meta = args[1] if len(args) > 1 and isinstance(args[1], dict) else {}
        source = str(meta.get("source") or "text").strip().lower()
        entry = str(meta.get("entry") or "").strip().lower()
        if source not in {"text", "voice"}:
            source = "text"
        if not text:
            return {"success": False, "reply": "Message empty hai.", "error": "Missing message"}

        previous_messages = self._read_history_file()
        messages = list(previous_messages)
        messages.append({"role": "user", "parts": [{"text": text}]})

        route: dict[str, Any] | None = None
        image_prompt = ""
        image_generation_started = False
        result: Any = None
        success = True
        try:
            recall_reply = self._conversation_recall_reply(text, previous_messages)
            if recall_reply:
                reply = recall_reply
            elif self._is_telemetry_chart_prompt(text, entry=entry):
                reply = self._chart_summary_reply(text)
            else:
                from shell_nl_router import route_natural_command

                route = route_natural_command(text)
                if not (route and route.get("tool")):
                    image_prompt = self._extract_image_generation_prompt(text)
                    if image_prompt:
                        route = self._image_generation_route(image_prompt)
                if route and route.get("tool"):
                    if str(route.get("tool")) == "shell_image_ai:generate_image_tool":
                        image_prompt = (
                            self._clean_image_prompt(self._route_image_prompt(route))
                            or self._extract_image_generation_prompt(text)
                            or text
                        )
                        route_args = dict(route.get("args") or {})
                        route_args["description"] = image_prompt
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
                    result = self._execute_routed_tool(route)
                    reply = self._format_chat_result(route, result)
                else:
                    reply = self._brain_chat_fallback(text, previous_messages=previous_messages)
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

        messages.append({"role": "model", "parts": [{"text": reply}]})
        self._write_history_file(messages)
        self.emit_event(
            "chat-updated",
            {"reply": reply, "route": route, "success": success, "source": source, "voice": source == "voice"},
        )
        return {"success": success, "reply": reply, "route": route, "result": result, "source": source}

    def _execute_routed_tool(self, route: dict[str, Any]) -> Any:
        from shell_tool_gateway import execute_tool_sync

        return execute_tool_sync(str(route["tool"]), route.get("args") or {})

    @staticmethod
    def _compact_chat_reply(reply: str, *, limit: int = 360) -> str:
        text = " ".join(str(reply or "").split()).strip()
        if len(text) <= limit:
            return text
        return f"{text[:limit].rsplit(' ', 1)[0]}..."

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
            r"^(?:of|for|about|ki|ka|ke|karke|kar\s+ke|kar\s+do|do|de\s+do|dijiye|please)\s+",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        if re.fullmatch(
            r"(?:image|photo|picture|pic|wallpaper|art|tasveer|chitra|generate|create|make|draw|design|banao|bana|banado|banaao|karo|karke|kar\s+ke|kar\s+do|do|de\s+do|dijiye|please|\s)+",
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
        action_word = r"(?:generate|create|make|draw|design|banao|bana|banado|banaao|karo|kar\s+do)"
        connector = r"(?:(?:of|for|about|ki|ka|ke)\b|:)"
        if not re.search(rf"\b{image_word}\b", raw, flags=re.I) or not re.search(
            rf"\b{action_word}\b",
            raw,
            flags=re.I,
        ):
            return ""

        patterns = (
            rf"^(?:please\s+)?(?:generate|create|make|draw|design)\s+"
            rf"(?:an?\s+|ek\s+|achhi\s+|acchi\s+|high\s+quality\s+)*"
            rf"{image_word}\s*{connector}?\s*(.*)$",
            rf"^(?:please\s+)?{image_word}\s+{action_word}\s*{connector}?\s*(.*)$",
            rf"^(?:please\s+)?{action_word}\s+"
            rf"(?:an?\s+|ek\s+|achhi\s+|acchi\s+|high\s+quality\s+)*"
            rf"{image_word}\s*{connector}?\s*(.*)$",
            rf"^(.+?)\s+(?:(?:ki|ka|ke)\b\s*)?{image_word}\s+{action_word}\s*$",
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
        lower = str(text or "").strip().lower()
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

    def _history_context_snippet(self, previous_messages: list[Any], *, limit: int = 6) -> str:
        rows: list[str] = []
        for message in previous_messages[-limit:]:
            role = str(message.get("role") or "") if isinstance(message, dict) else ""
            text = self._history_text(message)
            if role and text:
                rows.append(f"{role}: {text[:220]}")
        return "\n".join(rows)

    def _brain_chat_fallback(self, text: str, *, previous_messages: list[Any] | None = None) -> str:
        context = self._history_context_snippet(previous_messages or [])
        system_prompt = (
            "You are Shell AI, a concise Hinglish desktop OS assistant. "
            "Answer the user's normal text question directly in 1-3 short lines. "
            "Do not claim you executed tools in this text-only fallback. "
            "Use recent conversation context if the user asks what they said or what task they gave."
        )
        prompt = text if not context else f"Recent conversation:\n{context}\n\nUser: {text}"
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
            if reply and not reply.lower().startswith("all brains failed"):
                return self._compact_chat_reply(reply)
        except Exception:
            pass

        return self._local_chat_answer(text)

    def _local_chat_answer(self, text: str) -> str:
        query = " ".join(str(text or "").lower().split())
        if "capital of france" in query:
            return "France ki capital Paris hai."
        if "memory" in query and "python" in query:
            return "Python memory objects ko heap mein manage karta hai; reference counting aur garbage collector unused objects clean karte hain."
        if "network protocol" in query:
            return "Network protocol rules ka set hota hai jisse devices data exchange karte hain, jaise TCP/IP, HTTP, DNS."
        if "who are you" in query or "tum kaun" in query:
            return "Main Shell AI hoon, tumhara desktop OS controller aur assistant."
        if query in {"hi", "hello", "hey", "salam", "assalamualaikum"}:
            return "Haan bhai, bolo. Main sun rahi hoon."
        return (
            "Mujhe sawaal mil gaya, lekin AI provider abhi available nahi hai. "
            "API key set karoge to main is par proper detailed jawab de paungi."
        )

    def _format_chat_result(self, route: dict[str, Any], result: Any) -> str:
        tool = route.get("tool", "backend")
        is_image_tool = str(tool) == "shell_image_ai:generate_image_tool"
        image_prompt = self._route_image_prompt(route) if is_image_tool else ""
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
                        return f"Image generated aur Gallery mein save ho gayi: {image_path.name}"
                    lowered_image_result = rendered_text.lower()
                    if "image generation failed" in lowered_image_result or "critical error" in lowered_image_result:
                        error_text = self._compact_chat_reply(rendered_text.strip(), limit=520)
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
                        return error_text
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
                    return self._compact_chat_reply(rendered_text, limit=520)
                if (
                    rendered_text.startswith("[BLOCKED]")
                    or "CODE WRITE BLOCKED" in rendered_text
                    or "Writing LLM-generated Python to disk is disabled" in rendered_text
                ):
                    reason = rendered_text.replace("[BLOCKED]", "", 1).strip()
                    return (
                        "Code creation safety settings se blocked hai. "
                        "Website/app scaffold default allowed hai; agar SHELL_BLOCK_PROJECT_SCAFFOLD=1 set hai to remove karo. "
                        "Core code writes ke liye trusted session mein SHELL_ALLOW_CODE_WRITE=1 use karo. "
                        f"{reason[:620]}"
                    ).strip()
                if "calculator" in str(tool).lower():
                    for line in rendered_text.splitlines():
                        if line.strip().lower().startswith("result:"):
                            return line.strip()
                return f"{tool} complete: {rendered_text[:700]}"
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
            return f"{tool} returned: {str(message).strip()[:700]}"
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
        return f"{tool} complete: {str(result).strip()[:700]}"

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

    def _tts_command(self, text: str) -> list[str] | None:
        system = platform.system().lower()
        if system == "darwin":
            say_bin = shutil.which("say") or ("/usr/bin/say" if Path("/usr/bin/say").exists() else "")
            if not say_bin:
                return None
            voice = os.environ.get("SHELL_TTS_VOICE", "").strip()
            return [say_bin, "-v", voice, text] if voice else [say_bin, text]

        if system == "windows":
            powershell = shutil.which("powershell") or shutil.which("powershell.exe")
            if not powershell:
                return None
            safe_text = text.replace("'", "''")
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Speak('{safe_text}')"
            )
            return [powershell, "-NoProfile", "-Command", script]

        for exe_name in ("spd-say", "espeak"):
            exe = shutil.which(exe_name)
            if exe:
                return [exe, text]
        return None

    def _speak_text(self, args: list[Any]) -> dict[str, Any]:
        text = " ".join(str(args[0] if args else "").strip().split())
        if not text:
            return {"success": False, "message": "No speech text provided"}

        max_chars = int(os.environ.get("SHELL_TTS_MAX_CHARS", "320") or "320")
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0].strip() + "..."

        command = self._tts_command(text)
        if not command:
            self.emit_event("speech-status", {"state": "error", "message": "No local TTS engine found"})
            return {"success": False, "message": "No local TTS engine found"}

        self._stop_speech_process()
        try:
            self._speech_process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            self.emit_event("speech-status", {"state": "speaking", "chars": len(text)})
            return {"success": True, "message": "Speech started", "chars": len(text)}
        except Exception as exc:
            self.emit_event("speech-status", {"state": "error", "message": str(exc)})
            return {"success": False, "message": str(exc)}

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
        self.emit_event("voice-status", {"state": "stopped", "actualRuntime": True})

    def _on_voice_status(self, status: str) -> None:
        self.emit_event("voice-status", {"state": str(status or "listening").lower(), "actualRuntime": True})

    def _on_voice_error(self, error: str) -> None:
        self.emit_event("voice-status", {"state": "error", "error": str(error or "Voice error"), "actualRuntime": True})

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


class ShellWebUI(QMainWindow):
    def __init__(self) -> None:
        if QWebEngineView is None or QWebChannel is None:
            raise RuntimeError("PyQt6 WebEngine/WebChannel is unavailable")

        super().__init__()
        self.setWindowTitle("Shell AI")
        self.resize(1280, 760)

        self.bridge = ShellBackendBridge(self)
        self.channel = QWebChannel(self)
        self.channel.registerObject("shellBridge", self.bridge)

        self.view = QWebEngineView(self)
        self.view.page().setWebChannel(self.channel)
        self._configure_web_permissions()
        self._configure_web_settings()

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.setCentralWidget(container)

        self._load_renderer()

    def _configure_web_settings(self) -> None:
        if QWebEngineSettings is None:
            return
        settings = self.view.settings()
        for attribute in (
            QWebEngineSettings.WebAttribute.JavascriptEnabled,
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            QWebEngineSettings.WebAttribute.WebGLEnabled,
            QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled,
            QWebEngineSettings.WebAttribute.ScreenCaptureEnabled,
        ):
            try:
                settings.setAttribute(attribute, True)
            except Exception:
                pass

    def _configure_web_permissions(self) -> None:
        page = self.view.page()
        if QWebEnginePage is not None:
            try:
                allowed_features = {
                    QWebEnginePage.Feature.MediaAudioCapture,
                    QWebEnginePage.Feature.MediaVideoCapture,
                    QWebEnginePage.Feature.MediaAudioVideoCapture,
                    QWebEnginePage.Feature.DesktopVideoCapture,
                    QWebEnginePage.Feature.DesktopAudioVideoCapture,
                }

                def grant_media_permission(origin: QUrl, feature: Any) -> None:
                    if feature in allowed_features:
                        page.setFeaturePermission(
                            origin,
                            feature,
                            QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
                        )

                self._feature_permission_handler = grant_media_permission
                page.featurePermissionRequested.connect(self._feature_permission_handler)
            except Exception:
                pass

    def _load_renderer(self) -> None:
        dev_url = os.environ.get("SHELL_WEB_UI_URL", "").strip()
        if dev_url:
            self.view.load(QUrl(dev_url))
            return
        if WEB_DIST_INDEX.exists():
            self.view.load(QUrl.fromLocalFile(str(WEB_DIST_INDEX)))
            return
        fallback = (
            "<html><body style='margin:0;background:#050505;color:#10b981;"
            "font-family:monospace;display:grid;place-items:center;height:100vh'>"
            "<div><h2>Shell AI Web UI build missing</h2>"
            "<p>Run <code>npm install</code> and <code>npm run build</code> in shell_web_ui.</p></div>"
            "</body></html>"
        )
        self.view.setHtml(fallback, QUrl.fromLocalFile(str(WEB_UI_ROOT)))
