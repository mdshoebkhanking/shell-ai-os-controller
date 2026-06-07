from __future__ import annotations

import os
import platform
import time
from typing import Any

from .checks import current_platform, executable_available, import_available, truthy
from .states import RuntimeState


_PYTHON_PACKAGES = {
    "aiohttp": "hub HTTP server",
    "socketio": "hub realtime events",
    "websocket": "Socket.IO websocket transport",
    "psutil": "system telemetry",
    "selenium": "browser automation",
    "playwright": "advanced browser automation",
    "pytesseract": "OCR",
    "sounddevice": "local microphone capture",
    "speech_recognition": "microphone speech-to-text",
    "livekit": "realtime voice",
    "sherpa_onnx": "offline streaming speech-to-text",
    "sentence_transformers": "Project RAG embeddings",
    "rank_bm25": "Project RAG lexical retrieval",
    "docker": "optional secure sandbox container backend",
    "google.genai": "Gemini provider",
    "openai": "OpenAI provider",
}

_EXECUTABLES = {
    "ffmpeg": "audio/video processing",
    "tesseract": "OCR executable",
    "uvx": "Windows-MCP launcher",
}

_SAFETY_FLAGS = [
    "SHELL_ALLOW_CODE_WRITE",
    "SHELL_ALLOW_AGENT_PATCH",
    "SHELL_BLOCK_TERMINAL_EXEC",
    "SHELL_BLOCK_WORKFLOW_COMMANDS",
    "SHELL_BLOCK_WORKFLOW_FILE_WRITE",
    "SHELL_BLOCK_WORKFLOW_FILE_READ",
    "SHELL_BLOCK_PROJECT_SCAFFOLD",
]


def _api_key_status() -> list[dict[str, Any]]:
    try:
        from shell_api_manager import list_api_keys

        return list_api_keys()
    except Exception as exc:
        return [{
            "name": "api_key_scan",
            "set": False,
            "required": False,
            "section": "diagnostics",
            "description": f"API key scan failed: {exc}",
        }]


def _dependency_status() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, purpose in _PYTHON_PACKAGES.items():
        rows.append({
            "name": name,
            "kind": "python_package",
            "purpose": purpose,
            "ok": import_available(name),
        })
    for name, purpose in _EXECUTABLES.items():
        rows.append({
            "name": name,
            "kind": "executable",
            "purpose": purpose,
            "ok": executable_available(name),
        })
    return rows


def _safety_status() -> list[dict[str, Any]]:
    return [
        {
            "name": flag,
            "enabled": truthy(os.environ.get(flag)),
            "default_safe": not truthy(os.environ.get(flag)),
        }
        for flag in _SAFETY_FLAGS
    ]


def run_startup_diagnostics() -> dict[str, Any]:
    """Return JSON-safe startup diagnostics without mutating runtime state."""
    api_keys = _api_key_status()
    dependencies = _dependency_status()
    safety = _safety_status()
    missing_required_keys = [row["name"] for row in api_keys if row.get("required") and not row.get("set")]
    missing_deps = [row["name"] for row in dependencies if not row.get("ok")]
    platform_name = current_platform()

    state = RuntimeState.READY
    reasons: list[str] = []
    if missing_required_keys:
        state = RuntimeState.NEEDS_API_KEY
        reasons.append("required API keys missing")
    if missing_deps:
        reasons.append("optional dependencies missing")
    if platform_name != "windows":
        reasons.append("Windows-MCP desktop actions require Windows")

    return {
        "status": "success",
        "state": state.value,
        "generated_at": time.time(),
        "platform": {
            "os": platform_name,
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
        },
        "api_keys": api_keys,
        "dependencies": dependencies,
        "safety": safety,
        "summary": {
            "api_keys_total": len(api_keys),
            "api_keys_set": sum(1 for row in api_keys if row.get("set")),
            "missing_required_api_keys": missing_required_keys,
            "dependencies_total": len(dependencies),
            "dependencies_missing": missing_deps,
            "reasons": reasons,
        },
    }
