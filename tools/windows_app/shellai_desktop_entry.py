from __future__ import annotations

import atexit
import importlib
import json
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
KOKORO_MODEL_DIR = ROOT / "models" / "tts" / "kokoro"
OFFLINE_LLM_MODEL_DIR = ROOT / "models" / "llm"
LOCAL_STT_MODEL_DIR = ROOT / "models" / "stt" / "sherpa-onnx"
_DLL_DIR_HANDLES: list[object] = []
_DLL_DIRS_ADDED: list[str] = []


def _frozen_internal_dir() -> Path | None:
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        try:
            return Path(str(meipass)).resolve()
        except Exception:
            pass
    candidate = ROOT / "ShellAIApp" / "_internal"
    if candidate.exists():
        return candidate.resolve()
    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).resolve().parent / "_internal"
        if candidate.exists():
            return candidate.resolve()
    return None


def _prepend_path_once(path: Path) -> None:
    text = str(path)
    parts = [part for part in os.environ.get("PATH", "").split(os.pathsep) if part]
    normalized = {part.lower() if os.name == "nt" else part for part in parts}
    key = text.lower() if os.name == "nt" else text
    if key not in normalized:
        os.environ["PATH"] = text + (os.pathsep + os.environ["PATH"] if os.environ.get("PATH") else "")


