from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from shell_safe_executor import god_tier_tool as function_tool


STATE_PATH = Path(os.environ.get("SHELL_FOCUS_STATE", "~/.shell_focus_mode_state.json")).expanduser()


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"active": False, "sessions": []}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_PATH)


@function_tool(category="productivity")
async def shell_deep_focus_mode_tool(
    action: str = "start",
    duration_minutes: int = 25,
    goal: str = "",
    block_apps: str = "",
) -> dict[str, Any]:
    """Start, stop, or inspect Shell deep focus automation state.

    The tool records a focus contract and intended blocked apps. It does not
    kill applications unless future user-approved automation explicitly enables
    that behavior.
    """
    action = str(action or "start").strip().lower()
    state = _load_state()
    now = time.time()
    if action == "stop":
        state["active"] = False
        state["stopped_at"] = now
        _save_state(state)
        return {"ok": True, "active": False, "message": "Deep focus mode stopped.", "state": state}
    if action in {"status", "inspect"}:
        return {"ok": True, "active": bool(state.get("active")), "state": state}
    if action != "start":
        return {"ok": False, "message": "Use action=start, stop, or status."}

    duration = max(1, min(int(duration_minutes or 25), 240))
    blocked = [item.strip() for item in str(block_apps or "").split(",") if item.strip()]
    session = {
        "goal": str(goal or "Deep work").strip(),
        "duration_minutes": duration,
        "block_apps": blocked,
        "started_at": now,
        "ends_at": now + duration * 60,
        "automation": {
            "notification_mute": "planned",
            "app_blocking": "recorded-only",
            "window_focus": "recorded-only",
        },
    }
    state["active"] = True
    state["current"] = session
    state.setdefault("sessions", []).append(session)
    state["sessions"] = state["sessions"][-50:]
    _save_state(state)
    return {"ok": True, "active": True, "message": "Deep focus mode started.", "session": session}
