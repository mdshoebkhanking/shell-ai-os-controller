from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / ".shell_runtime"
LOG_DIR = RUNTIME_DIR / "logs"
HEALTH_REPORT = RUNTIME_DIR / "install_health.json"
PORT_HINT = ROOT / ".shell_hub_port"
WEB_UI_ROOT = ROOT / "shell_web_ui"
WEB_UI_DIST_INDEX = WEB_UI_ROOT / "dist" / "index.html"
SUPPORTED_PYTHON_MIN = (3, 10)
STABLE_PYTHON_LINES = ("3.13", "3.12", "3.11", "3.10")
SUPPORTED_NODE_MIN_20 = (20, 19, 0)
SUPPORTED_NODE_MIN_22 = (22, 12, 0)

CORE_IMPORTS = {
    "aiohttp": "hub HTTP server",
    "socketio": "realtime UI events",
    "psutil": "system telemetry",
    "requests": "HTTP client",
}

UI_IMPORTS = {
    "OpenGL": "3D UI visualizer",
    "numpy": "UI numeric rendering helpers",
    "PIL": "UI image loading",
    "GPUtil": "GPU stats panel",
    "pynput": "quick launcher hotkey backend",
    "keyboard": "alternate quick launcher hotkey backend",
    "PyInstaller": "optional UI executable builder",
}

OPTIONAL_IMPORTS = {
    "websocket": "Socket.IO websocket transport",
    "playwright": "browser automation",
    "pytesseract": "OCR Python bridge",
    "sounddevice": "microphone capture",
    "speech_recognition": "microphone speech-to-text",
    "livekit": "realtime voice runtime",
    "openwakeword": "optional wake word detection",
    "pywinauto": "Windows UI Automation driver",
    "silero_vad": "optional voice activity detection",
    "sherpa_onnx": "optional offline streaming STT fallback",
    "sentence_transformers": "optional semantic embeddings for Project RAG",
    "rank_bm25": "optional BM25 lexical retrieval for Project RAG",
    "docker": "optional container backend for secure sandbox",
    "edge_tts": "optional neural TTS",
    "kokoro_onnx": "optional natural offline TTS runtime",
    "pyttsx3": "offline low-latency TTS fallback",
}

OPTIONAL_EXECUTABLES = {
    "ffmpeg": "audio/video processing",
    "tesseract": "OCR engine",
    "uvx": "Windows-MCP launcher",
    "node": "optional Node.js runtime for bundled web integrations",
    "npm": "optional Node.js package installer",
}

IMAGE_PROVIDER_KEYS = {
    "OpenAI Images": ("OPENAI_API_KEY",),
    "Stability AI": ("STABILITY_API_KEY",),
    "Replicate": ("REPLICATE_API_KEY",),
    "HuggingFace": ("HUGGINGFACE_API_KEY", "HF_API_KEY"),
}

OPTIONAL_REQUIREMENT_NAMES = {
    "deep-translator",
    "docker",
    "edge-tts",
    "gtts",
    "instagrapi",
    "kokoro-onnx",
    "pdf2image",
    "playwright",
    "pyaudio",
    "openwakeword",
    "pyinstaller",
    "pywinauto",
    "pygame-ce",
    "pygetwindow",
    "pypdf",
    "pyttsx3",
    "pywin32",
    "pyzbar",
    "rank-bm25",
    "rembg",
    "scikit-learn",
    "selenium",
    "sentence-transformers",
    "sherpa-onnx",
    "silero-vad",
    "ursina",
    "wmi",
    "yfinance",
    "youtube-transcript-api",
    "yt-dlp",
}

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class StepResult:
    name: str
    ok: bool
    status: str = "OK"
    message: str = ""
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "status": self.status,
            "message": self.message,
            "details": dict(self.details),
        }


def _print(line: str = "") -> None:
    print(line, flush=True)


def detect_os() -> str:
    value = platform.system().lower()
    if value == "darwin":
        return "mac"
    if value.startswith("win"):
        return "windows"
    if value == "linux":
        return "linux"
    return value or "unknown"


def venv_dir() -> Path:
    configured = os.environ.get("SHELLAI_VENV_DIR", "").strip()
    if configured:
        return (ROOT / configured).resolve() if not Path(configured).is_absolute() else Path(configured)
    managed = ROOT / ".shellai_venv"
    if python_in_venv(managed).exists():
        return managed
    return ROOT / ".shellai_venv"


def python_in_venv(path: Path) -> Path:
    if detect_os() == "windows":
        return path / "Scripts" / "python.exe"
    return path / "bin" / "python"


def pip_in_venv(path: Path) -> Path:
    if detect_os() == "windows":
        return path / "Scripts" / "pip.exe"
    return path / "bin" / "pip"


def venv_scripts_dir(path: Path) -> Path:
    if detect_os() == "windows":
        return path / "Scripts"
    return path / "bin"


