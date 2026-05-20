from __future__ import annotations

import os
import platform
import time

from .base import BaseTool, ToolMetadata, ToolRequest, ToolResult


class OSTool(BaseTool):
    metadata = ToolMetadata(
        name="os",
        description="Safe operating-system context helpers.",
        capabilities=["get_os_info", "expand_user_path", "open_path_stub"],
    )

    def run(self, request: ToolRequest) -> ToolResult:
        operation = str(request.args.get("operation") or "get_os_info").strip()
        started = time.time()
        if operation == "get_os_info":
            data = {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "cwd": os.getcwd(),
            }
            self._record(request, "ok", "os info", data)
            return ToolResult(
                tool_name=self.metadata.name,
                status="ok",
                stdout="\n".join(f"{key}: {value}" for key, value in data.items()),
                metadata=data,
                started_at=started,
                duration_ms=round((time.time() - started) * 1000.0, 3),
            )
        if operation == "expand_user_path":
            raw = str(request.args.get("path") or "~")
            expanded = str(self.resolve_path(raw, request.working_dir))
            self._record(request, "ok", "expanded path", {"path": raw, "expanded": expanded})
            return ToolResult(
                tool_name=self.metadata.name,
                status="ok",
                stdout=expanded,
                metadata={"path": raw, "expanded": expanded},
                started_at=started,
                duration_ms=round((time.time() - started) * 1000.0, 3),
            )
        if operation == "open_path":
            message = "open_path is a platform-specific stub in Stage 6."
            self._record(request, "not_implemented", message, {"path": request.args.get("path")})
            return ToolResult(
                tool_name=self.metadata.name,
                status="not_implemented",
                stderr=message,
                metadata={"path": request.args.get("path")},
                started_at=started,
                duration_ms=round((time.time() - started) * 1000.0, 3),
            )
        message = f"Unsupported OS operation: {operation}"
        self._record(request, "error", message, {"operation": operation})
        return ToolResult(
            tool_name=self.metadata.name,
            status="error",
            stderr=message,
            metadata={"operation": operation},
            started_at=started,
            duration_ms=round((time.time() - started) * 1000.0, 3),
        )
