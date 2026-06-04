from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.package_public_release import iter_release_files, validate_release_file_set, version  # noqa: E402
from tools.production_release_check import build_report  # noqa: E402


STAGING_ROOT = ROOT / ".shell_runtime" / "windows_installer_staging"
APP_STAGE = STAGING_ROOT / "ShellAI"
DIST_DIR = ROOT / "dist"
INNO_SCRIPT = ROOT / "tools" / "windows_installer" / "ShellAI_Setup.iss"
REPORT_PATH = DIST_DIR / "windows_installer_package.json"
WINDOWS_APP_ENTRY = ROOT / "tools" / "windows_app" / "shellai_desktop_entry.py"
WEB_UI_ROOT = ROOT / "shell_web_ui"
WEB_UI_DIST = WEB_UI_ROOT / "dist"
WEB_UI_DIST_INDEX = WEB_UI_DIST / "index.html"
APP_BUNDLE_DIR = APP_STAGE / "ShellAIApp"
APP_BUNDLE_EXE = APP_BUNDLE_DIR / "ShellAI.exe"
APP_EXE_RELATIVE = r"ShellAIApp\ShellAI.exe"


def _safe_clear_staging() -> None:
    staging = STAGING_ROOT.resolve()
    runtime = (ROOT / ".shell_runtime").resolve()
    if runtime not in staging.parents:
        raise RuntimeError(f"Refusing to clear unexpected staging path: {staging}")
    if STAGING_ROOT.exists():
        shutil.rmtree(STAGING_ROOT)
    APP_STAGE.mkdir(parents=True, exist_ok=True)