def python_version_tuple(py: Path | str) -> tuple[int, int, int] | None:
    result = run_cmd(
        [py, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
        name="python version",
        timeout=20,
    )
    if not result.ok:
        return None
    raw = (result.message or "").strip().splitlines()[-1].strip()
    try:
        major, minor, patch = raw.split(".", 2)
        return int(major), int(minor), int(patch)
    except Exception:
        return None


def command_version_tuple(command: str, version_arg: str = "--version") -> tuple[int, int, int] | None:
    result = run_cmd([command, version_arg], name=f"{command} version", timeout=20)
    if not result.ok:
        return None
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", result.message or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def preferred_python_executable() -> str | None:
    refresh_windows_process_path()
    configured = os.environ.get("SHELLAI_PYTHON", "").strip()
    candidates = [configured] if configured else []
    # When a Windows launcher starts this file with `py -3.13`, the actual
    # interpreter path is sys.executable and may not be discoverable as
    # `python3.13` on PATH. Prefer it when it is already compatible.
    candidates.append(sys.executable)
    candidates.extend([f"python{line}" for line in STABLE_PYTHON_LINES])
    candidates.extend(["python3", "python"])

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        exe = shutil.which(candidate)
        if not exe:
            continue
        if python_supported(python_version_tuple(exe)):
            return exe
    return None


def python_supported(version: tuple[int, int, int] | None) -> bool:
    if version is None:
        return False
    return version[:2] >= SUPPORTED_PYTHON_MIN


def node_supported(version: tuple[int, int, int] | None) -> bool:
    if version is None:
        return False
    major, minor, patch = version
    if major == 20:
        return (minor, patch) >= SUPPORTED_NODE_MIN_20[1:]
    if major == 22:
        return (minor, patch) >= SUPPORTED_NODE_MIN_22[1:]
    return major > 22


def python_support_message(version: tuple[int, int, int] | None) -> str:
    supported = ".".join(str(part) for part in SUPPORTED_PYTHON_MIN)
    if version is None:
        return f"Could not detect Python version. Shell AI needs Python {supported}+."
    current = ".".join(str(part) for part in version)
    if python_supported(version):
        return f"Python {current} is supported."
    return f"Python {current} is too old. Shell AI needs Python {supported}+."


def node_support_message(version: tuple[int, int, int] | None) -> str:
    required = "20.19+ or 22.12+"
    if version is None:
        return f"Could not detect Node.js version. Shell Web UI builds need Node.js {required}."
    current = ".".join(str(part) for part in version)
    if node_supported(version):
        return f"Node.js {current} is supported for Shell Web UI builds."
    return f"Node.js {current} is too old. Shell Web UI builds need Node.js {required}."


def ensure_runtime_dirs() -> None:
    for path in (RUNTIME_DIR, LOG_DIR, ROOT / ".shell_chat_history"):
        path.mkdir(parents=True, exist_ok=True)


def _split_path(value: str) -> list[str]:
    return [part for part in value.split(os.pathsep) if part]


def _path_key(value: str) -> str:
    return value.casefold() if detect_os() == "windows" else value


def _prepend_path_entries(entries: Iterable[str | Path]) -> int:
    current = _split_path(os.environ.get("PATH", ""))
    seen = {_path_key(item) for item in current}
    added: list[str] = []
    for entry in entries:
        raw = str(entry).strip()
        if not raw:
            continue
        key = _path_key(raw)
        if key in seen:
            continue
        if Path(raw).exists():
            added.append(raw)
            seen.add(key)
    if added:
        os.environ["PATH"] = os.pathsep.join([*added, *current])
    return len(added)


def refresh_windows_process_path() -> StepResult:
    if detect_os() != "windows":
        return StepResult("windows PATH", True, "OK", "Not required on this OS")

    entries: list[str | Path] = []
    try:
        import winreg  # type: ignore

        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            with winreg.OpenKey(hive, r"Environment") as key:
                raw, _kind = winreg.QueryValueEx(key, "Path")
                entries.extend(_split_path(str(raw)))
    except Exception:
        pass

    program_files = os.environ.get("ProgramFiles", "")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    app_data = os.environ.get("APPDATA", "")
    user_profile = os.environ.get("USERPROFILE", "")
    entries.extend(
        [
            Path(program_files) / "nodejs" if program_files else "",
            Path(program_files_x86) / "nodejs" if program_files_x86 else "",
            Path(program_files) / "Tesseract-OCR" if program_files else "",
            Path(local_app_data) / "Microsoft" / "WinGet" / "Links" if local_app_data else "",
            Path(user_profile) / ".local" / "bin" if user_profile else "",
            Path(app_data) / "Python" / "Scripts" if app_data else "",
        ]
    )
    added = _prepend_path_entries(entries)
    return StepResult("windows PATH", True, "OK", f"Refreshed process PATH; added {added} tool location(s)")


def _is_bare_command(value: str) -> bool:
    return (
        bool(value)
        and "/" not in value
        and "\\" not in value
        and not any(part.isspace() for part in value)
    )


def _subprocess_command(argv: Iterable[str | Path]) -> list[str]:
    cmd = [str(part) for part in argv]
    if detect_os() == "windows" and cmd and _is_bare_command(cmd[0]):
        resolved = shutil.which(cmd[0])
        if resolved:
            cmd[0] = resolved
    return cmd


def run_cmd(
    argv: Iterable[str | Path],
    *,
    name: str,
    timeout: int = 600,
    env: dict[str, str] | None = None,
    cwd: Path = ROOT,
) -> StepResult:
    cmd = _subprocess_command(argv)
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        elapsed = round((time.perf_counter() - started) * 1000.0, 2)
        ok = proc.returncode == 0
        return StepResult(
            name,
            ok,
            "OK" if ok else "ERROR",
            (proc.stdout or "").strip()[-3000:],
            {"returncode": proc.returncode, "elapsed_ms": elapsed, "command": cmd},
        )
    except subprocess.TimeoutExpired as exc:
        return StepResult(name, False, "ERROR", f"Timed out after {timeout}s", {"command": cmd, "output": (exc.stdout or "")[-2000:]})
    except FileNotFoundError:
        return StepResult(name, False, "ERROR", f"Command not found: {cmd[0]}", {"command": cmd})
    except Exception as exc:
        return StepResult(name, False, "ERROR", str(exc), {"command": cmd})


def create_env_if_missing() -> StepResult:
    env_path = ROOT / ".env"
    if env_path.exists():
        return StepResult(".env", True, "OK", ".env already exists")
    for template in (ROOT / ".env.example", ROOT / ".env.template"):
        if template.exists():
            env_path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
            return StepResult(".env", True, "OK", f"Created .env from {template.name}")
    env_path.write_text(
        "\n".join([
            "GOOGLE_API_KEY=",
            "GEMINI_MODEL=gemini-2.5-flash",
            "SHELL_ALLOW_CODE_WRITE=0",
            "SHELL_ALLOW_TERMINAL_EXEC=0",
            "SHELL_TTS_ENGINE=fast",
            "SHELL_IMAGE_LOCAL_FALLBACK=1",
            "",
        ]),
        encoding="utf-8",
    )
    return StepResult(".env", True, "OK", "Created minimal .env")


def _env_file_values() -> dict[str, str]:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _is_configured_secret_value(value: str | None) -> bool:
    cleaned = str(value or "").strip().strip("\"'")
    if not cleaned:
        return False
    lowered = cleaned.lower()
    return not (
        lowered.startswith("your_")
        or lowered in {"changeme", "change_me", "none", "null", "placeholder"}
    )


def _configured_env_key(key: str, file_values: dict[str, str]) -> bool:
    return _is_configured_secret_value(os.environ.get(key)) or _is_configured_secret_value(file_values.get(key))


def _env_flag_enabled(key: str, default: bool, file_values: dict[str, str]) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        raw = file_values.get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def image_provider_readiness() -> StepResult:
    """Report image-generation provider readiness without exposing secret values."""
    file_values = _env_file_values()
    ready = [
        label
        for label, keys in IMAGE_PROVIDER_KEYS.items()
        if any(_configured_env_key(key, file_values) for key in keys)
    ]
    local_fallback = _env_flag_enabled("SHELL_IMAGE_LOCAL_FALLBACK", True, file_values)
    details = {"providers": ready, "local_fallback": local_fallback}
    if ready:
        suffix = "; local fallback enabled" if local_fallback else "; local fallback disabled"
        return StepResult("image providers", True, "OK", f"Cloud image providers configured: {', '.join(ready)}{suffix}", details)
    if local_fallback:
        return StepResult(
            "image providers",
            True,
            "WARN",
            "No cloud image provider key configured; Shell will use local preview fallback. "
            "Add OPENAI_API_KEY, STABILITY_API_KEY, REPLICATE_API_KEY, or HUGGINGFACE_API_KEY for real AI images.",
            details,
        )
    return StepResult(
        "image providers",
        True,
        "WARN",
        "No image provider key configured and SHELL_IMAGE_LOCAL_FALLBACK is disabled; image generation will fail until a provider key is added.",
        details,
    )


def safe_rebuild_venv(path: Path) -> StepResult:
    try:
        resolved = path.resolve()
        root = ROOT.resolve()
        allowed = {".shellai_venv", ".codex_ui_venv", "venv"}
        if resolved.parent != root or resolved.name not in allowed:
            return StepResult("venv rebuild", False, "ERROR", f"Refusing to rebuild unexpected venv path: {resolved}")
        if resolved.exists():
            shutil.rmtree(resolved)
        return StepResult("venv rebuild", True, "OK", f"Removed unsupported venv: {resolved.name}")
    except Exception as exc:
        return StepResult("venv rebuild", False, "ERROR", str(exc))


def ensure_venv(path: Path, *, rebuild_unsupported: bool = False) -> StepResult:
    py = python_in_venv(path)
    if py.exists():
        version = python_version_tuple(py)
        if python_supported(version):
            return StepResult("venv", True, "OK", f"Using {path.name}", {"python": str(py), "version": version})
        if rebuild_unsupported:
            rebuilt = safe_rebuild_venv(path)
            if not rebuilt.ok:
                return rebuilt
        else:
            return StepResult(
                "venv",
                False,
                "ERROR",
                f"{python_support_message(version)} Run Repair Shell AI to rebuild the virtual environment.",
                {"python": str(py), "version": version},
            )
    builder = preferred_python_executable()
    if builder is None:
        current = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
        return StepResult(
            "venv",
            False,
            "ERROR",
            f"{python_support_message(current)} Install Python 3.10+ or run one-click install with system package installation enabled.",
        )
    return run_cmd([builder, "-m", "venv", str(path)], name="create venv", timeout=300)


def install_python_deps(path: Path, *, repair: bool = False) -> list[StepResult]:
    py = python_in_venv(path)
    results = [
        run_cmd([py, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], name="upgrade pip", timeout=600),
    ]
    req = ROOT / "requirements.txt"
    if req.exists():
        results.extend(install_requirement_file(py, req, "install requirements", repair=repair, timeout=1800))
    ui_req = ROOT / "shell_ui" / "requirements_ui.txt"
    if ui_req.exists():
        results.extend(install_requirement_file(py, ui_req, "install UI requirements", repair=repair, timeout=1200))
    playwright = run_cmd([py, "-m", "playwright", "install", "chromium"], name="install playwright chromium", timeout=900)
    if not playwright.ok:
        playwright = StepResult(
            playwright.name,
            True,
            "WARN",
            "Playwright browser install skipped or failed; browser automation can be repaired later. "
            + (playwright.message or ""),
            playwright.details,
        )
    results.append(playwright)
    return results


def requirement_specs(path: Path) -> list[str]:
    specs: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if " #" in line:
            line = line.split(" #", 1)[0].strip()
        if line:
            specs.append(line)
    return specs


def requirement_name(spec: str) -> str:
    markerless = spec.split(";", 1)[0].strip()
    match = re.match(r"([A-Za-z0-9_.-]+)", markerless)
    return (match.group(1) if match else markerless).lower().replace("_", "-")


def is_optional_requirement(spec: str) -> bool:
    return requirement_name(spec) in OPTIONAL_REQUIREMENT_NAMES


def install_requirement_file(py: Path, req: Path, name: str, *, repair: bool, timeout: int) -> list[StepResult]:
    cmd = [py, "-m", "pip", "install", "-r", req]
    if repair:
        cmd.insert(4, "--upgrade")
    bulk = run_cmd(cmd, name=name, timeout=timeout)
    if bulk.ok:
        return [bulk]

    results: list[StepResult] = [
        StepResult(
            name,
            True,
            "WARN",
            "Bulk dependency install failed; retrying packages individually so optional packages do not block startup. "
            + (bulk.message or ""),
            bulk.details,
        )
    ]
    for spec in requirement_specs(req):
        pkg_name = requirement_name(spec)
        single_cmd = [py, "-m", "pip", "install", spec]
        if repair:
            single_cmd.insert(4, "--upgrade")
        result = run_cmd(single_cmd, name=f"install {pkg_name}", timeout=max(300, min(timeout, 900)))
        if result.ok:
            results.append(result)
            continue
        if is_optional_requirement(spec):
            results.append(
                StepResult(
                    result.name,
                    True,
                    "WARN",
                    f"Optional dependency skipped: {result.message}",
                    result.details,
                )
            )
        else:
            results.append(result)
    return results


def _npm_project_install(project: Path, label: str, *, build: bool = False) -> list[StepResult]:
    package_json = project / "package.json"
    if not package_json.exists():
        return [StepResult(label, True, "OK", f"No package.json found in {project.relative_to(ROOT)}")]
    refresh_windows_process_path()
    if shutil.which("npm") is None:
        if build and WEB_UI_DIST_INDEX.exists():
            return [StepResult(label, True, "WARN", "npm not found; using existing Shell Web UI build")]
        status = "ERROR" if build else "WARN"
        return [StepResult(label, not build, status, "npm not found; install Node.js LTS and run Repair Shell AI")]
    node_version = command_version_tuple("node")
    if not node_supported(node_version):
        message = node_support_message(node_version) + " Install or upgrade Node.js, then run Repair Shell AI."
        if build and WEB_UI_DIST_INDEX.exists():
            return [StepResult(label, True, "WARN", message, {"node_version": node_version})]
        status = "ERROR" if build else "WARN"
        return [StepResult(label, not build, status, message, {"node_version": node_version})]

    cmd = ["npm", "ci"] if (project / "package-lock.json").exists() else ["npm", "install"]
    results = [run_cmd(cmd, name=f"install {label}", timeout=1200, cwd=project)]
    if build and results[-1].ok:
        results.append(run_cmd(["npm", "run", "build"], name=f"build {label}", timeout=900, cwd=project))
    return results


def install_node_deps() -> list[StepResult]:
    results: list[StepResult] = []
    results.extend(_npm_project_install(ROOT, "root node helpers", build=False))
    if WEB_UI_ROOT.exists():
        results.extend(_npm_project_install(WEB_UI_ROOT, "Shell Web UI", build=True))
    else:
        results.append(StepResult("Shell Web UI", False, "ERROR", "shell_web_ui directory is missing"))
    return results


def web_ui_build_readiness() -> StepResult:
    if os.environ.get("SHELL_WEB_UI_URL", "").strip():
        return StepResult("Shell Web UI build", True, "OK", "Using SHELL_WEB_UI_URL dev renderer")
    if WEB_UI_DIST_INDEX.exists():
        return StepResult("Shell Web UI build", True, "OK", str(WEB_UI_DIST_INDEX.relative_to(ROOT)))
    return StepResult(
        "Shell Web UI build",
        False,
        "ERROR",
        "shell_web_ui/dist/index.html is missing. Run ONE_CLICK_INSTALL or Repair Shell AI to install npm dependencies and build the renderer.",
    )


def web_ui_toolchain_readiness() -> StepResult:
    if os.environ.get("SHELL_WEB_UI_URL", "").strip():
        return StepResult("Shell Web UI toolchain", True, "OK", "Using SHELL_WEB_UI_URL dev renderer")
    if not (WEB_UI_ROOT / "package.json").exists():
        return StepResult("Shell Web UI toolchain", False, "ERROR", "shell_web_ui/package.json is missing")
    refresh_windows_process_path()
    npm_found = shutil.which("npm") is not None
    node_version = command_version_tuple("node") if shutil.which("node") else None
    if npm_found and node_supported(node_version):
        return StepResult("Shell Web UI toolchain", True, "OK", node_support_message(node_version))
    issue = "npm not found" if not npm_found else node_support_message(node_version)
    if WEB_UI_DIST_INDEX.exists():
        return StepResult("Shell Web UI toolchain", True, "WARN", f"{issue}; existing Web UI build will be used")
    return StepResult(
        "Shell Web UI toolchain",
        False,
        "ERROR",
        f"{issue}. Install Node.js 20.19+ or 22.12+, then run Repair Shell AI.",
        {"node_version": node_version, "npm_found": npm_found},
    )


def windows_mcp_readiness(path: Path) -> StepResult:
    """Report whether Windows-MCP can run when desktop automation is used."""
    if detect_os() != "windows":
        return StepResult("Windows-MCP", True, "OK", "Windows-only integration not required on this OS")
    py = python_in_venv(path)
    version = python_version_tuple(py) if py.exists() else None
    uvx_found = shutil.which("uvx") is not None or (venv_scripts_dir(path) / "uvx.exe").exists()
    issues: list[str] = []
    if not python_supported(version):
        issues.append(python_support_message(version))
    if version is not None and version[:2] < (3, 13):
        issues.append("Windows-MCP requires Python 3.13+; run Repair Shell AI to rebuild with Python 3.13.")
    if not uvx_found:
        issues.append("uv/uvx is missing; run ONE_CLICK_INSTALL.bat or Repair_ShellAI.bat.")
    if issues:
        return StepResult(
            "Windows-MCP",
            True,
            "WARN",
            " ".join(issues),
            {"python": version, "uvx": uvx_found},
        )
    return StepResult("Windows-MCP", True, "OK", "Windows-MCP ready: Python 3.13+ and uvx available")


def windows_audio_preflight() -> StepResult:
    """Unmute/default-volume Windows audio before Shell starts speaking."""
    if detect_os() != "windows":
        return StepResult("windows audio", True, "OK", "Not required on this OS")
    script = ROOT / "installer" / "windows_audio_preflight.ps1"
    if not script.exists():
        return StepResult("windows audio", True, "WARN", "Windows audio preflight script missing")
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return StepResult(
            "windows audio",
            True,
            "WARN",
            "PowerShell not found; cannot auto-unmute Windows audio. Use Windows volume controls if Shell is silent.",
        )
    result = run_cmd(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script,
            "-MinimumVolume",
            os.environ.get("SHELL_WINDOWS_MIN_VOLUME", "65"),
        ],
        name="windows audio",
        timeout=30,
    )
    if result.ok:
        return result
    return StepResult(
        "windows audio",
        True,
        "WARN",
        "Could not auto-unmute Windows audio. Use Windows volume controls if Shell is silent. "
        + (result.message or ""),
        result.details,
    )


