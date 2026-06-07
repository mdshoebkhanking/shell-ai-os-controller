from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_PATH = ROOT / ".shell_runtime" / "windows_acceptance_report.json"
SCREENS_DIR = ROOT / ".shell_runtime" / "windows_acceptance_screens"
APP_EXE = ROOT / "ShellAIApp" / "ShellAI.exe"
APP_ICON = ROOT / "shell-ai.ico"
RAM_WARN_MB = 1400
RAM_FAIL_MB = 2200


def configure_probe_root(root: Path) -> None:
    global ROOT, REPORT_PATH, SCREENS_DIR, APP_EXE, APP_ICON

    ROOT = root.resolve()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    REPORT_PATH = ROOT / ".shell_runtime" / "windows_acceptance_report.json"
    SCREENS_DIR = ROOT / ".shell_runtime" / "windows_acceptance_screens"
    APP_EXE = ROOT / "ShellAIApp" / "ShellAI.exe"
    APP_ICON = ROOT / "shell-ai.ico"


def env_flag(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Check:
    name: str
    ok: bool
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "status": self.status,
            "message": self.message,
            "details": dict(self.details),
        }


def run_cmd(
    argv: list[str | Path],
    *,
    name: str,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> Check:
    started = time.perf_counter()
    cmd = [str(part) for part in argv]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
        output = (proc.stdout or "").strip()
        ok = proc.returncode == 0
        return Check(
            name=name,
            ok=ok,
            status="PASS" if ok else "FAIL",
            message=output[-3000:] if output else f"exit={proc.returncode}",
            details={"returncode": proc.returncode, "elapsed_ms": elapsed_ms, "command": cmd},
        )
    except subprocess.TimeoutExpired as exc:
        return Check(
            name=name,
            ok=False,
            status="FAIL",
            message=f"Timed out after {timeout}s",
            details={"command": cmd, "output": (exc.stdout or "")[-2000:]},
        )
    except Exception as exc:
        return Check(name=name, ok=False, status="FAIL", message=str(exc), details={"command": cmd})


def managed_python() -> Path:
    from installer.bootstrap import python_in_venv, venv_dir

    py = python_in_venv(venv_dir())
    return py if py.exists() else Path(sys.executable)


def find_executable(exe: str, py: Path | None = None) -> str | None:
    found = shutil.which(exe)
    if found:
        return found

    if platform.system().lower().startswith("win") and py:
        scripts_dir = Path(py).parent
        base = Path(exe).name
        suffixes = ("",) if Path(base).suffix else ("", ".exe", ".cmd", ".bat")
        for suffix in suffixes:
            candidate = scripts_dir / f"{base}{suffix}"
            if candidate.exists():
                return str(candidate)
    return None


def check_health(py: Path) -> Check:
    return run_cmd([py, "installer/bootstrap.py", "health"], name="install health", timeout=180)


def check_hub(py: Path) -> Check:
    env = os.environ.copy()
    env.setdefault("SHELL_V2_TIMEOUT_S", "3")
    env.setdefault("SHELL_AI_PROVIDER_TIMEOUT_S", "8")
    log_dir = ROOT / ".shell_runtime" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "windows_acceptance_hub.log"
    started = time.perf_counter()
    with log_path.open("a", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [str(py), "shell_hub.py"],
            cwd=str(ROOT),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline = time.time() + 25
            while time.time() < deadline:
                if proc.poll() is not None:
                    break
                port_hint = ROOT / ".shell_hub_port"
                ports = ["5000", "5001", "5002", "5003"]
                if port_hint.exists():
                    ports.insert(0, port_hint.read_text(encoding="utf-8", errors="replace").strip())
                for port in ports:
                    if not port:
                        continue
                    for path in ("/ready", "/health"):
                        try:
                            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=0.7) as response:
                                if response.status == 200:
                                    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
                                    return Check(
                                        "hub startup",
                                        True,
                                        "PASS",
                                        f"Shell Hub ready on port {port}",
                                        {
                                            "elapsed_ms": elapsed_ms,
                                            "port": port,
                                            "path": path,
                                            "log": str(log_path),
                                        },
                                    )
                        except Exception:
                            pass
                time.sleep(0.25)
            tail = ""
            if log_path.exists():
                tail = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:])
            return Check("hub startup", False, "FAIL", tail or "Hub did not become healthy", {"log": str(log_path)})
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


