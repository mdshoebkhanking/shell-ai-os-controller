#!/usr/bin/env python3
"""
Shell Workspace Tools.

Small, safe file operations for the UI workspace panel. These tools are
intentionally scoped to the configured Shell workspace so chat commands can
create and inspect files without enabling unrestricted code writing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from shell_safe_executor import god_tier_tool as function_tool


PROJECT_ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = PROJECT_ROOT / ".shell_settings.json"
DEFAULT_WORKSPACE = PROJECT_ROOT / "shell_workspace"


def resolve_workspace_path() -> Path:
    """Return the configured workspace path, creating it when needed."""
    raw = os.environ.get("SHELL_WORKSPACE_PATH", "").strip()
    if not raw and SETTINGS_PATH.exists():
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            raw = str(settings.get("workspace_path") or "").strip()
        except Exception:
            raw = ""
    root = Path(raw).expanduser() if raw else DEFAULT_WORKSPACE
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_relative_path(path: str) -> Path:
    raw = str(path or "").strip().strip("\"'` ")
    if not raw:
        raise ValueError("File path is required.")
    if "\x00" in raw:
        raise ValueError("File path contains an invalid null byte.")
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        raise ValueError("Use a relative workspace path, not an absolute path.")
    parts = candidate.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Path traversal is not allowed.")
    if len(raw) > 240:
        raise ValueError("File path is too long.")
    return candidate


def _resolve_inside_workspace(path: str) -> tuple[Path, Path, Path]:
    root = resolve_workspace_path()
    rel = _safe_relative_path(path)
    full = (root / rel).resolve()
    try:
        full.relative_to(root)
    except ValueError as exc:
        raise ValueError("Resolved path escapes the Shell workspace.") from exc
    return root, rel, full


def _text_preview(content: str, limit: int = 12000) -> tuple[str, bool]:
    text = str(content or "")
    if len(text) <= limit:
        return text, False
    return text[:limit], True


@function_tool(category="files")
async def create_workspace_file_tool(path: str, content: str = "", overwrite: bool = False) -> dict[str, Any]:
    """
    Create a text file inside the Shell workspace.

    Args:
        path: Relative path inside the Shell workspace, for example notes.md.
        content: Text content to write.
        overwrite: Set true to replace an existing file.
    """
    try:
        root, rel, full = _resolve_inside_workspace(path)
    except ValueError as exc:
        return {"ok": False, "message": str(exc), "relative_path": str(path or ""), "ui_hint": "refresh_workspace"}
    exists = full.exists()
    if exists and not overwrite:
        return {
            "ok": False,
            "action": "exists",
            "message": "File already exists. Say overwrite/replace to update it.",
            "workspace": str(root),
            "relative_path": str(rel),
            "path": str(full),
            "ui_hint": "open_in_workspace",
        }
    full.parent.mkdir(parents=True, exist_ok=True)
    text = str(content or "")
    full.write_text(text, encoding="utf-8")
    return {
        "ok": True,
        "action": "updated" if exists else "created",
        "message": f"{'Updated' if exists else 'Created'} {rel}",
        "workspace": str(root),
        "relative_path": str(rel),
        "path": str(full),
        "bytes": len(text.encode("utf-8")),
        "ui_hint": "open_in_workspace",
    }


@function_tool(category="files")
async def read_workspace_file_tool(path: str, max_chars: int = 20000) -> dict[str, Any]:
    """
    Read a text file from the Shell workspace.

    Args:
        path: Relative path inside the Shell workspace.
        max_chars: Maximum characters to return to the chat response.
    """
    try:
        root, rel, full = _resolve_inside_workspace(path)
    except ValueError as exc:
        return {"ok": False, "message": str(exc), "relative_path": str(path or ""), "ui_hint": "refresh_workspace"}
    if not full.exists():
        return {
            "ok": False,
            "message": "File not found in the Shell workspace.",
            "workspace": str(root),
            "relative_path": str(rel),
            "path": str(full),
            "ui_hint": "open_in_workspace",
        }
    if full.is_dir():
        return {
            "ok": False,
            "message": "That path is a folder, not a file.",
            "workspace": str(root),
            "relative_path": str(rel),
            "path": str(full),
            "ui_hint": "open_in_workspace",
        }
    try:
        text = full.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "ok": False,
            "message": "File is not valid UTF-8 text.",
            "workspace": str(root),
            "relative_path": str(rel),
            "path": str(full),
            "ui_hint": "open_in_workspace",
        }
    preview, truncated = _text_preview(text, max(1000, int(max_chars or 20000)))
    return {
        "ok": True,
        "action": "read",
        "workspace": str(root),
        "relative_path": str(rel),
        "path": str(full),
        "chars": len(text),
        "truncated": truncated,
        "content": preview,
        "ui_hint": "open_in_workspace",
    }


@function_tool(category="files")
async def list_workspace_files_tool(limit: int = 200) -> dict[str, Any]:
    """
    List files inside the Shell workspace.

    Args:
        limit: Maximum number of files to return.
    """
    root = resolve_workspace_path()
    rows: list[dict[str, Any]] = []
    max_rows = max(1, min(int(limit or 200), 1000))
    for full in sorted(root.rglob("*")):
        if full.is_dir():
            continue
        try:
            rel = full.relative_to(root)
        except ValueError:
            continue
        try:
            stat = full.stat()
        except OSError:
            continue
        rows.append({
            "path": str(full),
            "relative_path": str(rel),
            "bytes": stat.st_size,
            "modified": stat.st_mtime,
        })
        if len(rows) >= max_rows:
            break
    return {
        "ok": True,
        "workspace": str(root),
        "count": len(rows),
        "files": rows,
        "ui_hint": "refresh_workspace",
    }


@function_tool(category="files")
async def workspace_status_tool() -> dict[str, Any]:
    """Return the active Shell workspace path and basic file count."""
    root = resolve_workspace_path()
    count = 0
    for full in root.rglob("*"):
        if full.is_file():
            count += 1
    return {
        "ok": True,
        "workspace": str(root),
        "file_count": count,
        "ui_hint": "refresh_workspace",
    }