def _silent_wav_probe_path() -> Path:
    import wave

    ensure_runtime_dirs()
    path = RUNTIME_DIR / "audio_probe_silence.wav"
    if path.exists():
        return path
    sample_rate = 8000
    frames = b"\x00\x00" * int(sample_rate * 0.05)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return path


def mac_audio_preflight() -> StepResult:
    """Verify macOS has a working CoreAudio output path before voice playback."""
    if detect_os() != "mac":
        return StepResult("mac audio", True, "OK", "Not required on this OS")
    if not shutil.which("afplay"):
        return StepResult("mac audio", True, "WARN", "afplay not found; cannot verify macOS audio output.")
    result = run_cmd(["afplay", str(_silent_wav_probe_path())], name="mac audio", timeout=5)
    if result.ok:
        return StepResult("mac audio", True, "OK", "macOS audio playback ready")
    msg = "macOS audio playback failed. Shell voice cannot be heard until an output device is available. "
    raw = (result.message or "").strip()
    if raw:
        msg += raw + " "
    if (Path("/Library/Audio/Plug-Ins/HAL/BlackHole2ch.driver")).exists():
        msg += "BlackHole is installed; reboot the Mac so the virtual audio driver loads, then select it/output audio in Audio MIDI Setup."
    else:
        msg += "Open Audio MIDI Setup and select a valid output device."
    return StepResult("mac audio", True, "WARN", msg, result.details)


