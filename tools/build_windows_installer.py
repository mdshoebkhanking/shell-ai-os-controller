from __future__ import annotations

import argparse
import importlib.metadata as importlib_metadata
import importlib.util
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

try:
    from tools.package_public_release import iter_release_files, validate_release_file_set, version  # type: ignore # noqa: E402
    from tools.production_release_check import build_report  # type: ignore # noqa: E402
except ModuleNotFoundError:
    def _load_tool_module(name: str):
        module_path = ROOT / "tools" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"_shell_{name}", module_path)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    _package_public_release = _load_tool_module("package_public_release")
    _production_release_check = _load_tool_module("production_release_check")
    iter_release_files = _package_public_release.iter_release_files
    validate_release_file_set = _package_public_release.validate_release_file_set
    version = _package_public_release.version
    build_report = _production_release_check.build_report


STAGING_ROOT = ROOT / ".shell_runtime" / "windows_installer_staging"
APP_STAGE = STAGING_ROOT / "ShellAI"
DIST_DIR = ROOT / "dist"
INNO_SCRIPT = ROOT / "tools" / "windows_installer" / "ShellAI_Setup.iss"
NSIS_SCRIPT = ROOT / "tools" / "windows_installer" / "ShellAI_Setup.nsi"
REPORT_PATH = DIST_DIR / "windows_installer_package.json"
WINDOWS_APP_ENTRY = ROOT / "tools" / "windows_app" / "shellai_desktop_entry.py"
WEB_UI_ROOT = ROOT / "shell_web_ui"
WEB_UI_DIST = WEB_UI_ROOT / "dist"
WEB_UI_DIST_INDEX = WEB_UI_DIST / "index.html"
APP_BUNDLE_DIR = APP_STAGE / "ShellAIApp"
APP_BUNDLE_EXE = APP_BUNDLE_DIR / "ShellAI.exe"
APP_EXE_RELATIVE = r"ShellAIApp\ShellAI.exe"
TTS_MODEL_STAGE = APP_STAGE / "models" / "tts"
LLM_MODEL_STAGE = APP_STAGE / "models" / "llm"
ICON_SOURCE = ROOT / "shell_web_ui" / "src" / "public" / "shell-logo.png"
ICON_BUILD_DIR = STAGING_ROOT / "build_assets"
ICON_ICO = ICON_BUILD_DIR / "shell-ai.ico"
APP_ICON_NAME = "shell-ai.ico"
APP_ICON_STAGE = APP_STAGE / APP_ICON_NAME
PYINSTALLER_HIDDEN_IMPORTS = [
    "aiohttp",
    "aiohttp.web",
    "aiohttp_cors",
    "engineio.async_drivers.aiohttp",
    "psutil",
    "requests",
    "shell_hub",
    "shell_offline_llm",
    "shell_tool_gateway",
    "shell_ui.splash_screen",
    "shell_web_ui.host",
    "socketio",
    "llama_cpp",
    "PyQt6.QtGui",
    "PyQt6.QtWebChannel",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
]
PYINSTALLER_COPY_METADATA = [
    "aiohttp",
    "aiohttp-cors",
    "google-genai",
    "livekit",
    "llama-cpp-python",
    "psutil",
    "PyQt6",
    "PyQt6-WebEngine",
    "python-dotenv",
    "python-engineio",
    "python-socketio",
    "requests",
]


def _available_pyinstaller_copy_metadata() -> list[str]:
    available: list[str] = []
    for package in PYINSTALLER_COPY_METADATA:
        try:
            importlib_metadata.distribution(package)
        except importlib_metadata.PackageNotFoundError:
            print(f"Skipping PyInstaller metadata for missing optional package: {package}")
            continue
        available.append(package)
    return available


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
        "installer": "NSIS",
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


def prepare_windows_icon(*, dry_run: bool) -> dict[str, object]:
    if not ICON_SOURCE.exists():
        raise RuntimeError(f"Shell app logo is missing: {ICON_SOURCE}")
    report = {
        "source": str(ICON_SOURCE),
        "icon": str(ICON_ICO),
        "status": "planned" if dry_run else "pending",
    }
    if dry_run:
        return report

    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise RuntimeError("Pillow is required to convert the Shell logo into a Windows .ico asset.") from exc

    ICON_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(ICON_SOURCE) as image:
        image.convert("RGBA").save(
            ICON_ICO,
            format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )
    if not ICON_ICO.exists():
        raise RuntimeError(f"Windows icon conversion failed: {ICON_ICO}")
    report.update({"status": "success", "size_bytes": ICON_ICO.stat().st_size})
    return report


def stage_installed_icon(app_icon: Path | None) -> str:
    if not app_icon or not app_icon.exists():
        return ""
    APP_ICON_STAGE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(app_icon, APP_ICON_STAGE)
    return str(APP_ICON_STAGE)


def _has_any_file(path: Path, patterns: tuple[str, ...]) -> bool:
    if not path.exists():
        return False
    for pattern in patterns:
        if next(path.rglob(pattern), None) is not None:
            return True
    return False


