from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class SandboxPolicy:
    allowed_commands: set[str] = field(default_factory=lambda: {"python", "python3"})
    timeout_s: float = 10.0
    max_output_chars: int = 12000
    allow_network: bool = False


@dataclass(frozen=True)
class SandboxResult:
    status: str
    message: str = ""
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "path": self.path,
        }


class TemporaryWorkspace:
    def __init__(self, policy: SandboxPolicy | None = None, root: str | Path | None = None):
        self.policy = policy or SandboxPolicy()
        self._owned = root is None
        self.root = Path(root) if root is not None else Path(tempfile.mkdtemp(prefix="shell_sandbox_"))
        self.root.mkdir(parents=True, exist_ok=True)
        self._snapshot_path: Path | None = None

    def close(self) -> None:
        if self._owned and self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "TemporaryWorkspace":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def resolve(self, relative_path: str | Path) -> Path:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root.resolve()):
            publish_event(AIEventType.SANDBOX_VIOLATION, {"path": str(relative_path)}, source="sandbox")
            raise PermissionError("sandbox path escapes workspace")
        return target

    def write_text(self, relative_path: str | Path, content: str) -> Path:
        target = self.resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
        return target

    def snapshot(self) -> Path:
        if self._snapshot_path and self._snapshot_path.exists():
            shutil.rmtree(self._snapshot_path, ignore_errors=True)
        self._snapshot_path = Path(tempfile.mkdtemp(prefix="shell_sandbox_snapshot_"))
        for child in self.root.iterdir():
            dest = self._snapshot_path / child.name
            if child.is_dir():
                shutil.copytree(child, dest)
            else:
                shutil.copy2(child, dest)
        return self._snapshot_path

    def rollback(self) -> None:
        if not self._snapshot_path or not self._snapshot_path.exists():
            return
        for child in list(self.root.iterdir()):
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        for child in self._snapshot_path.iterdir():
            dest = self.root / child.name
            if child.is_dir():
                shutil.copytree(child, dest)
            else:
                shutil.copy2(child, dest)

    def run(self, command: list[str]) -> SandboxResult:
        if not command:
            return SandboxResult("error", "empty command", path=str(self.root))
        executable = Path(command[0]).name
        if executable not in self.policy.allowed_commands:
            publish_event(AIEventType.SANDBOX_VIOLATION, {"command": command}, source="sandbox")
            return SandboxResult("blocked", f"command {executable!r} is not allowed", path=str(self.root))
        start = time.time()
        try:
            proc = subprocess.run(
                command,
                cwd=str(self.root),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.policy.timeout_s,
                check=False,
            )
            return SandboxResult(
                "success" if proc.returncode == 0 else "error",
                f"completed in {round((time.time() - start) * 1000, 1)}ms",
                proc.returncode,
                proc.stdout[: self.policy.max_output_chars],
                proc.stderr[: self.policy.max_output_chars],
                str(self.root),
            )
        except subprocess.TimeoutExpired as exc:
            return SandboxResult("timeout", f"timed out after {self.policy.timeout_s}s", None, (exc.stdout or "")[: self.policy.max_output_chars], (exc.stderr or "")[: self.policy.max_output_chars], str(self.root))

