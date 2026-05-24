from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SECRET_ENV_PARTS = (
    "api_key", "apikey", "auth", "bearer", "client_secret", "credential",
    "key", "password", "private", "secret", "session", "token", "webhook",
)
SAFE_ENV_NAMES = {
    "PATH", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL",
    "TMPDIR", "TEMP", "TMP", "PYTHONPATH",
}
NETWORK_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(socket|requests|urllib|httpx|aiohttp|ftplib|smtplib|websocket)\b",
    re.MULTILINE,
)


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def secure_sandbox_enabled() -> bool:
    return _truthy(os.environ.get("SHELL_SECURE_SANDBOX_ENABLED"))


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _redact_code_preview(code: str, limit: int = 300) -> str:
    preview = str(code or "")[:limit]
    preview = re.sub(r"(?i)(api[_-]?key|token|secret|password)\s*=\s*['\"][^'\"]+['\"]", r"\1=<redacted>", preview)
    return preview


def _is_secret_name(name: str) -> bool:
    lowered = name.lower()
    return any(part in lowered for part in SECRET_ENV_PARTS)


def scrub_environment(base: dict[str, str] | None = None, *, home: Path | None = None) -> dict[str, str]:
    source = dict(os.environ if base is None else base)
    scrubbed: dict[str, str] = {}
    for key, value in source.items():
        if _is_secret_name(key):
            continue
        if key in SAFE_ENV_NAMES or key.startswith(("PYTHON", "QT_", "LC_")):
            scrubbed[key] = value
    sandbox_home = str(home) if home else tempfile.gettempdir()
    scrubbed["HOME"] = sandbox_home
    scrubbed["USERPROFILE"] = sandbox_home
    scrubbed["PYTHONNOUSERSITE"] = "1"
    scrubbed["SHELL_SANDBOX"] = "1"
    return scrubbed


@dataclass(frozen=True)
class SandboxConfig:
    timeout_s: float = 30.0
    network_enabled: bool = False
    keep_success: bool = False
    root_dir: Path = field(default_factory=lambda: Path(tempfile.gettempdir()) / "shell_secure_sandbox")
    audit_path: Path = field(default_factory=lambda: Path(".shell_runtime") / "secure_sandbox_audit.jsonl")

    @classmethod
    def from_environment(cls, *, timeout_s: float | None = None) -> "SandboxConfig":
        return cls(
            timeout_s=_env_float(
                "SHELL_SECURE_SANDBOX_TIMEOUT_S",
                timeout_s if timeout_s is not None else 30.0,
                minimum=1.0,
                maximum=300.0,
            ),
            network_enabled=_truthy(os.environ.get("SHELL_SECURE_SANDBOX_NETWORK")),
            keep_success=_truthy(os.environ.get("SHELL_SECURE_SANDBOX_KEEP_SUCCESS")),
            root_dir=Path(os.environ.get("SHELL_SECURE_SANDBOX_ROOT", tempfile.gettempdir())).expanduser()
            / "shell_secure_sandbox",
            audit_path=Path(os.environ.get("SHELL_SECURE_SANDBOX_AUDIT", ".shell_runtime/secure_sandbox_audit.jsonl")).expanduser(),
        )


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    command: list[str]
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    elapsed_ms: float = 0.0
    workspace: str = ""
    audit_id: str = ""
    rolled_back: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "command": list(self.command),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "elapsed_ms": self.elapsed_ms,
            "workspace": self.workspace,
            "audit_id": self.audit_id,
            "rolled_back": self.rolled_back,
            "error": self.error,
        }