def offline_tts_stage_report() -> dict[str, object]:
    kokoro_ready = _has_any_file(TTS_MODEL_STAGE / "kokoro", ("*.onnx",)) and _has_any_file(
        TTS_MODEL_STAGE / "kokoro",
        ("voices*.bin", "voices*.json", "*.bin"),
    )
    piper_ready = _has_any_file(TTS_MODEL_STAGE / "piper", ("*.onnx",)) and _has_any_file(
        TTS_MODEL_STAGE / "piper",
        ("*.onnx.json", "*.json"),
    )
    model_files = [path for path in TTS_MODEL_STAGE.rglob("*") if path.is_file()] if TTS_MODEL_STAGE.exists() else []
    status = "ready" if kokoro_ready or piper_ready else "fallback"
    reason = (
        "Packaged offline TTS model assets detected."
        if status == "ready"
        else "No packaged natural offline TTS model assets detected; installer will rely on OS/browser speech fallback."
    )
    return {
        "status": status,
        "reason": reason,
        "model_dir": str(TTS_MODEL_STAGE),
        "model_file_count": len(model_files),
        "recommended_engine": "kokoro",
        "model_family": "Kokoro-82M",
        "language_support": ["english", "hinglish", "hindi"],
        "hinglish_strategy": "Shell routes mixed English/Hindi clauses before Kokoro synthesis.",
        "engines": {
            "kokoro": {
                "ready": kokoro_ready,
                "model_family": "Kokoro-82M",
                "expected_files": ["kokoro-v1.0.int8.onnx", "voices-v1.0.bin"],
                "language_support": ["english", "hinglish", "hindi"],
            },
            "piper": {"ready": piper_ready},
        },
    }


def offline_llm_stage_report() -> dict[str, object]:
    model_files = [path for path in LLM_MODEL_STAGE.rglob("*.gguf") if path.is_file()] if LLM_MODEL_STAGE.exists() else []
    total_bytes = sum(path.stat().st_size for path in model_files)
    qwen_ready = any(path.name.lower().startswith("qwen3-1.7b") for path in model_files)
    status = "ready" if qwen_ready else "fallback"
    reason = (
        "Packaged offline LLM model assets detected."
        if status == "ready"
        else "No packaged GGUF offline LLM model assets detected; Shell will use provider/local deterministic fallback."
    )
    return {
        "status": status,
        "reason": reason,
        "model_dir": str(LLM_MODEL_STAGE),
        "model_file_count": len(model_files),
        "total_size_bytes": total_bytes,
        "recommended_engine": "llama-cpp-python",
        "model_family": "Qwen3-1.7B-GGUF",
        "model_repo": "Qwen/Qwen3-1.7B-GGUF",
        "language_support": ["english", "hinglish", "hindi"],
        "runtime_downloads": False,
        "engines": {
            "llama_cpp_python": {
                "ready": qwen_ready,
                "expected_files": ["Qwen3-1.7B-Q8_0.gguf"],
                "model_family": "Qwen3-1.7B-GGUF",
            },
        },
    }