def stage_release_files() -> dict[str, object]:
    _safe_clear_staging()
    files = iter_release_files()
    validate_release_file_set(files)
    for source in files:
        relative = source.relative_to(ROOT)
        target = APP_STAGE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    marker = {
        "name": "Shell AI OS Controller",
        "version": version(),
        "created_at": time.time(),
        "source_file_count": len(files),
        "installer": "Inno Setup",
    }
    (APP_STAGE / "windows_installer_build.json").write_text(
        json.dumps(marker, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return marker


def _npm_command() -> str:
    return shutil.which("npm.cmd") or shutil.which("npm") or "npm"


def ensure_web_ui_build() -> None:
    if WEB_UI_DIST_INDEX.exists():
        return
    package_json = WEB_UI_ROOT / "package.json"
    if not package_json.exists():
        raise RuntimeError("shell_web_ui/package.json is missing; cannot build bundled renderer.")
    npm = _npm_command()
    install_cmd = [npm, "ci"] if (WEB_UI_ROOT / "package-lock.json").exists() else [npm, "install"]
    subprocess.run(install_cmd, cwd=str(WEB_UI_ROOT), check=True)
    subprocess.run([npm, "run", "build"], cwd=str(WEB_UI_ROOT), check=True)
    if not WEB_UI_DIST_INDEX.exists():
        raise RuntimeError("Shell Web UI build finished but shell_web_ui/dist/index.html is missing.")


def copy_web_ui_dist_to_stage() -> None:
    ensure_web_ui_build()
    target = APP_STAGE / "shell_web_ui" / "dist"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(WEB_UI_DIST, target)


def build_bundled_desktop_app() -> dict[str, object]:
    if platform.system().lower() != "windows":
        raise RuntimeError("Bundled ShellAI.exe compilation requires Windows with PyInstaller.")
    if not WINDOWS_APP_ENTRY.exists():
        raise RuntimeError(f"Windows desktop app entry is missing: {WINDOWS_APP_ENTRY}")

    pyinstaller_probe = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if pyinstaller_probe.returncode != 0:
        raise RuntimeError("PyInstaller is not installed. Run Repair_ShellAI.bat or install shell_ui/requirements_ui.txt.")

    dist_root = STAGING_ROOT / "pyinstaller_dist"
    work_root = STAGING_ROOT / "pyinstaller_build"
    spec_root = STAGING_ROOT / "pyinstaller_spec"
    for path in (dist_root, work_root, spec_root, APP_BUNDLE_DIR):
        if path.exists():
            shutil.rmtree(path)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "ShellAI",
        "--distpath",
        str(dist_root),
        "--workpath",
        str(work_root),
        "--specpath",
        str(spec_root),
        "--paths",
        str(ROOT),
        "--hidden-import",
        "PyQt6.QtWebChannel",
        "--hidden-import",
        "PyQt6.QtWebEngineCore",
        "--hidden-import",
        "PyQt6.QtWebEngineWidgets",
        "--hidden-import",
        "shell_web_ui.host",
        "--hidden-import",
        "shell_ui.splash_screen",
        "--collect-all",
        "PyQt6",
        str(WINDOWS_APP_ENTRY),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    built = dist_root / "ShellAI"
    built_exe = built / "ShellAI.exe"
    if not built_exe.exists():
        raise RuntimeError(f"PyInstaller finished but bundled app is missing: {built_exe}")
    shutil.move(str(built), str(APP_BUNDLE_DIR))
    return {
        "app_dir": str(APP_BUNDLE_DIR),
        "app_exe": str(APP_BUNDLE_EXE),
        "app_size_bytes": sum(path.stat().st_size for path in APP_BUNDLE_DIR.rglob("*") if path.is_file()),
    }


def find_inno_compiler() -> str | None:
    configured = os.environ.get("INNO_SETUP_COMPILER", "").strip()
    candidates = [configured] if configured else []
    candidates.extend(["ISCC.exe", "ISCC"])
    program_files = [
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
    ]
    for root in program_files:
        if root:
            candidates.append(str(Path(root) / "Inno Setup 6" / "ISCC.exe"))
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        found = shutil.which(candidate) if not Path(candidate).exists() else candidate
        if found:
            return str(found)
    return None


def run_release_check(*, strict: bool) -> None:
    report = build_report(include_health=True, strict=strict)
    if report.get("status") != "pass":
        blockers = "; ".join(str(item) for item in report.get("blockers") or [])
        raise RuntimeError(f"Production release check failed: {blockers}")


def compile_inno_setup(iscc: str) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    installer_path = DIST_DIR / f"shell-ai-os-controller-setup-{version()}.exe"
    cmd = [
        iscc,
        f"/DAppSource={APP_STAGE}",
        f"/DOutputDir={DIST_DIR}",
        f"/DAppVersion={version()}",
        f"/DAppExeName={APP_EXE_RELATIVE}",
        "/DBundledApp=1",
        str(INNO_SCRIPT),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    if not installer_path.exists():
        raise RuntimeError(f"Inno Setup finished but installer is missing: {installer_path}")
    return installer_path


def build_windows_installer(*, dry_run: bool, skip_release_check: bool, strict: bool, skip_app_build: bool = False) -> dict[str, object]:
    if not skip_release_check:
        run_release_check(strict=strict)
    marker = stage_release_files()
    if not dry_run:
        copy_web_ui_dist_to_stage()
    iscc = find_inno_compiler()
    app_report: dict[str, object] = {
        "status": "not-built",
        "expected_app_exe": str(APP_BUNDLE_EXE),
    }
    report: dict[str, object] = {
        "status": "staged",
        "version": version(),
        "staging_dir": str(APP_STAGE),
        "inno_compiler": iscc or "",
        "source_file_count": marker["source_file_count"],
        "bundled_app": app_report,
        "expected_output": str(DIST_DIR / f"shell-ai-os-controller-setup-{version()}.exe"),
    }
    if dry_run:
        report["status"] = "dry-run"
    else:
        if platform.system().lower() != "windows":
            raise RuntimeError("Windows .exe installer compilation requires Windows with Inno Setup.")
        if skip_app_build:
            report["bundled_app"] = {"status": "skipped", "expected_app_exe": str(APP_BUNDLE_EXE)}
        else:
            app_report = build_bundled_desktop_app()
            app_report["status"] = "success"
            report["bundled_app"] = app_report
        if not iscc:
            raise RuntimeError("Inno Setup compiler not found. Install Inno Setup 6 or set INNO_SETUP_COMPILER.")
        installer = compile_inno_setup(iscc)
        report.update(
            {
                "status": "success",
                "path": str(installer),
                "size_bytes": installer.stat().st_size,
            }
        )
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage and build the Shell AI Windows .exe installer.")
    parser.add_argument("--dry-run", action="store_true", help="Stage release files and validate installer inputs without compiling.")
    parser.add_argument("--skip-release-check", action="store_true", help="Skip production release check; intended for CI jobs that already ran it.")
    parser.add_argument("--no-strict", action="store_true", help="Do not treat local .env development flags as release blockers.")
    parser.add_argument("--skip-app-build", action="store_true", help="Compile installer from staged source without building bundled ShellAI.exe.")
    args = parser.parse_args(argv)
    try:
        report = build_windows_installer(
            dry_run=args.dry_run,
            skip_release_check=args.skip_release_check,
            strict=not args.no_strict,
            skip_app_build=args.skip_app_build,
        )
    except Exception as exc:
        print(f"Windows installer build failed: {exc}")
        return 2
    print(f"Shell AI Windows installer {report['status']}")
    print(f"Version: {report['version']}")
    print(f"Staging: {report['staging_dir']}")
    bundled = report.get("bundled_app") or {}
    if isinstance(bundled, dict):
        print(f"App EXE: {bundled.get('app_exe') or bundled.get('expected_app_exe')}")
    print(f"Output: {report.get('path') or report.get('expected_output')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
