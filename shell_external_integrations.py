"""Optional external integrations cloned into ``integrations/external``.

These tools make third-party repos visible to Shell without importing their
runtime code during startup. Execution remains opt-in and permission-gated.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from shell_safe_executor import god_tier_tool as function_tool

try:  # Load .env so permission gates work from CLI, hub, and UI paths.
    from shell_config import config as _shell_config  # noqa: F401
except Exception:  # pragma: no cover - config failures should not hide tools
    _shell_config = None  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parent
EXTERNAL_ROOT = PROJECT_ROOT / "integrations" / "external"
AGENT_BROWSER_ROOT = EXTERNAL_ROOT / "agent-browser"
OPENCLAW_ROOT = EXTERNAL_ROOT / "awesome-openclaw-skills"

FALLBACK_AGENT_BROWSER_SKILLS = [
    {
        "name": "agent-browser",
        "description": "Browser automation CLI for AI agents.",
        "path": "optional:agent-browser",
    },
    {
        "name": "core",
        "description": "Core browser automation workflows, snapshots, screenshots, and interaction patterns.",
        "path": "optional:agent-browser/skill-data/core",
    },
]

FALLBACK_OPENCLAW_SKILLS = [
    {
        "name": "GitHub Automation",
        "slug": "github-automation",
        "category": "coding agents and ides",
        "description": "Community skill category for GitHub and repository workflows.",
        "url": "https://clawskills.sh/skills/github-automation",
    },
    {
        "name": "Agent Browser",
        "slug": "agent-browser",
        "category": "browser and automation",
        "description": "Community browser automation skill entry.",
        "url": "https://clawskills.sh/skills/agent-browser",
    },
]


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[:limit]


def _package_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _license_name(root: Path) -> str:
    text = _read_text(root / "LICENSE", limit=800)
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if "Apache License" in first:
        return "Apache-2.0"
    if "MIT License" in first:
        return "MIT"
    return first or "unknown"


def _skill_frontmatter(path: Path) -> dict[str, str]:
    text = _read_text(path, limit=120_000)
    meta: dict[str, str] = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            for line in text[3:end].splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip().strip('"')
    if not meta.get("name"):
        meta["name"] = path.parent.name
    if not meta.get("description"):
        heading = next((ln.strip("# ").strip() for ln in text.splitlines() if ln.startswith("#")), "")
        meta["description"] = heading
    return meta


def agent_browser_skills() -> list[dict[str, str]]:
    skills: list[dict[str, str]] = []
    for pattern in ("skills/*/SKILL.md", "skill-data/*/SKILL.md"):
        for path in sorted(AGENT_BROWSER_ROOT.glob(pattern)):
            meta = _skill_frontmatter(path)
            rel = path.relative_to(PROJECT_ROOT)
            skills.append({
                "name": meta.get("name", path.parent.name),
                "description": meta.get("description", ""),
                "path": str(rel),
            })
    deduped: dict[str, dict[str, str]] = {}
    for row in skills:
        deduped[row["name"]] = row
    if not deduped:
        for row in FALLBACK_AGENT_BROWSER_SKILLS:
            deduped[row["name"]] = dict(row)
    return sorted(deduped.values(), key=lambda row: row["name"])


def parse_openclaw_skills(query: str = "", category: str = "", limit: int = 20) -> list[dict[str, str]]:
    q = str(query or "").strip().lower()
    cat_filter = str(category or "").strip().lower().replace(" ", "-")
    rows: list[dict[str, str]] = []
    pattern = re.compile(r"^-\s+\[([^\]]+)\]\(([^)]+)\)\s+-\s+(.*)$")
    category_files = sorted((OPENCLAW_ROOT / "categories").glob("*.md"))
    for path in category_files:
        cat = path.stem
        if cat_filter and cat_filter not in cat:
            continue
        for line in _read_text(path).splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            name, url, desc = match.groups()
            blob = f"{name} {desc} {cat}".lower()
            if q and q not in blob:
                continue
            rows.append({
                "name": name.strip(),
                "slug": url.rstrip("/").rsplit("/", 1)[-1].replace(".md", ""),
                "category": cat.replace("-", " "),
                "description": desc.strip(),
                "url": url.strip(),
            })
            if len(rows) >= max(1, min(int(limit or 20), 100)):
                return rows
    if not rows and not category_files:
        capped = max(1, min(int(limit or 20), 100))
        for row in FALLBACK_OPENCLAW_SKILLS:
            blob = f"{row['name']} {row['description']} {row['category']}".lower()
            if q and q not in blob:
                continue
            if cat_filter and cat_filter not in row["category"].replace(" ", "-"):
                continue
            rows.append(dict(row))
            if len(rows) >= capped:
                break
    return rows


def _agent_browser_executable() -> list[str]:
    configured = os.environ.get("SHELL_AGENT_BROWSER_BIN", "").strip()
    if configured:
        return [configured]
    found = shutil.which("agent-browser")
    if found:
        return [found]
    node = shutil.which("node")
    local_bin = AGENT_BROWSER_ROOT / "bin" / "agent-browser.js"
    if node and local_bin.exists():
        return [node, str(local_bin)]
    return ["agent-browser"]


def _agent_browser_available() -> bool:
    if os.environ.get("SHELL_AGENT_BROWSER_BIN", "").strip():
        return True
    if shutil.which("agent-browser"):
        return True
    return bool(shutil.which("node") and (AGENT_BROWSER_ROOT / "bin" / "agent-browser.js").exists())


def _safe_agent_browser_args(command: str) -> list[str]:
    import shlex

    args = shlex.split(str(command or "").strip(), posix=os.name != "nt")
    if not args:
        raise ValueError("agent-browser command is empty")
    if args[0] == "agent-browser":
        args = args[1:]
    return args


def _agent_browser_env() -> dict[str, str]:
    env = dict(os.environ)
    if not env.get("AGENT_BROWSER_SOCKET_DIR"):
        socket_dir = (
            env.get("SHELL_AGENT_BROWSER_SOCKET_DIR")
            or str(Path("/tmp") / "shell-agent-browser")
        )
        env["AGENT_BROWSER_SOCKET_DIR"] = socket_dir
    try:
        Path(env["AGENT_BROWSER_SOCKET_DIR"]).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return env


def _safe_openclaw_slug(skill_slug: str) -> str:
    raw = str(skill_slug or "").strip().rstrip("/")
    if "/" in raw:
        raw = raw.rsplit("/", 1)[-1]
    raw = raw.replace(".md", "")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,160}", raw):
        raise ValueError("OpenClaw skill slug must contain only letters, numbers, dot, underscore, or dash.")
    return raw


@function_tool(category="browser")
async def external_integration_status_tool() -> dict[str, Any]:
    """Show status for cloned third-party integrations used by Shell."""
    pkg = _package_json(AGENT_BROWSER_ROOT / "package.json")
    return {
        "status": "success",
        "external_root": str(EXTERNAL_ROOT.relative_to(PROJECT_ROOT)),
        "agent_browser": {
            "present": AGENT_BROWSER_ROOT.exists(),
            "version": pkg.get("version", ""),
            "license": _license_name(AGENT_BROWSER_ROOT),
            "cli_available": _agent_browser_available(),
            "global_cli_available": shutil.which("agent-browser") is not None,
            "local_launcher_available": bool(
                shutil.which("node") and (AGENT_BROWSER_ROOT / "bin" / "agent-browser.js").exists()
            ),
            "local_source": str(AGENT_BROWSER_ROOT.relative_to(PROJECT_ROOT)),
            "skills": len(agent_browser_skills()) if AGENT_BROWSER_ROOT.exists() else 0,
            "execution_enabled": _truthy(os.environ.get("SHELL_ALLOW_AGENT_BROWSER_EXEC")),
            "socket_dir": os.environ.get("SHELL_AGENT_BROWSER_SOCKET_DIR") or "/tmp/shell-agent-browser",
        },
        "awesome_openclaw_skills": {
            "present": OPENCLAW_ROOT.exists(),
            "license": _license_name(OPENCLAW_ROOT),
            "local_source": str(OPENCLAW_ROOT.relative_to(PROJECT_ROOT)),
            "category_files": len(list((OPENCLAW_ROOT / "categories").glob("*.md"))) if OPENCLAW_ROOT.exists() else 0,
            "clawhub_available": shutil.which("clawhub") is not None,
            "install_enabled": _truthy(os.environ.get("SHELL_ALLOW_OPENCLAW_SKILL_INSTALL")),
        },
    }


@function_tool(category="browser")
async def agent_browser_skill_catalog_tool(limit: int = 20) -> dict[str, Any]:
    """List locally cloned agent-browser skills available to Shell."""
    skills = agent_browser_skills()
    capped = max(1, min(int(limit or 20), 100))
    return {
        "status": "success",
        "count": len(skills),
        "skills": skills[:capped],
        "usage": "Use `agent_browser_command_tool` with SHELL_ALLOW_AGENT_BROWSER_EXEC=1 for real browser automation.",
    }


@function_tool(category="browser")
async def agent_browser_command_tool(command: str, timeout_s: int = 30, dry_run: bool = False) -> dict[str, Any]:
    """Run or preview an agent-browser CLI command with explicit permission gating."""
    args = _safe_agent_browser_args(command)
    argv = _agent_browser_executable() + args
    enabled = _truthy(os.environ.get("SHELL_ALLOW_AGENT_BROWSER_EXEC"))
    if dry_run or not enabled:
        return {
            "status": "blocked" if not enabled else "dry_run",
            "state": "NEEDS_PERMISSION" if not enabled else "DRY_RUN",
            "command": argv,
            "message": "Set SHELL_ALLOW_AGENT_BROWSER_EXEC=1 to execute browser automation. Use dry_run=true to preview only.",
            "safe_examples": [
                "skills list",
                "skills get core",
                "open https://example.com",
                "snapshot -i",
                "screenshot page.png",
            ],
        }
    try:
        proc = subprocess.run(
            argv,
            cwd=str(PROJECT_ROOT),
            env=_agent_browser_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=max(1, min(int(timeout_s or 30), 120)),
            check=False,
        )
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "returncode": proc.returncode,
            "command": argv,
            "output": (proc.stdout or "")[-8000:],
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "state": "MISSING_DEPENDENCY",
            "command": argv,
            "message": "agent-browser CLI not found. Run the local agent-browser postinstall or install with npm.",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "error",
            "state": "TIMEOUT",
            "command": argv,
            "message": f"agent-browser timed out after {timeout_s}s",
            "output": str(exc.stdout or "")[-4000:],
        }


@function_tool(category="ai")
async def openclaw_skill_search_tool(query: str = "", category: str = "", limit: int = 20) -> dict[str, Any]:
    """Search the locally cloned Awesome OpenClaw skills index."""
    results = parse_openclaw_skills(query=query, category=category, limit=limit)
    return {
        "status": "success",
        "query": query,
        "category": category,
        "count": len(results),
        "results": results,
        "security_note": (
            "OpenClaw skills are curated but not audited. Review source and permissions before installing or running any skill."
        ),
    }


@function_tool(category="ai")
async def openclaw_skill_install_tool(skill_slug: str, timeout_s: int = 60, dry_run: bool = False) -> dict[str, Any]:
    """Install an OpenClaw skill through clawhub with explicit permission gating."""
    slug = _safe_openclaw_slug(skill_slug)
    clawhub = shutil.which("clawhub")
    command = [clawhub or "clawhub", "install", slug]
    enabled = _truthy(os.environ.get("SHELL_ALLOW_OPENCLAW_SKILL_INSTALL"))
    security_note = (
        "OpenClaw skills are community packages. Review the skill source, permissions, and secrets access before use."
    )
    if dry_run or not enabled:
        return {
            "status": "blocked" if not enabled else "dry_run",
            "state": "NEEDS_PERMISSION" if not enabled else "DRY_RUN",
            "command": command,
            "skill_slug": slug,
            "message": "Set SHELL_ALLOW_OPENCLAW_SKILL_INSTALL=1 to install OpenClaw skills. Use dry_run=true to preview only.",
            "security_note": security_note,
        }
    if not clawhub:
        return {
            "status": "error",
            "state": "MISSING_DEPENDENCY",
            "command": command,
            "skill_slug": slug,
            "message": "clawhub CLI is not installed or not on PATH, so Shell cannot install OpenClaw skills yet.",
            "security_note": security_note,
        }
    try:
        proc = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=max(1, min(int(timeout_s or 60), 300)),
            check=False,
        )
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "returncode": proc.returncode,
            "command": command,
            "skill_slug": slug,
            "output": (proc.stdout or "")[-8000:],
            "security_note": security_note,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "error",
            "state": "TIMEOUT",
            "command": command,
            "skill_slug": slug,
            "message": f"clawhub timed out after {timeout_s}s",
            "output": str(exc.stdout or "")[-4000:],
            "security_note": security_note,
        }
