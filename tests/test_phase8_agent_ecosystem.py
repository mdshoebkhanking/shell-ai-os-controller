import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_agent_audit_module():
    path = ROOT / "tools" / "agent_ecosystem_audit.py"
    spec = importlib.util.spec_from_file_location("agent_ecosystem_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_agent_registry_plans_safe_task_and_blocks_risky_task_without_approval():
    from core.agent_ecosystem import (
        AgentCapability,
        AgentEcosystemRegistry,
        AgentProfile,
        AgentRiskLevel,
        AgentRole,
        AgentTask,
    )

    registry = AgentEcosystemRegistry()
    registry.register(AgentProfile("planner", AgentRole.PLANNER, "Planner", [AgentCapability("plan.workflow")]))
    registry.register(AgentProfile("executor", AgentRole.EXECUTOR, "Executor", [AgentCapability("execute.tool", risk_level=AgentRiskLevel.CAUTION)]))
    registry.register(AgentProfile("validator", AgentRole.VALIDATOR, "Validator", [AgentCapability("validate.result")]))

    safe_plan = registry.plan(AgentTask("plan", ["plan.workflow"]))
    risky_plan = registry.plan(AgentTask("desktop", ["execute.tool"], risk_level=AgentRiskLevel.DANGEROUS))

    assert safe_plan.blocked == []
    assert safe_plan.assignments[0].allowed is True
    assert risky_plan.requires_approval is True
    assert risky_plan.assignments[0].allowed is False


def test_agent_memory_binding_respects_requested_scopes():
    from core.agent_ecosystem import AgentEcosystemRegistry, AgentTask, MemoryScope

    task = AgentTask("remember project", [], memory_scopes=[MemoryScope.CONTEXTUAL, MemoryScope.LONG_TERM])
    binding = AgentEcosystemRegistry().bind_memory(task, [MemoryScope.CONTEXTUAL])

    assert binding["granted"] == ["contextual"]
    assert binding["denied"] == ["long_term"]
    assert binding["privacy_safe"] is False


def test_agent_message_is_structured_for_observable_handoffs():
    from core.agent_ecosystem import AgentEcosystemRegistry, MessageIntent

    message = AgentEcosystemRegistry().message("planner", "executor", MessageIntent.DELEGATE, {"goal": "test"}, task_id="task-1", trace_id="trace-1")

    assert message.to_dict()["intent"] == "delegate"
    assert message.to_dict()["trace_id"] == "trace-1"
    assert message.to_dict()["task_id"] == "task-1"


def test_automation_template_validator_requires_approval_for_risky_templates():
    from core.agent_ecosystem import AgentRiskLevel
    from marketplace import AutomationTemplate, AutomationTemplateStep, AutomationTemplateValidator

    risky = AutomationTemplate(
        template_id="risky",
        name="Risky",
        description="Writes files",
        trigger="manual",
        steps=[AutomationTemplateStep("write.file")],
        required_permissions=["filesystem.write"],
        risk_level=AgentRiskLevel.DANGEROUS,
        marketplace_ready=True,
        author="mdshoebking",
    )
    safe = AutomationTemplate(
        template_id="safe",
        name="Safe",
        description="Summarizes text",
        trigger="manual",
        steps=[AutomationTemplateStep("summarize.text")],
        required_permissions=[],
        marketplace_ready=True,
        author="mdshoebking",
    )

    validator = AutomationTemplateValidator()

    assert any("approval" in item["message"] for item in validator.validate(risky))
    assert validator.validate(safe) == []


def test_phase8_sdk_permissions_are_explicit():
    from sdk.manifest import ExtensionManifest

    manifest = ExtensionManifest.from_dict(
        {
            "name": "agent-pack",
            "version": "1.0.0",
            "shell_api": "1.x",
            "kind": "agent",
            "entrypoint": "agent.py",
            "permissions": ["agent.spawn", "agent.delegate", "automation.share", "marketplace.publish", "marketplace.install", "multimodal.capture"],
        }
    )

    assert "agent.spawn" in manifest.permissions
    assert "marketplace.publish" in manifest.permissions


def test_agent_ecosystem_audit_reports_scores_without_high_findings():
    module = load_agent_audit_module()
    report = module.build_report()

    assert report["status"] == "pass"
    assert report["summary"]["ai_agent_readiness_score"] >= 85
    assert report["summary"]["safety_architecture_score"] >= 90
    assert report["summary"]["developer_extensibility_score"] >= 85


def test_phase8_docs_are_linked_from_public_docs_and_readme():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required = [
        "AI_AGENT_ECOSYSTEM_PHASE8.md",
        "MULTI_AGENT_ORCHESTRATION_PHASE8.md",
        "AI_MEMORY_SYSTEM_PHASE8.md",
        "TOOL_EXECUTION_AUTOMATION_PHASE8.md",
        "AUTOMATION_MARKETPLACE_PHASE8.md",
        "AGENT_SAFETY_GOVERNANCE_PHASE8.md",
        "VOICE_MULTIMODAL_FUTURE_PHASE8.md",
        "DEVELOPER_SDK_ECOSYSTEM_PHASE8.md",
    ]

    for doc in required:
        assert (ROOT / "docs" / doc).exists()
        assert doc in docs_index
        assert doc in readme


def test_ci_and_release_run_agent_ecosystem_gate():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "tools/agent_ecosystem_audit.py" in ci
    assert "tools/agent_ecosystem_audit.py" in release
    assert "--fail-on-high" in ci
    assert "--fail-on-high" in release
