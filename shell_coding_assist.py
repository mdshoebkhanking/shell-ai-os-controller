from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

from shell_safe_executor import god_tier_tool as function_tool


IGNORE_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".next", "out"}
CODE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".md", ".json", ".html", ".css", ".yml", ".yaml"}


def _iter_files(root: Path, max_files: int) -> list[Path]:
    rows: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in IGNORE_DIRS and not name.startswith(".")]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() not in CODE_EXTS:
                continue
            rows.append(path)
            if len(rows) >= max_files:
                return rows
    return rows


def _read_preview(path: Path, limit: int = 6000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""


@function_tool(category="developer")
async def shell_scan_project_folder_tool(project_path: str, max_files: int = 300) -> dict[str, Any]:
    """Scan a project folder and return a fast Shell codebase inventory."""
    root = Path(str(project_path or "")).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return {"ok": False, "message": f"Project folder not found: {root}"}
    limit = max(1, min(int(max_files or 300), 3000))
    files = _iter_files(root, limit)
    ext_counts = Counter(path.suffix.lower() or "<none>" for path in files)
    total_bytes = 0
    newest: list[dict[str, Any]] = []
    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue
        total_bytes += stat.st_size
        newest.append({"path": str(path), "relative_path": str(path.relative_to(root)), "bytes": stat.st_size, "mtime": stat.st_mtime})
    newest.sort(key=lambda row: row["mtime"], reverse=True)
    return {
        "ok": True,
        "project_path": str(root),
        "files_scanned": len(files),
        "total_bytes": total_bytes,
        "extensions": dict(ext_counts.most_common()),
        "recent_files": newest[:20],
        "ignored_dirs": sorted(IGNORE_DIRS),
    }


@function_tool(category="developer")
async def shell_automated_coding_assist_tool(project_path: str, prompt: str, max_files: int = 120) -> dict[str, Any]:
    """Find code files relevant to a prompt and produce a local coding context pack."""
    root = Path(str(project_path or "")).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return {"ok": False, "message": f"Project folder not found: {root}"}
    prompt_text = str(prompt or "").strip()
    if not prompt_text:
        return {"ok": False, "message": "A coding prompt is required."}
    try:
        from shell_project_rag import index_project, project_rag_enabled, query_project

        if project_rag_enabled():
            index_project(str(root), max_files=max_files)
            rag = query_project(str(root), prompt_text, limit=12)
            if rag.get("ok") and rag.get("matches"):
                return {
                    "ok": True,
                    "project_path": str(root),
                    "prompt": prompt_text,
                    "matches": [
                        {
                            "relative_path": row.get("relative_path", ""),
                            "path": str(root / str(row.get("relative_path", ""))),
                            "score": row.get("score", 0),
                            "start_line": row.get("start_line", 1),
                            "end_line": row.get("end_line", 1),
                            "preview": row.get("preview", "")[:900],
                        }
                        for row in rag.get("matches", [])
                    ],
                    "source": "project_rag_v2",
                    "next_step": "Use these ranked RAG chunks as the coding context before editing.",
                }
    except Exception:
        pass
    words = {word.lower() for word in prompt_text.replace("/", " ").replace("_", " ").split() if len(word) >= 3}
    files = _iter_files(root, max(1, min(int(max_files or 120), 1000)))
    matches: list[dict[str, Any]] = []
    for path in files:
        rel = str(path.relative_to(root))
        preview = _read_preview(path)
        hay = f"{rel}\n{preview}".lower()
        score = sum(1 for word in words if word in hay)
        if score:
            matches.append({"relative_path": rel, "path": str(path), "score": score, "preview": preview[:900]})
    matches.sort(key=lambda row: (row["score"], row["relative_path"]), reverse=True)
    return {
        "ok": True,
        "project_path": str(root),
        "prompt": prompt_text,
        "matches": matches[:12],
        "next_step": "Use these files as the coding context before editing.",
    }
