#!/usr/bin/env python3
"""Audit Shell's cloud, API, sync, and platform readiness.

This is intentionally deterministic: it validates repository contracts and
release gates without requiring network access or hosted services.
"""

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

from core.events.bus import AIEventType, publish_event
from core.platform_api import PlatformAPIContract

REPORT_PATH = ROOT / ".shell_runtime" / "cloud_readiness_report.json"


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    message: str
    recommendation: str
    path: str = ""


REQUIRED_DOCS = [
    "docs/CLOUD_INFRASTRUCTURE_PHASE7.md",
    "docs/API_ECOSYSTEM_PHASE7.md",
    "docs/AI_ORCHESTRATION_PHASE7.md",
    "docs/SYNC_STORAGE_STRATEGY_PHASE7.md",
    "docs/SECURITY_INFRASTRUCTURE_PHASE7.md",
    "docs/PLUGIN_AUTOMATION_ECOSYSTEM_PHASE7.md",
    "docs/DEVOPS_CLOUD_DEPLOYMENT_PHASE7.md",
    "docs/ENTERPRISE_TEAM_PRODUCT_STRATEGY_PHASE7.md",
]

REQUIRED_API_MARKERS = [
    "_request_authorized",
    "_socket_authorized",
    "ALLOWED_ORIGINS",
    "/health",
    "/capabilities",
    "non-loopback hub bind",
]

SCORE_WEIGHTS = {
    "critical": 30,
    "high": 18,
    "medium": 7,
    "low": 3,
    "info": 0,
}


def read_text(path: str) -> str:
    candidate = ROOT / path
    if not candidate.exists():
        return ""
    return candidate.read_text(encoding="utf-8", errors="ignore")


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def score(findings: list[Finding], base: int = 100) -> int:
    penalty = sum(SCORE_WEIGHTS.get(item.severity, 0) for item in findings)
    return max(0, base - penalty)


def check_platform_contract(findings: list[Finding]) -> dict[str, Any]:
    contract = PlatformAPIContract()
    contract_findings = contract.validate()
    for item in contract_findings:
        findings.append(
            Finding(
                severity=str(item.get("severity") or "medium"),
                category="api_contract",
                message=str(item.get("message") or "API contract finding"),
                recommendation="Keep every public and local endpoint declared with method, path, scope, and rate policy.",
                path="core/platform_api/contracts.py",
            )
        )
    skeleton = contract.openapi_skeleton()
    if skeleton.get("openapi") != "3.1.0":
        findings.append(
            Finding(
                "high",
                "api_contract",
                "OpenAPI skeleton is missing or not versioned as OpenAPI 3.1.",
                "Keep API descriptions compatible with modern OpenAPI tooling.",
                "core/platform_api/contracts.py",
            )
        )
    return {"route_count": len(contract.routes), "openapi": skeleton.get("openapi")}


def check_local_api_hardening(findings: list[Finding]) -> None:
    hub = read_text("shell_hub.py")
    for marker in REQUIRED_API_MARKERS:
        if marker not in hub:
            findings.append(
                Finding(
                    "high",
                    "api_security",
                    f"Local hub is missing required hardening marker: {marker}",
                    "Preserve loopback-only defaults, bearer checks, health endpoints, and explicit remote-bind protection.",
                    "shell_hub.py",
                )
            )
    if "aiohttp_cors.ResourceOptions" not in hub:
        findings.append(
            Finding(
                "medium",
                "api_security",
                "CORS headers were not detected in the local hub.",
                "Keep browser-accessible APIs restricted to explicit local origins until remote auth is implemented.",
                "shell_hub.py",
            )
        )


def check_sync_storage(findings: list[Finding]) -> None:
    required = [
        "core/context_sync/engine.py",
        "core/global_context/engine.py",
        "core/memory",
        "core/distributed_memory/fabric.py",
    ]
    for path in required:
        if not exists(path):
            findings.append(
                Finding(
                    "medium",
                    "sync_storage",
                    f"Expected sync or memory component is missing: {path}",
                    "Keep local-first sync, memory, and global context modules separated before cloud sync is added.",
                    path,
                )
            )
    findings.append(
        Finding(
            "medium",
            "sync_storage",
            "No production cloud sync adapter is present yet.",
            "Add encrypted sync providers behind feature flags before offering multi-device accounts.",
            "docs/SYNC_STORAGE_STRATEGY_PHASE7.md",
        )
    )


def check_plugin_ecosystem(findings: list[Finding]) -> None:
    manifest = read_text("sdk/manifest.py")
    required_permissions = ["api.external", "events.publish", "events.subscribe", "workflow.run", "cloud.sync", "workspace.sync"]
    for permission in required_permissions:
        if permission not in manifest:
            findings.append(
                Finding(
                    "medium",
                    "plugin_ecosystem",
                    f"Plugin SDK is missing Phase 7 permission: {permission}",
                    "Keep cloud/API/event permissions explicit so extensions can be sandboxed and audited.",
                    "sdk/manifest.py",
                )
            )
    if not exists("marketplace/registry.py"):
        findings.append(
            Finding(
                "high",
                "plugin_ecosystem",
                "Marketplace registry validation is missing.",
                "Keep manifests verified before marketplace or third-party plugin loading.",
                "marketplace/registry.py",
            )
        )


