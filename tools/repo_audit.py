from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / ".shell_runtime" / "repo_audit_report.json"

EXCLUDED_DIRS = {
    ".git",
    ".codex_ui_venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".gstack",
    ".phoenix_backups",
    ".pycache_tmp",
    ".reuse",
    ".shell_image_cache",
    ".shell_runtime",
    ".shell_chat_history",
    ".shellai_venv",
    "__pycache__",
    "_backups_",
    "_ui_cyber",
    "build",
    "Desktop",
    "dist",
    "env",
    "integrations/external",
    "node_modules",
    "shell.v1.0-main-main",
    "shell_downloads",
    "shell_projects",
    "shell_workspace",
    "smoke",
    "swarm",
    "ui_screenshots",
    "venv",
}

RUNTIME_ARTIFACTS = {
    ".env",
    ".shell_settings.json",
    ".telegram_log.json",
    ".telegram_state.json",
    ".telegram_users.json",
    "shell_ai.log",
    "agent_run.log",
    "hub_error.log",
    "ui_run.log",
    "test_results.txt",
    "test_results_g3.txt",
}

REQUIRED_PUBLIC_FILES = {
    "README.md",
    "LICENSE",
    "NOTICE",
    "LEGAL.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
}

SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{40,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"\b\d{5,20}:[A-Za-z0-9_-]{20,}\b"),
]


def _is_excluded(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return True
    rel_text = rel.as_posix()
    if bool(set(rel.parts) & EXCLUDED_DIRS):
        return True
    return any(rel_text == item or rel_text.startswith(item.rstrip("/") + "/") for item in EXCLUDED_DIRS if "/" in item)


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if path.is_file() and not _is_excluded(path):
            files.append(path)
    return files


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _issue(severity: str, category: str, message: str, path: str | None = None) -> dict[str, str]:
    item = {"severity": severity, "category": category, "message": message}
    if path:
        item["path"] = path
    return item


def _check_required_files() -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for rel in sorted(REQUIRED_PUBLIC_FILES):
        if not (ROOT / rel).exists():
            issues.append(_issue("high", "release", f"Required public repository file missing: {rel}", rel))
    return issues


def _check_runtime_artifacts(files: list[Path]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for path in files:
        if path.name in RUNTIME_ARTIFACTS:
            issues.append(
                _issue(
                    "info",
                    "cleanliness",
                    "Local runtime/generated artifact exists in working tree; ensure it is never staged or packaged.",
                    _rel(path),
                )
            )
    return issues


def _check_secret_patterns(files: list[Path]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for path in files:
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".zip", ".pyc", ".pdf", ".ico"}:
            continue
        if path.name in RUNTIME_ARTIFACTS or path.name.startswith(".env"):
            continue
        if path.name.startswith(".env"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                issues.append(_issue("high", "security", "Potential secret/token pattern found.", _rel(path)))
                break
    return issues


def _check_duplicate_dependency_lines() -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    req = ROOT / "requirements.txt"
    if not req.exists():
        return [_issue("high", "dependencies", "requirements.txt is missing.", "requirements.txt")]
    names: list[str] = []
    for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
        clean = line.split("#", 1)[0].strip()
        if not clean or clean.startswith("-"):
            continue
        clean = clean.split(";", 1)[0].strip()
        name = re.split(r"[<>=!~\[]", clean, maxsplit=1)[0].strip().lower().replace("_", "-")
        if name:
            names.append(name)
    for name, count in Counter(names).items():
        if count > 1:
            issues.append(_issue("medium", "dependencies", f"Duplicate requirement entry: {name}", "requirements.txt"))
    return issues


def _check_python_parse(files: list[Path]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for path in files:
        if path.suffix != ".py":
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError as exc:
            issues.append(_issue("high", "syntax", f"Python syntax error: {exc}", _rel(path)))
    return issues


def _check_duplicate_file_content(files: list[Path]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    by_hash: dict[str, list[str]] = defaultdict(list)
    for path in files:
        if path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".zip"}:
            continue
        try:
            data = path.read_bytes()
        except Exception:
            continue
        if len(data) < 256:
            continue
        digest = hashlib.sha256(data).hexdigest()
        by_hash[digest].append(_rel(path))
    for paths in by_hash.values():
        meaningful = [p for p in paths if not p.endswith(("LICENSE", "README.md"))]
        if len(meaningful) > 1:
            issues.append(_issue("low", "duplication", f"Duplicate file content: {', '.join(meaningful[:5])}"))
    return issues


def _score(issues: list[dict[str, str]]) -> dict[str, Any]:
    weights = {"high": 20, "medium": 5, "low": 1, "info": 0}
    penalty = sum(weights.get(item["severity"], 1) for item in issues)
    score = max(0, 100 - penalty)
    return {
        "score": score,
        "status": "pass" if not any(item["severity"] == "high" for item in issues) else "fail",
        "counts": dict(Counter(item["severity"] for item in issues)),
    }


def build_report() -> dict[str, Any]:
    files = _iter_files()
    issues: list[dict[str, str]] = []
    issues.extend(_check_required_files())
    issues.extend(_check_runtime_artifacts(files))
    issues.extend(_check_secret_patterns(files))
    issues.extend(_check_duplicate_dependency_lines())
    issues.extend(_check_python_parse(files))
    issues.extend(_check_duplicate_file_content(files))

    by_category = Counter(item["category"] for item in issues)
    return {
        "generated_at": time.time(),
        "root": str(ROOT),
        "file_count": len(files),
        "summary": _score(issues),
        "issues": issues,
        "categories": dict(by_category),
        "recommendations": [
            "Keep runtime files out of git and public packages.",
            "Run production_release_check.py --strict before publishing.",
            "Review optional dependency licenses before binary distribution.",
            "Replace placeholder screenshots with public-safe media before launch.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit repository cleanliness and release hygiene.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--fail-on-high", action="store_true", help="Exit non-zero if high-severity issues exist.")
    args = parser.parse_args(argv)

    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(f"Repository audit: {summary['score']}/100 ({summary['status'].upper()})")
        print(f"Files scanned: {report['file_count']}")
        print(f"Issues: {summary['counts']}")
        for item in report["issues"][:20]:
            path = f" [{item['path']}]" if "path" in item else ""
            print(f"- {item['severity'].upper()} {item['category']}: {item['message']}{path}")
        print(f"Report: {REPORT_PATH}")

    if args.fail_on_high and report["summary"]["status"] != "pass":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