def check_ui_probe(py: Path, *, visible: bool) -> Check:
    report_path = ROOT / ".shell_runtime" / "windows_ui_probe_report.json"
    cmd: list[str | Path] = [
        py,
        "tools/e2e_ui_probe.py",
        "--json-out",
        report_path,
        "--screens-dir",
        SCREENS_DIR,
        "--skip-mcp-smoke",
    ]
    if visible:
        cmd.append("--visible")
    result = run_cmd(cmd, name="real UI probe", timeout=90)
    details = dict(result.details)
    details["report"] = str(report_path)
    if report_path.exists():
        try:
            probe_report = json.loads(report_path.read_text(encoding="utf-8", errors="replace"))
            details["probe_ok"] = bool(probe_report.get("ok"))
            details["probe_errors"] = list(probe_report.get("errors") or [])
            if result.ok:
                return Check(
                    "real UI probe",
                    True,
                    "PASS",
                    f"UI smoke passed; report={report_path}",
                    details,
                )
            errors = "; ".join(str(item) for item in (probe_report.get("errors") or []) if str(item).strip())
            message = errors or f"UI smoke failed; report={report_path}"
            return Check("real UI probe", False, "FAIL", message, details)
        except Exception as exc:
            details["report_parse_error"] = str(exc)
    return Check("real UI probe", result.ok, result.status, result.message, details)


def check_agent_probe(py: Path) -> Check:
    report_path = ROOT / ".shell_runtime" / "windows_agents_probe_report.json"
    return run_cmd(
        [py, "tools/agents_ui_probe.py", "--json-out", report_path, "--timeout-s", "35"],
        name="agent UI probe",
        timeout=240,
    )


def check_voice_runtime(py: Path) -> Check:
    code = (
        "import importlib.util, json; "
        "mods=['pyttsx3','edge_tts','kokoro_onnx','onnxruntime','soundfile','sounddevice','speech_recognition']; "
        "print(json.dumps({m: bool(importlib.util.find_spec(m)) for m in mods}, sort_keys=True))"
    )
    result = run_cmd([py, "-c", code], name="voice dependency probe", timeout=30)
    if result.ok and "pyttsx3" in result.message:
        return result
    return result


def check_offline_tts_status(py: Path) -> Check:
    code = (
        "import json; "
        "from shell_offline_tts import offline_tts_status; "
        "print(json.dumps(offline_tts_status(), sort_keys=True)); "
        "raise SystemExit(0)"
    )
    result = run_cmd([py, "-c", code], name="offline TTS status probe", timeout=30)
    if result.ok:
        try:
            payload = json.loads(result.message.splitlines()[-1])
            packaged = (ROOT / "models" / "tts" / "kokoro").exists()
            if packaged and not payload.get("available"):
                return Check(
                    "offline TTS status probe",
                    False,
                    "FAIL",
                    f"Packaged Kokoro assets exist but offline TTS is unavailable: {payload.get('reason')}",
                    {**result.details, "status": payload},
                )
        except Exception:
            pass
        return result
    return Check(
        "offline TTS status probe",
        False,
        "FAIL",
        result.message or "Offline TTS status unavailable; Shell must not use OS TTS fallback.",
        result.details,
    )


def _windows_icon_count(path: Path) -> int:
    if not path.exists() or platform.system().lower() != "windows":
        return 0
    try:
        import ctypes

        return int(ctypes.windll.shell32.ExtractIconExW(str(path), -1, None, None, 0))
    except Exception:
        return 0


