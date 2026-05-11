from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.agent_ecosystem import AgentRiskLevel
from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class AutomationTemplateStep:
    action: str
    params_schema: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    rollback: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "params_schema": dict(self.params_schema),
            "requires_approval": self.requires_approval,
            "rollback": self.rollback,
        }


@dataclass(frozen=True)
class AutomationTemplate:
    template_id: str
    name: str
    description: str
    trigger: str
    steps: list[AutomationTemplateStep]
    required_permissions: list[str] = field(default_factory=list)
    risk_level: AgentRiskLevel = AgentRiskLevel.SAFE
    author: str = "local"
    version: str = "1.0.0"
    marketplace_ready: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "steps": [step.to_dict() for step in self.steps],
            "required_permissions": list(self.required_permissions),
            "risk_level": self.risk_level.value,
            "author": self.author,
            "version": self.version,
            "marketplace_ready": self.marketplace_ready,
        }


class AutomationTemplateValidator:
    RISKY_PERMISSIONS = {"shell.execute", "desktop.control", "filesystem.write", "api.keys", "cloud.execute"}

    def validate(self, template: AutomationTemplate) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        if not template.template_id or not template.name or not template.steps:
            findings.append({"severity": "high", "message": "automation template requires id, name, and at least one step"})
        risky_permissions = sorted(set(template.required_permissions) & self.RISKY_PERMISSIONS)
        risky_template = template.risk_level in {AgentRiskLevel.DANGEROUS, AgentRiskLevel.CRITICAL} or bool(risky_permissions)
        if risky_template and not any(step.requires_approval for step in template.steps):
            findings.append({"severity": "high", "message": "risky automation requires at least one explicit approval step"})
        if template.marketplace_ready and risky_template and not all(step.rollback or step.requires_approval for step in template.steps):
            findings.append({"severity": "medium", "message": "marketplace risky automation needs rollback notes or approval on every step"})
        if template.marketplace_ready and template.author == "local":
            findings.append({"severity": "medium", "message": "marketplace automation should use a verified publisher identity"})
        publish_event(
            AIEventType.AUTOMATION_TEMPLATE_VALIDATED,
            {"template_id": template.template_id, "finding_count": len(findings), "marketplace_ready": template.marketplace_ready},
            source="marketplace.automation_templates",
        )
        return findings

    def marketplace_decision(self, template: AutomationTemplate) -> dict[str, Any]:
        findings = self.validate(template)
        high = [item for item in findings if item.get("severity") == "high"]
        decision = {
            "template_id": template.template_id,
            "approved_for_listing": template.marketplace_ready and not high,
            "finding_count": len(findings),
            "findings": findings,
        }
        publish_event(AIEventType.MARKETPLACE_PACKAGE_EVALUATED, decision, source="marketplace.automation_templates")
        return decision
