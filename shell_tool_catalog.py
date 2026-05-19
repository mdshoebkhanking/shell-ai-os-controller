"""
Static backend tool catalog for Shell UI and MCP.

The scanner intentionally uses AST instead of importing tool modules. Many
tool modules open browsers, touch OS APIs, or require optional packages at
import time; the UI only needs metadata until the user executes a tool.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any, Optional, Union


PROJECT_ROOT = Path(__file__).resolve().parent
_DISCOVER_TOOL_CACHE: dict[tuple[str, tuple[tuple[str, int, int], ...]], list[dict[str, Any]]] = {}
_DISK_CACHE_VERSION = 2
_DISK_CACHE_PATH = PROJECT_ROOT / ".shell_runtime" / "tool_catalog_cache.json"

_SKIP_DIRS = {
    ".git",
    "__pycache__",
    "venv",
    "node_modules",
    "_backups_",
    ".phoenix_backups",
    ".shell_image_cache",
    "shell.v1.0-main-main",
}

_DANGEROUS_WORDS = {
    "delete",
    "remove",
    "rm",
    "command",
    "terminal",
    "powershell",
    "python",
    "execute",
    "write",
    "send_email",
    "whatsapp",
    "telegram",
}


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _decorator_category(node: ast.AST) -> str:
    if not isinstance(node, ast.Call):
        return ""
    for kw in node.keywords:
        if kw.arg == "category" and isinstance(kw.value, ast.Constant):
            value = kw.value.value
            if isinstance(value, str):
                return value
    return ""


def _is_tool_function(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for dec in node.decorator_list:
        name = _decorator_name(dec)
        if name in {"function_tool", "god_tier_tool"}:
            return True
    return False


def _annotation_to_text(node: Optional[ast.AST]) -> str:
    if node is None:
        return "str"
    try:
        return ast.unparse(node)
    except Exception:
        if isinstance(node, ast.Name):
            return node.id
        return "str"


def _default_to_value(node: Optional[ast.AST]) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except Exception:
        try:
            return ast.unparse(node)
        except Exception:
            return None


def _category_for(module: str, func_name: str) -> str:
    name = f"{module}.{func_name}".lower()
    if _is_agent_tool(module, func_name):
        return "agents"
    buckets = [
        ("browser", ("browser", "youtube", "google", "web")),
        ("files", ("file", "pdf", "zip", "organizer", "downloader", "converter")),
        ("system", ("system", "window", "keyboard", "mouse", "terminal", "screenshot", "platform", "supervisor", "runtime")),
        ("communication", ("email", "whatsapp", "telegram", "social", "instagram")),
        ("ai", ("brain", "agent", "image", "ocr", "vision", "translator", "knowledge")),
        ("productivity", ("calendar", "scheduler", "productivity", "ppt", "text", "json")),
        ("developer", ("code", "regex", "hash", "network", "diagnostic", "self_heal")),
        ("media", ("music", "video", "qr")),
        ("finance", ("stock", "crypto")),
        ("games", ("game", "dice", "trivia")),
    ]
    for category, words in buckets:
        if any(word in name for word in words):
            return category
    return "general"


def _is_agent_tool(module: str, func_name: str) -> bool:
    blob = f"{module}.{func_name}".lower()
    if module == "shell_agent_orchestrator":
        return True
    return (
        module in {"shell_agents", "shell_extra_agents", "shell_agent_tools"}
        and ("agent" in func_name.lower() or "swarm" in blob)
    )


def _risk_for(module: str, func_name: str) -> str:
    blob = f"{module}.{func_name}".lower()
    return "guarded" if any(word in blob for word in _DANGEROUS_WORDS) else "normal"


def _iter_python_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            if filename == Path(__file__).name:
                continue
            path = Path(dirpath) / filename
            rel = path.relative_to(root)
            if len(rel.parts) > 3:
                continue
            yield path


def _module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    return ".".join(rel.parts)


def _copy_catalog(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    copied = []
    for item in items:
        row = dict(item)
        row["params"] = [dict(param) for param in item.get("params", [])]
        copied.append(row)
    return copied


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _disk_cache_enabled(root_path: Path) -> bool:
    if _truthy(os.environ.get("SHELL_DISABLE_TOOL_CATALOG_CACHE")):
        return False
    return root_path == PROJECT_ROOT


def _signature_to_json(signature: tuple[tuple[str, int, int], ...]) -> list[list[object]]:
    return [[path, mtime_ns, size] for path, mtime_ns, size in signature]


def _read_disk_cache(signature: tuple[tuple[str, int, int], ...]) -> list[dict[str, Any]] | None:
    try:
        payload = json.loads(_DISK_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if payload.get("version") != _DISK_CACHE_VERSION:
        return None
    if payload.get("signature") != _signature_to_json(signature):
        return None
    catalog = payload.get("catalog")
    if not isinstance(catalog, list):
        return None
    return [dict(item) for item in catalog if isinstance(item, dict)]


def _write_disk_cache(signature: tuple[tuple[str, int, int], ...], tools: list[dict[str, Any]]) -> None:
    try:
        _DISK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _DISK_CACHE_VERSION,
            "signature": _signature_to_json(signature),
            "catalog": tools,
        }
        tmp = _DISK_CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        tmp.replace(_DISK_CACHE_PATH)
    except Exception:
        return


def _params_for(node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> list[dict[str, Any]]:
    args = list(node.args.posonlyargs) + list(node.args.args)
    if args and args[0].arg in {"self", "cls"}:
        args = args[1:]
    defaults = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)
    params = []
    for arg, default_node in zip(args, defaults):
        default = _default_to_value(default_node)
        params.append({
            "name": arg.arg,
            "annotation": _annotation_to_text(arg.annotation),
            "required": default_node is None,
            "default": default,
        })
    for arg, default_node in zip(node.args.kwonlyargs, node.args.kw_defaults):
        default = _default_to_value(default_node)
        params.append({
            "name": arg.arg,
            "annotation": _annotation_to_text(arg.annotation),
            "required": default_node is None,
            "default": default,
        })
    return params


def discover_tool_catalog(root: Optional[Union[str, os.PathLike[str]]] = None) -> list[dict[str, Any]]:
    root_path = Path(root).resolve() if root else PROJECT_ROOT
    paths = sorted(_iter_python_files(root_path), key=lambda p: str(p.relative_to(root_path)))
    signature_rows = []
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        signature_rows.append((str(path.relative_to(root_path)), stat.st_mtime_ns, stat.st_size))
    signature = tuple(signature_rows)
    cache_key = (str(root_path), signature)
    cached = _DISCOVER_TOOL_CACHE.get(cache_key)
    if cached is not None:
        return _copy_catalog(cached)

    if _disk_cache_enabled(root_path):
        disk_cached = _read_disk_cache(signature)
        if disk_cached is not None:
            _DISCOVER_TOOL_CACHE[cache_key] = _copy_catalog(disk_cached)
            return _copy_catalog(disk_cached)

    if len(_DISCOVER_TOOL_CACHE) > 4:
        _DISCOVER_TOOL_CACHE.clear()

    tools: list[dict[str, Any]] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=str(path))
        except Exception:
            continue
        module = _module_name(root_path, path)
        for node in ast.walk(tree):
            if not _is_tool_function(node):
                continue
            assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            decorator_category = ""
            for dec in node.decorator_list:
                decorator_category = _decorator_category(dec) or decorator_category
            category = decorator_category or _category_for(module, node.name)
            doc = ast.get_docstring(node) or ""
            first_doc_line = doc.strip().splitlines()[0].strip() if doc.strip() else ""
            kind = "agent" if _is_agent_tool(module, node.name) else "tool"
            tools.append({
                "kind": kind,
                "id": f"{module}:{node.name}",
                "name": node.name,
                "title": node.name.replace("_tool", "").replace("_", " ").title(),
                "module": module,
                "file": str(path.relative_to(root_path)),
                "line": int(getattr(node, "lineno", 0) or 0),
                "async": isinstance(node, ast.AsyncFunctionDef),
                "category": category,
                "risk": _risk_for(module, node.name),
                "description": first_doc_line,
                "params": _params_for(node),
            })
    tools.sort(key=lambda item: (item["category"], item["module"], item["name"]))
    if _disk_cache_enabled(root_path):
        _write_disk_cache(signature, tools)
    _DISCOVER_TOOL_CACHE[cache_key] = _copy_catalog(tools)
    return _copy_catalog(tools)


def mcp_action_catalog() -> list[dict[str, Any]]:
    """Return real MCP tools exposed through CursorTouch/Windows-MCP.

    Shell's earlier `mcp_server.py` actions were a proprietary HTTP command
    dispatcher, not Anthropic/Model Context Protocol. The UI now treats
    Windows-MCP as the MCP surface and keeps decorated Shell tools/agents as
    separate local backend capabilities.
    """
    try:
        from shell_windows_mcp import windows_mcp_tool_catalog
        return windows_mcp_tool_catalog()
    except Exception:
        return []


def discover_capabilities(root: Optional[Union[str, os.PathLike[str]]] = None) -> dict[str, Any]:
    raw_actions = mcp_action_catalog()
    raw_tools = discover_tool_catalog(root)
    raw_catalog = raw_actions + raw_tools
    try:
        from core.tools.registry import capability_summary, enrich_catalog

        catalog = enrich_catalog(raw_catalog)
        summary_extra = capability_summary(catalog)
    except Exception:
        catalog = raw_catalog
        summary_extra = {}
    actions = [item for item in catalog if item.get("kind") == "windows_mcp_tool"]
    tools = [item for item in catalog if item.get("kind") != "windows_mcp_tool"]
    categories = sorted({item["category"] for item in catalog})
    agent_count = sum(1 for item in tools if item.get("kind") == "agent")
    summary = {
        "actions": len(actions),
        "tools": len(tools) - agent_count,
        "agents": agent_count,
        "total": len(catalog),
        "categories": categories,
    }
    summary.update(summary_extra)
    return {
        "status": "success",
        "actions": actions,
        "tools": tools,
        "catalog": catalog,
        "summary": summary,
    }