def system_dependency_commands(os_name: str) -> list[list[str]]:
    refresh_windows_process_path()
    if os_name == "mac" and shutil.which("brew"):
        missing = []
        if preferred_python_executable() is None:
            missing.append("python@3.13")
        missing.extend([pkg for pkg, exe in (("ffmpeg", "ffmpeg"), ("tesseract", "tesseract")) if shutil.which(exe) is None])
        if (WEB_UI_ROOT / "package.json").exists() and shutil.which("node") is None:
            missing.append("node")
        return [["brew", "install", *missing]] if missing else []
    if os_name == "linux":
        if shutil.which("apt-get"):
            return [["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "-y", "ffmpeg", "tesseract-ocr", "python3-venv", "nodejs", "npm"]]
        if shutil.which("dnf"):
            return [["sudo", "dnf", "install", "-y", "ffmpeg", "tesseract", "python3-virtualenv", "nodejs", "npm"]]
        if shutil.which("pacman"):
            return [["sudo", "pacman", "-S", "--needed", "ffmpeg", "tesseract", "python-virtualenv", "nodejs", "npm"]]
    if os_name == "windows" and shutil.which("winget"):
        commands: list[list[str]] = []
        winget_base = ["winget", "install", "-e", "--accept-source-agreements", "--accept-package-agreements"]
        if preferred_python_executable() is None:
            commands.append([*winget_base, "--id", "Python.Python.3.13"])
        if shutil.which("ffmpeg") is None:
            commands.append([*winget_base, "--id", "Gyan.FFmpeg"])
        if shutil.which("tesseract") is None:
            commands.append([*winget_base, "--id", "UB-Mannheim.TesseractOCR"])
        if shutil.which("uvx") is None:
            commands.append([*winget_base, "--id", "astral-sh.uv"])
        node_version = command_version_tuple("node") if shutil.which("node") else None
        if (WEB_UI_ROOT / "package.json").exists() and (
            shutil.which("node") is None or shutil.which("npm") is None or not node_supported(node_version)
        ):
            action = "upgrade" if shutil.which("node") else "install"
            commands.append(["winget", action, "-e", "--accept-source-agreements", "--accept-package-agreements", "--id", "OpenJS.NodeJS.LTS"])
        return commands
    return []


def install_system_deps(*, yes: bool = False) -> list[StepResult]:
    os_name = detect_os()
    commands = system_dependency_commands(os_name)
    if not commands:
        return [StepResult("system dependencies", True, "WARN", "No supported package manager found or nothing missing")]
    if not yes:
        return [StepResult("system dependencies", True, "WARN", "Skipped system packages; rerun install with --yes to auto-install ffmpeg/OCR")]
    results = [run_cmd(cmd, name=f"system dependency: {cmd[0]}", timeout=1200) for cmd in commands]
    results.append(refresh_windows_process_path())
    return results


def check_import(py: Path, module: str, purpose: str, required: bool) -> StepResult:
    result = run_cmd([py, "-c", f"import {module}; print('ok')"], name=f"import {module}", timeout=30)
    if result.ok:
        return StepResult(module, True, "OK", purpose)
    status = "ERROR" if required else "WARN"
    return StepResult(module, not required, status, human_dependency_message(module, purpose), {"raw": result.message})


def human_dependency_message(name: str, purpose: str) -> str:
    return f"{purpose} dependency is missing. Run Repair Shell AI to install `{name}` automatically."


def health_report(path: Path | None = None) -> dict[str, object]:
    ensure_runtime_dirs()
    refresh_windows_process_path()
    path = path or venv_dir()
    py = python_in_venv(path)
    results: list[StepResult] = []
    results.append(StepResult("os", True, "OK", detect_os(), {"platform": platform.platform()}))
    results.append(StepResult("venv", py.exists(), "OK" if py.exists() else "ERROR", str(py)))
    if py.exists():
        version = python_version_tuple(py)
        results.append(
            StepResult(
                "python",
                python_supported(version),
                "OK" if python_supported(version) else "ERROR",
                python_support_message(version),
                {"executable": str(py), "supported_min": ".".join(map(str, SUPPORTED_PYTHON_MIN))},
            )
        )
        for module, purpose in CORE_IMPORTS.items():
            results.append(check_import(py, module, purpose, True))
        for module, purpose in UI_IMPORTS.items():
            results.append(check_import(py, module, purpose, False))
        for module, purpose in OPTIONAL_IMPORTS.items():
            results.append(check_import(py, module, purpose, False))
    else:
        version = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
        results.append(
            StepResult(
                "python",
                python_supported(version),
                "OK" if python_supported(version) else "ERROR",
                python_support_message(version),
                {"executable": sys.executable, "supported_min": ".".join(map(str, SUPPORTED_PYTHON_MIN))},
            )
        )
    results.append(web_ui_toolchain_readiness())
    results.append(web_ui_build_readiness())
    results.append(image_provider_readiness())
    for exe, purpose in OPTIONAL_EXECUTABLES.items():
        found = shutil.which(exe) is not None
        if not found and py.exists():
            suffix = ".exe" if detect_os() == "windows" else ""
            found = (venv_scripts_dir(path) / f"{exe}{suffix}").exists()
        results.append(StepResult(exe, True, "OK" if found else "WARN", purpose if found else f"{purpose} executable not found; Repair can install it where supported"))
    results.append(windows_mcp_readiness(path))
    results.append(mac_audio_preflight())
    results.append(create_env_if_missing())
    try:
        from shell_production_guard import audit_production_environment

        guard = audit_production_environment(root=ROOT)
        guard_ok = not guard["blockers"] or not guard["production_mode"]
        guard_status = "OK" if not guard["blockers"] else ("ERROR" if guard["production_mode"] else "WARN")
        if guard["blockers"]:
            guard_message = f"{len(guard['blockers'])} production blocker(s); public release mode will refuse launch"
        else:
            guard_message = "Production guard passed"
        results.append(
            StepResult(
                "production guard",
                guard_ok,
                guard_status,
                guard_message,
                {
                    "production_mode": guard["production_mode"],
                    "blockers": guard["blockers"],
                    "warnings": guard["warnings"],
                },
            )
        )
    except Exception as exc:
        results.append(StepResult("production guard", False, "ERROR", f"Production guard failed to run: {exc}"))
    missing_core = [row.name for row in results if row.status == "ERROR"]
    warnings = [row.name for row in results if row.status == "WARN"]
    report = {
        "ok": not missing_core,
        "state": "READY" if not missing_core else "NEEDS_REPAIR",
        "generated_at": time.time(),
        "root": str(ROOT),
        "venv": str(path),
        "results": [row.to_dict() for row in results],
        "summary": {"errors": missing_core, "warnings": warnings},
    }
    HEALTH_REPORT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def print_health(report: dict[str, object]) -> None:
    _print(f"Shell AI health: {report['state']}")
    for row in report["results"]:
        marker = "OK" if row["status"] == "OK" else row["status"]
        _print(f"  [{marker}] {row['name']}: {row['message']}")


def install(*, repair: bool = False, yes: bool = False, skip_system: bool = False) -> int:
    ensure_runtime_dirs()
    refresh_windows_process_path()
    path = venv_dir()
    _print("Shell AI one-click setup")
    _print(f"Root: {ROOT}")
    _print(f"Venv: {path}")
    venv_result = ensure_venv(path, rebuild_unsupported=repair)
    results = [create_env_if_missing(), venv_result]
    system_deps_checked = False
    if not venv_result.ok and not skip_system:
        results.extend(install_system_deps(yes=yes))
        system_deps_checked = True
        venv_result = ensure_venv(path, rebuild_unsupported=repair)
        results.append(venv_result)
    if not skip_system and not system_deps_checked:
        results.extend(install_system_deps(yes=yes))
    if venv_result.ok and python_in_venv(path).exists():
        results.extend(install_python_deps(path, repair=repair))
        results.extend(install_node_deps())
    report = health_report(path)
    for result in results:
        _print(f"[{result.status}] {result.name}: {result.message.splitlines()[-1] if result.message else ''}")
    print_health(report)
    return 0 if report["ok"] else 2


def wait_for_hub(proc: subprocess.Popen, timeout_s: float = 20.0) -> tuple[bool, str]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            return False, "hub exited early"
        port = ""
        if PORT_HINT.exists():
            port = PORT_HINT.read_text(encoding="utf-8").strip()
        for candidate in [port, "5000", "5001", "5002", "5003"]:
            if not candidate:
                continue
            for path in ("/ready", "/health"):
                url = f"http://127.0.0.1:{candidate}{path}"
                try:
                    with urllib.request.urlopen(url, timeout=0.5) as resp:
                        if resp.status == 200:
                            return True, candidate
                except Exception:
                    pass
        time.sleep(0.2)
    return False, "hub did not become healthy"


def tail_file(path: Path, lines: int = 80) -> str:
    try:
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(content[-lines:])
    except Exception as exc:
        return f"Could not read {path}: {exc}"


def apply_runtime_performance_defaults(env: dict[str, str]) -> None:
    """Keep bundled local runtimes responsive on entry-level Windows PCs."""

    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env.setdefault(key, "1")
    if detect_os() == "windows":
        env.setdefault("SHELL_WINDOWS_PERFORMANCE_MODE", "balanced")
        env.setdefault("SHELL_OFFLINE_LLM_CONTEXT", "768")
        env.setdefault("SHELL_OFFLINE_LLM_BATCH", "32")
        env.setdefault("SHELL_OFFLINE_LLM_MAX_TOKENS", "96")


def launch(*, repair_if_needed: bool = False) -> int:
    ensure_runtime_dirs()
    refresh_windows_process_path()
    path = venv_dir()
    report = health_report(path)
    if not report["ok"]:
        print_health(report)
        if repair_if_needed:
            rc = install(repair=True, yes=False, skip_system=True)
            if rc != 0:
                return rc
        else:
            _print("\nShell AI needs repair before launch. Run Repair Shell AI.")
            return 2

    py = python_in_venv(path)
    env = os.environ.copy()
    env.setdefault("SHELL_TTS_ENGINE", "fast")
    env.setdefault("SHELL_V2_STREAM", "1")
    env.setdefault("SHELL_V2_TIMEOUT_S", "12")
    env.setdefault("SHELL_AI_PROVIDER_TIMEOUT_S", "18")
    apply_runtime_performance_defaults(env)
    scripts = str(venv_scripts_dir(path))
    env["PATH"] = scripts + os.pathsep + env.get("PATH", "")
    audio_result = windows_audio_preflight()
    _print(f"[{audio_result.status}] {audio_result.name}: {audio_result.message}")
    if PORT_HINT.exists():
        try:
            PORT_HINT.unlink()
        except Exception:
            pass

    hub_log = (LOG_DIR / "hub.log").open("a", encoding="utf-8")
    ui_log = (LOG_DIR / "ui.log").open("a", encoding="utf-8")
    _print(f"Logs: {LOG_DIR}")
    hub = subprocess.Popen([str(py), "shell_hub.py"], cwd=str(ROOT), env=env, stdout=hub_log, stderr=subprocess.STDOUT, text=True)
    ok, port_or_error = wait_for_hub(hub)
    if not ok:
        _print(f"Hub startup failed: {port_or_error}")
        tail = tail_file(LOG_DIR / "hub.log")
        if tail:
            _print("\n--- hub.log ---")
            _print(tail)
        hub.terminate()
        return 3
    env["SHELL_HUB_URL"] = f"http://127.0.0.1:{port_or_error}"
    env["SHELL_TOKEN_URL"] = f"http://127.0.0.1:{port_or_error}/token"
    _print(f"Shell Hub ready: {env['SHELL_HUB_URL']}")

    try:
        rc = subprocess.call([str(py), "launch.py"], cwd=str(ROOT), env=env, stdout=ui_log, stderr=subprocess.STDOUT)
        if rc != 0:
            _print(f"Shell UI exited with code {rc}")
            tail = tail_file(LOG_DIR / "ui.log")
            if tail:
                _print("\n--- ui.log ---")
                _print(tail)
        return rc
    finally:
        try:
            hub.terminate()
            hub.wait(timeout=5)
        except Exception:
            try:
                hub.kill()
            except Exception:
                pass
        hub_log.close()
        ui_log.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shell AI one-click installer, launcher, health, and repair tool.")
    sub = parser.add_subparsers(dest="command", required=True)
    install_p = sub.add_parser("install", help="Create venv, install dependencies, create config, and validate.")
    install_p.add_argument("--yes", action="store_true", help="Allow supported OS package-manager installs.")
    install_p.add_argument("--skip-system", action="store_true", help="Skip ffmpeg/OCR system package installs.")
    repair_p = sub.add_parser("repair", help="Repair venv/dependencies and re-run health checks.")
    repair_p.add_argument("--yes", action="store_true", help="Allow supported OS package-manager installs.")
    repair_p.add_argument("--skip-system", action="store_true", help="Skip ffmpeg/OCR system package installs.")
    sub.add_parser("health", help="Print install/runtime health.")
    launch_p = sub.add_parser("launch", help="Start hub and UI with the managed venv.")
    launch_p.add_argument("--repair-if-needed", action="store_true", help="Attempt Python dependency repair before launch.")
    args = parser.parse_args(argv)

    if args.command == "install":
        return install(repair=False, yes=args.yes, skip_system=args.skip_system)
    if args.command == "repair":
        return install(repair=True, yes=args.yes, skip_system=args.skip_system)
    if args.command == "health":
        print_health(health_report())
        return 0
    if args.command == "launch":
        return launch(repair_if_needed=args.repair_if_needed)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
