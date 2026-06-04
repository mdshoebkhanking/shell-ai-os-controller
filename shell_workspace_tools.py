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
import re
from pathlib import Path
from typing import Any

from shell_safe_executor import god_tier_tool as function_tool


PROJECT_ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = PROJECT_ROOT / ".shell_settings.json"
DEFAULT_WORKSPACE = PROJECT_ROOT / "shell_workspace"
TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".log",
    ".json",
    ".csv",
    ".html",
    ".htm",
    ".py",
    ".js",
    ".css",
    ".xml",
    ".yaml",
    ".yml",
}


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


def _desktop_dir() -> Path:
    home = Path.home()
    candidates = [
        Path(os.environ.get("USERPROFILE", "")).expanduser() / "Desktop" if os.environ.get("USERPROFILE") else None,
        home / "Desktop",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate.resolve()
    path = home / "Desktop"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _allowed_destination_root(destination: str) -> tuple[str, Path]:
    key = str(destination or "workspace").strip().lower().replace(" ", "_")
    aliases = {
        "desk": "desktop",
        "desk_top": "desktop",
        "dextop": "desktop",
        "desktop": "desktop",
        "document": "documents",
        "documents": "documents",
        "download": "downloads",
        "downloads": "downloads",
        "workspace": "workspace",
        "shell_workspace": "workspace",
    }
    normalized = aliases.get(key, key)
    home = Path.home()
    roots = {
        "desktop": _desktop_dir,
        "documents": lambda: (home / "Documents").resolve(),
        "downloads": lambda: (home / "Downloads").resolve(),
        "workspace": resolve_workspace_path,
    }
    if normalized not in roots:
        raise ValueError("Destination allowed nahi hai. Use desktop, documents, downloads, ya workspace.")
    root = roots[normalized]()
    root.mkdir(parents=True, exist_ok=True)
    return normalized, root.resolve()


def _safe_filename(filename: str, file_type: str) -> str:
    raw = str(filename or "").strip().strip("\"'` ")
    ext_hint = str(file_type or "").strip().lower().lstrip(".")
    if not raw:
        raw = f"shell_file.{ext_hint or 'txt'}"
    raw = raw.replace("\\", "/").split("/")[-1]
    raw = re.sub(r"[\x00-\x1f]", "", raw)
    raw = re.sub(r'[<>:"|?*]', "_", raw).strip(" ._")
    if not raw:
        raw = f"shell_file.{ext_hint or 'txt'}"
    if "." not in raw:
        raw = f"{raw}.{ext_hint or 'txt'}"
    if len(raw) > 160:
        stem = Path(raw).stem[:120].strip(" ._") or "shell_file"
        suffix = Path(raw).suffix[:16] or f".{ext_hint or 'txt'}"
        raw = f"{stem}{suffix}"
    return raw


def _slug_filename(text: str, file_type: str) -> str:
    words = re.sub(r"[^a-zA-Z0-9]+", " ", str(text or "")).strip().lower().split()
    stem = "_".join(words[:8]) or "shell_file"
    ext = (file_type or "txt").strip().lower().lstrip(".") or "txt"
    return f"{stem[:80]}.{ext}"


def _minimal_pdf_bytes(text: str, title: str = "Shell File") -> bytes:
    lines: list[str] = []
    for raw_line in str(text or "").splitlines() or [""]:
        line = raw_line.strip()
        while len(line) > 88:
            lines.append(line[:88])
            line = line[88:]
        lines.append(line)
    safe_lines = []
    for line in lines[:52]:
        cleaned = line.encode("latin-1", errors="replace").decode("latin-1")
        cleaned = cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        safe_lines.append(cleaned)
    commands = ["BT", "/F1 11 Tf", "50 770 Td"]
    title_text = str(title or "Shell File").encode("latin-1", errors="replace").decode("latin-1")
    title_text = title_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    commands.append(f"({title_text}) Tj")
    commands.append("0 -24 Td")
    commands.append("/F1 10 Tf")
    for line in safe_lines:
        commands.append(f"({line}) Tj")
        commands.append("0 -14 Td")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return b"".join(chunks)


def _write_pdf(path: Path, content: str, title: str) -> None:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        doc = SimpleDocTemplate(str(path), pagesize=letter)
        styles = getSampleStyleSheet()
        story = [Paragraph(str(title or path.stem), styles["Title"]), Spacer(1, 12)]
        for paragraph in str(content or "").splitlines() or [""]:
            story.append(Paragraph(paragraph or " ", styles["BodyText"]))
            story.append(Spacer(1, 6))
        doc.build(story)
    except Exception:
        path.write_bytes(_minimal_pdf_bytes(content, title=title or path.stem))


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
async def create_user_file_tool(
    filename: str = "",
    content: str = "",
    destination: str = "desktop",
    file_type: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Create a user-visible file in an allowed folder such as Desktop.

    Args:
        filename: File name only. Path separators are ignored for safety.
        content: Text content to write into the file.
        destination: desktop, documents, downloads, or workspace.
        file_type: Optional extension when filename has none, e.g. pdf or txt.
        overwrite: Set true to replace an existing file.
    """
    try:
        destination_key, root = _allowed_destination_root(destination)
    except ValueError as exc:
        return {"ok": False, "message": str(exc), "destination": destination}

    text = str(content or "").strip()
    inferred_type = str(file_type or "").strip().lower().lstrip(".")
    if not inferred_type and filename:
        inferred_type = Path(str(filename)).suffix.lower().lstrip(".")
    if not filename:
        filename = _slug_filename(text or "shell file", inferred_type or "txt")
    safe_name = _safe_filename(filename, inferred_type or "txt")
    full = (root / safe_name).resolve()
    try:
        full.relative_to(root)
    except ValueError:
        return {"ok": False, "message": "Resolved file path escaped the allowed destination.", "path": str(full)}

    suffix = full.suffix.lower()
    if suffix == ".pdf":
        writer = "pdf"
    elif suffix in TEXT_EXTENSIONS:
        writer = "text"
    else:
        return {
            "ok": False,
            "message": "Unsupported file type. Use txt, md, json, csv, html, py, js, css, xml, yaml, log, or pdf.",
            "path": str(full),
        }

    exists = full.exists()
    if exists and not overwrite:
        return {
            "ok": False,
            "action": "exists",
            "message": "File already exists. Say overwrite/replace to update it.",
            "destination": destination_key,
            "path": str(full),
            "filename": safe_name,
        }

    if not text:
        text = "Shell created this file."
    full.parent.mkdir(parents=True, exist_ok=True)
    if writer == "pdf":
        _write_pdf(full, text, title=Path(safe_name).stem.replace("_", " ").title())
    else:
        full.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")
    size = full.stat().st_size
    return {
        "ok": True,
        "action": "updated" if exists else "created",
        "message": f"{'Updated' if exists else 'Created'} {safe_name} on {destination_key}",
        "destination": destination_key,
        "path": str(full),
        "filename": safe_name,
        "bytes": size,
        "ui_hint": "open_file_location",
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
