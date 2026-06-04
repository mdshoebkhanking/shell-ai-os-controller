from __future__ import annotations

import atexit
import os
import runpy
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import TextIO


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name.lower() == "shellaiapp":
            return exe_dir.parent
        return exe_dir
    return Path(__file__).resolve().parents[2]


ROOT = _app_root()
os.chdir(ROOT)
for candidate in (ROOT, ROOT / "shell_ui", ROOT / "shell_web_ui"):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

LOG_DIR = ROOT / ".shell_runtime" / "logs"
PORT_HINT = ROOT / ".shell_hub_port"

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("SHELL_LEGACY_UI", "0")
os.environ.setdefault("SHELL_V2_STREAM", "1")
os.environ.setdefault("SHELL_IMAGE_LOCAL_FALLBACK", "1")
os.environ.setdefault("SHELL_DESKTOP_BUNDLED", "1")
os.environ.setdefault("SHELL_TTS_ENGINE", "fast")
os.environ.setdefault("SHELL_V2_TIMEOUT_S", "12")
os.environ.setdefault("SHELL_AI_PROVIDER_TIMEOUT_S", "18")


_LOG_STREAMS: list[TextIO] = []


def _attach_windowed_log(name: str) -> None:
    """Windowed PyInstaller apps have no terminal; route prints to a log file."""

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stream = (LOG_DIR / name).open("a", encoding="utf-8", buffering=1)
    _LOG_STREAMS.append(stream)
    sys.stdout = stream
    sys.stderr = stream


def _close_logs() -> None:
    for stream in _LOG_STREAMS:
        try:
            stream.close()
        except Exception:
            pass


atexit.register(_close_logs)


def _creationflags() -> int:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return int(subprocess.CREATE_NO_WINDOW)
    return 0


def _wait_for_hub(proc: subprocess.Popen[object], timeout_s: float = 25.0) -> tuple[bool, str]:
    deadline = time.time() + timeout_s
    candidates = ["5000", "5001", "5002", "5003"]
    while time.time() < deadline:
        if proc.poll() is not None:
            return False, "hub exited early"
        if PORT_HINT.exists():
            try:
                hinted = PORT_HINT.read_text(encoding="utf-8").strip()
                if hinted and hinted not in candidates:
                    candidates.insert(0, hinted)
            except Exception:
                pass
        for candidate in candidates:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{candidate}/ready", timeout=0.5) as resp:
                    if resp.status == 200:
                        return True, candidate
            except Exception:
                pass
        time.sleep(0.2)
    return False, "hub did not become healthy"


def _start_bundled_hub() -> tuple[subprocess.Popen[object], str]:
    if PORT_HINT.exists():
        try:
            PORT_HINT.unlink()
        except Exception:
            pass
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    hub_log = (LOG_DIR / "hub.log").open("a", encoding="utf-8", buffering=1)
    _LOG_STREAMS.append(hub_log)
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, "--shell-ai-hub"],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=hub_log,
        stderr=subprocess.STDOUT,
        close_fds=False if os.name == "nt" else True,
        creationflags=_creationflags(),
    )
    ok, port_or_error = _wait_for_hub(proc)
    if not ok:
        try:
            proc.terminate()
        except Exception:
            pass
        raise RuntimeError(f"Bundled Shell Hub startup failed: {port_or_error}")
    return proc, port_or_error


def _run_script(script_name: str) -> None:
    script_path = ROOT / script_name
    if not script_path.exists():
        raise RuntimeError(f"Bundled Shell AI script is missing: {script_path}")
    runpy.run_path(str(script_path), run_name="__main__")


def _run_hub_mode() -> None:
    _attach_windowed_log("hub.log")
    _run_script("shell_hub.py")


def _run_app_mode() -> None:
    _attach_windowed_log("app.log")
    hub, port = _start_bundled_hub()
    os.environ["SHELL_HUB_URL"] = f"http://127.0.0.1:{port}"
    os.environ["SHELL_TOKEN_URL"] = f"http://127.0.0.1:{port}/token"
    try:
        _run_script("launch.py")
    finally:
        try:
            hub.terminate()
            hub.wait(timeout=5)
        except Exception:
            try:
                hub.kill()
            except Exception:
                pass


if "--shell-ai-hub" in sys.argv[1:]:
    _run_hub_mode()
else:
    _run_app_mode()
