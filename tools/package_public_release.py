from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from tools.production_release_check import build_report  # type: ignore  # noqa: E402
except ModuleNotFoundError:
    spec = importlib.util.spec_from_file_location("_shell_production_release_check", ROOT / "tools" / "production_release_check.py")
    if spec is None or spec.loader is None:
        raise
    _release_check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_release_check)
    build_report = _release_check.build_report


DIST_DIR = ROOT / "dist"
SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{40,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"\b\d{5,20}:[A-Za-z0-9_-]{20,}\b"),  # Telegram bot token shape
]

REQUIRED_PACKAGE_FILES = {
    ".env.example",
    "INSTALLATION.md",
    "ONE_CLICK_INSTALL.bat",
    "ONE_CLICK_INSTALL.command",
    "Repair_ShellAI.bat",
    "Run_Windows_Acceptance_Test.bat",
    "Start_ShellAI.bat",
    "installer/bootstrap.py",
    "installer/windows_audio_preflight.ps1",
    "launch.py",
    "requirements.txt",
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
}

FORBIDDEN_PACKAGE_PATH_PREFIXES = {
    "node_modules/",
    "shell_web_ui/dist/",
    "shell_web_ui/node_modules/",
}

FORBIDDEN_PACKAGE_FILES = {
    ".env",
    "AGENT_FIX.md",
    "SESSION_LOG.md",
    "dist/public_release_package.json",
}

EXCLUDED_DIRS = {
    ".git",
    ".gstack",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".phoenix_backups",
    ".pycache_tmp",
    ".shell_image_cache",
    ".shell_runtime",
    ".shell_chat_history",
    ".shellai_venv",
    ".codex_ui_venv",
    "__pycache__",
    "build",
    "dist",
    "env",
    "node_modules",
    "_backups_",
    "_ui_cyber",
    "Desktop",
    "shell_downloads",
    "shell_projects",
    "smoke",
    "ui_screenshots",
    "venv",
}

EXCLUDED_PATH_PREFIXES = {
    ("integrations", "external"),
    ("shell_ui", "build"),
    ("shell.v1.0-main-main",),
}

EXCLUDED_NAMES = {
    ".DS_Store",
    ".env",
    "AGENT_FIX.md",
    ".phoenix_analytics.json",
    ".shell_full_smoke_report.json",
    ".shell_hub_port",
    ".shell_settings.json",
    ".shell_safety_audit.log",
    ".shell_theme.json",
    ".telegram_log.json",
    ".telegram_rules.json",
    ".telegram_schedule.json",
    ".telegram_state.json",
    ".telegram_users.json",
    "agent_error.log",
    "agent_run.log",
    "control_log.txt",
    "glass_chat.png",
    "glass_settings.png",
    "glass_system.png",
    "glass_voice.png",
    "hub_error.log",
    "hub_run.log",
    "qr_test.png",
    "screenshot_chat.png",
    "screenshot_voice_test.png",
    "shell_brain.json",
    "shell_browser_history.json",
    "shell_image_history.json",
    "shell_ai.log",
    "shell_ai.log.prev2",
    "shell_telegram_stats.json",
    "shot_chat.png",
    "shot_settings.png",
    "shot_system.png",
    "shot_system_nav.png",
    "shot_voice.png",
    "smoke_test_output.tmp.png",
    "test_results.txt",
    "test_results_g3.txt",
    "_agent_test.err",
    "ui_run.log",
    "SESSION_LOG.md",
}

EXCLUDED_SUFFIXES = {
    ".bak",
    ".cache",
    ".log",
    ".mp3",
    ".mp4",
    ".pdf",
    ".pyc",
    ".pyo",
    ".tmp",
    ".wav",
}

PUBLIC_MEDIA_EXCEPTIONS = {
    ("videos", "shell-current-ui-landscape-demo.mp4"),
}

TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".command",
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".template",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def version() -> str:
    path = ROOT / "VERSION"
    if path.exists():
        return path.read_text(encoding="utf-8").strip() or "0.0.0"
    return "0.0.0"


def excluded(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    rel_parts = rel.parts
    if any(rel_parts[: len(prefix)] == prefix for prefix in EXCLUDED_PATH_PREFIXES):
        return True
    parts = set(rel.parts)
    if parts & EXCLUDED_DIRS:
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    if path.name.startswith(".env.") and path.name not in {".env.example", ".env.template"}:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES and rel_parts not in PUBLIC_MEDIA_EXCEPTIONS:
        return True
    return False


def looks_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {"VERSION", ".env.example", ".env.template"}


def assert_no_secrets(path: Path) -> None:
    if not looks_text(path):
        return
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise RuntimeError(f"Potential secret detected in release file: {path.relative_to(ROOT)}")


def iter_release_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if path.is_dir() or excluded(path):
            continue
        assert_no_secrets(path)
        files.append(path)
    return sorted(files, key=lambda p: str(p.relative_to(ROOT)))


def validate_release_file_set(files: list[Path]) -> None:
    rel_paths = {path.relative_to(ROOT).as_posix() for path in files}
    missing = sorted(REQUIRED_PACKAGE_FILES - rel_paths)
    if missing:
        raise RuntimeError("Release package missing required files: " + ", ".join(missing))

    forbidden = sorted(
        rel
        for rel in rel_paths
        if rel in FORBIDDEN_PACKAGE_FILES or any(rel.startswith(prefix) for prefix in FORBIDDEN_PACKAGE_PATH_PREFIXES)
    )
    if forbidden:
        preview = ", ".join(forbidden[:10])
        extra = "" if len(forbidden) <= 10 else f", and {len(forbidden) - 10} more"
        raise RuntimeError("Release package includes generated/runtime files: " + preview + extra)


def build_package(*, strict: bool = True) -> dict[str, object]:
    report = build_report(include_health=True, strict=strict)
    if report["status"] != "pass":
        raise RuntimeError("Public release check failed. Run tools/production_release_check.py for details.")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    name = f"shell-ai-os-controller-{version()}.zip"
    output = DIST_DIR / name
    files = iter_release_files()
    validate_release_file_set(files)
    package_file_count = len(files) + 1  # release_manifest.json is written into the zip.
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            zf.write(path, path.relative_to(ROOT).as_posix())
        manifest = {
            "name": "Shell AI OS Controller",
            "version": version(),
            "created_at": time.time(),
            "file_count": package_file_count,
            "source_file_count": len(files),
            "release_check": {
                "status": report["status"],
                "warnings": report["warnings"],
            },
            "required_package_files": sorted(REQUIRED_PACKAGE_FILES),
        }
        zf.writestr("release_manifest.json", json.dumps(manifest, indent=2, sort_keys=True))

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    package_report = {
        "status": "success",
        "path": str(output),
        "sha256": digest,
        "file_count": package_file_count,
        "size_bytes": output.stat().st_size,
    }
    (DIST_DIR / "public_release_package.json").write_text(json.dumps(package_report, indent=2, sort_keys=True), encoding="utf-8")
    return package_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a clean Shell AI public release zip.")
    parser.add_argument("--no-strict", action="store_true", help="Do not fail on unsafe local .env dev flags.")
    args = parser.parse_args(argv)
    try:
        report = build_package(strict=not args.no_strict)
    except Exception as exc:
        print(f"Package failed: {exc}")
        return 2
    print("Shell AI public release package created")
    print(f"Path: {report['path']}")
    print(f"SHA256: {report['sha256']}")
    print(f"Files: {report['file_count']}")
    print(f"Size: {report['size_bytes']} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
