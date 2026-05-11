from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class WorkspaceMode(str, Enum):
    CODING = "coding"
    WRITING = "writing"
    BROWSING = "browsing"
    MEDIA = "media"
    RESEARCH = "research"
    GENERAL = "general"


@dataclass(frozen=True)
class WorkspaceState:
    root: str
    mode: WorkspaceMode
    languages: list[str] = field(default_factory=list)
    active_project: str = ""
    git_branch: str = ""
    dirty_git: bool = False
    recent_files: list[str] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "mode": self.mode.value,
            "languages": list(self.languages),
            "active_project": self.active_project,
            "git_branch": self.git_branch,
            "dirty_git": self.dirty_git,
            "recent_files": list(self.recent_files),
            "signals": dict(self.signals),
        }


class WorkspaceDetector:
    CODE_EXTS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".swift": "swift",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".cs": "csharp",
    }
    WRITING_EXTS = {".md", ".txt", ".docx", ".rtf"}
    MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".mp4", ".mov", ".wav", ".mp3"}

    def detect(self, cwd: str | Path) -> WorkspaceState:
        root = self._project_root(Path(cwd).resolve())
        files = self._recent_files(root)
        languages = sorted({self.CODE_EXTS.get(path.suffix.lower(), "") for path in files} - {""})
        mode = self._mode(files, languages)
        branch, dirty = self._git_state(root)
        signals = {
            "has_requirements": (root / "requirements.txt").exists(),
            "has_package_json": (root / "package.json").exists(),
            "has_pyproject": (root / "pyproject.toml").exists(),
            "has_git": (root / ".git").exists(),
        }
        return WorkspaceState(
            root=str(root),
            mode=mode,
            languages=languages,
            active_project=root.name,
            git_branch=branch,
            dirty_git=dirty,
            recent_files=[str(path.relative_to(root)) for path in files[:25]],
            signals=signals,
        )

    def _project_root(self, path: Path) -> Path:
        current = path if path.is_dir() else path.parent
        for candidate in [current, *current.parents]:
            if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists() or (candidate / "package.json").exists():
                return candidate
        return current

    def _recent_files(self, root: Path) -> list[Path]:
        files: list[Path] = []
        skip = {".git", "__pycache__", "node_modules", "venv", ".codex_ui_venv"}
        try:
            for path in root.rglob("*"):
                if len(files) > 300:
                    break
                if any(part in skip for part in path.parts):
                    continue
                if path.is_file():
                    files.append(path)
        except Exception:
            return []
        files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        return files

    def _mode(self, files: list[Path], languages: list[str]) -> WorkspaceMode:
        if languages:
            return WorkspaceMode.CODING
        suffixes = {p.suffix.lower() for p in files[:50]}
        if suffixes & self.MEDIA_EXTS:
            return WorkspaceMode.MEDIA
        if suffixes & self.WRITING_EXTS:
            return WorkspaceMode.WRITING
        if any("research" in p.name.lower() or "notes" in p.name.lower() for p in files[:50]):
            return WorkspaceMode.RESEARCH
        return WorkspaceMode.GENERAL

    def _git_state(self, root: Path) -> tuple[str, bool]:
        if not (root / ".git").exists():
            return "", False
        try:
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(root),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            ).stdout.strip()
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(root),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            ).stdout.strip()
            return branch, bool(status)
        except Exception:
            return "", False

