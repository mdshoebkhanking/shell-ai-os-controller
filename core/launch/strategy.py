from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LaunchStage(str, Enum):
    PRIVATE_ALPHA = "private_alpha"
    PUBLIC_BETA = "public_beta"
    RELEASE_CANDIDATE = "release_candidate"
    PUBLIC_GA = "public_ga"
    ENTERPRISE_READY = "enterprise_ready"


class DistributionChannel(str, Enum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    PORTABLE_ZIP = "portable_zip"
    SOURCE = "source"
    WEBSITE = "website"


class TrustSignal(str, Enum):
    LICENSE = "license"
    SECURITY_POLICY = "security_policy"
    CODE_OF_CONDUCT = "code_of_conduct"
    CONTRIBUTING = "contributing"
    CHECKSUMS = "checksums"
    SIGNED_RELEASES = "signed_releases"
    PROVENANCE = "provenance"
    TESTS = "tests"
    RELEASE_NOTES = "release_notes"
    GOVERNANCE = "governance"
    SUPPORT = "support"


STAGE_ORDER = {
    LaunchStage.PRIVATE_ALPHA: 1,
    LaunchStage.PUBLIC_BETA: 2,
    LaunchStage.RELEASE_CANDIDATE: 3,
    LaunchStage.PUBLIC_GA: 4,
    LaunchStage.ENTERPRISE_READY: 5,
}


@dataclass(frozen=True)
class LaunchChecklistItem:
    item_id: str
    category: str
    description: str
    required_for: LaunchStage
    complete: bool = False
    path: str = ""

    def is_blocking_for(self, stage: LaunchStage) -> bool:
        return STAGE_ORDER[self.required_for] <= STAGE_ORDER[stage] and not self.complete

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "category": self.category,
            "description": self.description,
            "required_for": self.required_for.value,
            "complete": self.complete,
            "path": self.path,
        }


@dataclass(frozen=True)
class DistributionArtifact:
    name: str
    channel: DistributionChannel
    format: str
    signed: bool = False
    notarized: bool = False
    checksum: bool = False
    auto_update_ready: bool = False
    enterprise_ready: bool = False

    def trust_score(self) -> int:
        score = 20
        score += 20 if self.checksum else 0
        score += 25 if self.signed else 0
        score += 15 if self.notarized else 0
        score += 10 if self.auto_update_ready else 0
        score += 10 if self.enterprise_ready else 0
        return min(score, 100)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "channel": self.channel.value,
            "format": self.format,
            "signed": self.signed,
            "notarized": self.notarized,
            "checksum": self.checksum,
            "auto_update_ready": self.auto_update_ready,
            "enterprise_ready": self.enterprise_ready,
            "trust_score": self.trust_score(),
        }


@dataclass(frozen=True)
class LaunchPlan:
    version: str
    stage: LaunchStage
    checklist: list[LaunchChecklistItem] = field(default_factory=list)
    artifacts: list[DistributionArtifact] = field(default_factory=list)
    trust_signals: list[TrustSignal] = field(default_factory=list)

    def blockers(self) -> list[LaunchChecklistItem]:
        return [item for item in self.checklist if item.is_blocking_for(self.stage)]

    def readiness_score(self) -> int:
        if not self.checklist:
            return 0
        required = [item for item in self.checklist if STAGE_ORDER[item.required_for] <= STAGE_ORDER[self.stage]]
        if not required:
            return 100
        complete = [item for item in required if item.complete]
        return round((len(complete) / len(required)) * 100)

    def distribution_score(self) -> int:
        if not self.artifacts:
            return 0
        return round(sum(artifact.trust_score() for artifact in self.artifacts) / len(self.artifacts))

    def trust_score(self) -> int:
        required = {
            TrustSignal.LICENSE,
            TrustSignal.SECURITY_POLICY,
            TrustSignal.CODE_OF_CONDUCT,
            TrustSignal.CONTRIBUTING,
            TrustSignal.CHECKSUMS,
            TrustSignal.TESTS,
            TrustSignal.RELEASE_NOTES,
        }
        present = set(self.trust_signals)
        return round((len(required & present) / len(required)) * 100)

    def distribution_matrix(self) -> dict[str, dict[str, Any]]:
        return {artifact.channel.value: artifact.to_dict() for artifact in self.artifacts}

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "stage": self.stage.value,
            "readiness_score": self.readiness_score(),
            "distribution_score": self.distribution_score(),
            "trust_score": self.trust_score(),
            "blockers": [item.to_dict() for item in self.blockers()],
            "checklist": [item.to_dict() for item in self.checklist],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "trust_signals": [signal.value for signal in self.trust_signals],
        }
