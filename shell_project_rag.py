#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.project_rag import ProjectRAGConfig, ProjectRAGIndex, project_rag_enabled
from shell_safe_executor import god_tier_tool as function_tool


def _project_path(path: str | None = None) -> Path:
    raw = str(path or "").strip()
    return Path(raw).expanduser().resolve() if raw else Path.cwd().resolve()


def _disabled_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "enabled": False,
        "message": "Project RAG v2 disabled. Set SHELL_PROJECT_RAG_ENABLED=1 to enable indexing and query.",
    }


def index_project(project_path: str | None = None, *, max_files: int | None = None) -> dict[str, Any]:
    root = _project_path(project_path)
    index = ProjectRAGIndex(root, config=ProjectRAGConfig.from_environment(max_files=max_files))
    return index.index_project(max_files=max_files)


def query_project(project_path: str | None, query: str, *, limit: int = 8) -> dict[str, Any]:
    root = _project_path(project_path)
    index = ProjectRAGIndex(root, config=ProjectRAGConfig.from_environment())
    return index.query(query, limit=limit)


def project_status(project_path: str | None = None) -> dict[str, Any]:
    root = _project_path(project_path)
    index = ProjectRAGIndex(root, config=ProjectRAGConfig.from_environment())
    return index.status()


@function_tool(category="developer")
async def project_rag_index_tool(project_path: str = "", max_files: int = 1000) -> dict[str, Any]:
    """
    Incrementally index a project folder for local code RAG.
    Args:
        project_path: Project folder path. Empty means current working directory.
        max_files: Maximum files to scan in this run.
    """
    if not project_rag_enabled():
        return _disabled_payload()
    return index_project(project_path, max_files=max_files)


@function_tool(category="developer")
async def project_rag_query_tool(query: str, project_path: str = "", limit: int = 8) -> dict[str, Any]:
    """
    Query the local Project RAG v2 index for coding assistance context.
    Args:
        query: Natural language or code search query.
        project_path: Project folder path. Empty means current working directory.
        limit: Maximum chunks to return.
    """
    if not project_rag_enabled():
        return _disabled_payload()
    root = _project_path(project_path)
    index = ProjectRAGIndex(root, config=ProjectRAGConfig.from_environment())
    status = index.status()
    if status.get("indexed_chunks", 0) <= 0:
        index.index_project()
    return index.query(query, limit=max(1, int(limit)))


@function_tool(category="developer")
async def project_rag_status_tool(project_path: str = "") -> dict[str, Any]:
    """Return Project RAG v2 enablement, index counts, dependency status, and DB path."""
    root = _project_path(project_path)
    index = ProjectRAGIndex(root, config=ProjectRAGConfig.from_environment())
    return index.status()


__all__ = [
    "index_project",
    "project_rag_enabled",
    "project_rag_index_tool",
    "project_rag_query_tool",
    "project_rag_status_tool",
    "project_status",
    "query_project",
]
