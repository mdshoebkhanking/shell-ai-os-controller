from __future__ import annotations

import fnmatch
import hashlib
import importlib.util
import json
import math
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol


SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cc", ".cpp", ".cxx",
    ".h", ".hpp", ".md", ".mdx", ".rst", ".txt", ".json", ".yaml", ".yml",
    ".toml", ".html", ".css", ".scss", ".sql", ".sh", ".bat", ".ps1",
}
DEFAULT_IGNORE_PATTERNS = (
    ".git/",
    "node_modules/",
    "venv/",
    ".venv/",
    "__pycache__/",
    "dist/",
    "build/",
    ".next/",
    "out/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".shell_runtime/",
    "*.pyc",
    "*.log",
    ".DS_Store",
)
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+")


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def project_rag_enabled() -> bool:
    return _truthy(os.environ.get("SHELL_PROJECT_RAG_ENABLED"))


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_RE.finditer(str(text or "")):
        raw = match.group(0)
        parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw).replace("_", " ").split()
        tokens.extend(part.lower() for part in parts if len(part) >= 2)
    return tokens


def _sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _json_load(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (na * nb)


class EmbeddingBackend(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]:
        ...


class SentenceTransformerBackend:
    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer  # type: ignore

        self.model_name = model_name or os.environ.get("SHELL_PROJECT_RAG_EMBED_MODEL", "all-MiniLM-L6-v2")
        self._model = SentenceTransformer(self.model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [list(map(float, row)) for row in vectors]


class HashEmbeddingBackend:
    """Small deterministic embedding backend for tests and no-download fallback probes."""

    def __init__(self, dims: int = 96):
        self.dims = max(8, int(dims))

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dims
            for token in _tokenize(text):
                idx = int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16) % self.dims
                vec[idx] += 1.0
            norm = math.sqrt(sum(value * value for value in vec)) or 1.0
            vectors.append([value / norm for value in vec])
        return vectors


@dataclass(frozen=True)
class ProjectRAGConfig:
    max_files: int = 1000
    max_file_bytes: int = 768_000
    chunk_chars: int = 1800
    chunk_overlap_chars: int = 180
    embeddings_enabled: bool = False
    embedding_model: str = "all-MiniLM-L6-v2"

    @classmethod
    def from_environment(cls, *, max_files: int | None = None) -> "ProjectRAGConfig":
        return cls(
            max_files=max(1, min(int(max_files or _env_int("SHELL_PROJECT_RAG_MAX_FILES", 1000, minimum=1, maximum=10000)), 10000)),
            max_file_bytes=_env_int("SHELL_PROJECT_RAG_MAX_FILE_BYTES", 768_000, minimum=4096, maximum=5_000_000),
            chunk_chars=_env_int("SHELL_PROJECT_RAG_CHUNK_CHARS", 1800, minimum=400, maximum=8000),
            chunk_overlap_chars=_env_int("SHELL_PROJECT_RAG_CHUNK_OVERLAP", 180, minimum=0, maximum=2000),
            embeddings_enabled=_truthy(os.environ.get("SHELL_PROJECT_RAG_EMBEDDINGS_ENABLED")),
            embedding_model=str(os.environ.get("SHELL_PROJECT_RAG_EMBED_MODEL", "all-MiniLM-L6-v2")),
        )


class IgnoreMatcher:
    def __init__(self, root: Path):
        self.root = root
        self.patterns = list(DEFAULT_IGNORE_PATTERNS)
        for name in (".gitignore", ".ignore"):
            path = root / name
            if path.is_file():
                self.patterns.extend(self._read_patterns(path))

    @staticmethod
    def _read_patterns(path: Path) -> list[str]:
        patterns: list[str] = []
        try:
            for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("!"):
                    continue
                patterns.append(line)
        except Exception:
            pass
        return patterns

    def ignored(self, path: Path, *, is_dir: bool = False) -> bool:
        try:
            rel = path.relative_to(self.root).as_posix()
        except ValueError:
            return True
        name = path.name
        parts = rel.split("/")
        for pattern in self.patterns:
            pat = pattern.strip()
            if not pat:
                continue
            dir_pat = pat.endswith("/")
            clean = pat.rstrip("/")
            if dir_pat:
                if clean in parts or rel == clean or rel.startswith(clean + "/"):
                    return True
                continue
            if "/" in clean:
                if fnmatch.fnmatch(rel, clean) or fnmatch.fnmatch(rel, clean.lstrip("/")):
                    return True
            elif fnmatch.fnmatch(name, clean) or clean in parts:
                return True
        return False


class ProjectRAGIndex:
    def __init__(
        self,
        project_path: str | Path,
        *,
        db_path: str | Path | None = None,
        config: ProjectRAGConfig | None = None,
        embedder: EmbeddingBackend | None = None,
    ) -> None:
        self.root = Path(project_path).expanduser().resolve()
        self.config = config or ProjectRAGConfig.from_environment()
        self.db_path = Path(db_path).expanduser() if db_path else self._default_db_path(self.root)
        self.embedder = embedder
        self.embedding_error = ""
        self.initialize()

    @staticmethod
    def _default_db_path(root: Path) -> Path:
        raw = os.environ.get("SHELL_PROJECT_RAG_DB")
        if raw:
            return Path(raw).expanduser()
        return root / ".shell_runtime" / "project_rag.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS project_files (
                    project_path TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    language TEXT NOT NULL,
                    chunks INTEGER NOT NULL,
                    indexed_at REAL NOT NULL,
                    PRIMARY KEY(project_path, relative_path)
                );

                CREATE TABLE IF NOT EXISTS project_chunks (
                    id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    tokens_json TEXT NOT NULL,
                    embedding_json TEXT NOT NULL DEFAULT '[]',
                    file_hash TEXT NOT NULL,
                    indexed_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_project_chunks_project
                    ON project_chunks(project_path, relative_path);
                """
            )
            conn.commit()

    def _get_embedder(self) -> EmbeddingBackend | None:
        if self.embedder is not None:
            return self.embedder
        if not self.config.embeddings_enabled:
            return None
        if importlib.util.find_spec("sentence_transformers") is None:
            self.embedding_error = "sentence-transformers unavailable"
            return None
        try:
            self.embedder = SentenceTransformerBackend(self.config.embedding_model)
            return self.embedder
        except Exception as exc:
            self.embedding_error = str(exc)
            return None

    def _iter_project_files(self, limit: int) -> list[Path]:
        matcher = IgnoreMatcher(self.root)
        files: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dir_path = Path(dirpath)
            dirnames[:] = [
                name for name in dirnames
                if not matcher.ignored(dir_path / name, is_dir=True)
            ]
            for filename in filenames:
                path = dir_path / filename
                if matcher.ignored(path):
                    continue
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                try:
                    if path.stat().st_size > self.config.max_file_bytes:
                        continue
                except OSError:
                    continue
                files.append(path)
                if len(files) >= limit:
                    return files
        return files

    @staticmethod
    def _read_file(path: Path) -> tuple[str, str]:
        try:
            raw = path.read_bytes()
        except OSError:
            return "", ""
        if b"\0" in raw[:4096]:
            return "", ""
        digest = _sha1_bytes(raw)
        return raw.decode("utf-8", errors="ignore"), digest

    def _chunks_for(self, relative_path: str, text: str) -> list[dict[str, Any]]:
        lines = text.splitlines()
        chunks: list[dict[str, Any]] = []
        start_line = 1
        current: list[str] = []
        current_chars = 0
        for line_no, line in enumerate(lines, 1):
            current.append(line)
            current_chars += len(line) + 1
            if current_chars >= self.config.chunk_chars:
                chunk_text = "\n".join(current).strip()
                if chunk_text:
                    chunks.append(
                        {
                            "relative_path": relative_path,
                            "chunk_index": len(chunks),
                            "start_line": start_line,
                            "end_line": line_no,
                            "text": chunk_text,
                            "tokens": _tokenize(f"{relative_path}\n{chunk_text}"),
                        }
                    )
                overlap = max(0, self.config.chunk_overlap_chars)
                if overlap:
                    tail = chunk_text[-overlap:]
                    current = [tail]
                    current_chars = len(tail)
                    start_line = line_no
                else:
                    current = []
                    current_chars = 0
                    start_line = line_no + 1
        chunk_text = "\n".join(current).strip()
        if chunk_text:
            chunks.append(
                {
                    "relative_path": relative_path,
                    "chunk_index": len(chunks),
                    "start_line": start_line,
                    "end_line": max(start_line, len(lines)),
                    "text": chunk_text,
                    "tokens": _tokenize(f"{relative_path}\n{chunk_text}"),
                }
            )
        return chunks

    def index_project(self, *, max_files: int | None = None) -> dict[str, Any]:
        if not self.root.exists() or not self.root.is_dir():
            return {"ok": False, "message": f"Project folder not found: {self.root}"}
        limit = max(1, min(int(max_files or self.config.max_files), 10000))
        files = self._iter_project_files(limit)
        scanned_rel = {path.relative_to(self.root).as_posix() for path in files}
        indexed = 0
        skipped = 0
        chunks_written = 0
        now = time.time()

        with self._connect() as conn:
            existing = {
                row["relative_path"]: row
                for row in conn.execute(
                    "SELECT * FROM project_files WHERE project_path = ?",
                    (str(self.root),),
                ).fetchall()
            }
            stale = sorted(set(existing) - scanned_rel)
            for rel in stale:
                conn.execute("DELETE FROM project_chunks WHERE project_path = ? AND relative_path = ?", (str(self.root), rel))
                conn.execute("DELETE FROM project_files WHERE project_path = ? AND relative_path = ?", (str(self.root), rel))

            for path in files:
                rel = path.relative_to(self.root).as_posix()
                try:
                    stat = path.stat()
                except OSError:
                    continue
                text, digest = self._read_file(path)
                if not text:
                    continue
                row = existing.get(rel)
                if (
                    row is not None
                    and row["file_hash"] == digest
                    and int(row["mtime_ns"]) == int(stat.st_mtime_ns)
                    and int(row["size"]) == int(stat.st_size)
                ):
                    skipped += 1
                    continue

                chunks = self._chunks_for(rel, text)
                embeddings = self._embed_chunks([f"{rel}\n{chunk['text']}" for chunk in chunks])
                conn.execute("DELETE FROM project_chunks WHERE project_path = ? AND relative_path = ?", (str(self.root), rel))
                for chunk, embedding in zip(chunks, embeddings):
                    chunk_id = hashlib.sha1(f"{self.root}:{rel}:{chunk['chunk_index']}:{digest}".encode("utf-8")).hexdigest()
                    conn.execute(
                        """
                        INSERT INTO project_chunks (
                            id, project_path, relative_path, chunk_index, start_line,
                            end_line, text, tokens_json, embedding_json, file_hash, indexed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk_id,
                            str(self.root),
                            rel,
                            int(chunk["chunk_index"]),
                            int(chunk["start_line"]),
                            int(chunk["end_line"]),
                            chunk["text"],
                            _json_dump(chunk["tokens"]),
                            _json_dump(embedding),
                            digest,
                            now,
                        ),
                    )
                conn.execute(
                    """
                    INSERT INTO project_files (
                        project_path, relative_path, file_hash, mtime_ns, size,
                        language, chunks, indexed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_path, relative_path) DO UPDATE SET
                        file_hash = excluded.file_hash,
                        mtime_ns = excluded.mtime_ns,
                        size = excluded.size,
                        language = excluded.language,
                        chunks = excluded.chunks,
                        indexed_at = excluded.indexed_at
                    """,
                    (
                        str(self.root),
                        rel,
                        digest,
                        int(stat.st_mtime_ns),
                        int(stat.st_size),
                        path.suffix.lower().lstrip("."),
                        len(chunks),
                        now,
                    ),
                )
                indexed += 1
                chunks_written += len(chunks)
            conn.commit()

        return {
            "ok": True,
            "project_path": str(self.root),
            "files_scanned": len(files),
            "files_indexed": indexed,
            "files_skipped": skipped,
            "files_removed": len(stale),
            "chunks_written": chunks_written,
            "embeddings_enabled": self._get_embedder() is not None,
            "embedding_error": self.embedding_error,
            "db_path": str(self.db_path),
        }

    def _embed_chunks(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embedder = self._get_embedder()
        if embedder is None:
            return [[] for _ in texts]
        try:
            return embedder.encode(texts)
        except Exception as exc:
            self.embedding_error = str(exc)
            return [[] for _ in texts]

    def _rows(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM project_chunks WHERE project_path = ?",
                (str(self.root),),
            ).fetchall()

    def query(self, query: str, *, limit: int = 8) -> dict[str, Any]:
        query_text = str(query or "").strip()
        if not query_text:
            return {"ok": False, "message": "Query is required.", "matches": []}
        rows = self._rows()
        query_tokens = _tokenize(query_text)
        docs_tokens = [list(_json_load(row["tokens_json"], [])) for row in rows]
        lexical_scores = self._lexical_scores(query_tokens, docs_tokens)
        query_embedding = self._embed_query(query_text)
        matches: list[dict[str, Any]] = []
        max_lexical = max(lexical_scores) if lexical_scores else 0.0
        for row, lexical, tokens in zip(rows, lexical_scores, docs_tokens):
            lexical_norm = (lexical / max_lexical) if max_lexical > 0 else 0.0
            embedding = list(_json_load(row["embedding_json"], []))
            semantic = _cosine(query_embedding, embedding) if query_embedding and embedding else 0.0
            path_bonus = 0.08 if any(token in row["relative_path"].lower() for token in query_tokens) else 0.0
            score = lexical_norm + (0.45 * max(0.0, semantic)) + path_bonus
            if score <= 0.0:
                continue
            matches.append(
                {
                    "id": row["id"],
                    "relative_path": row["relative_path"],
                    "start_line": int(row["start_line"]),
                    "end_line": int(row["end_line"]),
                    "score": round(score, 5),
                    "lexical_score": round(lexical_norm, 5),
                    "semantic_score": round(float(semantic), 5),
                    "preview": str(row["text"])[:1200],
                    "matched_tokens": sorted(set(query_tokens) & set(tokens))[:20],
                }
            )
        matches.sort(key=lambda item: (item["score"], item["relative_path"]), reverse=True)
        return {
            "ok": True,
            "project_path": str(self.root),
            "query": query_text,
            "count": len(matches[: max(1, int(limit))]),
            "matches": matches[: max(1, int(limit))],
            "embedding_error": self.embedding_error,
        }

    def _embed_query(self, query: str) -> list[float]:
        embedder = self._get_embedder()
        if embedder is None:
            return []
        try:
            vectors = embedder.encode([query])
            return vectors[0] if vectors else []
        except Exception as exc:
            self.embedding_error = str(exc)
            return []

    @staticmethod
    def _lexical_scores(query_tokens: list[str], docs_tokens: list[list[str]]) -> list[float]:
        if not query_tokens or not docs_tokens:
            return [0.0 for _ in docs_tokens]
        fallback_scores = ProjectRAGIndex._fallback_lexical_scores(query_tokens, docs_tokens)
        if importlib.util.find_spec("rank_bm25") is not None:
            try:
                from rank_bm25 import BM25Okapi  # type: ignore

                bm25_scores = [max(0.0, float(score)) for score in BM25Okapi(docs_tokens).get_scores(query_tokens)]
                if any(score > 0.0 for score in bm25_scores):
                    return [
                        max(bm25_score, fallback_score)
                        for bm25_score, fallback_score in zip(bm25_scores, fallback_scores)
                    ]
            except Exception:
                pass
        return fallback_scores

    @staticmethod
    def _fallback_lexical_scores(query_tokens: list[str], docs_tokens: list[list[str]]) -> list[float]:
        doc_count = len(docs_tokens)
        avgdl = sum(len(doc) for doc in docs_tokens) / max(1, doc_count)
        doc_sets = [set(doc) for doc in docs_tokens]
        df = {token: sum(1 for doc_set in doc_sets if token in doc_set) for token in set(query_tokens)}
        scores: list[float] = []
        k1 = 1.5
        b = 0.75
        for doc in docs_tokens:
            doc_len = max(1, len(doc))
            counts: dict[str, int] = {}
            for token in doc:
                counts[token] = counts.get(token, 0) + 1
            score = 0.0
            for token in query_tokens:
                freq = counts.get(token, 0)
                if freq <= 0:
                    continue
                idf = math.log(1.0 + ((doc_count - df.get(token, 0) + 0.5) / (df.get(token, 0) + 0.5)))
                denom = freq + k1 * (1.0 - b + b * (doc_len / max(1.0, avgdl)))
                score += idf * ((freq * (k1 + 1.0)) / denom)
            scores.append(score)
        return scores

    def status(self) -> dict[str, Any]:
        with self._connect() as conn:
            file_count = conn.execute(
                "SELECT COUNT(*) AS c FROM project_files WHERE project_path = ?",
                (str(self.root),),
            ).fetchone()
            chunk_count = conn.execute(
                "SELECT COUNT(*) AS c FROM project_chunks WHERE project_path = ?",
                (str(self.root),),
            ).fetchone()
        return {
            "ok": True,
            "enabled": project_rag_enabled(),
            "project_path": str(self.root),
            "db_path": str(self.db_path),
            "indexed_files": int(file_count["c"] if file_count else 0),
            "indexed_chunks": int(chunk_count["c"] if chunk_count else 0),
            "sentence_transformers_installed": importlib.util.find_spec("sentence_transformers") is not None,
            "rank_bm25_installed": importlib.util.find_spec("rank_bm25") is not None,
            "embeddings_enabled": self.config.embeddings_enabled,
            "embedding_error": self.embedding_error,
        }


__all__ = [
    "HashEmbeddingBackend",
    "ProjectRAGConfig",
    "ProjectRAGIndex",
    "project_rag_enabled",
]
