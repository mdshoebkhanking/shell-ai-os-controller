from __future__ import annotations

from typing import Any

from shell_safe_executor import god_tier_tool as function_tool


@function_tool(category="system")
async def shell_background_processes_tool(action: str = "list", name: str = "", limit: int = 20) -> dict[str, Any]:
    """Inspect background processes for Shell-style process management."""
    action = str(action or "list").strip().lower()
    if action not in {"list", "status", "watch"}:
        return {"ok": False, "message": "Use action=list, status, or watch. Process killing remains in guarded Shell system tools."}
    try:
        import psutil
    except Exception:
        return {"ok": False, "message": "psutil is not installed, so process inspection is unavailable."}
    needle = str(name or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        proc_name = str(info.get("name") or "")
        if needle and needle not in proc_name.lower():
            continue
        rows.append({
            "pid": info.get("pid"),
            "name": proc_name,
            "username": info.get("username"),
            "cpu_percent": info.get("cpu_percent") or 0.0,
            "memory_percent": round(float(info.get("memory_percent") or 0.0), 3),
            "status": info.get("status"),
        })
    rows.sort(key=lambda row: (row["cpu_percent"], row["memory_percent"]), reverse=True)
    return {"ok": True, "action": action, "count": len(rows), "processes": rows[: max(1, min(int(limit or 20), 100))]}
