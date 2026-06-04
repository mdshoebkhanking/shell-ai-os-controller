from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_tool_module(name: str, filename: str):
    try:
        return __import__(f"tools.{name}", fromlist=["*"])
    except ModuleNotFoundError:
        spec = importlib.util.spec_from_file_location(f"_shell_{name}", ROOT / "tools" / filename)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


_release_check = _load_tool_module("production_release_check", "production_release_check.py")
_package_release = _load_tool_module("package_public_release", "package_public_release.py")
build_release_report = _release_check.build_report
version = _package_release.version


REPORT_PATH = ROOT / ".shell_runtime" / "production_readiness_report.json"
PACKAGE_PATH = ROOT / "dist" / f"shell-ai-os-controller-{version()}.zip"
TEST_CONFIG_PATH = ROOT / ".shell_runtime" / "production_readiness_shellai" / "config.json"

TEST_COMMAND = [
    "-m",
    "pytest",
    "tests/test_evolution_governor.py",
    "tests/test_production_foundation.py",
    "tests/test_security_regressions.py",
    "tests/test_installer_bootstrap.py",
    "tests/test_windows_mcp_integration.py",
    "tests/test_external_integrations.py",
    "tests/test_low_latency_interaction.py",
    "tests/test_voice_latency_runtime.py",
    "-q",
]


@dataclass(frozen=True)
class Gate:
    name: str
    points: int
    passed: bool
    details: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "points": self.points,
            "passed": self.passed,
            "earned": self.points if self.passed else 0,
            "details": self.details,
        }


def _file_contains(path: Path, needle: str) -> bool:
    return path.exists() and needle in path.read_text(encoding="utf-8", errors="replace")


def _verify_package() -> tuple[bool, str]:
    if not PACKAGE_PATH.exists():
        return False, f"package missing: {PACKAGE_PATH}"
    try:
        with zipfile.ZipFile(PACKAGE_PATH) as zf:
            names = zf.namelist()
            bad = [
                name
                for name in names
                if name == ".env"
                or name == ".shell_settings.json"
                or name in {
                    ".telegram_log.json",
                    ".telegram_rules.json",
                    ".telegram_schedule.json",
                    ".telegram_state.json",
                    ".telegram_users.json",
                    "shell_telegram_stats.json",
                }
                or name.startswith(".shell_runtime/")
                or name.startswith(".shell_image_cache/")
                or name.startswith(".shellai_venv/")
                or name.startswith("Desktop/")
                or name.startswith("integrations/external/")
                or name.startswith("node_modules/")
                or name.startswith("shell_ui/build/")
                or name.startswith("smoke/")
                or name.startswith("ui_screenshots/")
                or name.startswith("venv/")
                or name
                in {
                    ".phoenix_analytics.json",
                    ".shell_full_smoke_report.json",
                    ".shell_hub_port",
                    ".shell_theme.json",
                    "control_log.txt",
                    "glass_chat.png",
                    "glass_settings.png",
                    "glass_system.png",
                    "glass_voice.png",
                    "qr_test.png",
                    "screenshot_chat.png",
                    "screenshot_voice_test.png",
                    "shell_brain.json",
                    "shell_browser_history.json",
                    "shell_image_history.json",
                    "shot_chat.png",
                    "shot_settings.png",
                    "shot_system.png",
                    "shot_system_nav.png",
                    "shot_voice.png",
                    "smoke_test_output.tmp.png",
                }
            ]
            if bad:
                return False, f"package includes excluded runtime files: {bad[:5]}"
            if "release_manifest.json" not in names:
                return False, "release_manifest.json missing"
            required = {
                "LICENSE",
                "NOTICE",
                "LEGAL.md",
                "SECURITY.md",
                "THIRD_PARTY_NOTICES.md",
                "ONE_CLICK_INSTALL.bat",
                "Start_ShellAI.bat",
                "Build_Windows_EXE.bat",
                "Run_Windows_Acceptance_Test.bat",
                "tools/build_windows_installer.py",
                "tools/windows_app/shellai_desktop_entry.py",
                "tools/windows_installer/ShellAI_Setup.iss",
                "tools/windows_acceptance_probe.py",
                "tools/signing_notarization_check.py",
            }
            missing = sorted(required - set(names))
            if missing:
                return False, f"release validation assets missing: {missing}"
            if "PUBLIC_RELEASE.md" not in names:
                return False, "PUBLIC_RELEASE.md missing from package"
            return True, f"{len(names)} files, no excluded runtime/secrets paths"
    except Exception as exc:
        return False, str(exc)


def _configured_test_python() -> Path | None:
    configured = os.environ.get("SHELLAI_TEST_PYTHON", "").strip()
    if not configured:
        return None
    path = Path(configured)
    return path if path.is_absolute() else ROOT / path


def _managed_venv_python() -> Path | None:
    try:
        from installer import bootstrap

        candidate = bootstrap.python_in_venv(bootstrap.venv_dir())
    except Exception:
        return None
    return candidate if candidate.exists() else None


