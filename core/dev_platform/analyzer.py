from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event
from core.filesystem_ai import ProjectIndexer


@dataclass(frozen=True)
class DevPlatformAnalysis:
    root: str
    languages: list[str] = field(default_factory=list)
    build_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "languages": list(self.languages),
            "build_files": list(self.build_files),
            "test_files": list(self.test_files),
            "recommendations": list(self.recommendations),
        }


class DevPlatformAnalyzer:
    LANGUAGE_BY_SUFFIX = {".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript", ".jsx": "javascript"}
    BUILD_FILES = {"requirements.txt", "pyproject.toml", "package.json", "pytest.ini"}

    def __init__(self, indexer: ProjectIndexer | None = None):
        self.indexer = indexer or ProjectIndexer()

    def analyze(self, root: str | Path) -> DevPlatformAnalysis:
        index = self.indexer.build(root, limit=1500)
        languages = sorted({self.LANGUAGE_BY_SUFFIX[f.suffix] for f in index.files if f.suffix in self.LANGUAGE_BY_SUFFIX})
        build_files = sorted([f.path for f in index.files if Path(f.path).name in self.BUILD_FILES])
        test_files = sorted([f.path for f in index.files if "test" in Path(f.path).name.lower()])
        recommendations: list[str] = []
        if "python" in languages and not any(Path(path).name == "pytest.ini" for path in build_files):
            recommendations.append("add pytest configuration")
        if not test_files:
            recommendations.append("add focused regression tests")
        analysis = DevPlatformAnalysis(index.root, languages, build_files, test_files, recommendations)
        publish_event(AIEventType.DEV_PLATFORM_ANALYSIS, analysis.to_dict(), source="core.dev_platform")
        return analysis
