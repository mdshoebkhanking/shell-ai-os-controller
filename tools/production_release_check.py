from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shell_production_guard import audit_production_environment, read_env_file  # noqa: E402


REPORT_PATH = ROOT / ".shell_runtime" / "production_release_report.json"


def _runtime_health() -> dict[str, object]:
    try:
        from installer.bootstrap import health_report

        report = health_report()
        return {
            "ok": bool(report.get("ok")),
            "state": report.get("state"),
            "summary": report.get("summary", {}),
        }
    except Exception as exc:
        return {"ok": False, "state": "ERROR", "summary": {"errors": [str(exc)], "warnings": []}}


def build_report(*, include_health: bool = True, strict: bool = False) -> dict[str, object]:
    env_example = read_env_file(ROOT / ".env.example")
    template = audit_production_environment(env_example, root=ROOT, check_assets=True)

    local_runtime = audit_production_environment(root=ROOT, check_assets=False)
    blockers = list(template["blockers"])
    warnings = list(template["warnings"])

    # Local .env can be intentionally permissive during development. For a
    # public release package it is excluded, so surface those findings as
    # warnings unless --strict is requested.
    local_blockers = [f"local-env: {item}" for item in local_runtime["blockers"]]
    if strict:
        blockers.extend(local_blockers)
    else:
        warnings.extend(local_blockers)
    warnings.extend(str(item) for item in local_runtime["warnings"])

    health = {"ok": True, "state": "SKIPPED", "summary": {"errors": [], "warnings": []}}
    if include_health:
        health = _runtime_health()
        if not health["ok"]:
            blockers.append(f"Runtime health is not ready: {health.get('state')}")

    report = {
        "generated_at": time.time(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "root": str(ROOT),
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
        "warnings": warnings,
        "template_guard": template,
        "local_runtime_guard": local_runtime,
        "health": health,
    }
    return report


def print_report(report: dict[str, object]) -> None:
    print(f"Shell AI public release check: {str(report['status']).upper()}")
    print(f"Root: {report['root']}")
    print()
    blockers = list(report.get("blockers") or [])
    warnings = list(report.get("warnings") or [])
    if blockers:
        print("Blockers:")
        for item in blockers:
            print(f"  - {item}")
    else:
        print("Blockers: none")
    print()
    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"  - {item}")
    else:
        print("Warnings: none")
    print()
    health = report.get("health") or {}
    print(f"Runtime health: {health.get('state')} (ok={health.get('ok')})")
    print(f"Report: {REPORT_PATH}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Shell AI for a public production release package.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of human-readable text.")
    parser.add_argument("--skip-health", action="store_true", help="Skip installer/runtime health checks.")
    parser.add_argument("--strict", action="store_true", help="Treat local .env unsafe development flags as failures.")
    parser.add_argument("--write-report", action="store_true", default=True, help="Write .shell_runtime/production_release_report.json.")
    args = parser.parse_args(argv)

    report = build_report(include_health=not args.skip_health, strict=args.strict)
    if args.write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_report(report)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
