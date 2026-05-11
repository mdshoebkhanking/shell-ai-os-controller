#!/usr/bin/env python3
"""Audit global launch, distribution, community, and trust readiness."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.launch import (
    DistributionArtifact,
    DistributionChannel,
    LaunchChecklistItem,
    LaunchPlan,
    LaunchStage,
    TrustSignal,
)


REPORT_PATH = ROOT / ".shell_runtime" / "launch_readiness_report.json"


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    message: str
    recommendation: str
    path: str = ""


SCORE_WEIGHTS = {
    "critical": 30,
    "high": 18,
    "medium": 7,
    "low": 3,
    "info": 0,
}

REQUIRED_PHASE9_DOCS = [
    "docs/GLOBAL_LAUNCH_PHASE9.md",
    "docs/ENTERPRISE_DISTRIBUTION_PHASE9.md",
    "docs/BRAND_AUTHORITY_TRUST_PHASE9.md",
    "docs/COMMUNITY_GROWTH_PHASE9.md",
    "docs/CONTENT_EDUCATION_PHASE9.md",
    "docs/WEBSITE_PUBLIC_PRESENCE_PHASE9.md",
    "docs/ENTERPRISE_ADOPTION_PHASE9.md",
    "docs/ANALYTICS_PRODUCT_INSIGHT_PHASE9.md",
    "docs/SUSTAINABILITY_PHASE9.md",
    "docs/COMPETITIVE_POSITIONING_PHASE9.md",
    "docs/LONG_TERM_GOVERNANCE_PHASE9.md",
]

COMMUNITY_FILES = [
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "GOVERNANCE.md",
    "CHANGELOG.md",
]

WORKFLOW_FILES = [
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/workflows/security.yml",
    ".github/workflows/repo-audit.yml",
    ".github/dependabot.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/RELEASE_TEMPLATE.md",
]


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def read_text(path: str) -> str:
    candidate = ROOT / path
    if not candidate.exists():
        return ""
    return candidate.read_text(encoding="utf-8", errors="ignore")


def score(findings: list[Finding], base: int = 100) -> int:
    return max(0, base - sum(SCORE_WEIGHTS.get(item.severity, 0) for item in findings))


def build_launch_plan() -> LaunchPlan:
    checklist = [
        LaunchChecklistItem("license", "trust", "License present", LaunchStage.PUBLIC_BETA, exists("LICENSE"), "LICENSE"),
        LaunchChecklistItem("security", "trust", "Security policy present", LaunchStage.PUBLIC_BETA, exists("SECURITY.md"), "SECURITY.md"),
        LaunchChecklistItem("support", "community", "Support policy present", LaunchStage.PUBLIC_BETA, exists("SUPPORT.md"), "SUPPORT.md"),
        LaunchChecklistItem("governance", "community", "Governance model present", LaunchStage.PUBLIC_BETA, exists("GOVERNANCE.md"), "GOVERNANCE.md"),
        LaunchChecklistItem("release_zip", "distribution", "Public zip packaging works", LaunchStage.RELEASE_CANDIDATE, exists("tools/package_public_release.py"), "tools/package_public_release.py"),
        LaunchChecklistItem("checksums", "distribution", "Release checksum flow documented", LaunchStage.RELEASE_CANDIDATE, "SHA256" in read_text("docs/RELEASE_PROCESS.md"), "docs/RELEASE_PROCESS.md"),
        LaunchChecklistItem("windows_acceptance", "distribution", "Fresh Windows install verified", LaunchStage.PUBLIC_GA, False, "docs/ENTERPRISE_DISTRIBUTION_PHASE9.md"),
        LaunchChecklistItem("signed_installers", "distribution", "Signed installers available", LaunchStage.ENTERPRISE_READY, False, "docs/ENTERPRISE_DISTRIBUTION_PHASE9.md"),
    ]
    artifacts = [
        DistributionArtifact("public zip", DistributionChannel.PORTABLE_ZIP, "zip", checksum=True, signed=False, enterprise_ready=False),
        DistributionArtifact("windows launcher", DistributionChannel.WINDOWS, "bat/bootstrap", checksum=True, signed=False, enterprise_ready=False),
        DistributionArtifact("mac launcher", DistributionChannel.MACOS, "command/bootstrap", checksum=True, signed=False, notarized=False),
        DistributionArtifact("linux launcher", DistributionChannel.LINUX, "shell/bootstrap", checksum=True, signed=False),
    ]
    signals = [
        TrustSignal.LICENSE,
        TrustSignal.SECURITY_POLICY,
        TrustSignal.CODE_OF_CONDUCT,
        TrustSignal.CONTRIBUTING,
        TrustSignal.CHECKSUMS,
        TrustSignal.TESTS,
        TrustSignal.RELEASE_NOTES,
        TrustSignal.GOVERNANCE,
        TrustSignal.SUPPORT,
    ]
    return LaunchPlan("1.0.0", LaunchStage.RELEASE_CANDIDATE, checklist, artifacts, signals)


def check_required_files(findings: list[Finding]) -> None:
    for path in COMMUNITY_FILES:
        if not exists(path):
            findings.append(Finding("high", "community", f"Missing community health file: {path}", "Add GitHub community health files before public launch.", path))
    for path in WORKFLOW_FILES:
        if not exists(path):
            findings.append(Finding("medium", "release", f"Missing release/community workflow file: {path}", "Keep CI, release, security, dependabot, PR, and release templates active.", path))


def check_docs(findings: list[Finding]) -> None:
    docs_index = read_text("docs/README.md")
    readme = read_text("README.md")
    for path in REQUIRED_PHASE9_DOCS:
        name = Path(path).name
        if not exists(path):
            findings.append(Finding("medium", "documentation", f"Missing Phase 9 doc: {path}", "Document launch, distribution, trust, community, content, website, enterprise, analytics, sustainability, positioning, and governance.", path))
            continue
        if name not in docs_index:
            findings.append(Finding("low", "documentation", f"Docs index does not link {name}", "Expose Phase 9 docs through docs/README.md.", "docs/README.md"))
        if name not in readme:
            findings.append(Finding("low", "documentation", f"README does not link {name}", "Expose Phase 9 docs through README.md.", "README.md"))


def check_release_gates(findings: list[Finding]) -> None:
    ci = read_text(".github/workflows/ci.yml")
    release = read_text(".github/workflows/release.yml")
    for marker in ["cloud_readiness_audit.py", "agent_ecosystem_audit.py", "launch_readiness_audit.py", "production_release_check.py"]:
        if marker not in ci:
            findings.append(Finding("medium", "release", f"CI does not run {marker}", "Run release integrity gates before launch.", ".github/workflows/ci.yml"))
        if marker not in release:
            findings.append(Finding("medium", "release", f"Release workflow does not run {marker}", "Run launch gates before publishing artifacts.", ".github/workflows/release.yml"))
    if "attest" not in release:
        findings.append(Finding("medium", "distribution", "Release workflow does not create artifact attestations.", "Keep provenance/attestation in the release workflow.", ".github/workflows/release.yml"))


def check_distribution(findings: list[Finding]) -> None:
    for path in ["ONE_CLICK_INSTALL.bat", "ONE_CLICK_INSTALL.command", "start_shellai.sh", "Start_ShellAI.bat", "repair_shellai.command", "Repair_ShellAI.bat"]:
        if not exists(path):
            findings.append(Finding("medium", "distribution", f"Expected installer/launcher file missing: {path}", "Keep one-click install/start/repair paths available for public users.", path))
    findings.extend(
        [
            Finding("medium", "distribution", "Windows installer/MSIX signing is planned but not implemented.", "Add Windows signing before enterprise or broad non-technical distribution.", "docs/ENTERPRISE_DISTRIBUTION_PHASE9.md"),
            Finding("medium", "distribution", "macOS notarized app/DMG is planned but not implemented.", "Add Developer ID signing and notarization before marketing macOS as production-ready.", "docs/ENTERPRISE_DISTRIBUTION_PHASE9.md"),
            Finding("medium", "distribution", "Auto-update system is planned but not implemented.", "Do not enable auto-update until signed manifests and rollback are implemented.", "docs/ENTERPRISE_DISTRIBUTION_PHASE9.md"),
        ]
    )


def check_trust_and_analytics(findings: list[Finding]) -> None:
    analytics = read_text("docs/ANALYTICS_PRODUCT_INSIGHT_PHASE9.md").lower()
    if "opt-in" not in analytics or "never collect" not in analytics:
        findings.append(Finding("medium", "trust", "Analytics docs do not clearly require opt-in and excluded data.", "Keep telemetry transparent, optional, and privacy-first.", "docs/ANALYTICS_PRODUCT_INSIGHT_PHASE9.md"))
    brand = read_text("docs/BRAND_AUTHORITY_TRUST_PHASE9.md").lower()
    if "not agi" not in brand and "agi" not in brand:
        findings.append(Finding("low", "brand", "Brand docs do not explicitly reject AGI claims.", "Keep launch language realistic and safe.", "docs/BRAND_AUTHORITY_TRUST_PHASE9.md"))


def add_known_launch_gaps(findings: list[Finding]) -> None:
    findings.extend(
        [
            Finding("medium", "adoption", "Real public launch still needs fresh Windows install validation.", "Run a clean Windows acceptance test before GA.", "docs/GLOBAL_LAUNCH_PHASE9.md"),
            Finding("low", "website", "Documentation website is planned but not deployed in this repo yet.", "Launch with GitHub README first, then deploy the static docs site.", "docs/WEBSITE_PUBLIC_PRESENCE_PHASE9.md"),
            Finding("low", "sustainability", "Funding/sponsorship channels are planned but not configured.", "Add funding only after public roadmap, support expectations, and contribution flow are stable.", "docs/SUSTAINABILITY_PHASE9.md"),
        ]
    )


def build_report() -> dict[str, Any]:
    findings: list[Finding] = []
    plan = build_launch_plan()
    check_required_files(findings)
    check_docs(findings)
    check_release_gates(findings)
    check_distribution(findings)
    check_trust_and_analytics(findings)
    add_known_launch_gaps(findings)

    high_or_worse = [item for item in findings if item.severity in {"critical", "high"}]
    report = {
        "status": "pass" if not high_or_worse else "attention",
        "summary": {
            "launch_readiness_score": score([item for item in findings if item.category in {"adoption", "release", "documentation"}], base=plan.readiness_score()),
            "community_scalability_score": score([item for item in findings if item.category == "community"]),
            "enterprise_readiness_score": score([item for item in findings if item.category in {"distribution", "trust"}], base=86),
            "ecosystem_trust_score": score([item for item in findings if item.category in {"trust", "release", "community"}], base=plan.trust_score()),
            "brand_authority_score": score([item for item in findings if item.category == "brand"], base=94),
            "documentation_maturity_score": score([item for item in findings if item.category == "documentation"]),
            "distribution_readiness_score": score([item for item in findings if item.category == "distribution"], base=85),
            "sustainability_score": score([item for item in findings if item.category == "sustainability"], base=88),
        },
        "launch_plan": plan.to_dict(),
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Shell Phase 9 launch and distribution readiness.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument("--fail-on-high", action="store_true", help="Exit non-zero if high or critical findings exist.")
    args = parser.parse_args()

    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Launch readiness: {report['status']} ({report['finding_count']} findings)")
        for key, value in report["summary"].items():
            print(f"- {key}: {value}/100")
        print(f"Report: {REPORT_PATH}")

    if args.fail_on_high and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
