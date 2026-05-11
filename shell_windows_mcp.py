"""CursorTouch Windows-MCP integration for Shell.

Windows-MCP is a real Model Context Protocol server. Shell uses it on
Windows through stdio (`uvx windows-mcp`) and exposes a stable static
catalog so the UI can render the tools even before the MCP process starts.
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import sys
import time
from typing import Any, Iterable


WINDOWS_MCP_REPO_URL = "https://github.com/CursorTouch/Windows-MCP"
WINDOWS_MCP_PYPI_PACKAGE = "windows-mcp"
WINDOWS_MCP_SERVER_NAME = "io.github.CursorTouch/Windows-MCP"
WINDOWS_MCP_MIN_PYTHON = "3.13"


def _param(name: str, annotation: str = "str", required: bool = False, default: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "annotation": annotation,
        "required": bool(required),
        "default": default,
    }


WINDOWS_MCP_STATIC_TOOLS: list[dict[str, Any]] = [
    {
        "name": "Click",
        "category": "windows",
        "risk": "guarded",
        "description": "Click on the Windows desktop at coordinates or a resolved target.",
        "params": [_param("x", "int", False, 0), _param("y", "int", False, 0), _param("button", "str", False, "left")],
    },
    {
        "name": "Type",
        "category": "windows",
        "risk": "guarded",
        "description": "Type text into the focused element or a target element.",
        "params": [_param("text", "str", True, ""), _param("clear", "bool", False, False)],
    },
    {
        "name": "Scroll",
        "category": "windows",
        "risk": "normal",
        "description": "Scroll vertically or horizontally on the active window or a region.",
        "params": [_param("direction", "str", False, "down"), _param("amount", "int", False, 5)],
    },
    {
        "name": "Move",
        "category": "windows",
        "risk": "normal",
        "description": "Move the pointer or drag to coordinates.",
        "params": [_param("x", "int", False, 0), _param("y", "int", False, 0), _param("drag", "bool", False, False)],
    },
    {
        "name": "Shortcut",
        "category": "windows",
        "risk": "guarded",
        "description": "Press keyboard shortcuts such as Ctrl+C or Alt+Tab.",
        "params": [_param("keys", "str", True, "Ctrl+C")],
    },
    {
        "name": "Wait",
        "category": "windows",
        "risk": "normal",
        "description": "Pause for a defined duration.",
        "params": [_param("seconds", "float", False, 1.0)],
    },
    {
        "name": "Screenshot",
        "category": "windows",
        "risk": "normal",
        "description": "Fast desktop screenshot with cursor position and open window context.",
        "params": [_param("display", "list[int]", False, None)],
    },
    {
        "name": "Snapshot",
        "category": "windows",
        "risk": "normal",
        "description": "Full desktop state capture with interactive elements and optional DOM mode.",
        "params": [
            _param("use_vision", "bool", False, False),
            _param("use_dom", "bool", False, False),
            _param("display", "list[int]", False, None),
        ],
    },
    {
        "name": "App",
        "category": "windows",
        "risk": "guarded",
        "description": "Launch, switch, move, resize, or control Windows applications.",
        "params": [_param("action", "str", True, "launch"), _param("name", "str", False, "")],
    },
    {
        "name": "Shell",
        "category": "windows",
        "risk": "guarded",
        "description": "Execute a PowerShell command through Windows-MCP.",
        "params": [_param("command", "str", True, "")],
    },
    {
        "name": "Scrape",
        "category": "browser",
        "risk": "normal",
        "description": "Scrape the current or requested webpage for text content.",
        "params": [_param("url", "str", False, "")],
    },
    {
        "name": "MultiSelect",
        "category": "windows",
        "risk": "guarded",
        "description": "Select multiple items using coordinates or labels.",
        "params": [_param("labels", "list[str]", False, []), _param("ctrl", "bool", False, True)],
    },
    {
        "name": "MultiEdit",
        "category": "windows",
        "risk": "guarded",
        "description": "Enter text into multiple input fields.",
        "params": [_param("fields", "list[dict]", False, [])],
    },
    {
        "name": "Clipboard",
        "category": "windows",
        "risk": "guarded",
        "description": "Read or set the Windows clipboard.",
        "params": [_param("action", "str", False, "read"), _param("text", "str", False, "")],
    },
    {
        "name": "Process",
        "category": "system",
        "risk": "guarded",
        "description": "List or terminate Windows processes.",
        "params": [_param("action", "str", False, "list"), _param("pid", "int", False, 0), _param("name", "str", False, "")],
    },
    {
        "name": "Notification",
        "category": "system",
        "risk": "normal",
        "description": "Send a Windows toast notification.",
        "params": [_param("title", "str", True, "Shell"), _param("message", "str", True, "")],
    },
    {
        "name": "Registry",
        "category": "system",
        "risk": "guarded",
        "description": "Read, write, delete, or list Windows Registry keys and values.",
        "params": [
            _param("action", "str", True, "read"),
            _param("key", "str", True, ""),
            _param("value_name", "str", False, ""),
            _param("value", "str", False, ""),
        ],
    },
]


def windows_mcp_command() -> list[str]:
    """Return the command Shell should use to start Windows-MCP."""
    raw = os.environ.get("SHELL_WINDOWS_MCP_COMMAND", "").strip()
    if raw:
        try:
            value = json.loads(raw)
            if isinstance(value, list) and all(isinstance(part, str) for part in value):
                return value
        except Exception:
            pass
        return shlex.split(raw, posix=os.name != "nt")
    executable = os.environ.get("SHELL_WINDOWS_MCP_EXE", "").strip()
    if not executable:
        executable = _find_uvx_executable()
    return [executable, WINDOWS_MCP_PYPI_PACKAGE]


def _find_uvx_executable() -> str:
    found = shutil.which("uvx")
    if found:
        return found
    scripts_dir = os.path.dirname(sys.executable)
    suffix = ".exe" if os.name == "nt" else ""
    candidate = os.path.join(scripts_dir, f"uvx{suffix}")
    if os.path.exists(candidate):
        return candidate
    return "uvx"


def windows_mcp_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("ANONYMIZED_TELEMETRY", "false")
    env.setdefault("WINDOWS_MCP_SCREENSHOT_BACKEND", "auto")
    env.setdefault("WINDOWS_MCP_SCREENSHOT_SCALE", "0.5")
    return env


def windows_mcp_runtime_supported() -> bool:
    return os.name == "nt" or str(os.environ.get("SHELL_WINDOWS_MCP_ALLOW_NON_WINDOWS", "")).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def windows_mcp_install_hint() -> str:
    return (
        "Windows-MCP requires Windows, Python 3.13+, and uv/uvx. "
        "Run ONE_CLICK_INSTALL.bat or Repair_ShellAI.bat on Windows; Shell will install uv and run: uvx windows-mcp. "
        f"Source: {WINDOWS_MCP_REPO_URL}"
    )


def windows_mcp_tool_catalog() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for row in WINDOWS_MCP_STATIC_TOOLS:
        name = str(row["name"])
        catalog.append(
            {
                "kind": "windows_mcp_tool",
                "id": f"windows-mcp:{name}",
                "name": name,
                "title": f"Windows {name}",
                "module": "windows-mcp",
                "file": WINDOWS_MCP_REPO_URL,
                "line": 0,
                "async": True,
                "category": row.get("category", "windows"),
                "risk": row.get("risk", "normal"),
                "description": row.get("description", ""),
                "params": [dict(param) for param in row.get("params", [])],
                "server": WINDOWS_MCP_SERVER_NAME,
                "source_url": WINDOWS_MCP_REPO_URL,
            }
        )
    return catalog


class WindowsMCPProcess:
    def __init__(self, command: Iterable[str] | None = None, *, timeout: float = 30.0):
        self.command = list(command) if command is not None else windows_mcp_command()
        self.timeout = float(timeout)
        self.process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._stderr_tail: list[str] = []
        self._stderr_task: asyncio.Task | None = None

    async def __aenter__(self) -> "WindowsMCPProcess":
        await self.start()
        return self

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        await self.close()

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=windows_mcp_env(),
        )
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        result = await self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Shell", "version": "1.0"},
            },
        )
        if not isinstance(result, dict):
            raise RuntimeError("Windows-MCP initialize returned an invalid response")
        await self.notify("notifications/initialized", {})

    async def close(self) -> None:
        proc = self.process
        self.process = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except Exception:
                proc.kill()
                try:
                    await proc.wait()
                except Exception:
                    pass
        if self._stderr_task is not None:
            self._stderr_task.cancel()

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self.request("tools/list", {})
        tools = result.get("tools", []) if isinstance(result, dict) else []
        return tools if isinstance(tools, list) else []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = await self.request(
            "tools/call",
            {"name": str(name), "arguments": dict(arguments or {})},
        )
        return result if isinstance(result, dict) else {"result": result}

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        proc = self.process
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise RuntimeError("Windows-MCP process is not running")
        self._request_id += 1
        request_id = self._request_id
        await self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        return await self._read_response(request_id)

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def _write(self, payload: dict[str, Any]) -> None:
        proc = self.process
        if proc is None or proc.stdin is None:
            raise RuntimeError("Windows-MCP stdin is unavailable")
        proc.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        await proc.stdin.drain()

    async def _read_response(self, request_id: int) -> Any:
        assert self.process is not None and self.process.stdout is not None
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                tail = "\n".join(self._stderr_tail[-8:])
                raise TimeoutError(f"Windows-MCP timed out waiting for request {request_id}. {tail}".strip())
            raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=remaining)
            if not raw:
                tail = "\n".join(self._stderr_tail[-8:])
                raise RuntimeError(f"Windows-MCP closed stdout. {tail}".strip())
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(json.dumps(message["error"], ensure_ascii=False, default=str))
            return message.get("result")

    async def _drain_stderr(self) -> None:
        proc = self.process
        if proc is None or proc.stderr is None:
            return
        try:
            while True:
                raw = await proc.stderr.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self._stderr_tail.append(line)
                    if len(self._stderr_tail) > 20:
                        self._stderr_tail = self._stderr_tail[-20:]
        except asyncio.CancelledError:
            return


def _run_sync(coro):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        asyncio.set_event_loop(None)
        loop.close()


async def _call_tool(command: list[str] | None, tool_name: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any]:
    async with WindowsMCPProcess(command=command, timeout=timeout) as client:
        result = await client.call_tool(tool_name, arguments)
        return {
            "status": "success",
            "transport": "windows-mcp",
            "server": WINDOWS_MCP_SERVER_NAME,
            "tool": tool_name,
            "result": result,
        }


def call_windows_mcp_tool_sync(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    command: list[str] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Call a Windows-MCP tool over stdio.

    On non-Windows machines the default command is not executed. Tests or
    advanced users can pass an explicit command or set
    SHELL_WINDOWS_MCP_ALLOW_NON_WINDOWS=1.
    """
    if command is None and not windows_mcp_runtime_supported():
        return {
            "status": "error",
            "state": "WINDOWS_ONLY",
            "transport": "windows-mcp",
            "tool": tool_name,
            "message": windows_mcp_install_hint(),
            "supported": False,
            "platform": sys_platform_label(),
            "required_platform": "Windows",
        }
    try:
        return _run_sync(_call_tool(command, tool_name, dict(arguments or {}), timeout or float(os.getenv("SHELL_WINDOWS_MCP_TIMEOUT", "30"))))
    except FileNotFoundError as exc:
        return {
            "status": "error",
            "state": "MISSING_DEPENDENCY",
            "transport": "windows-mcp",
            "tool": tool_name,
            "message": f"Windows-MCP command not found: {exc}",
            "command": command or windows_mcp_command(),
        }
    except Exception as exc:
        return {
            "status": "error",
            "state": "RUNTIME_ERROR",
            "transport": "windows-mcp",
            "tool": tool_name,
            "message": str(exc),
            "command": command or windows_mcp_command(),
        }


def sys_platform_label() -> str:
    if os.name == "nt":
        return "Windows"
    if sys.platform == "darwin":
        return "macOS"
    return sys.platform
