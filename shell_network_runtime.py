"""
Lazy realtime hub network runtime.

The desktop UI should not hydrate python-socketio, engineio, or their HTTP
transport dependencies during first paint. This module is lightweight to import;
the websocket stack is loaded only when a SocketIOClient instance starts.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable

from shell_async_signals import WorkerThread
from shell_async_signals import signal as runtime_signal


logger = logging.getLogger("shell.network_runtime")
_PROJECT_ROOT = Path(__file__).resolve().parent


def _silent_engineio_logger():
    lg = logging.getLogger("shell.ui.engineio")
    lg.setLevel(logging.CRITICAL)
    lg.propagate = False
    if not lg.handlers:
        lg.addHandler(logging.NullHandler())
    return lg


def _hub_base_url_candidates(default_url: str = "http://localhost:5000") -> list[str]:
    candidates: list[str] = []
    env_url = str(os.environ.get("SHELL_HUB_URL", "")).strip()
    if env_url:
        candidates.append(env_url.rstrip("/"))
    try:
        hint = _PROJECT_ROOT / ".shell_hub_port"
        if hint.exists():
            txt = hint.read_text(encoding="utf-8").strip()
            if txt.isdigit():
                candidates.append(f"http://127.0.0.1:{int(txt)}")
    except Exception as exc:
        logger.debug("hub port hint read failed: %s", exc)
    candidates.append(default_url.rstrip("/"))
    for port in (5000, 5001, 5002, 5003):
        candidates.append(f"http://127.0.0.1:{port}")
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        normalized = candidate.strip().rstrip("/")
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _resolve_hub_base_url(default_url: str = "http://localhost:5000") -> str:
    return _hub_base_url_candidates(default_url)[0]


def _hub_auth_token() -> str:
    return (os.environ.get("SHELL_HUB_TOKEN") or os.environ.get("SHELL_API_TOKEN") or "").strip()


def _hub_socket_auth():
    token = _hub_auth_token()
    return {"token": token} if token else None


def _load_socketio_module():
    try:
        import socketio
    except Exception as exc:
        return None, f"python-socketio unavailable: {exc}"
    return socketio, ""


class SocketIOClient(WorkerThread):
    """Optional hub event stream client loaded outside the UI startup path."""

    connection_status = runtime_signal(bool)
    agent_speaking = runtime_signal(bool, str)
    agent_thinking = runtime_signal(bool)
    user_speaking = runtime_signal(str)
    system_stats = runtime_signal(dict)
    voice_amplitude = runtime_signal(float)
    deep_research = runtime_signal(dict)
    agent_reply = runtime_signal(str)
    user_message = runtime_signal(str)
    tool_event = runtime_signal(dict)
    api_key_update = runtime_signal(dict)
    safety_warning = runtime_signal(str)

    def __init__(
        self,
        hub_url=None,
        *,
        socketio_module_factory: Callable[[], tuple[Any, str]] | None = None,
        auth_factory: Callable[[], dict[str, str] | None] | None = None,
    ):
        super().__init__()
        self.sio = None
        self.is_connected = False
        self.running = True
        self.hub_url = hub_url or _resolve_hub_base_url()
        self._retry_ms = int(os.environ.get("UI_HUB_RETRY_MS", "1500"))
        self._socketio_module_factory = socketio_module_factory or _load_socketio_module
        self._auth_factory = auth_factory or _hub_socket_auth
        self._load_error = ""

    def _ensure_client(self) -> bool:
        if self.sio is not None:
            return True
        socketio, error = self._socketio_module_factory()
        if error or socketio is None:
            self._load_error = error or "python-socketio unavailable"
            logger.info("Socket.IO client disabled: %s", self._load_error)
            return False
        self.sio = socketio.Client(
            logger=False,
            engineio_logger=_silent_engineio_logger(),
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=1,
            reconnection_delay_max=5,
        )
        self._bind_events()
        return True

    def _bind_events(self) -> None:
        if self.sio is None:
            return

        @self.sio.event
        def connect():
            self.is_connected = True
            self.connection_status.emit(True)

        @self.sio.event
        def disconnect():
            self.is_connected = False
            self.connection_status.emit(False)

        @self.sio.event
        def shell_response(data):
            data = data if isinstance(data, dict) else {}
            event_type = data.get("type")
            text = data.get("text", "")
            if event_type == "agent_speech_start":
                self.agent_speaking.emit(True, text)
            elif event_type == "agent_speech_stop":
                self.agent_speaking.emit(False, text)
                self.agent_thinking.emit(False)
            elif event_type == "agent_thinking":
                self.agent_thinking.emit(True)
                self.agent_speaking.emit(False, text)
            elif event_type == "user_speech":
                self.user_speaking.emit(text)
            elif event_type == "agent_reply":
                self.agent_reply.emit(text)
            elif event_type == "user_message":
                self.user_message.emit(text)
            elif event_type == "safety_warning":
                self.safety_warning.emit(text)

        @self.sio.event
        def system_stats(data):
            if isinstance(data, dict):
                self.system_stats.emit(data)

        @self.sio.event
        def voice_data(data):
            amplitude = data.get("amplitude", 0.0) if isinstance(data, dict) else 0.0
            if amplitude > 0.01:
                self.voice_amplitude.emit(float(amplitude))

        @self.sio.event
        def research_update(data):
            if isinstance(data, dict):
                self.deep_research.emit(data)

        @self.sio.event
        def tool_event(data):
            if isinstance(data, dict):
                self.tool_event.emit(data)

        @self.sio.event
        def api_key_update(data):
            if isinstance(data, dict):
                self.api_key_update.emit(data)

    def emit_gui_input(self, payload: dict[str, Any]) -> bool:
        if not self.is_connected or self.sio is None:
            return False
        try:
            self.sio.emit("gui_input", payload)
            return True
        except Exception as exc:
            logger.debug("socketio gui_input emit failed: %s", exc)
            return False

    def run(self):
        if not self._ensure_client():
            self.connection_status.emit(False)
            return
        while self.running:
            ok = False
            for url in _hub_base_url_candidates(self.hub_url):
                try:
                    self.hub_url = url
                    auth = self._auth_factory()
                    if auth:
                        self.sio.connect(url, wait_timeout=5, auth=auth)
                    else:
                        self.sio.connect(url, wait_timeout=5)
                    ok = True
                    while self.running and self.sio.connected:
                        self.msleep(250)
                    if not self.running:
                        break
                except Exception:
                    self.connection_status.emit(False)
            if not self.running:
                break
            self.msleep(max(300, self._retry_ms) if not ok else 250)

    def stop(self):
        self.running = False
        if self.sio is None:
            return
        try:
            if self.sio.connected:
                self.sio.disconnect()
        except Exception as exc:
            logger.debug("socketio disconnect failed: %s", exc)
        try:
            self.sio.shutdown()
        except Exception as exc:
            logger.debug("socketio shutdown failed: %s", exc)


__all__ = [
    "SocketIOClient",
    "_hub_base_url_candidates",
    "_hub_socket_auth",
    "_load_socketio_module",
    "_resolve_hub_base_url",
]
