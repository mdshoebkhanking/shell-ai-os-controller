from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import validate_environment  # noqa: E402
from core.health import run_startup_diagnostics  # noqa: E402

try:  # noqa: E402
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional in minimal tooling contexts
    load_dotenv = None  # type: ignore[assignment]


REPORT_PATH = ROOT / ".shell_runtime" / "enterprise_diagnostics_report.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            return data if isinstance(data, dict) else {"value": data}
    except Exception as exc:
        return {"error": str(exc)}
    return {}


def _doc_presence() -> dict[str, bool]:
    required = [
        "README.md",
        "DESIGN.md",
        "SECURITY.md",
        "PUBLIC_RELEASE.md",
        "docs/ENTERPRISE_ARCHITECTURE_REVIEW.md",
        "docs/AI_INFRASTRUCTURE_PLAN.md",
        "docs/CONFIGURATION_SYSTEM.md",
        "docs/OBSERVABILITY_AND_DEBUGGING.md",
        "docs/PERFORMANCE_ENGINEERING_PLAN.md",
        "docs/DEVELOPER_EXPERIENCE.md",
        "docs/ENTERPRISE_SECURITY_PREP.md",
        "docs/MONETIZATION_READINESS.md",
        "docs/LONG_TERM_ECOSYSTEM_STRATEGY.md",
    ]
    return {path: (ROOT / path).exists() for path in required}


def build_report() -> dict[str, Any]:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env", encoding="utf-8")
    runtime_dir = ROOT / ".shell_runtime"
    config_report = validate_environment().to_dict()
    health_report = run_startup_diagnostics()
    docs = _doc_presence()
    repo_audit = _load_json(runtime_dir / "repo_audit_report.json")
    readiness = _load_json(runtime_dir / "production_readiness_report.json")
    missing_docs = [path for path, present in docs.items() if not present]
    config_errors = int((config_report.get("summary") or {}).get("errors") or 0)
    status = "pass" if not missing_docs and config_errors == 0 else "needs_attention"
    return {
        "status": status,
        "generated_at": time.time(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "config": config_report,
        "health_summary": health_report.get("summary", {}),
        "public_docs": docs,
        "missing_docs": missing_docs,
        "repo_audit_summary": repo_audit.get("summary", repo_audit.get("score", {})),
        "production_readiness": {
            "score": readiness.get("automated_local_score"),
            "status": readiness.get("automated_status"),
        },
        "support_note": "Report is redacted. Do not attach .env, logs, tokens, or screenshots containing private data.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a redacted Shell AI enterprise diagnostics report.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument("--fail-on-attention", action="store_true", help="Exit nonzero if report needs attention.")
    args = parser.parse_args(argv)

    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Shell AI enterprise diagnostics: {str(report.get('status')).upper()}")
        print(f"Config profile: {(report.get('config') or {}).get('profile')}")
        print(f"Missing docs: {len(report.get('missing_docs') or [])}")
        print(f"Production readiness: {report.get('production_readiness')}")
        print(f"Report: {REPORT_PATH}")

    return 2 if args.fail_on_attention and report.get("status") != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
