from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / ".shell_runtime" / "signing_notarization_report.json"


@dataclass
class Gate:
    name: str
    ready: bool
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ready": self.ready,
            "status": self.status,
            "message": self.message,
            "details": dict(self.details),
        }


def run_cmd(argv: list[str], *, timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, (proc.stdout or "").strip()
    except Exception as exc:
        return 127, str(exc)


def mac_gate() -> Gate:
    if platform.system() != "Darwin":
        return Gate("macOS notarization", False, "NOT_APPLICABLE", "Run this gate on macOS with Apple Developer credentials.")
    codesign = shutil.which("codesign")
    xcrun = shutil.which("xcrun")
    security = shutil.which("security")
    if not codesign or not xcrun or not security:
        return Gate("macOS notarization", False, "BLOCKED", "macOS signing tools are missing.", {"codesign": codesign, "xcrun": xcrun, "security": security})

    rc, identities = run_cmd(["security", "find-identity", "-v", "-p", "codesigning"])
    has_developer_id = rc == 0 and "Developer ID Application" in identities
    rc_notary, notary_help = run_cmd(["xcrun", "notarytool", "--help"])
    notary_available = rc_notary == 0 and "notary" in notary_help.lower()
    profile = os.environ.get("SHELL_NOTARY_PROFILE", "").strip()
    apple_id = os.environ.get("SHELL_NOTARY_APPLE_ID", "").strip()
    team_id = os.environ.get("SHELL_NOTARY_TEAM_ID", "").strip()
    password = os.environ.get("SHELL_NOTARY_PASSWORD", "").strip()
    has_credentials = bool(profile or (apple_id and team_id and password))

    if has_developer_id and notary_available and has_credentials:
        return Gate(
            "macOS notarization",
            True,
            "READY",
            "Developer ID identity, notarytool, and notarization credentials are available.",
            {"credential_mode": "keychain-profile" if profile else "env"},
        )
    blockers = []
    if not has_developer_id:
        blockers.append("no Developer ID Application certificate in keychain")
    if not notary_available:
        blockers.append("notarytool unavailable")
    if not has_credentials:
        blockers.append("no SHELL_NOTARY_PROFILE or Apple notarization env credentials")
    return Gate(
        "macOS notarization",
        False,
        "BLOCKED",
        "; ".join(blockers),
        {"identity_output_tail": identities[-1200:], "notarytool": notary_available},
    )


def windows_gate() -> Gate:
    signtool = shutil.which("signtool")
    osslsigncode = shutil.which("osslsigncode")
    pfx = os.environ.get("SHELL_WINDOWS_SIGN_PFX", "").strip()
    cert_subject = os.environ.get("SHELL_WINDOWS_SIGN_SUBJECT", "").strip()
    cert_available = bool(pfx or cert_subject)
    if signtool and cert_available:
        return Gate("Windows Authenticode signing", True, "READY", "signtool and certificate configuration are available.", {"tool": signtool})
    if osslsigncode and pfx:
        return Gate("Windows Authenticode signing", True, "READY", "osslsigncode and PFX configuration are available.", {"tool": osslsigncode})
    blockers = []
    if not signtool and not osslsigncode:
        blockers.append("signtool/osslsigncode not found")
    if not cert_available:
        blockers.append("no SHELL_WINDOWS_SIGN_PFX or SHELL_WINDOWS_SIGN_SUBJECT configured")
    return Gate(
        "Windows Authenticode signing",
        False,
        "BLOCKED",
        "; ".join(blockers),
        {"signtool": signtool, "osslsigncode": osslsigncode},
    )


def build_report() -> dict[str, Any]:
    gates = [mac_gate(), windows_gate()]
    report = {
        "generated_at": time.time(),
        "root": str(ROOT),
        "platform": platform.platform(),
        "status": "READY" if all(gate.ready for gate in gates) else "BLOCKED",
        "gates": [gate.to_dict() for gate in gates],
        "notes": [
            "This check does not fake code signing. It only reports whether signing/notarization can be performed.",
            "Final public GA needs a signed Windows installer and notarized macOS app/package, or a documented unsigned beta channel.",
        ],
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check release signing and macOS notarization readiness.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when signing/notarization is blocked.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Shell AI signing/notarization readiness: {report['status']}")
        for gate in report["gates"]:
            print(f"[{gate['status']}] {gate['name']}: {gate['message']}")
        print(f"Report: {REPORT_PATH}")
    return 2 if args.strict and report["status"] != "READY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
