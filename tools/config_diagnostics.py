from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import validate_environment  # noqa: E402

try:  # noqa: E402
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional in minimal tooling contexts
    load_dotenv = None  # type: ignore[assignment]


REPORT_PATH = ROOT / ".shell_runtime" / "config_diagnostics.json"


def build_report() -> dict[str, object]:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env", encoding="utf-8")
    return validate_environment().to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Shell AI enterprise configuration profile.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit nonzero when config has errors.")
    args = parser.parse_args(argv)

    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report.get("summary") or {}
        print(f"Shell AI config diagnostics: {str(report.get('status')).upper()}")
        print(f"Profile: {report.get('profile')}")
        print(f"Issues: {summary}")
        for issue in report.get("issues") or []:
            if isinstance(issue, dict):
                print(f"- {str(issue.get('level')).upper()} {issue.get('key')}: {issue.get('message')}")
        print(f"Report: {REPORT_PATH}")

    return 2 if args.fail_on_error and report.get("status") != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
