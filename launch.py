from __future__ import annotations

import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WEB_UI_ROOT = ROOT / "shell_web_ui"
WEB_UI_DIST_INDEX = WEB_UI_ROOT / "dist" / "index.html"


def _npm_command() -> str:
    return shutil.which("npm.cmd") or shutil.which("npm") or "npm"


def _ensure_shell_defaults() -> None:
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
    os.environ.setdefault("SHELL_IMAGE_LOCAL_FALLBACK", "1")
    os.environ.setdefault("SHELL_OFFLINE_LLM_ASYNC_UI", "1")
    if sys.platform.startswith("win"):
        os.environ.setdefault("SHELL_WINDOWS_PERFORMANCE_MODE", "balanced")


def _load_shell_config() -> None:
    # Provider keys must be loaded before Electron starts the backend bridge.
    try:
        from shell_config import config as _shell_config  # noqa: F401
    except Exception as exc:
        print(f"Config load failed (non-fatal): {exc}", flush=True)


def _ensure_renderer_build() -> None:
    if WEB_UI_DIST_INDEX.exists():
        return
    npm = _npm_command()
    if not (WEB_UI_ROOT / "package.json").exists():
        raise RuntimeError("shell_web_ui/package.json missing; Electron UI cannot start.")
    install_cmd = [npm, "ci"] if (WEB_UI_ROOT / "package-lock.json").exists() else [npm, "install"]
    subprocess.run(install_cmd, cwd=str(WEB_UI_ROOT), check=True)
    subprocess.run([npm, "run", "build"], cwd=str(WEB_UI_ROOT), check=True)
    if not WEB_UI_DIST_INDEX.exists():
        raise RuntimeError("Electron renderer build did not create shell_web_ui/dist/index.html.")


def _launch_electron() -> int:
    npm = _npm_command()
    env = os.environ.copy()
    env.setdefault("SHELL_ELECTRON_HOST", "1")
    env.setdefault("SHELL_ELECTRON_BACKEND_ROOT", str(ROOT))
    print("Starting Shell AI Electron desktop...", flush=True)
    return subprocess.call([npm, "run", "electron:dev"], cwd=str(WEB_UI_ROOT), env=env)


def main() -> int:
    try:
        _ensure_shell_defaults()
        _load_shell_config()
        _ensure_renderer_build()
        return _launch_electron()
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"FATAL: {exc}", flush=True)
        print(traceback.format_exc(), flush=True)
        if sys.stdout.isatty():
            input("Press Enter to exit...")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
