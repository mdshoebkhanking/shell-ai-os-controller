from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FileIndexEntry:
    path: str
    suffix: str
    size: int
    mtime: float
    digest: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "suffix": self.suffix, "size": self.size, "mtime": self.mtime, "digest": self.digest, "tags": list(self.tags)}


@dataclass(frozen=True)
class ProjectIndex:
    root: str
    generated_at: float
    files: list[FileIndexEntry]
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"root": self.root, "generated_at": self.generated_at, "files": [f.to_dict() for f in self.files], "summary": dict(self.summary)}


class ProjectIndexer:
    SKIP_DIRS = {".git", "__pycache__", "node_modules", "venv", ".codex_ui_venv", ".pytest_cache"}

    def __init__(self, cache_path: str | Path = ".shell_runtime/project_index.json"):
        self.cache_path = Path(cache_path)

    def build(self, root: str | Path, *, limit: int = 1000) -> ProjectIndex:
        root_path = Path(root).resolve()
        entries: list[FileIndexEntry] = []
        for path in root_path.rglob("*"):
            if len(entries) >= limit:
                break
            if any(part in self.SKIP_DIRS for part in path.parts):
                continue
            if not path.is_file():
                continue
            try:
                stat = path.stat()
                rel = str(path.relative_to(root_path))
                digest = self._digest(path, stat.st_size)
                entries.append(FileIndexEntry(rel, path.suffix.lower(), stat.st_size, stat.st_mtime, digest, self._tags(path)))
            except Exception:
                continue
        summary = self._summary(entries)
        index = ProjectIndex(str(root_path), time.time(), entries, summary)
        self._write(index)
        return index

    def search(self, index: ProjectIndex, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        tokens = {t.lower() for t in str(query).split() if t.strip()}
        scored = []
        for entry in index.files:
            hay = f"{entry.path} {' '.join(entry.tags)}".lower()
            score = sum(1 for token in tokens if token in hay)
            if score:
                row = entry.to_dict()
                row["score"] = score
                scored.append(row)
        scored.sort(key=lambda row: (row["score"], -row["size"]), reverse=True)
        return scored[:limit]

    def _digest(self, path: Path, size: int) -> str:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            h.update(handle.read(8192 if size > 8192 else size))
        return h.hexdigest()[:16]

    def _tags(self, path: Path) -> list[str]:
        tags = []
        if path.name in {"requirements.txt", "package.json", "pyproject.toml"}:
            tags.append("dependency-config")
        if path.suffix.lower() in {".md", ".rst"}:
            tags.append("documentation")
        if path.suffix.lower() in {".py", ".js", ".ts", ".tsx", ".jsx"}:
            tags.append("code")
        if "test" in path.name.lower():
            tags.append("test")
        return tags

    def _summary(self, entries: list[FileIndexEntry]) -> dict[str, Any]:
        by_suffix: dict[str, int] = {}
        for entry in entries:
            by_suffix[entry.suffix or "<none>"] = by_suffix.get(entry.suffix or "<none>", 0) + 1
        return {"file_count": len(entries), "by_suffix": by_suffix}

    def _write(self, index: ProjectIndex) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        tmp.write_text(json.dumps(index.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.cache_path)