def build_bundled_desktop_app(app_icon: Path | None = None) -> dict[str, object]:
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
        "--collect-all",
        "PyQt6",
    ]
    for hidden_import in PYINSTALLER_HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", hidden_import])
    for package in _available_pyinstaller_copy_metadata():
        cmd.extend(["--copy-metadata", package])
    if app_icon and app_icon.exists():
        cmd.extend(["--icon", str(app_icon)])
    cmd.append(str(WINDOWS_APP_ENTRY))
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    built = dist_root / "ShellAI"
    built_exe = built / "ShellAI.exe"
    if not built_exe.exists():
        raise RuntimeError(f"PyInstaller finished but bundled app is missing: {built_exe}")
    shutil.move(str(built), str(APP_BUNDLE_DIR))
    return {
        "app_dir": str(APP_BUNDLE_DIR),
        "app_exe": str(APP_BUNDLE_EXE),
        "app_icon": str(app_icon) if app_icon else "",
        "installed_icon": str(APP_ICON_STAGE) if APP_ICON_STAGE.exists() else "",
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


def find_nsis_compiler() -> str | None:
    configured = os.environ.get("NSIS_COMPILER", "").strip()
    candidates = [configured] if configured else []
    candidates.extend(["makensis.exe", "makensis"])
    program_files = [
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
    ]
    for root in program_files:
        if root:
            candidates.append(str(Path(root) / "NSIS" / "makensis.exe"))
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


def compile_inno_setup(iscc: str, app_icon: Path | None = None) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    installer_path = DIST_DIR / f"shell-ai-os-controller-setup-{version()}.exe"
    cmd = [
        iscc,
        f"/DAppSource={APP_STAGE}",
        f"/DOutputDir={DIST_DIR}",
        f"/DAppVersion={version()}",
        f"/DAppExeName={APP_EXE_RELATIVE}",
        f"/DAppIconName={APP_ICON_NAME}",
        "/DBundledApp=1",
    ]
    if app_icon and app_icon.exists():
        cmd.append(f"/DInstallerIcon={app_icon}")
    cmd.append(str(INNO_SCRIPT))
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    if not installer_path.exists():
        raise RuntimeError(f"Inno Setup finished but installer is missing: {installer_path}")
    return installer_path


def compile_nsis_setup(makensis: str, app_icon: Path | None = None) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    installer_path = DIST_DIR / f"shell-ai-os-controller-setup-{version()}.exe"
    cmd = [
        makensis,
        f"/DAppSource={APP_STAGE}",
        f"/DOutputDir={DIST_DIR}",
        f"/DAppVersion={version()}",
        f"/DAppExeName={APP_EXE_RELATIVE}",
        f"/DAppIconName={APP_ICON_NAME}",
        f"/DLicenseFile={ROOT / 'LICENSE'}",
    ]
    if app_icon and app_icon.exists():
        cmd.append(f"/DInstallerIcon={app_icon}")
    cmd.append(str(NSIS_SCRIPT))
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    if not installer_path.exists():
        raise RuntimeError(f"NSIS finished but installer is missing: {installer_path}")
    return installer_path


def build_windows_installer(
    *,
    dry_run: bool,
    skip_release_check: bool,
    strict: bool,
    skip_app_build: bool = False,
    installer_engine: str = "nsis",
) -> dict[str, object]:
    if not skip_release_check:
        run_release_check(strict=strict)
    if installer_engine not in {"nsis", "inno"}:
        raise RuntimeError(f"Unsupported installer engine: {installer_engine}")
    marker = stage_release_files()
    offline_tts_report = offline_tts_stage_report()
    offline_llm_report = offline_llm_stage_report()
    if not dry_run:
        copy_web_ui_dist_to_stage()
    icon_report = prepare_windows_icon(dry_run=dry_run)
    app_icon = ICON_ICO if not dry_run else None
    installed_icon = stage_installed_icon(app_icon)
    if installed_icon:
        icon_report["installed_icon"] = installed_icon
    iscc = find_inno_compiler()
    makensis = find_nsis_compiler()
    compiler = makensis if installer_engine == "nsis" else iscc
    app_report: dict[str, object] = {
        "status": "not-built",
        "expected_app_exe": str(APP_BUNDLE_EXE),
    }
    report: dict[str, object] = {
        "status": "staged",
        "version": version(),
        "staging_dir": str(APP_STAGE),
        "installer_engine": installer_engine,
        "installer_script": str(NSIS_SCRIPT if installer_engine == "nsis" else INNO_SCRIPT),
        "installer_compiler": compiler or "",
        "icon": icon_report,
        "nsis_compiler": makensis or "",
        "inno_compiler": iscc or "",
        "source_file_count": marker["source_file_count"],
        "bundled_app": app_report,
        "offline_tts": offline_tts_report,
        "offline_llm": offline_llm_report,
        "expected_output": str(DIST_DIR / f"shell-ai-os-controller-setup-{version()}.exe"),
    }
    if dry_run:
        report["status"] = "dry-run"
    else:
        if platform.system().lower() != "windows":
            engine_name = "NSIS" if installer_engine == "nsis" else "Inno Setup"
            raise RuntimeError(f"Windows .exe installer compilation requires Windows with {engine_name}.")
        if skip_app_build:
            report["bundled_app"] = {"status": "skipped", "expected_app_exe": str(APP_BUNDLE_EXE)}
        else:
            app_report = build_bundled_desktop_app(app_icon)
            app_report["status"] = "success"
            report["bundled_app"] = app_report
        if installer_engine == "nsis":
            if not makensis:
                raise RuntimeError("NSIS compiler not found. Install NSIS or set NSIS_COMPILER.")
            installer = compile_nsis_setup(makensis, app_icon)
        else:
            if not iscc:
                raise RuntimeError("Inno Setup compiler not found. Install Inno Setup 6 or set INNO_SETUP_COMPILER.")
            installer = compile_inno_setup(iscc, app_icon)
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
    parser.add_argument(
        "--installer-engine",
        choices=("nsis", "inno"),
        default="nsis",
        help="Windows setup compiler to use. NSIS matches the IRIS/electron-builder setup style.",
    )
    args = parser.parse_args(argv)
    try:
        report = build_windows_installer(
            dry_run=args.dry_run,
            skip_release_check=args.skip_release_check,
            strict=not args.no_strict,
            skip_app_build=args.skip_app_build,
            installer_engine=args.installer_engine,
        )
    except Exception as exc:
        print(f"Windows installer build failed: {exc}")
        return 2
    print(f"Shell AI Windows installer {report['status']}")
    print(f"Version: {report['version']}")
    print(f"Installer engine: {report.get('installer_engine')}")
    print(f"Staging: {report['staging_dir']}")
    bundled = report.get("bundled_app") or {}
    if isinstance(bundled, dict):
        print(f"App EXE: {bundled.get('app_exe') or bundled.get('expected_app_exe')}")
    print(f"Output: {report.get('path') or report.get('expected_output')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
