from __future__ import annotations

import time
from pathlib import Path

from .base import BaseTool, ToolMetadata, ToolRequest, ToolResult


class FileTool(BaseTool):
    metadata = ToolMetadata(
        name="file",
        description="Read, write, append, and list local files.",
        capabilities=["read_file", "write_file", "append_file", "list_dir"],
    )

    def run(self, request: ToolRequest) -> ToolResult:
        operation = str(request.args.get("operation") or "").strip()
        if not operation:
            return self._error(request, "Missing file operation")
        if operation == "read_file":
            return self.read_file(request)
        if operation == "write_file":
            return self.write_file(request)
        if operation == "append_file":
            return self.append_file(request)
        if operation == "list_dir":
            return self.list_dir(request)
        return self._error(request, f"Unsupported file operation: {operation}")

    def _path(self, request: ToolRequest) -> Path:
        return self.resolve_path(str(request.args.get("path") or "."), request.working_dir)

    def _result(self, request: ToolRequest, status: str, stdout: str = "", stderr: str = "", metadata=None) -> ToolResult:
        started = time.time()
        self._record(request, status, f"file {request.args.get('operation')}", metadata)
        return ToolResult(
            tool_name=self.metadata.name,
            status=status,
            stdout=stdout,
            stderr=stderr,
            metadata=dict(metadata or {}),
            started_at=started,
            duration_ms=round((time.time() - started) * 1000.0, 3),
        )

    def _error(self, request: ToolRequest, message: str) -> ToolResult:
        return self._result(request, "error", stderr=message, metadata={"error": message})

    def read_file(self, request: ToolRequest) -> ToolResult:
        path = self._path(request)
        try:
            text = path.read_text(encoding=str(request.args.get("encoding") or "utf-8"))
            return self._result(request, "ok", stdout=text, metadata={"path": str(path), "bytes": len(text.encode("utf-8"))})
        except Exception as exc:
            return self._error(request, str(exc))

    def write_file(self, request: ToolRequest) -> ToolResult:
        path = self._path(request)
        content = str(request.args.get("content") or "")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding=str(request.args.get("encoding") or "utf-8"))
            return self._result(request, "ok", stdout=str(path), metadata={"path": str(path), "bytes": len(content.encode("utf-8"))})
        except Exception as exc:
            return self._error(request, str(exc))

    def append_file(self, request: ToolRequest) -> ToolResult:
        path = self._path(request)
        content = str(request.args.get("content") or "")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding=str(request.args.get("encoding") or "utf-8")) as handle:
                handle.write(content)
            return self._result(request, "ok", stdout=str(path), metadata={"path": str(path), "bytes": len(content.encode("utf-8"))})
        except Exception as exc:
            return self._error(request, str(exc))

    def list_dir(self, request: ToolRequest) -> ToolResult:
        path = self._path(request)
        try:
            rows = sorted(item.name + ("/" if item.is_dir() else "") for item in path.iterdir())
            return self._result(request, "ok", stdout="\n".join(rows), metadata={"path": str(path), "count": len(rows)})
        except Exception as exc:
            return self._error(request, str(exc))
