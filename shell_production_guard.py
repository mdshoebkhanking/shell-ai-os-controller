"""Production-release safety guard for Shell AI.

This module intentionally does not load python-dotenv. It reads `.env`
directly so installer/launcher code can validate the effective runtime
configuration before importing the larger application stack.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parent

TRUTHY = {"1", "true", "yes", "on", "enabled"}
LOCAL_HOSTS = {"", "127.0.0.1", "localhost", "::1"}

DANGEROUS_FLAGS: dict[str, str] = {
    "SHELL_ALLOW_CODE_WRITE": "allows core/runtime code mutation",
    "SHELL_ALLOW_AGENT_PATCH": "allows runtime patching of core agent files",
    "SHELL_ALLOW_OPENCLAW_SKILL_INSTALL": "allows unaudited skill installation",
    "SHELL_ALLOW_ARBITRARY_DOWNLOAD_PATH": "allows downloads outside the managed folder",
    "SHELL_HUB_ALLOW_UNAUTH_REMOTE": "allows unauthenticated remote hub access",
    "SHELL_MCP_ALLOW_UNAUTH_REMOTE": "allows unauthenticated remote MCP access",
    "SHELL_TELEGRAM_ALLOW_TERMINAL": "allows terminal execution through Telegram",
}

REQUIRED_PUBLIC_RELEASE_FILES = [
    ".env.example",
    ".gitignore",
    "README.md",
    "INSTALLATION.md",
    "requirements.txt",
    "installer/bootstrap.py",
    "launch.py",
    "shell_hub.py",
    "shell_ui/requirements_ui.txt",
    "shell_web_ui/host.py",
    "shell_web_ui/index.html",
    "shell_web_ui/package-lock.json",
    "shell_web_ui/package.json",
    "shell_web_ui/src/App.tsx",
    "shell_web_ui/src/IndexRoot.tsx",
    "shell_web_ui/src/main.tsx",
    "shell_web_ui/src/shellBridge.ts",
    "shell_web_ui/tsconfig.json",
    "shell_web_ui/vite.config.ts",
    "ONE_CLICK_INSTALL.bat",
    "Build_Public_Release.bat",
    "Start_ShellAI.bat",
    "Repair_ShellAI.bat",
    "ONE_CLICK_INSTALL.command",
    "Build_Public_Release.command",
    "start_shellai.command",
    "repair_shellai.command",
    "start_shellai.sh",
    "repair_shellai.sh",
    "installer/windows_audio_preflight.ps1",
]


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in TRUTHY


def _strip_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def read_env_file(path: str | Path) -> dict[str, str]:
    """Parse simple KEY=value files without exposing secret values."""
    env: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return env
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            env[key] = _strip_env_value(value)
    return env


def _effective_env(root: Path) -> dict[str, str]:
    env = read_env_file(root / ".env")
    for key in set(env) | set(DANGEROUS_FLAGS) | {
        "SHELL_PRODUCTION_MODE",
        "SHELL_PUBLIC_RELEASE",
        "SHELL_HUB_HOST",
        "SHELL_HUB_TOKEN",
        "SHELL_MCP_HOST",
        "SHELL_MCP_TOKEN",
        "AUTO_START_TELEGRAM_BOT",
        "TELEGRAM_BOT_TOKEN",
        "SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED",
        "SHELL_TELEGRAM_ALLOWED_CHAT_IDS",
    }:
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def production_mode_enabled(env: Mapping[str, object] | None = None) -> bool:
    source = env if env is not None else os.environ
    return truthy(source.get("SHELL_PRODUCTION_MODE")) or truthy(source.get("SHELL_PUBLIC_RELEASE"))


def _check_assets(root: Path, blockers: list[str], warnings: list[str], checks: list[dict[str, object]]) -> None:
    for rel in REQUIRED_PUBLIC_RELEASE_FILES:
        exists = (root / rel).exists()
        checks.append({"name": f"asset:{rel}", "ok": exists})
        if not exists:
            blockers.append(f"Missing public release asset: {rel}")

    gitignore = root / ".gitignore"
    if gitignore.exists():
        text = gitignore.read_text(encoding="utf-8", errors="replace")
        protects_env = any(line.strip() in {".env", ".env.*"} for line in text.splitlines())
        checks.append({"name": "asset:.gitignore protects .env", "ok": protects_env})
        if not protects_env:
            blockers.append(".gitignore must exclude .env secrets before public release")
    else:
        warnings.append(".gitignore missing; verify secrets are excluded before publishing")


def audit_production_environment(
    env: Mapping[str, object] | None = None,
    *,
    root: str | Path | None = None,
    check_assets: bool = True,
) -> dict[str, object]:
    """Return a redacted production-safety report.

    The report only contains key names and safety states, never secret values.
    """
    project_root = Path(root).resolve() if root is not None else ROOT
    source = dict(env) if env is not None else _effective_env(project_root)
    blockers: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, object]] = []

    for key, reason in DANGEROUS_FLAGS.items():
        enabled = truthy(source.get(key))
        checks.append({"name": key, "ok": not enabled, "reason": reason})
        if enabled:
            blockers.append(f"{key} must be disabled for public production release ({reason}).")

    for label, host_key, token_key, unauth_key in (
        ("hub", "SHELL_HUB_HOST", "SHELL_HUB_TOKEN", "SHELL_HUB_ALLOW_UNAUTH_REMOTE"),
        ("mcp", "SHELL_MCP_HOST", "SHELL_MCP_TOKEN", "SHELL_MCP_ALLOW_UNAUTH_REMOTE"),
    ):
        host = str(source.get(host_key) or "127.0.0.1").strip()
        token_set = bool(str(source.get(token_key) or "").strip())
        remote = host not in LOCAL_HOSTS
        checks.append({"name": f"{label}:remote_bind_requires_token", "ok": (not remote) or token_set})
        if remote and not token_set and not truthy(source.get(unauth_key)):
            blockers.append(f"{host_key} is remote-facing, so {token_key} must be set.")

    telegram_enabled = truthy(source.get("AUTO_START_TELEGRAM_BOT")) or truthy(source.get("SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED"))
    telegram_token_set = bool(str(source.get("TELEGRAM_BOT_TOKEN") or "").strip())
    allowed_chats_set = bool(str(source.get("SHELL_TELEGRAM_ALLOWED_CHAT_IDS") or "").strip())
    checks.append({"name": "telegram:token_when_enabled", "ok": (not telegram_enabled) or telegram_token_set})
    if telegram_enabled and not telegram_token_set:
        blockers.append("Telegram automation is enabled but TELEGRAM_BOT_TOKEN is not set.")
    if truthy(source.get("SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED")) and not allowed_chats_set:
        blockers.append("Telegram PC control requires SHELL_TELEGRAM_ALLOWED_CHAT_IDS.")

    if env is None and (project_root / ".env").exists():
        warnings.append("Local .env exists. Do not include it in any public release package.")

    if check_assets:
        _check_assets(project_root, blockers, warnings, checks)

    mode = production_mode_enabled(source)
    status = "pass" if not blockers else "fail"
    return {
        "status": status,
        "production_mode": mode,
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
    }


def enforce_production_guard(*, root: str | Path | None = None) -> None:
    report = audit_production_environment(root=root)
    if report["production_mode"] and report["blockers"]:
        preview = "; ".join(str(item) for item in report["blockers"][:5])
        raise RuntimeError(f"Production guard failed: {preview}")


def main() -> int:
    report = audit_production_environment()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
