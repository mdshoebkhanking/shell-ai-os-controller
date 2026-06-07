from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

from aiohttp import web


def _project_root() -> Path:
    for env_name in ("SHELL_APP_ROOT", "SHELL_INSTALL_ROOT"):
        configured = os.environ.get(env_name, "").strip()
        if not configured:
            continue
        candidate = Path(configured).resolve()
        if (candidate / "shell_web_ui").exists() and (candidate / "shell_tool_catalog.py").exists():
            return candidate
    cwd = Path.cwd().resolve()
    if (cwd / "shell_web_ui").exists() and (cwd / "shell_tool_catalog.py").exists():
        return cwd
    return Path(__file__).resolve().parent


ROOT = _project_root()
for candidate in (ROOT, ROOT / "shell_web_ui"):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)
os.environ.setdefault("SHELL_APP_ROOT", str(ROOT))
os.environ.setdefault("SHELL_INSTALL_ROOT", str(ROOT))
os.environ.setdefault("SHELL_RUNTIME_DIR", str(ROOT / ".shell_runtime"))
PORT_HINT = ROOT / ".shell_electron_bridge_port"
REQUIRED_BACKEND_TOOL_IDS = (
    "shell_agent_orchestrator:orchestrate_shell_goal_tool",
    "shell_code_engine:create_fullstack_app_tool",
    "shell_browser_CTRL:play_youtube_video",
)


def _json_response(data: Any = None, *, ok: bool = True, error: str = "") -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _pick_port() -> int:
    configured = os.environ.get("SHELL_ELECTRON_BRIDGE_PORT", "").strip()
    if configured.isdigit():
        return int(configured)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ElectronBridgeServer:
    def __init__(self) -> None:
        self._event_queues: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop = asyncio.get_event_loop()

        from shell_web_ui.host import ShellBackendBridge

        self._bridge = ShellBackendBridge()
        self._bridge.add_event_listener(self._emit_event)

    def _emit_event(self, channel: str, payload: Any) -> None:
        event = {"channel": str(channel or ""), "payload": payload, "ts": time.time()}
        for queue in list(self._event_queues):
            self._loop.call_soon_threadsafe(queue.put_nowait, event)

    async def ready(self, _request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "status": "ready", "ts": time.time()})

    async def call(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            body = {}
        channel = str(body.get("channel") or "")
        args = body.get("args")
        if not isinstance(args, list):
            args = [] if args is None else [args]
        try:
            raw = self._bridge.call(channel, json.dumps(args, ensure_ascii=False))
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, dict) and "data" in parsed:
                return web.json_response(parsed)
            return web.json_response(_json_response(parsed))
        except Exception as exc:
            return web.json_response(_json_response(None, ok=False, error=str(exc)), status=500)

    async def events(self, _request: web.Request) -> web.StreamResponse:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._event_queues.add(queue)
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(_request)
        try:
            await response.write(b": shell electron bridge connected\n\n")
            while True:
                event = await queue.get()
                await response.write(f"event: shell-bridge-event\n".encode("utf-8"))
                await response.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
        except (asyncio.CancelledError, ConnectionResetError, RuntimeError):
            pass
        finally:
            self._event_queues.discard(queue)
        return response

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/ready", self.ready)
        app.router.add_post("/call", self.call)
        app.router.add_get("/events", self.events)
        return app


async def run(port: int) -> None:
    server = ElectronBridgeServer()
    runner = web.AppRunner(server.app())
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    PORT_HINT.write_text(str(port), encoding="utf-8")
    print(f"SHELL_ELECTRON_BRIDGE_PORT={port}", flush=True)
    while True:
        await asyncio.sleep(3600)


def _backend_probe() -> int:
    from shell_tool_catalog import discover_tool_catalog
    from shell_tool_gateway import execute_tool_sync

    rows = discover_tool_catalog(ROOT)
    ids = {str(row.get("id") or "") for row in rows}
    missing = [tool_id for tool_id in REQUIRED_BACKEND_TOOL_IDS if tool_id not in ids]
    execution_result: dict[str, Any] | None = None
    if not missing:
        execution_result = execute_tool_sync(
            "shell_agent_orchestrator:orchestrate_shell_goal_tool",
            {
                "goal": "status check only",
                "execute": False,
                "approved": False,
            },
        )
    payload = {
        "ok": not missing and isinstance(execution_result, dict) and execution_result.get("status") == "success",
        "root": str(ROOT),
        "toolCount": len(ids),
        "requiredTools": list(REQUIRED_BACKEND_TOOL_IDS),
        "missingTools": missing,
        "orchestratorStatus": execution_result.get("status") if isinstance(execution_result, dict) else "",
    }
    print("SHELL_BACKEND_PROBE_JSON=" + json.dumps(payload, sort_keys=True), flush=True)
    return 0 if payload["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shell AI Electron backend bridge.")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--shell-ai-backend-probe", action="store_true")
    args = parser.parse_args(argv)
    os.environ.setdefault("SHELL_CHAT_PROVIDER_MODE", os.environ.get("SHELL_CHAT_PROVIDER_MODE", "auto"))
    os.environ.setdefault("SHELL_OFFLINE_LLM_ASYNC_UI", "1")
    os.environ.setdefault("SHELL_WINDOWS_PERFORMANCE_MODE", "balanced")
    os.environ.setdefault("SHELL_IMAGE_LOCAL_FALLBACK", "1")
    if args.shell_ai_backend_probe:
        return _backend_probe()
    port = args.port or _pick_port()
    try:
        asyncio.run(run(port))
    except KeyboardInterrupt:
        return 0
    finally:
        try:
            PORT_HINT.unlink()
        except FileNotFoundError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
