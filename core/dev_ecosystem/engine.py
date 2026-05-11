from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.dev_platform import DevPlatformAnalysis, DevPlatformAnalyzer
from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class DevEcosystemReport:
    analysis: DevPlatformAnalysis
    ci_files: list[str] = field(default_factory=list)
    dependency_files: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis": self.analysis.to_dict(),
            "ci_files": list(self.ci_files),
            "dependency_files": list(self.dependency_files),
            "diagnostics": list(self.diagnostics),
        }


class DevEcosystemEngine:
    def __init__(self, analyzer: DevPlatformAnalyzer | None = None):
        self.analyzer = analyzer or DevPlatformAnalyzer()

    def inspect(self, root: str | Path) -> DevEcosystemReport:
        analysis = self.analyzer.analyze(root)
        build_files = set(analysis.build_files)
        ci_files = sorted([path for path in build_files if ".github" in path or "workflow" in path])
        dependency_files = sorted([path for path in build_files if Path(path).name in {"requirements.txt", "package.json", "pyproject.toml"}])
        diagnostics = []
        if not ci_files:
            diagnostics.append("no CI workflow detected")
        if not dependency_files:
            diagnostics.append("no dependency manifest detected")
        report = DevEcosystemReport(analysis, ci_files, dependency_files, diagnostics)
        publish_event(AIEventType.DEV_ECOSYSTEM_ANALYSIS, report.to_dict(), source="core.dev_ecosystem")
        return report