def check_installed_bundled_app_layout() -> Check:
    installed_context = APP_EXE.exists() or (ROOT / "windows_installer_build.json").exists()
    details = {
        "app_exe": str(APP_EXE),
        "app_exe_exists": APP_EXE.exists(),
        "app_icon": str(APP_ICON),
        "app_icon_exists": APP_ICON.exists(),
        "kokoro_dir": str(ROOT / "models" / "tts" / "kokoro"),
        "kokoro_dir_exists": (ROOT / "models" / "tts" / "kokoro").exists(),
        "llm_dir_exists": (ROOT / "models" / "llm").exists(),
        "stt_dir_exists": (ROOT / "models" / "stt").exists(),
        "app_exe_icon_count": _windows_icon_count(APP_EXE),
    }
    if not APP_EXE.exists():
        status = "FAIL" if installed_context else "WARN"
        return Check("bundled EXE layout", status != "FAIL", status, f"Missing bundled app EXE: {APP_EXE}", details)
    if not APP_ICON.exists():
        return Check("bundled EXE layout", False, "FAIL", f"Missing installed icon: {APP_ICON}", details)
    if platform.system().lower() == "windows" and int(details["app_exe_icon_count"]) <= 0:
        return Check("bundled EXE layout", False, "FAIL", "ShellAI.exe has no extractable icon resource.", details)
    if not details["kokoro_dir_exists"]:
        return Check("bundled EXE layout", False, "FAIL", "Installed Kokoro model directory is missing.", details)
    return Check("bundled EXE layout", True, "PASS", "Bundled EXE, icon, and offline model folders are present.", details)


def check_frozen_offline_tts_path(py: Path) -> Check:
    if not APP_EXE.exists():
        return Check("frozen offline TTS path", False, "WARN", "Skipped because ShellAIApp/ShellAI.exe is not installed.")
    code = rf"""
import json
import sys
from pathlib import Path
import shell_offline_tts

sys.frozen = True
sys.executable = {str(APP_EXE)!r}
setattr(sys, "_MEIPASS", str(Path({str(APP_EXE)!r}).parent / "_internal"))
shell_offline_tts.PROJECT_ROOT = Path(getattr(sys, "_MEIPASS"))
print(json.dumps(shell_offline_tts.offline_tts_status(), sort_keys=True))
"""
    result = run_cmd([py, "-c", code], name="frozen offline TTS path", timeout=30)
    if not result.ok:
        return result
    try:
        payload = json.loads(result.message.splitlines()[-1])
    except Exception:
        return Check("frozen offline TTS path", False, "FAIL", result.message, result.details)
    if payload.get("available"):
        return Check("frozen offline TTS path", True, "PASS", f"Kokoro resolved from {payload.get('modelDir')}", {**result.details, "status": payload})
    return Check(
        "frozen offline TTS path",
        False,
        "FAIL",
        f"Frozen EXE layout cannot resolve Kokoro: {payload.get('reason')}",
        {**result.details, "status": payload},
    )


def check_frozen_offline_llm_catalog(py: Path) -> Check:
    if not APP_EXE.exists():
        return Check("frozen offline LLM catalog", False, "WARN", "Skipped because ShellAIApp/ShellAI.exe is not installed.")
    code = rf"""
import json
import sys
from pathlib import Path
import shell_offline_llm

sys.frozen = True
sys.executable = {str(APP_EXE)!r}
setattr(sys, "_MEIPASS", str(Path({str(APP_EXE)!r}).parent / "_internal"))
shell_offline_llm.PROJECT_ROOT = Path(getattr(sys, "_MEIPASS"))
status = shell_offline_llm.offline_llm_status()
catalog = status.get("catalog") if isinstance(status, dict) else {{}}
options = catalog.get("options") if isinstance(catalog, dict) else []
installed = status.get("installedModels") if isinstance(status, dict) else []
summary = {{
    "success": bool(status.get("success")) if isinstance(status, dict) else False,
    "available": bool(status.get("available")) if isinstance(status, dict) else False,
    "runtimeDownloads": status.get("runtimeDownloads") if isinstance(status, dict) else None,
    "reason": status.get("reason") if isinstance(status, dict) else "",
    "optionsCount": len(options) if isinstance(options, list) else 0,
    "installedModelsCount": len(installed) if isinstance(installed, list) else 0,
    "selectedModelId": status.get("selectedModelId") if isinstance(status, dict) else "",
    "installDir": status.get("installDir") if isinstance(status, dict) else "",
}}
print(json.dumps(summary, sort_keys=True))
"""
    result = run_cmd([py, "-c", code], name="frozen offline LLM catalog", timeout=30)
    if not result.ok:
        return result
    try:
        payload = json.loads(result.message.splitlines()[-1])
    except Exception:
        return Check("frozen offline LLM catalog", False, "FAIL", result.message, result.details)
    options_count = int(payload.get("optionsCount") or 0)
    if payload.get("runtimeDownloads") is True and options_count >= 4:
        return Check(
            "frozen offline LLM catalog",
            True,
            "PASS",
            f"Offline LLM uses on-demand catalog with {options_count} model options.",
            {**result.details, "status": payload},
        )
    return Check(
        "frozen offline LLM catalog",
        False,
        "FAIL",
        f"Frozen EXE does not expose the on-demand offline LLM catalog: {payload.get('reason')}",
        {**result.details, "status": payload},
    )


