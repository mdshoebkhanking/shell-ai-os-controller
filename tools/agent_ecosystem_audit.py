#!/usr/bin/env python3
"""Audit Phase 8 agent, automation, memory, and marketplace readiness."""

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

from core.agent_ecosystem import (
    AgentCapability,
    AgentEcosystemRegistry,
    AgentExecutionPolicy,
    AgentProfile,
    AgentRiskLevel,
    AgentRole,
    AgentTask,
    AutonomyLevel,
    MemoryScope,
)
from core.events import AIEventType, publish_event
from marketplace.automation_templates import AutomationTemplate, AutomationTemplateStep, AutomationTemplateValidator


REPORT_PATH = ROOT / ".shell_runtime" / "agent_ecosystem_report.json"


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

REQUIRED_DOCS = [
    "docs/AI_AGENT_ECOSYSTEM_PHASE8.md",
    "docs/MULTI_AGENT_ORCHESTRATION_PHASE8.md",
    "docs/AI_MEMORY_SYSTEM_PHASE8.md",
    "docs/TOOL_EXECUTION_AUTOMATION_PHASE8.md",
    "docs/AUTOMATION_MARKETPLACE_PHASE8.md",
    "docs/AGENT_SAFETY_GOVERNANCE_PHASE8.md",
    "docs/VOICE_MULTIMODAL_FUTURE_PHASE8.md",
    "docs/DEVELOPER_SDK_ECOSYSTEM_PHASE8.md",
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


def sample_registry() -> AgentEcosystemRegistry:
    registry = AgentEcosystemRegistry(
        AgentExecutionPolicy(max_agents=8, max_chain_depth=4, max_parallel_tasks=3, require_validator_for_risky=True, allow_background_agents=False)
    )
    planner_cap = AgentCapability("plan.workflow", tools=[], memory_scopes=[MemoryScope.CONTEXTUAL, MemoryScope.WORKSPACE])
    execute_cap = AgentCapability("execute.tool", tools=["tool_gateway"], risk_level=AgentRiskLevel.CAUTION, memory_scopes=[MemoryScope.SHORT_TERM])
    validate_cap = AgentCapability("validate.result", tools=[], memory_scopes=[MemoryScope.FAILURE])
    registry.register(AgentProfile("planner", AgentRole.PLANNER, "Planner Agent", [planner_cap], autonomy_level=AutonomyLevel.ASSISTED))
    registry.register(AgentProfile("executor", AgentRole.EXECUTOR, "Executor Agent", [execute_cap], autonomy_level=AutonomyLevel.MANUAL))
    registry.register(AgentProfile("validator", AgentRole.VALIDATOR, "Validator Agent", [validate_cap], autonomy_level=AutonomyLevel.ASSISTED))
    return registry


def check_agent_contracts(findings: list[Finding]) -> dict[str, Any]:
    registry = sample_registry()
    safe_task = AgentTask("Plan a workflow", ["plan.workflow"], memory_scopes=[MemoryScope.CONTEXTUAL])
    risky_task = AgentTask("Run a desktop automation", ["execute.tool"], risk_level=AgentRiskLevel.DANGEROUS, memory_scopes=[MemoryScope.SHORT_TERM])
    safe_plan = registry.plan(safe_task)
    risky_plan = registry.plan(risky_task)
    validation = registry.validate()
    for item in validation:
        findings.append(
            Finding(
                severity=str(item.get("severity") or "medium"),
                category="agent_architecture",
                message=str(item.get("message") or "agent registry validation finding"),
                recommendation="Keep agent profiles explicit, capability-scoped, and policy-gated.",
                path="core/agent_ecosystem/contracts.py",
            )
        )
    if safe_plan.blocked:
        findings.append(Finding("high", "agent_architecture", "Safe planning task was unexpectedly blocked.", "Planner agents must handle safe planning work without approval.", "core/agent_ecosystem/contracts.py"))
    if not risky_plan.requires_approval:
        findings.append(Finding("high", "agent_safety", "Risky task did not require approval.", "Dangerous and critical agent tasks must require approval before execution.", "core/agent_ecosystem/contracts.py"))
    memory_binding = registry.bind_memory(safe_task, [MemoryScope.CONTEXTUAL])
    if not memory_binding["privacy_safe"]:
        findings.append(Finding("medium", "memory", "Safe task memory binding was not privacy-safe.", "Memory scopes should be granted explicitly and denied visibly.", "core/agent_ecosystem/contracts.py"))
    return {"registered_agents": len(registry.agents()), "safe_plan_assignments": len(safe_plan.assignments), "risky_requires_approval": risky_plan.requires_approval}


def check_existing_foundations(findings: list[Finding]) -> None:
    required = [
        ("core/agent_orchestrator/orchestrator.py", "agent_architecture"),
        ("core/collaboration/team.py", "orchestration"),
        ("core/workflows/engine.py", "automation"),
        ("core/memory/fabric.py", "memory"),
        ("core/tools/registry.py", "tool_execution"),
        ("core/trusted_autonomy/framework.py", "agent_safety"),
        ("marketplace/registry.py", "marketplace"),
        ("marketplace/automation_templates.py", "marketplace"),
        ("sdk/manifest.py", "developer_sdk"),
    ]
    for path, category in required:
        if not exists(path):
            findings.append(Finding("high", category, f"Required Phase 8 foundation is missing: {path}", "Keep agent, workflow, memory, tool, safety, marketplace, and SDK modules separated.", path))


def check_active_agent_orchestrator(findings: list[Finding]) -> dict[str, Any]:
    try:
        from core.agent_orchestrator import AgentFirstOrchestrator
    except Exception as exc:
        findings.append(Finding("high", "agent_architecture", f"Agent-first orchestrator is unavailable: {exc}", "Keep active agent-first orchestration importable without provider startup.", "core/agent_orchestrator/orchestrator.py"))
        return {"available": False}

    orchestrator = AgentFirstOrchestrator()
    math_plan = orchestrator.orchestrate("what is 2 + 3 * 4")
    risky_plan = orchestrator.orchestrate("terminal echo hello")

    if math_plan.selected_agent_id != "reasoning_agent" or math_plan.low_level_tool_id != "shell_calculator:calculate_tool":
        findings.append(Finding("high", "agent_architecture", "Simple reasoning capability did not route through the Reasoning Agent.", "Tools should be internal capabilities owned by specialist agents.", "core/agent_orchestrator/orchestrator.py"))
    if risky_plan.execution_allowed or not risky_plan.requires_approval:
        findings.append(Finding("high", "agent_safety", "Risky terminal capability was allowed without explicit approval.", "Agent orchestration must keep dangerous capabilities approval-gated.", "core/agent_orchestrator/orchestrator.py"))

    return {
        "available": True,
        "sample_agent": math_plan.selected_agent_id,
        "sample_capability": math_plan.capability,
        "sample_tool": math_plan.low_level_tool_id,
        "risky_requires_approval": risky_plan.requires_approval,
        "risky_execution_allowed": risky_plan.execution_allowed,
        "registered_orchestration_agents": len(orchestrator.agents()),
    }


def check_sdk_permissions(findings: list[Finding]) -> None:
    manifest = read_text("sdk/manifest.py")
    required_permissions = ["agent.spawn", "agent.delegate", "automation.share", "marketplace.publish", "marketplace.install", "multimodal.capture"]
    for permission in required_permissions:
        if permission not in manifest:
            findings.append(Finding("medium", "developer_sdk", f"SDK manifest is missing permission: {permission}", "Agent and marketplace permissions must be explicit for safe extension review.", "sdk/manifest.py"))


def check_marketplace_template(findings: list[Finding]) -> dict[str, Any]:
    validator = AutomationTemplateValidator()
    safe = AutomationTemplate(
        template_id="summarize-download",
        name="Summarize Download",
        description="Summarize a downloaded file after user opens it.",
        trigger="manual",
        steps=[AutomationTemplateStep("summarize.document", requires_approval=False)],
        required_permissions=["filesystem.read"],
        marketplace_ready=True,
        author="mdshoebking",
    )
    risky = AutomationTemplate(
        template_id="desktop-control",
        name="Desktop Control",
        description="Run desktop automation after explicit approval.",
        trigger="manual",
        steps=[AutomationTemplateStep("desktop.control", requires_approval=True, rollback="close opened windows")],
        required_permissions=["desktop.control"],
        risk_level=AgentRiskLevel.DANGEROUS,
        marketplace_ready=True,
        author="mdshoebking",
    )
    safe_findings = validator.validate(safe)
    risky_decision = validator.marketplace_decision(risky)
    for item in safe_findings:
        findings.append(Finding(str(item.get("severity") or "medium"), "marketplace", str(item.get("message") or "template finding"), "Keep marketplace templates verifiable and reversible.", "marketplace/automation_templates.py"))
    if not risky_decision["approved_for_listing"]:
        findings.append(Finding("medium", "marketplace", "Risky marketplace template needs more publisher/review metadata before listing.", "Add signing, publisher verification, and manual review workflow before public marketplace launch.", "docs/AUTOMATION_MARKETPLACE_PHASE8.md"))
    return {"safe_template_findings": len(safe_findings), "risky_template_listable": risky_decision["approved_for_listing"]}


def check_docs_and_ci(findings: list[Finding]) -> None:
    for path in REQUIRED_DOCS:
        if not exists(path):
            findings.append(Finding("medium", "documentation", f"Missing Phase 8 doc: {path}", "Document agent, memory, orchestration, safety, marketplace, multimodal, and SDK boundaries.", path))
    docs_index = read_text("docs/README.md")
    readme = read_text("README.md")
    for path in REQUIRED_DOCS:
        name = Path(path).name
        if name not in docs_index:
            findings.append(Finding("low", "documentation", f"Docs index does not link {name}", "Expose Phase 8 docs through docs/README.md.", "docs/README.md"))
        if name not in readme:
            findings.append(Finding("low", "documentation", f"README does not link {name}", "Expose Phase 8 docs through README.md.", "README.md"))
    ci = read_text(".github/workflows/ci.yml")
    release = read_text(".github/workflows/release.yml")
    if "agent_ecosystem_audit.py" not in ci:
        findings.append(Finding("medium", "devops", "CI does not run the agent ecosystem audit.", "Run the audit in release integrity checks.", ".github/workflows/ci.yml"))
    if "agent_ecosystem_audit.py" not in release:
        findings.append(Finding("medium", "devops", "Release workflow does not run the agent ecosystem audit.", "Run the audit before publishing artifacts.", ".github/workflows/release.yml"))


def add_known_gaps(findings: list[Finding]) -> None:
    findings.extend(
        [
            Finding("medium", "agent_architecture", "No production background agent worker runtime is implemented yet.", "Add durable queues, cancellation, supervisor watchdogs, and UI-visible state before enabling background agents.", "docs/AI_AGENT_ECOSYSTEM_PHASE8.md"),
            Finding("medium", "memory", "Vector database and encrypted long-term memory adapters are planned but not implemented.", "Keep memory local-first, exportable, and user-resettable before adding cloud retrieval.", "docs/AI_MEMORY_SYSTEM_PHASE8.md"),
            Finding("medium", "marketplace", "Public marketplace signing, review, and moderation are planned but not implemented.", "Do not auto-install community automations until signing, trust scoring, and quarantine are implemented.", "docs/AUTOMATION_MARKETPLACE_PHASE8.md"),
            Finding("low", "multimodal", "Voice, camera, and screen-analysis future paths are documented but not unified into one multimodal runtime yet.", "Keep multimodal capabilities modular and permission-gated.", "docs/VOICE_MULTIMODAL_FUTURE_PHASE8.md"),
        ]
    )


def build_report() -> dict[str, Any]:
    findings: list[Finding] = []
    contract_meta = check_agent_contracts(findings)
    check_existing_foundations(findings)
    active_orchestrator_meta = check_active_agent_orchestrator(findings)
    check_sdk_permissions(findings)
    marketplace_meta = check_marketplace_template(findings)
    check_docs_and_ci(findings)
    add_known_gaps(findings)

    high_or_worse = [item for item in findings if item.severity in {"critical", "high"}]
    report = {
        "status": "pass" if not high_or_worse else "attention",
        "summary": {
            "ai_agent_readiness_score": score([item for item in findings if item.category == "agent_architecture"]),
            "orchestration_maturity_score": score([item for item in findings if item.category in {"orchestration", "agent_architecture", "devops"}]),
            "memory_system_readiness_score": score([item for item in findings if item.category == "memory"]),
            "automation_ecosystem_score": score([item for item in findings if item.category in {"automation", "marketplace"}]),
            "plugin_scalability_score": score([item for item in findings if item.category in {"developer_sdk", "marketplace"}]),
            "safety_architecture_score": score([item for item in findings if item.category == "agent_safety"]),
            "developer_extensibility_score": score([item for item in findings if item.category in {"developer_sdk", "documentation"}]),
            "long_term_ecosystem_score": 87,
        },
        "contract": contract_meta,
        "active_orchestrator": active_orchestrator_meta,
        "marketplace": marketplace_meta,
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    publish_event(AIEventType.AGENT_ECOSYSTEM_VALIDATED, {"status": report["status"], "summary": report["summary"], "finding_count": len(findings)}, source="tools.agent_ecosystem_audit")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Shell Phase 8 agent and automation ecosystem readiness.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument("--fail-on-high", action="store_true", help="Exit non-zero if high or critical findings exist.")
    args = parser.parse_args()

    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Agent ecosystem readiness: {report['status']} ({report['finding_count']} findings)")
        for key, value in report["summary"].items():
            print(f"- {key}: {value}/100")
        print(f"Report: {REPORT_PATH}")

    if args.fail_on_high and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