class SecureCodingSandbox:
    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig.from_environment()

    def _new_workspace(self) -> Path:
        self.config.root_dir.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="run_", dir=str(self.config.root_dir)))

    def _audit(self, payload: dict[str, Any]) -> None:
        self.config.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    @staticmethod
    def _code_hash(code: str) -> str:
        return hashlib.sha256(str(code or "").encode("utf-8", errors="ignore")).hexdigest()

    def _network_guard(self, code: str) -> str:
        if self.config.network_enabled:
            return ""
        match = NETWORK_IMPORT_RE.search(str(code or ""))
        if not match:
            return ""
        return f"network disabled: blocked import '{match.group(1)}'"

    async def run_python(self, code: str, *, timeout_s: float | None = None) -> SandboxResult:
        return await self._run_source(code, language="python", timeout_s=timeout_s)

    async def run_source(self, code: str, *, language: str = "python", timeout_s: float | None = None) -> SandboxResult:
        return await self._run_source(code, language=language, timeout_s=timeout_s)

    async def run_file(self, file_path: str | Path, *, timeout_s: float | None = None) -> SandboxResult:
        source = Path(file_path).expanduser().resolve()
        if not source.is_file():
            return SandboxResult(False, [], error=f"file not found: {source}")
        ext = source.suffix.lower()
        if ext == ".py":
            language = "python"
            command_name = "main.py"
        elif ext == ".js":
            language = "javascript"
            command_name = "main.js"
        else:
            return SandboxResult(False, [], error=f"unsupported sandbox file type: {ext}")
        code = source.read_text(encoding="utf-8", errors="ignore")
        return await self._run_source(code, language=language, timeout_s=timeout_s, filename=command_name)

    async def _run_source(
        self,
        code: str,
        *,
        language: str,
        timeout_s: float | None = None,
        filename: str | None = None,
    ) -> SandboxResult:
        if not str(code or "").strip():
            return SandboxResult(False, [], error="code is required")
        guard = self._network_guard(code)
        audit_id = uuid.uuid4().hex
        if guard:
            payload = self._audit_payload(audit_id, [], code, None, status="blocked", error=guard)
            self._audit(payload)
            return SandboxResult(False, [], audit_id=audit_id, error=guard)

        workspace = self._new_workspace()
        if language == "python":
            filename = filename or "main.py"
            command = [sys.executable, filename]
        elif language in {"javascript", "node", "js"}:
            filename = filename or "main.js"
            command = ["node", filename]
        else:
            shutil.rmtree(workspace, ignore_errors=True)
            return SandboxResult(False, [], audit_id=audit_id, error=f"unsupported language: {language}")

        source_path = workspace / filename
        source_path.write_text(str(code), encoding="utf-8")
        timeout = float(timeout_s or self.config.timeout_s)
        started = time.perf_counter()
        timed_out = False
        exit_code: int | None = None
        stdout = b""
        stderr = b""
        error = ""
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(workspace),
                env=scrub_environment(home=workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                timed_out = True
                proc.kill()
                stdout, stderr = await proc.communicate()
            exit_code = proc.returncode
        except FileNotFoundError as exc:
            error = str(exc)
        except Exception as exc:
            error = str(exc)

        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        ok = bool(not timed_out and not error and exit_code == 0)
        should_cleanup = (not ok) or (ok and not self.config.keep_success)
        rolled_back = False
        if should_cleanup:
            shutil.rmtree(workspace, ignore_errors=True)
            rolled_back = not workspace.exists()
        payload = self._audit_payload(
            audit_id,
            command,
            code,
            workspace,
            status="ok" if ok else "failed",
            exit_code=exit_code,
            timed_out=timed_out,
            elapsed_ms=elapsed_ms,
            rolled_back=rolled_back,
            error=error,
        )
        self._audit(payload)
        return SandboxResult(
            ok=ok,
            command=command,
            stdout=stdout.decode("utf-8", errors="replace")[:5000],
            stderr=stderr.decode("utf-8", errors="replace")[:3000],
            exit_code=exit_code,
            timed_out=timed_out,
            elapsed_ms=elapsed_ms,
            workspace=str(workspace),
            audit_id=audit_id,
            rolled_back=rolled_back,
            error=error,
        )

    def _audit_payload(
        self,
        audit_id: str,
        command: list[str],
        code: str,
        workspace: Path | None,
        *,
        status: str,
        exit_code: int | None = None,
        timed_out: bool = False,
        elapsed_ms: float = 0.0,
        rolled_back: bool = False,
        error: str = "",
    ) -> dict[str, Any]:
        return {
            "audit_id": audit_id,
            "ts": time.time(),
            "status": status,
            "command": list(command),
            "workspace": str(workspace or ""),
            "code_sha256": self._code_hash(code),
            "code_preview": _redact_code_preview(code),
            "timeout_s": self.config.timeout_s,
            "network_enabled": self.config.network_enabled,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "elapsed_ms": elapsed_ms,
            "rolled_back": rolled_back,
            "error": error,
        }


__all__ = [
    "SandboxConfig",
    "SandboxResult",
    "SecureCodingSandbox",
    "scrub_environment",
    "secure_sandbox_enabled",
]