def _test_python() -> str:
    configured = _configured_test_python()
    if configured and configured.exists():
        return str(configured)
    managed = _managed_venv_python()
    if managed:
        return str(managed)
    return sys.executable


def _run_tests() -> tuple[bool, str]:
    env = os.environ.copy()
    env["SHELLAI_CONFIG"] = str(TEST_CONFIG_PATH)
    test_python = _test_python()
    proc = subprocess.run(
        [test_python, *TEST_COMMAND],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=180,
        check=False,
    )
    raw_output = proc.stdout or ""
    output = raw_output.strip().splitlines()
    tail = "\n".join(output[-8:])
    if proc.returncode != 0 and "No module named pytest" in raw_output:
        tail = (
            f"pytest is unavailable in {test_python}. "
            "Run Repair_ShellAI.bat or `python installer/bootstrap.py repair --yes --skip-system`, then rerun Build_Public_Release.bat."
        )
    return proc.returncode == 0, tail


def build_readiness_report(*, run_tests: bool = False) -> dict[str, Any]:
    release = build_release_report(include_health=True, strict=True)
    package_ok, package_details = _verify_package()
    tests_ok = True
    tests_details = "not run in this invocation; use --run-tests"
    if run_tests:
        tests_ok, tests_details = _run_tests()

    prompt_has_disclaimer = _file_contains(ROOT / "shell_prompts.py", "Never claim unrestricted self-evolution")
    docs_have_release = all((ROOT / name).exists() for name in ("PUBLIC_RELEASE.md", "CHANGELOG.md", "VERSION"))
    docs_have_user_flow = _file_contains(ROOT / "README.md", "ONE_CLICK_INSTALL.bat") and _file_contains(ROOT / "PUBLIC_RELEASE.md", "Build The Public Zip")

    gates = [
        Gate("release_gate", 20, release["status"] == "pass", "production_release_check.py strict passed" if release["status"] == "pass" else "; ".join(release["blockers"])),
        Gate("runtime_health", 15, bool(release["health"].get("ok")), f"state={release['health'].get('state')}"),
        Gate("package_integrity", 15, package_ok, package_details),
        Gate("safety_defaults", 15, not release["template_guard"]["blockers"] and not release["local_runtime_guard"]["blockers"], "dangerous public defaults disabled"),
        Gate("focused_tests", 20, tests_ok, tests_details),
        Gate("release_docs", 10, docs_have_release and docs_have_user_flow, "public release, changelog, version, and one-click flow documented"),
        Gate("anti_deceptive_ai_claims", 5, prompt_has_disclaimer, "prompt includes bounded evolution/safety instruction"),
    ]
    earned = sum(g.points for g in gates if g.passed)
    total = sum(g.points for g in gates)
    external_gates = [
        {
            "name": "fresh_windows_install",
            "required_for_final_public_ga": True,
            "status": "requires target Windows machine / RDP execution",
            "minimum_checks": ["Run_Windows_Acceptance_Test.bat", "Start_ShellAI.bat", "voice output", "Windows-MCP app open/close"],
        },
        {
            "name": "signed_installer",
            "required_for_final_public_ga": True,
            "status": "requires publisher certificate / notarization; run Check_Release_Signing",
            "minimum_checks": ["Windows Authenticode", "macOS notarization or clear unsigned-user instructions"],
        },
        {
            "name": "clean_user_acceptance_test",
            "required_for_final_public_ga": True,
            "status": "requires non-developer tester",
            "minimum_checks": ["install without terminal knowledge", "API setup wizard", "chat", "voice", "repair flow"],
        },
    ]
    report = {
        "generated_at": time.time(),
        "version": version(),
        "automated_local_score": round((earned / total) * 100, 2),
        "automated_status": "pass" if earned == total else "fail",
        "gates": [gate.to_dict() for gate in gates],
        "external_gates": external_gates,
        "release_check": {
            "status": release["status"],
            "warnings": release["warnings"],
            "blockers": release["blockers"],
        },
        "package": str(PACKAGE_PATH),
    }
    return report


def print_report(report: dict[str, Any]) -> None:
    print(f"Shell AI automated production readiness: {report['automated_local_score']}/100")
    print(f"Status: {str(report['automated_status']).upper()}")
    print(f"Version: {report['version']}")
    print()
    for gate in report["gates"]:
        marker = "PASS" if gate["passed"] else "FAIL"
        print(f"[{marker}] {gate['name']}: {gate['earned']}/{gate['points']} - {gate['details']}")
    print()
    print("External gates required for final public GA:")
    for gate in report["external_gates"]:
        print(f"- {gate['name']}: {gate['status']}")
    print()
    print(f"Report: {REPORT_PATH}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score Shell AI automated production readiness.")
    parser.add_argument("--run-tests", action="store_true", help="Run focused production test suite.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args(argv)

    report = build_readiness_report(run_tests=args.run_tests)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_report(report)
    return 0 if report["automated_status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
