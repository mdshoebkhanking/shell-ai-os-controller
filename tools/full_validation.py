from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / ".shell_runtime" / "full_validation_report.json"


@dataclass(frozen=True)
class ValidationStep:
    name: str
    command: tuple[str, ...]
    timeout_seconds: int
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": list(self.command),
            "timeout_seconds": self.timeout_seconds,
            "required": self.required,
        }


def build_steps(python: str) -> list[ValidationStep]:
    return [
        ValidationStep("unit_and_regression_tests", (python, "-m", "pytest", "-q"), 240),
        ValidationStep(
            "ui_e2e_probe",
            (
                python,
                "tools/e2e_ui_probe.py",
                "--screens-dir",
                ".shell_runtime/ui_probe_screens",
                "--json-out",
                ".shell_runtime/ui_probe_report.json",
            ),
            120,
        ),
        ValidationStep(
            "latency_probe_ui",
            (
                python,
                "tools/latency_probe.py",
                "--ui",
                "--json-out",
                ".shell_runtime/latency_full_validation.json",
            ),
            120,
        ),
        ValidationStep(
            "memory_probe_ui_tts",
            (
                python,
                "tools/memory_probe.py",
                "--ui",
                "--tts",
                "--listener",
                "--json-out",
                ".shell_runtime/memory_full_validation.json",
            ),
            120,
        ),
        ValidationStep("strict_public_release_check", (python, "tools/production_release_check.py", "--strict"), 120),
        ValidationStep("config_diagnostics", (python, "tools/config_diagnostics.py", "--fail-on-error"), 120),
        ValidationStep("build_public_release_package", (python, "tools/package_public_release.py"), 180),
        ValidationStep("production_readiness", (python, "tools/production_readiness.py", "--run-tests"), 240),
        ValidationStep("enterprise_diagnostics", (python, "tools/enterprise_diagnostics.py", "--fail-on-attention"), 120),
        ValidationStep("ui_ux_audit", (python, "tools/ui_ux_audit.py", "--fail-on-high"), 120),
        ValidationStep("cloud_api_readiness", (python, "tools/cloud_readiness_audit.py", "--fail-on-high"), 120),
        ValidationStep("agent_ecosystem_audit", (python, "tools/agent_ecosystem_audit.py", "--fail-on-high"), 120),
        ValidationStep("launch_readiness_audit", (python, "tools/launch_readiness_audit.py", "--fail-on-high"), 120),
        ValidationStep("public_github_launch_audit", (python, "tools/public_github_launch_audit.py", "--fail-on-high"), 120),
        ValidationStep("ecosystem_master_audit", (python, "tools/ecosystem_master_audit.py", "--fail-on-high"), 120),
    ]


def run_step(step: ValidationStep) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            step.command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=step.timeout_seconds,
            check=False,
        )
        output = proc.stdout or ""
        return {
            **step.to_dict(),
            "status": "pass" if proc.returncode == 0 else "fail",
            "returncode": proc.returncode,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "output_tail": "\n".join(output.strip().splitlines()[-40:]),
        }
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return {
            **step.to_dict(),
            "status": "timeout",
            "returncode": None,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "output_tail": "\n".join(str(output).strip().splitlines()[-40:]),
        }


def git_status() -> dict[str, Any]:
    proc = subprocess.run(
        ("git", "status", "--short", "--branch"),
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
        check=False,
    )
    lines = (proc.stdout or "").splitlines()
    dirty = any(line and not line.startswith("## ") for line in lines)
    return {
        "status": "pass" if proc.returncode == 0 and not dirty else "fail",
        "returncode": proc.returncode,
        "dirty": dirty,
        "output": proc.stdout or "",
    }


def build_report(*, require_clean_git: bool, python: str) -> dict[str, Any]:
    started = time.perf_counter()
    steps = [run_step(step) for step in build_steps(python)]
    git = git_status()
    required_failures = [step for step in steps if step["required"] and step["status"] != "pass"]
    if require_clean_git and git["status"] != "pass":
        required_failures.append(
            {
                "name": "clean_git_worktree",
                "status": "fail",
                "output_tail": git["output"],
            }
        )
    return {
        "generated_at": time.time(),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "python": python,
        "require_clean_git": require_clean_git,
        "status": "pass" if not required_failures else "fail",
        "steps": steps,
        "git": git,
        "failure_count": len(required_failures),
    }


def print_report(report: dict[str, Any]) -> None:
    print(f"Shell AI full validation: {str(report['status']).upper()}")
    print(f"Duration: {report['duration_seconds']}s")
    print(f"Python: {report['python']}")
    print()
    for step in report["steps"]:
        marker = "PASS" if step["status"] == "pass" else "FAIL"
        print(f"[{marker}] {step['name']} ({step['duration_seconds']}s)")
        if step["status"] != "pass" and step.get("output_tail"):
            print(step["output_tail"])
            print()
    git = report["git"]
    git_marker = "PASS" if git["status"] == "pass" else "WARN"
    print(f"[{git_marker}] git_worktree dirty={git['dirty']}")
    print(git["output"].strip())
    print()
    print(f"Report: {REPORT_PATH}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Shell AI's full local validation gate before release or push.")
    parser.add_argument("--python", default=sys.executable, help="Python executable to use for validation subprocesses.")
    parser.add_argument("--require-clean-git", action="store_true", help="Fail if tracked files are modified.")
    parser.add_argument("--json", action="store_true", help="Print the JSON report.")
    args = parser.parse_args(argv)

    report = build_report(require_clean_git=args.require_clean_git, python=args.python)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_report(report)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