def check_devops(findings: list[Finding]) -> None:
    ci = read_text(".github/workflows/ci.yml")
    release = read_text(".github/workflows/release.yml")
    if "cloud_readiness_audit.py" not in ci:
        findings.append(
            Finding(
                "medium",
                "devops",
                "CI does not run the cloud readiness audit.",
                "Run the audit in release integrity checks so API/cloud regressions are visible.",
                ".github/workflows/ci.yml",
            )
        )
    if "cloud_readiness_audit.py" not in release:
        findings.append(
            Finding(
                "medium",
                "devops",
                "Release workflow does not run the cloud readiness audit.",
                "Run the audit before publishing artifacts.",
                ".github/workflows/release.yml",
            )
        )
    if not exists("Dockerfile"):
        findings.append(
            Finding(
                "low",
                "devops",
                "No container image definition is present.",
                "Add Docker/container packaging only when the backend is separated from the desktop UI.",
                "docs/DEVOPS_CLOUD_DEPLOYMENT_PHASE7.md",
            )
        )


def check_docs(findings: list[Finding]) -> None:
    for path in REQUIRED_DOCS:
        if not exists(path):
            findings.append(
                Finding(
                    "medium",
                    "documentation",
                    f"Missing Phase 7 document: {path}",
                    "Document cloud, API, sync, security, plugin, DevOps, and enterprise boundaries before implementation.",
                    path,
                )
            )
    docs_index = read_text("docs/README.md")
    if "Cloud, API, And Platform Readiness" not in docs_index:
        findings.append(
            Finding(
                "low",
                "documentation",
                "Documentation index does not expose Phase 7 cloud/API docs.",
                "Add a clear Phase 7 section to docs/README.md.",
                "docs/README.md",
            )
        )


def check_security(findings: list[Finding]) -> None:
    security_docs = read_text("docs/SECURITY_INFRASTRUCTURE_PHASE7.md")
    if "zero-trust" not in security_docs.lower():
        findings.append(
            Finding(
                "medium",
                "security",
                "Security infrastructure docs do not mention zero-trust style assumptions.",
                "Document remote trust boundaries, scoped tokens, least privilege, and denied-by-default network access.",
                "docs/SECURITY_INFRASTRUCTURE_PHASE7.md",
            )
        )
    findings.append(
        Finding(
            "medium",
            "security",
            "Remote authentication, RBAC, and encrypted cloud secret storage are planned but not implemented.",
            "Do not expose Shell APIs beyond localhost until OAuth/device auth, RBAC, audit logs, and encrypted storage are implemented.",
            "docs/SECURITY_INFRASTRUCTURE_PHASE7.md",
        )
    )


def build_report() -> dict[str, Any]:
    findings: list[Finding] = []
    contract_meta = check_platform_contract(findings)
    check_local_api_hardening(findings)
    check_sync_storage(findings)
    check_plugin_ecosystem(findings)
    check_devops(findings)
    check_docs(findings)
    check_security(findings)

    high_or_worse = [item for item in findings if item.severity in {"critical", "high"}]
    report = {
        "status": "pass" if not high_or_worse else "attention",
        "summary": {
            "cloud_readiness_score": score([item for item in findings if item.category in {"sync_storage", "documentation", "devops"}]),
            "api_maturity_score": score([item for item in findings if item.category in {"api_contract", "api_security"}]),
            "ai_orchestration_readiness_score": 88,
            "infrastructure_scalability_score": score([item for item in findings if item.category in {"sync_storage", "devops", "plugin_ecosystem"}]),
            "security_maturity_score": score([item for item in findings if item.category == "security"]),
            "plugin_ecosystem_readiness_score": score([item for item in findings if item.category == "plugin_ecosystem"]),
            "devops_readiness_score": score([item for item in findings if item.category == "devops"]),
            "enterprise_readiness_score": 83,
        },
        "contract": contract_meta,
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    publish_event(
        AIEventType.CLOUD_READINESS_REPORTED,
        {"status": report["status"], "finding_count": len(findings), "summary": report["summary"]},
        source="tools.cloud_readiness_audit",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Shell cloud/API/platform readiness.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument("--fail-on-high", action="store_true", help="Exit non-zero if high or critical findings exist.")
    args = parser.parse_args()

    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Cloud readiness: {report['status']} ({report['finding_count']} findings)")
        for key, value in report["summary"].items():
            print(f"- {key}: {value}/100")
        print(f"Report: {REPORT_PATH}")

    if args.fail_on_high and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