def check_frozen_runtime_probe() -> Check:
    if not platform.system().lower().startswith("win"):
        return Check("frozen EXE runtime probe", False, "BLOCKED", "Must run on Windows.")
    if not APP_EXE.exists():
        return Check("frozen EXE runtime probe", False, "WARN", f"Skipped because {APP_EXE} is not installed.")
    log_path = ROOT / ".shell_runtime" / "logs" / "runtime_probe.log"
    previous_log_size = log_path.stat().st_size if log_path.exists() else 0
    try:
        proc = subprocess.run(
            [str(APP_EXE), "--shell-ai-runtime-probe"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Check("frozen EXE runtime probe", False, "FAIL", "Runtime probe timed out.", {"log": str(log_path)})
    except Exception as exc:
        return Check("frozen EXE runtime probe", False, "FAIL", str(exc), {"log": str(log_path)})

    details: dict[str, Any] = {
        "returncode": proc.returncode,
        "log": str(log_path),
        "stdout": (proc.stdout or "")[-1000:],
    }
    marker = ""
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if previous_log_size and len(log_text) >= previous_log_size:
            log_text = log_text[previous_log_size:]
        for line in reversed(log_text.splitlines()):
            if line.startswith("SHELL_RUNTIME_PROBE_JSON="):
                marker = line.split("=", 1)[1]
                break
    if not marker:
        return Check("frozen EXE runtime probe", False, "FAIL", "Runtime probe did not write a status payload.", details)
    try:
        payload = json.loads(marker)
    except Exception as exc:
        details["payload"] = marker[-1200:]
        return Check("frozen EXE runtime probe", False, "FAIL", f"Runtime probe payload is invalid JSON: {exc}", details)
    details["payload"] = payload
    tts = payload.get("offline_tts") if isinstance(payload, dict) else {}
    llm = payload.get("offline_llm") if isinstance(payload, dict) else {}
    tts_ready = isinstance(tts, dict) and tts.get("available") is True
    llm_catalog_ready, llm_options_count = _offline_llm_catalog_ready(llm)
    if proc.returncode == 0 and tts_ready and llm_catalog_ready:
        return Check("frozen EXE runtime probe", True, "PASS", "Frozen EXE resolved Kokoro TTS and offline LLM catalog.", details)
    return Check(
        "frozen EXE runtime probe",
        False,
        "FAIL",
        (
            f"Frozen EXE runtime incomplete: tts_ready={tts_ready}"
            f" ({_candidate_failure_summary(tts) if isinstance(tts, dict) else 'unknown'}), "
            f"llm_catalog_ready={llm_catalog_ready} options={llm_options_count}"
            f" ({llm.get('reason') if isinstance(llm, dict) else 'unknown'}), "
            f"exit={proc.returncode}"
        ),
        details,
    )


def _offline_llm_catalog_ready(status: Any) -> tuple[bool, int]:
    if not isinstance(status, dict) or status.get("runtimeDownloads") is not True:
        return False, 0
    catalog = status.get("catalog")
    options = catalog.get("options") if isinstance(catalog, dict) else []
    options_count = len(options) if isinstance(options, list) else 0
    return options_count >= 4, options_count


def _candidate_failure_summary(status: dict[str, Any]) -> str:
    reason = str(status.get("reason") or "unknown")
    candidates = status.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return reason
    parts: list[str] = []
    for candidate in candidates[:3]:
        if not isinstance(candidate, dict):
            continue
        engine = str(candidate.get("engine") or "candidate")
        candidate_reason = str(candidate.get("reason") or "unknown")
        model_dir = str(candidate.get("modelDir") or "")
        suffix = f" at {model_dir}" if model_dir else ""
        parts.append(f"{engine}: {candidate_reason}{suffix}")
    return f"{reason}; " + "; ".join(parts) if parts else reason


def check_windows_app_open_smoke(py: Path) -> Check:
    if not platform.system().lower().startswith("win"):
        return Check("Windows app-open smoke", False, "BLOCKED", "Must run on Windows.")
    if not env_flag("SHELL_ACCEPTANCE_OPEN_APPS"):
        return Check(
            "Windows app-open smoke",
            True,
            "WARN",
            "Skipped. Set SHELL_ACCEPTANCE_OPEN_APPS=1 to launch Calculator and Notepad through Shell tools.",
        )
    code = r"""
import json
import time
from shell_tool_gateway import execute_tool_sync

cases = ["calculater", "note pad"]
observed = {}
for app_title in cases:
    opened = execute_tool_sync("shell_window_CTRL:open_app", {"app_title": app_title})
    observed[app_title] = opened
    if opened.get("status") != "success":
        raise SystemExit(json.dumps({"failed": app_title, "observed": observed}, sort_keys=True, default=str))
    result = opened.get("result") or {}
    if isinstance(result, dict) and result.get("success") is False:
        raise SystemExit(json.dumps({"failed": app_title, "observed": observed}, sort_keys=True, default=str))
    time.sleep(0.8)
    try:
        close_title = "calculator" if app_title == "calculater" else "notepad"
        observed[f"close:{app_title}"] = execute_tool_sync(
            "shell_window_CTRL:close_app",
            {"window_title": close_title},
        )
    except Exception as exc:
        observed[f"close:{app_title}"] = {"status": "warn", "error": str(exc)}

print(json.dumps(observed, sort_keys=True, default=str))
"""
    result = run_cmd([py, "-c", code], name="Windows app-open smoke", timeout=60)
    if result.ok:
        return result
    return Check(
        "Windows app-open smoke",
        False,
        "FAIL",
        result.message or "Shell app-open smoke failed.",
        result.details,
    )


def check_bundled_exe_memory() -> Check:
    if not platform.system().lower().startswith("win"):
        return Check("bundled EXE RAM smoke", False, "BLOCKED", "Must run on Windows.")
    if not APP_EXE.exists():
        return Check("bundled EXE RAM smoke", False, "WARN", f"Skipped because {APP_EXE} is not installed.")
    if not env_flag("SHELL_ACCEPTANCE_LAUNCH_EXE"):
        return Check(
            "bundled EXE RAM smoke",
            True,
            "WARN",
            "Skipped. Set SHELL_ACCEPTANCE_LAUNCH_EXE=1 to launch ShellAI.exe and measure memory.",
            {"warn_mb": RAM_WARN_MB, "fail_mb": RAM_FAIL_MB},
        )
    try:
        import psutil
    except Exception as exc:
        return Check("bundled EXE RAM smoke", True, "WARN", f"psutil unavailable: {exc}")

    env = os.environ.copy()
    env.setdefault("SHELL_WINDOWS_PERFORMANCE_MODE", "balanced")
    env.setdefault("SHELL_WEBENGINE_RENDERER", "balanced")
    started = time.perf_counter()
    proc = subprocess.Popen([str(APP_EXE)], cwd=str(ROOT), env=env)
    samples: list[dict[str, Any]] = []
    try:
        parent = psutil.Process(proc.pid)
        deadline = time.time() + 35
        while time.time() < deadline:
            time.sleep(1.0)
            try:
                processes = [parent] + parent.children(recursive=True)
                rss_mb = sum(p.memory_info().rss for p in processes if p.is_running()) / 1024 / 1024
                samples.append(
                    {
                        "elapsed_s": round(time.perf_counter() - started, 2),
                        "rss_mb": round(rss_mb, 2),
                        "process_count": len(processes),
                    }
                )
            except Exception:
                if proc.poll() is not None:
                    break
        peak_mb = max((sample["rss_mb"] for sample in samples), default=0.0)
        details = {
            "pid": proc.pid,
            "samples": samples[-12:],
            "peak_mb": peak_mb,
            "returncode": proc.poll(),
            "warn_mb": RAM_WARN_MB,
            "fail_mb": RAM_FAIL_MB,
        }
        if not samples or proc.poll() is not None:
            return Check("bundled EXE RAM smoke", False, "FAIL", "ShellAI.exe exited before RAM sampling completed.", details)
        if peak_mb >= RAM_FAIL_MB:
            return Check("bundled EXE RAM smoke", False, "FAIL", f"Peak RSS {peak_mb:.0f} MB exceeds {RAM_FAIL_MB} MB.", details)
        if peak_mb >= RAM_WARN_MB:
            return Check("bundled EXE RAM smoke", True, "WARN", f"Peak RSS {peak_mb:.0f} MB exceeds warning target {RAM_WARN_MB} MB.", details)
        return Check("bundled EXE RAM smoke", True, "PASS", f"Peak RSS {peak_mb:.0f} MB.", details)
    except Exception as exc:
        return Check("bundled EXE RAM smoke", False, "FAIL", str(exc), {"pid": proc.pid})
    finally:
        try:
            parent = psutil.Process(proc.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def check_local_tts_command(py: Path) -> Check:
    code = (
        "import json; "
        "from PyQt6.QtCore import QCoreApplication; "
        "from shell_web_ui.host import ShellBackendBridge; "
        "QCoreApplication.instance() or QCoreApplication([]); "
        "cmd=ShellBackendBridge()._tts_command('Shell voice test'); "
        "print(json.dumps({'available': bool(cmd), 'command': cmd[0] if cmd else ''}, sort_keys=True)); "
        "raise SystemExit(1 if cmd else 0)"
    )
    result = run_cmd([py, "-c", code], name="OS TTS fallback blocked probe", timeout=30)
    if result.ok:
        return Check(
            "OS TTS fallback blocked probe",
            True,
            "PASS",
            result.message or "OS TTS fallback is blocked by default.",
            result.details,
        )
    return Check(
        "OS TTS fallback blocked probe",
        False,
        "FAIL",
        result.message or "OS TTS fallback command is still available by default.",
        result.details,
    )


def check_hard_task_routes(py: Path) -> Check:
    code = r"""
import json
from shell_nl_router import route_natural_command

cases = {
    "website banao landing page for bakery": "shell_code_engine:create_fullstack_app_tool",
    "todo app banao with login": "shell_code_engine:create_fullstack_app_tool",
    "snake game banao": "shell_game_builder:build_game_tool",
    "AI tools ke bare mein pdf bana do": "shell_workspace_tools:create_user_file_tool",
    "cat ke photo generate karo": "shell_image_ai:generate_image_tool",
    "open calculator": "shell_window_CTRL:open_app",
    "close calculator": "shell_window_CTRL:close_app",
    "voice status check": "shell_neural_voice:shell_streaming_voice_status_tool",
}
arg_expectations = {
    "AI tools ke bare mein pdf bana do": {"destination": "documents", "file_type": "pdf"},
    "cat ke photo generate karo": {"force_fresh": True, "use_cache": False},
}

observed = {}
for prompt, expected in cases.items():
    route = route_natural_command(prompt) or {}
    observed[prompt] = {"tool": route.get("tool"), "args": route.get("args") or {}}
    if route.get("tool") != expected:
        raise SystemExit(json.dumps({"expected": expected, "observed": observed, "prompt": prompt}, sort_keys=True))
    for key, expected_value in arg_expectations.get(prompt, {}).items():
        observed_value = (route.get("args") or {}).get(key)
        if observed_value != expected_value:
            raise SystemExit(json.dumps({
                "expected": {key: expected_value},
                "observed": observed,
                "prompt": prompt,
            }, sort_keys=True))

print(json.dumps(observed, sort_keys=True))
"""
    return run_cmd([py, "-c", code], name="hard task routing probe", timeout=30)


def check_windows_runtime(py: Path) -> list[Check]:
    checks: list[Check] = []
    checks.append(
        Check(
            "target OS",
            platform.system().lower().startswith("win"),
            "PASS" if platform.system().lower().startswith("win") else "BLOCKED",
            f"Detected {platform.platform()}",
        )
    )
    for exe, label in (("ffmpeg", "audio/video tools"), ("tesseract", "OCR"), ("uvx", "Windows-MCP")):
        found = find_executable(exe, py)
        checks.append(
            Check(
                f"{exe} executable",
                True,
                "PASS" if found else "WARN",
                f"{label}: {found or 'not found; run Repair_ShellAI.bat if needed'}",
            )
        )
    try:
        from installer.bootstrap import windows_audio_preflight, windows_mcp_readiness, venv_dir

        audio = windows_audio_preflight()
        checks.append(Check(audio.name, audio.ok, audio.status, audio.message, audio.details))
        mcp = windows_mcp_readiness(venv_dir())
        checks.append(Check(mcp.name, mcp.ok, mcp.status, mcp.message, mcp.details))
    except Exception as exc:
        checks.append(Check("windows readiness helpers", False, "FAIL", str(exc)))
    return checks


def write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def print_summary(report: dict[str, Any]) -> None:
    print()
    print("Shell AI Windows acceptance probe")
    print(f"Status: {report['status']}")
    print(f"Report: {REPORT_PATH}")
    print()
    for check in report["checks"]:
        print(f"[{check['status']}] {check['name']}: {check['message'].splitlines()[-1] if check['message'] else ''}")
    print()
    print("Manual UAT still required on the visible Windows desktop:")
    print("1. Double-click Start_ShellAI.bat and confirm the UI opens.")
    print("2. Chat: ask 'open calculator', then 'close calculator'.")
    print("3. Chat: ask one normal question and confirm text appears without automatic voice.")
    print("4. Voice page: start voice and confirm speaker output is audible.")
    print("5. Settings: type into API key fields while update status is visible; confirm no typing lag.")
    print("6. Settings: add/remove a test API key and confirm it persists after restart.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Windows fresh-install and non-developer acceptance probes.")
    parser.add_argument("--app-root", type=Path, help="Installed or staged Shell AI app root to validate.")
    parser.add_argument("--runtime-only", action="store_true", help="Skip UI/hub launch probes and validate packaged runtime gates only.")
    parser.add_argument("--visible-ui-probe", action="store_true", help="Run the PyQt UI probe on the visible display.")
    parser.add_argument("--include-agents", action="store_true", help="Also drive all registered agents through chat UI.")
    parser.add_argument("--allow-non-windows", action="store_true", help="Developer-only: run probes even when the target OS is not Windows.")
    args = parser.parse_args(argv)
    if args.app_root:
        configure_probe_root(args.app_root)

    py = managed_python()
    checks: list[Check] = []
    checks.extend(check_windows_runtime(py))
    checks.append(check_health(py))
    is_windows = platform.system().lower().startswith("win")
    if is_windows or args.allow_non_windows:
        checks.append(check_installed_bundled_app_layout())
        if not args.runtime_only:
            checks.append(check_hub(py))
            checks.append(check_ui_probe(py, visible=args.visible_ui_probe))
        checks.append(check_voice_runtime(py))
        checks.append(check_offline_tts_status(py))
        checks.append(check_frozen_offline_tts_path(py))
        checks.append(check_frozen_offline_llm_catalog(py))
        checks.append(check_frozen_runtime_probe())
        if not args.runtime_only:
            checks.append(check_windows_app_open_smoke(py))
            checks.append(check_bundled_exe_memory())
        checks.append(check_local_tts_command(py))
        checks.append(check_hard_task_routes(py))
        if args.include_agents:
            checks.append(check_agent_probe(py))
    else:
        checks.append(
            Check(
                "Windows-only runtime probes",
                False,
                "BLOCKED",
                "Skipped hub/UI/voice probes because this acceptance test must be run inside the Windows RDP machine.",
            )
        )

    hard_fail = any(check.status == "FAIL" for check in checks)
    blocked = any(check.status == "BLOCKED" for check in checks)
    report = {
        "generated_at": time.time(),
        "status": "FAIL" if hard_fail else ("BLOCKED" if blocked else "PASS"),
        "python": str(py),
        "root": str(ROOT),
        "checks": [check.to_dict() for check in checks],
        "manual_uat_required": True,
        "manual_uat_items": [
            "Start_ShellAI.bat opens visible UI",
            "chat text response works and does not auto-trigger TTS",
            "voice page produces audible speech",
            "Windows-MCP app open/close works on Windows",
            "settings typing remains responsive while update status is visible",
            "settings/API persistence survives restart",
        ],
    }
    write_report(report)
    print_summary(report)
    return 1 if hard_fail or blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
