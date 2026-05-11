from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EcosystemDimension(str, Enum):
    ARCHITECTURE = "architecture"
    SCALABILITY = "scalability"
    AI_INFRASTRUCTURE = "ai_infrastructure"
    SECURITY = "security"
    OPEN_SOURCE = "open_source"
    DEVOPS = "devops"
    UI_UX = "ui_ux"
    BRANDING = "branding"
    ONBOARDING = "onboarding"
    ENTERPRISE = "enterprise"
    PLUGIN = "plugin"
    AUTOMATION = "automation"
    SUSTAINABILITY = "sustainability"


@dataclass(frozen=True)
class EcosystemFinding:
    severity: str
    dimension: EcosystemDimension
    message: str
    recommendation: str
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "dimension": self.dimension.value,
            "message": self.message,
            "recommendation": self.recommendation,
            "path": self.path,
        }


@dataclass(frozen=True)
class EcosystemScorecard:
    scores: dict[EcosystemDimension, int]

    def overall(self) -> int:
        if not self.scores:
            return 0
        weights = {
            EcosystemDimension.ARCHITECTURE: 1.2,
            EcosystemDimension.SECURITY: 1.2,
            EcosystemDimension.DEVOPS: 1.1,
            EcosystemDimension.ONBOARDING: 1.1,
            EcosystemDimension.ENTERPRISE: 0.9,
        }
        total_weight = 0.0
        weighted = 0.0
        for dimension, score in self.scores.items():
            weight = weights.get(dimension, 1.0)
            weighted += score * weight
            total_weight += weight
        return round(weighted / total_weight)

    def to_dict(self) -> dict[str, Any]:
        rows = {dimension.value: score for dimension, score in self.scores.items()}
        rows["overall_ecosystem_maturity"] = self.overall()
        return rows


@dataclass(frozen=True)
class EcosystemMaturityReport:
    scorecard: EcosystemScorecard
    findings: list[EcosystemFinding] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    roadmap_priorities: list[str] = field(default_factory=list)

    def status(self) -> str:
        if any(finding.severity in {"critical", "high"} for finding in self.findings):
            return "attention"
        return "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status(),
            "summary": self.scorecard.to_dict(),
            "finding_count": len(self.findings),
            "findings": [finding.to_dict() for finding in self.findings],
            "opportunities": list(self.opportunities),
            "roadmap_priorities": list(self.roadmap_priorities),
        }
