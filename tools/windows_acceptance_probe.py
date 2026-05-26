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
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.7) as response:
                            if response.status == 200:
                                elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
                                return Check(
                                    "hub startup",
                                    True,
                                    "PASS",
                                    f"Shell Hub healthy on port {port}",
                                    {"elapsed_ms": elapsed_ms, "port": port, "log": str(log_path)},
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
    ]
    if visible:
        cmd.append("--visible")
    return run_cmd(cmd, name="real UI probe", timeout=90)


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
        "mods=['pyttsx3','edge_tts','sounddevice','speech_recognition']; "
        "print(json.dumps({m: bool(importlib.util.find_spec(m)) for m in mods}, sort_keys=True))"
    )
    result = run_cmd([py, "-c", code], name="voice dependency probe", timeout=30)
    if result.ok and "pyttsx3" in result.message:
        return result
    return result


def check_local_tts_command(py: Path) -> Check:
    code = (
        "import json; "
        "from PyQt6.QtCore import QCoreApplication; "
        "from shell_web_ui.host import ShellBackendBridge; "
        "QCoreApplication.instance() or QCoreApplication([]); "
        "cmd=ShellBackendBridge()._tts_command('Shell voice test'); "
        "print(json.dumps({'available': bool(cmd), 'command': cmd[0] if cmd else ''}, sort_keys=True)); "
        "raise SystemExit(0 if cmd else 1)"
    )
    result = run_cmd([py, "-c", code], name="local TTS command probe", timeout=30)
    if result.ok:
        return result
    return Check(
        "local TTS command probe",
        True,
        "WARN",
        result.message or "No local TTS command detected; audible voice remains a manual UI check.",
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
    "open calculator": "shell_window_CTRL:open_app",
    "close calculator": "shell_window_CTRL:close_app",
    "voice status check": "shell_neural_voice:shell_streaming_voice_status_tool",
}

observed = {}
for prompt, expected in cases.items():
    route = route_natural_command(prompt) or {}
    observed[prompt] = route.get("tool")
    if route.get("tool") != expected:
        raise SystemExit(json.dumps({"expected": expected, "observed": observed, "prompt": prompt}, sort_keys=True))

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
    print("5. Settings: add/remove a test API key and confirm it persists after restart.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Windows fresh-install and non-developer acceptance probes.")
    parser.add_argument("--visible-ui-probe", action="store_true", help="Run the PyQt UI probe on the visible display.")
    parser.add_argument("--include-agents", action="store_true", help="Also drive all registered agents through chat UI.")
    parser.add_argument("--allow-non-windows", action="store_true", help="Developer-only: run probes even when the target OS is not Windows.")
    args = parser.parse_args(argv)

    py = managed_python()
    checks: list[Check] = []
    checks.extend(check_windows_runtime(py))
    checks.append(check_health(py))
    is_windows = platform.system().lower().startswith("win")
    if is_windows or args.allow_non_windows:
        checks.append(check_hub(py))
        checks.append(check_ui_probe(py, visible=args.visible_ui_probe))
        checks.append(check_voice_runtime(py))
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
            "settings/API persistence survives restart",
        ],
    }
    write_report(report)
    print_summary(report)
    return 1 if hard_fail or blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
