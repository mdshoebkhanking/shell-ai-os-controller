#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.secure_sandbox import SandboxConfig, SecureCodingSandbox, secure_sandbox_enabled
from shell_safe_executor import god_tier_tool as function_tool


def _disabled_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "enabled": False,
        "message": "Secure sandbox disabled. Set SHELL_SECURE_SANDBOX_ENABLED=1 to run code in isolated temp workspaces.",
    }


async def run_python_in_sandbox(code: str, *, timeout_s: float | None = None) -> dict[str, Any]:
    sandbox = SecureCodingSandbox(SandboxConfig.from_environment(timeout_s=timeout_s))
    return (await sandbox.run_python(code, timeout_s=timeout_s)).to_dict()


async def run_file_in_sandbox(file_path: str | Path, *, timeout_s: float | None = None) -> dict[str, Any]:
    sandbox = SecureCodingSandbox(SandboxConfig.from_environment(timeout_s=timeout_s))
    return (await sandbox.run_file(file_path, timeout_s=timeout_s)).to_dict()


def format_sandbox_result(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        if result.get("timed_out"):
            return f"Sandbox timed out after {result.get('elapsed_ms', 0)} ms. audit_id={result.get('audit_id', '')}"
        err = result.get("error") or result.get("stderr") or "sandbox execution failed"
        return f"Sandbox failed: {err}\naudit_id={result.get('audit_id', '')}"
    parts = [f"Sandbox OK ({result.get('elapsed_ms', 0)} ms, audit_id={result.get('audit_id', '')})"]
    if result.get("stdout"):
        parts.append(f"Output:\n{result['stdout']}")
    if result.get("stderr"):
        parts.append(f"Stderr:\n{result['stderr']}")
    return "\n".join(parts)


@function_tool(category="developer")
async def secure_sandbox_run_python_tool(code: str, timeout_s: float = 30.0) -> dict[str, Any]:
    """
    Run Python code in an isolated temp workspace with scrubbed env, timeout, audit, and failure cleanup.
    Args:
        code: Python code to execute.
        timeout_s: Execution timeout in seconds.
    """
    if not secure_sandbox_enabled():
        return _disabled_payload()
    return await run_python_in_sandbox(code, timeout_s=timeout_s)


@function_tool(category="developer")
async def secure_sandbox_run_file_tool(file_path: str, timeout_s: float = 30.0) -> dict[str, Any]:
    """
    Run a Python or JavaScript file in an isolated temp workspace.
    Args:
        file_path: Path to a .py or .js file.
        timeout_s: Execution timeout in seconds.
    """
    if not secure_sandbox_enabled():
        return _disabled_payload()
    return await run_file_in_sandbox(file_path, timeout_s=timeout_s)


@function_tool(category="developer")
async def secure_sandbox_status_tool() -> dict[str, Any]:
    """Return secure sandbox enablement, audit path, timeout, and network guard status."""
    cfg = SandboxConfig.from_environment()
    return {
        "ok": True,
        "enabled": secure_sandbox_enabled(),
        "timeout_s": cfg.timeout_s,
        "root_dir": str(cfg.root_dir),
        "audit_path": str(cfg.audit_path),
        "network_enabled": cfg.network_enabled,
        "network_isolation": "python-import-guard",
        "docker_backend": "not_enabled",
    }


__all__ = [
    "run_file_in_sandbox",
    "run_python_in_sandbox",
    "format_sandbox_result",
    "secure_sandbox_run_file_tool",
    "secure_sandbox_run_python_tool",
    "secure_sandbox_status_tool",
]