def _add_windows_dll_dir(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        return
    text = str(path)
    if text in _DLL_DIRS_ADDED:
        return
    _prepend_path_once(path)
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if os.name == "nt" and callable(add_dll_directory):
        try:
            _DLL_DIR_HANDLES.append(add_dll_directory(text))
        except OSError:
            pass
    _DLL_DIRS_ADDED.append(text)


def _add_frozen_dll_dirs() -> None:
    internal = _frozen_internal_dir()
    if internal is None:
        return
    # PyInstaller's onedir layout stores native dependencies in package
    # subdirectories. Seed those locations before Kokoro imports onnxruntime.
    candidates = [
        internal,
        internal / "onnxruntime" / "capi",
        internal / "sherpa_onnx" / "lib",
        internal / "llama_cpp" / "lib",
        internal / "PyQt6" / "Qt6" / "bin",
        internal / "numpy.libs",
        internal / "espeakng_loader",
        internal / "_soundfile_data",
        internal / "_sounddevice_data" / "portaudio-binaries",
    ]
    # PATH insertion prepends, so reverse iteration preserves candidate priority.
    for candidate in reversed(candidates):
        _add_windows_dll_dir(candidate)


_add_frozen_dll_dirs()

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("SHELL_LEGACY_UI", "0")
os.environ.setdefault("SHELL_V2_STREAM", "1")
os.environ.setdefault("SHELL_IMAGE_LOCAL_FALLBACK", "1")
os.environ.setdefault("SHELL_DESKTOP_BUNDLED", "1")
os.environ.setdefault("SHELL_TTS_ENGINE", "fast")
os.environ.setdefault("SHELL_VOICE_MODE", "auto")
os.environ.setdefault("SHELL_V2_TIMEOUT_S", "12")
os.environ.setdefault("SHELL_AI_PROVIDER_TIMEOUT_S", "18")
os.environ.setdefault("SHELL_APP_ROOT", str(ROOT))
os.environ.setdefault("SHELL_INSTALL_ROOT", str(ROOT))
os.environ.setdefault("SHELL_RUNTIME_DIR", str(ROOT / ".shell_runtime"))
os.environ.setdefault("SHELL_OFFLINE_TTS", "1")
os.environ.setdefault("SHELL_NATURAL_TTS_ENGINE", "kokoro")
os.environ.setdefault("SHELL_OFFLINE_TTS_ENGINE", "kokoro")
os.environ.setdefault("SHELL_NATURAL_TTS_MODEL_DIR", str(KOKORO_MODEL_DIR))
os.environ.setdefault("SHELL_OFFLINE_TTS_MODEL_DIR", str(KOKORO_MODEL_DIR))
os.environ.setdefault("SHELL_OFFLINE_LLM_MODEL_DIR", str(OFFLINE_LLM_MODEL_DIR))
os.environ.setdefault("SHELL_LOCAL_STT_ENABLED", "1")
os.environ.setdefault("SHELL_LOCAL_STT_MODEL_DIR", str(LOCAL_STT_MODEL_DIR))


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


def _run_runtime_probe_mode() -> None:
    _attach_windowed_log("runtime_probe.log")
    payload: dict[str, object] = {
        "root": str(ROOT),
        "executable": sys.executable,
        "frozen": bool(getattr(sys, "frozen", False)),
        "meipass": str(getattr(sys, "_MEIPASS", "")),
        "dllDirs": list(_DLL_DIRS_ADDED),
        "env": {
            "SHELL_APP_ROOT": os.environ.get("SHELL_APP_ROOT", ""),
            "SHELL_INSTALL_ROOT": os.environ.get("SHELL_INSTALL_ROOT", ""),
            "SHELL_NATURAL_TTS_ENGINE": os.environ.get("SHELL_NATURAL_TTS_ENGINE", ""),
            "SHELL_NATURAL_TTS_MODEL_DIR": os.environ.get("SHELL_NATURAL_TTS_MODEL_DIR", ""),
            "SHELL_OFFLINE_LLM_MODEL_DIR": os.environ.get("SHELL_OFFLINE_LLM_MODEL_DIR", ""),
            "SHELL_LOCAL_STT_MODEL_DIR": os.environ.get("SHELL_LOCAL_STT_MODEL_DIR", ""),
            "SHELL_VOICE_MODE": os.environ.get("SHELL_VOICE_MODE", ""),
        },
        "paths": {
            "kokoroModelDirExists": KOKORO_MODEL_DIR.exists(),
            "kokoroModelFiles": sorted(path.name for path in KOKORO_MODEL_DIR.glob("*") if path.is_file())[:12]
            if KOKORO_MODEL_DIR.exists()
            else [],
            "offlineLlmDirExists": OFFLINE_LLM_MODEL_DIR.exists(),
            "localSttDirExists": LOCAL_STT_MODEL_DIR.exists(),
        },
    }
    import_checks: dict[str, dict[str, object]] = {}
    for module_name in (
        "onnxruntime",
        "onnxruntime.capi.onnxruntime_pybind11_state",
        "kokoro_onnx",
        "espeakng_loader",
    ):
        try:
            module = importlib.import_module(module_name)
            import_checks[module_name] = {
                "ok": True,
                "file": str(getattr(module, "__file__", "")),
            }
        except Exception as exc:
            import_checks[module_name] = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
    payload["import_checks"] = import_checks
    exit_code = 0
    try:
        import shell_offline_tts
        from shell_offline_tts import offline_tts_status

        payload["offline_tts_module"] = {
            "file": getattr(shell_offline_tts, "__file__", ""),
            "projectRoot": str(getattr(shell_offline_tts, "PROJECT_ROOT", "")),
        }
        tts_status = offline_tts_status()
        payload["offline_tts"] = tts_status
        if not tts_status.get("available"):
            exit_code = 2
    except Exception as exc:
        payload["offline_tts"] = {"available": False, "reason": str(exc)}
        exit_code = 2

    try:
        from shell_offline_llm import offline_llm_status

        llm_status = offline_llm_status()
        payload["offline_llm"] = llm_status
        if not llm_status.get("available") and not _offline_llm_catalog_ready(llm_status):
            exit_code = 2
    except Exception as exc:
        payload["offline_llm"] = {"available": False, "reason": str(exc)}
        exit_code = 2

    print("SHELL_RUNTIME_PROBE_JSON=" + json.dumps(payload, sort_keys=True, default=str), flush=True)
    raise SystemExit(exit_code)


def _offline_llm_catalog_ready(status: object) -> bool:
    if not isinstance(status, dict) or status.get("runtimeDownloads") is not True:
        return False
    catalog = status.get("catalog")
    options = catalog.get("options") if isinstance(catalog, dict) else []
    return isinstance(options, list) and len(options) >= 4


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
elif "--shell-ai-runtime-probe" in sys.argv[1:]:
    _run_runtime_probe_mode()
else:
    _run_app_mode()
