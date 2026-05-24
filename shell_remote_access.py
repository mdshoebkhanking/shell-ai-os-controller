from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any

from shell_safe_executor import god_tier_tool as function_tool


REMOTE_STATE = Path(os.environ.get("SHELL_REMOTE_ACCESS_STATE", "~/.shell_remote_access_sessions.json")).expanduser()


def _load() -> dict[str, Any]:
    try:
        return json.loads(REMOTE_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"sessions": []}


def _save(state: dict[str, Any]) -> None:
    REMOTE_STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = REMOTE_STATE.with_suffix(REMOTE_STATE.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(REMOTE_STATE)


def _port_open(port: int) -> bool:
    if port <= 0:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.08)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


@function_tool(category="system")
async def shell_remote_access_tool(action: str = "status", port: int = 0, label: str = "") -> dict[str, Any]:
    """Manage Shell-style remote access session records for localhost sharing."""
    action = str(action or "status").strip().lower()
    state = _load()
    if action in {"status", "list"}:
        return {"ok": True, "sessions": state.get("sessions", []), "state_path": str(REMOTE_STATE)}
    if action in {"close", "stop"}:
        for session in state.get("sessions", []):
            session["active"] = False
            session["closed_at"] = time.time()
        _save(state)
        return {"ok": True, "message": "Remote access session records closed.", "sessions": state.get("sessions", [])}
    if action not in {"deploy", "open", "start"}:
        return {"ok": False, "message": "Use action=status, deploy, or close."}
    if int(port or 0) <= 0:
        return {"ok": False, "message": "A localhost port is required for remote deployment."}
    session = {
        "label": str(label or f"localhost:{int(port)}"),
        "port": int(port),
        "active": True,
        "local_port_open": _port_open(int(port)),
        "created_at": time.time(),
        "handoff": "Use Shell Telegram or an approved tunnel provider to expose this port.",
    }
    state.setdefault("sessions", []).append(session)
    state["sessions"] = state["sessions"][-20:]
    _save(state)
    return {"ok": True, "session": session, "state_path": str(REMOTE_STATE)}
