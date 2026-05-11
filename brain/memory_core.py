import os
import json
import logging
import math
import time
import asyncio
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# --- SENTENCE TRANSFORMERS SETUP (LOCAL EMBEDDINGS — LAZY LOADED) ---
try:
    from sentence_transformers import SentenceTransformer
    LOCAL_EMBED_AVAILABLE = True
except ImportError:
    LOCAL_EMBED_AVAILABLE = False

logger = logging.getLogger("shell_memory_core")

# Load configurable values from ShellConfig (falls back to defaults if .env not set)
try:
    from shell_config import config as _config
    MEMORY_FILE = "brain/data/long_term_memory.json"
    MAX_MEMORIES = _config.memory.get("max_memories", 10000)
    SAVE_BATCH_SIZE = _config.memory.get("save_batch_size", 10)
except ImportError:
    MEMORY_FILE = "brain/data/long_term_memory.json"
    MAX_MEMORIES = 10000
    SAVE_BATCH_SIZE = 10

# Keywords that boost importance score
IMPORTANCE_KEYWORDS = [
    "error", "critical", "important", "remember", "password", "key", "secret",
    "deadline", "urgent", "fix", "bug", "crash", "fail", "success", "goal",
    "learn", "never", "always", "warning", "todo", "hack", "security"
]


class VectorMemory:
    """
    Lightweight Vector Database (JSON-based) with thread safety,
    memory limits, lazy encoder loading, memory decay, episodic/semantic/procedural
    types, working memory, consolidation, compression, relationship graph,
    and context-aware retrieval.
    """

    # =============================================
    # WorkingMemory Inner Class
    # =============================================
    class WorkingMemory:
        """Short-term scratch pad for multi-step reasoning. FIFO, 10 items."""

        def __init__(self, capacity=10):
            self._items = []
            self._capacity = capacity

        def push(self, item: str, context: str = ""):
            self._items.append({"text": item, "context": context, "timestamp": time.time()})
            if len(self._items) > self._capacity:
                self._items.pop(0)

        def get_all(self) -> List[str]:
            return [i["text"] for i in self._items]

        def get_context_string(self) -> str:
            if not self._items:
                return ""
            parts = ["Working Memory:"]
            for i, item in enumerate(self._items, 1):
                parts.append(f"  {i}. {item['text'][:200]}")
            return "\n".join(parts)

        def clear(self):
            self._items.clear()

        def size(self) -> int:
            return len(self._items)

    # =============================================
    # Core Init & Load/Save
    # =============================================

    def __init__(self):
        self.memory_path = MEMORY_FILE
        self.data_dir = os.path.dirname(MEMORY_FILE)
        self._lock = threading.Lock()
        self._unsaved_count = 0
        try:
            self.similarity_threshold = _config.memory.get("similarity_threshold", 0.55)
        except Exception:
            self.similarity_threshold = 0.55
        self.memories = self._load_memory()
        self.encoder = None  # Lazy loaded on first use
        self._encoder_loaded = False
        self._model = None  # Alias for encoder used by new methods
        self.working_memory = self.WorkingMemory()
        self._ensure_dir()

    def _save_memory(self) -> bool:  # type: ignore[override]
        """Thread-safe atomic save using os.replace (POSIX+Windows atomic).

        Returns True on success, False on failure. Callers that batch
        writes (see add_memory) should only reset their unsaved counter
        when this returns True — otherwise unsaved edits would silently
        become "saved" even when the write failed.
        """
        try:
            temp_path = self.memory_path + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.memories, f, indent=2, ensure_ascii=False)
            # Best-effort backup before swapping in the new file.
            if os.path.exists(self.memory_path):
                try:
                    os.replace(self.memory_path, self.memory_path + ".bak")
                except OSError as _bak:
                    logger.debug("memory_core backup skipped: %s", _bak)
            os.replace(temp_path, self.memory_path)
            return True
        except Exception as e:
            logger.error(f"Memory save failed: {e}")
            return False

    def _lazy_load_encoder(self):
        """Load SentenceTransformer only when first needed (saves 3-5s startup).

        The _encoder_loaded flag is set only AFTER a successful load. If the
        first attempt fails (network blip, model download timeout), the next
        call will retry rather than permanently degrading to keyword search.
        """
        if self._encoder_loaded:
            return
        if not LOCAL_EMBED_AVAILABLE:
            # Nothing to load, mark as "done" to avoid spamming the warning.
            if not getattr(self, "_encoder_warning_emitted", False):
                logger.warning("SentenceTransformers not installed. Using keyword fallback.")
                self._encoder_warning_emitted = True
            self._encoder_loaded = True
            return
        try:
            self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
            self._model = self.encoder
            self._encoder_loaded = True  # only on success
            logger.info("✅ Local Embedding model loaded (lazy).")
        except Exception as e:
            logger.error(f"Local Embedding Init Failed: {e}")
            # Leave _encoder_loaded = False so a future call can retry.

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)

    def _load_memory(self) -> List[Dict]:
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Enforce limit on load
                    if len(data) > MAX_MEMORIES:
                        logger.warning(f"Memory file has {len(data)} entries, trimming to {MAX_MEMORIES}.")
                        data = data[-MAX_MEMORIES:]
                    return data
            except json.JSONDecodeError as e:
                logger.error(f"Memory file corrupted: {e}. Starting fresh with backup.")
                # Backup corrupted file
                backup_path = self.memory_path + ".corrupted.bak"
                try:
                    os.rename(self.memory_path, backup_path)
                except OSError:
                    pass
            except Exception as e:
                logger.error(f"Memory load failed: {e}")
        return []

    def _save(self):
        """Alias for _save_memory for consistency."""
        self._save_memory()

    # =============================================
    # Embedding & Similarity
    # =============================================

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Generates embedding using Local SentenceTransformer Model (lazy loaded)."""
        self._lazy_load_encoder()
        if not self.encoder:
            return None
        try:
            embedding = self.encoder.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"❌ Local Embedding Failed: {e}")
            return None

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Calculates cosine similarity between two vectors."""
        if not v1 or not v2:
            return 0.0
        try:
            import numpy as np
            a = np.array(v1)
            b = np.array(v2)
            if a.shape != b.shape:
                return 0.0
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(np.dot(a, b) / (norm_a * norm_b))
        except ImportError:
            # Pure python fallback
            if len(v1) != len(v2):
                return 0.0
            dot_product = sum(a * b for a, b in zip(v1, v2))
            magnitude1 = math.sqrt(sum(a * a for a in v1))
            magnitude2 = math.sqrt(sum(b * b for b in v2))
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            return dot_product / (magnitude1 * magnitude2)
        except Exception as e:
            logger.error(f"Cosine Sim Error: {e}")
            return 0.0

    # =============================================
    # Memory Decay
    # =============================================

    def _apply_decay(self, memory: Dict, current_time=None) -> float:
        """Calculate decay factor based on age. Returns 0.1 to 1.0.
        High-importance memories decay 3x slower (90 days vs 30 days).
        """
        if current_time is None:
            current_time = time.time()
        # Handle both ISO string timestamps and epoch floats
        created = memory.get("timestamp", current_time)
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created).timestamp()
            except (ValueError, TypeError):
                created = current_time
        age_hours = (current_time - created) / 3600
        # High-importance memories decay 3x slower
        importance = memory.get("meta", {}).get("importance", 0.5)
        decay_rate = 30 * 24  # 30 days (in hours) to reach floor
        if importance > 0.7:
            decay_rate *= 3  # 90 days for important memories
        decay = max(0.1, 1.0 - (age_hours / decay_rate))
        return decay

    # =============================================
    # Core Search (with decay integration)
    # =============================================

    def search_memory(self, query: str, top_k: int = 5) -> List[Dict]:
        """Thread-safe semantic search."""
        with self._lock:
            return self._search_memory_internal(query, top_k)

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Alias for search_memory."""
        return self.search_memory(query, top_k)

    def _search_memory_internal(self, query: str, top_k: int) -> List[Dict]:
        query_vector = self._get_embedding(query)
        current_time = time.time()

        # 1. Vector Search (Preferred) — with decay
        if query_vector:
            scored_memories = []
            for mem in self.memories:
                if "vector" in mem and mem["vector"]:
                    score = self._cosine_similarity(query_vector, mem["vector"])
                    decay = self._apply_decay(mem, current_time)
                    adjusted_score = score * decay
                    if adjusted_score > self.similarity_threshold:
                        result = {**mem, "similarity": round(adjusted_score, 4)}
                        scored_memories.append((adjusted_score, result))
            scored_memories.sort(key=lambda x: x[0], reverse=True)
            return [m for _, m in scored_memories[:top_k]]

        # 2. Keyword Search Fallback
        logger.info("⚠️ Using Keyword Search Fallback")
        keywords = query.lower().split()
        results = []
        for mem in self.memories:
            text = mem.get("text", "").lower()
            match_count = sum(1 for k in keywords if k in text)
            if match_count > 0:
                results.append((match_count, mem))
        results.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in results[:top_k]]

    # =============================================
    # Core Add Memory
    # =============================================

    def add_memory(self, text: str, meta: Dict[str, Any] = None):
        """Thread-safe memory addition with size limit enforcement and auto-importance."""
        if meta is None:
            meta = {}
        if not text or not text.strip():
            return

        # Auto-calculate importance if not provided
        if "importance" not in meta:
            meta["importance"] = self.importance_score(text)

        with self._lock:
            vector = self._get_embedding(text)
            memory_item = {
                "id": f"mem_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.memories)}",
                "text": text,
                "vector": vector,
                "timestamp": datetime.now().isoformat(),
                "meta": meta,
                "tags": []
            }
            self.memories.append(memory_item)

            # Enforce memory limit — remove oldest entries
            if len(self.memories) > MAX_MEMORIES:
                overflow = len(self.memories) - MAX_MEMORIES
                self.memories = self.memories[overflow:]
                logger.info(f"🧹 Memory trimmed: removed {overflow} oldest entries.")

            # Batch save to reduce disk I/O
            self._unsaved_count += 1
            if self._unsaved_count >= SAVE_BATCH_SIZE:
                self._save_memory()
                self._unsaved_count = 0

        logger.info(f"💾 Memory Saved: {text[:30]}...")

    def flush(self):
        """Force save any unsaved memories to disk."""
        with self._lock:
            if self._unsaved_count > 0:
                self._save_memory()
                self._unsaved_count = 0

    # =============================================
    # Episodic / Semantic / Procedural Memory Types
    # =============================================

    def add_episodic_memory(self, text: str, meta: Dict[str, Any] = None):
        """Store event/conversation memory."""
        if meta is None:
            meta = {}
        meta["memory_type"] = "episodic"
        return self.add_memory(text, meta=meta)

    def add_semantic_memory(self, text: str, meta: Dict[str, Any] = None):
        """Store factual/knowledge memory."""
        if meta is None:
            meta = {}
        meta["memory_type"] = "semantic"
        return self.add_memory(text, meta=meta)

    def add_procedural_memory(self, text: str, meta: Dict[str, Any] = None):
        """Store how-to/workflow memory."""
        if meta is None:
            meta = {}
        meta["memory_type"] = "procedural"
        return self.add_memory(text, meta=meta)

    def search_episodic(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search only episodic (event/conversation) memories."""
        results = self.search(query, top_k=top_k * 3)
        return [r for r in results if r.get("meta", {}).get("memory_type") == "episodic"][:top_k]

    def search_semantic(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search only semantic (factual/knowledge) memories."""
        results = self.search(query, top_k=top_k * 3)
        return [r for r in results if r.get("meta", {}).get("memory_type") == "semantic"][:top_k]

    def search_procedural(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search only procedural (how-to/workflow) memories."""
        results = self.search(query, top_k=top_k * 3)
        return [r for r in results if r.get("meta", {}).get("memory_type") == "procedural"][:top_k]

    # =============================================
    # RAG INGESTION METHODS
    # =============================================

    def ingest_file(self, file_path: str):
        """Ingests a file into memory (RAG). Supports txt, md, py, json, pdf."""
        if not os.path.exists(file_path):
            return f"❌ File not found: {file_path}"

        ext = os.path.splitext(file_path)[1].lower()
        text = ""

        try:
            if ext == ".pdf":
                try:
                    import pypdf
                    reader = pypdf.PdfReader(file_path)
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                except ImportError:
                    return "❌ pypdf module not found. Install it to read PDFs."
                except Exception as e:
                    return f"❌ PDF Error: {e}"
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

            if not text.strip():
                return "⚠️ Empty file."

            chunks = self._chunk_text(text)
            count = 0
            for chunk in chunks:
                self.add_memory(chunk, meta={"source": file_path, "type": "document_chunk"})
                count += 1

            # Force save after ingestion
            self.flush()
            return f"✅ Ingested {count} chunks from {os.path.basename(file_path)}"

        except Exception as e:
            return f"❌ Ingestion Error: {e}"

    def ingest_folder(self, folder_path: str, recursive: bool = True):
        """Ingests all supported files in a folder, skipping junk directories."""
        if not os.path.exists(folder_path):
            return f"❌ Folder not found: {folder_path}"

        supported_exts = {".txt", ".md", ".py", ".json", ".js", ".html", ".css", ".bat", ".sh", ".pdf", ".rs", ".go"}
        ignored_dirs = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build", ".next", ".vscode", ".idea"}
        results = []

        for root, dirs, files in os.walk(folder_path):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in supported_exts:
                    full_path = os.path.join(root, file)
                    res = self.ingest_file(full_path)
                    if "✅" in str(res):
                        results.append(full_path)
            if not recursive:
                break

        self.flush()
        return f"✅ Processed {len(results)} files."

    def _chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
        """Smart Semantic Chunking — splits by paragraphs first."""
        if not text:
            return []

        paragraphs = text.replace('\r\n', '\n').split('\n\n')
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = current_chunk[-overlap:] + "\n\n" + para
                else:
                    chunks.append(para[:chunk_size])
                    current_chunk = ""
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    # =============================================
    # V2 Upgrades — Tags, Stats, Delete, etc.
    # =============================================

    def tag_memory(self, memory_id: str, tags: List[str]) -> str:
        """Add tags to a specific memory by its ID."""
        with self._lock:
            for mem in self.memories:
                if mem.get("id") == memory_id:
                    existing_tags = mem.get("tags", [])
                    new_tags = list(set(existing_tags + tags))
                    mem["tags"] = new_tags
                    self._unsaved_count += 1
                    if self._unsaved_count >= SAVE_BATCH_SIZE:
                        self._save_memory()
                        self._unsaved_count = 0
                    return f"Tagged '{memory_id}' with {tags}. Total tags: {new_tags}"
            return f"Memory '{memory_id}' not found."

    def search_by_tag(self, tag: str, top_k: int = 10) -> List[Dict]:
        """Search memories that have a specific tag."""
        with self._lock:
            results = []
            for mem in self.memories:
                mem_tags = mem.get("tags", [])
                if tag.lower() in [t.lower() for t in mem_tags]:
                    results.append(mem)
                    if len(results) >= top_k:
                        break
            return results

    def get_memory_stats(self) -> Dict[str, Any]:
        """Return statistics about the memory store."""
        with self._lock:
            total = len(self.memories)
            if total == 0:
                return {"total": 0, "by_tag": {}, "by_source": {}, "oldest": None, "newest": None}

            # Count by tag
            tag_counts = {}
            for mem in self.memories:
                for tag in mem.get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            # Count by source (from meta)
            source_counts = {}
            for mem in self.memories:
                source = mem.get("meta", {}).get("source", "unknown")
                mem_type = mem.get("meta", {}).get("type", "general")
                key = mem_type if source == "unknown" else source
                source_counts[key] = source_counts.get(key, 0) + 1

            # Count by memory_type
            type_counts = {}
            for mem in self.memories:
                mt = mem.get("meta", {}).get("memory_type", "untyped")
                type_counts[mt] = type_counts.get(mt, 0) + 1

            # Oldest and newest
            timestamps = [mem.get("timestamp", "") for mem in self.memories if mem.get("timestamp")]
            oldest = min(timestamps) if timestamps else None
            newest = max(timestamps) if timestamps else None

            return {
                "total": total,
                "by_tag": tag_counts,
                "by_source": source_counts,
                "by_memory_type": type_counts,
                "oldest": oldest,
                "newest": newest
            }

    def delete_memory(self, memory_id: str) -> str:
        """Delete a specific memory by its ID."""
        with self._lock:
            original_len = len(self.memories)
            self.memories = [m for m in self.memories if m.get("id") != memory_id]
            if len(self.memories) < original_len:
                self._save_memory()
                return f"Deleted memory '{memory_id}'."
            return f"Memory '{memory_id}' not found."

    def clear_old_memories(self, days: int = 30) -> str:
        """Remove memories older than N days."""
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()
        with self._lock:
            original_len = len(self.memories)
            self.memories = [
                m for m in self.memories
                if m.get("timestamp", "") >= cutoff_iso
            ]
            removed = original_len - len(self.memories)
            if removed > 0:
                self._save_memory()
            return f"Removed {removed} memories older than {days} days. Remaining: {len(self.memories)}."

    def get_recent(self, n: int = 10) -> List[Dict]:
        """Get N most recent memories."""
        with self._lock:
            return list(reversed(self.memories[-n:]))

    def add_conversation_memory(self, user_msg: str, assistant_msg: str):
        """Store a conversation turn as a memory."""
        text = f"User: {user_msg}\nAssistant: {assistant_msg}"
        self.add_memory(text, meta={
            "type": "conversation",
            "user_msg": user_msg[:500],
            "assistant_msg": assistant_msg[:500]
        })

    def search_conversations(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search only conversation-type memories."""
        with self._lock:
            # First get all conversation memories
            conv_memories = [m for m in self.memories if m.get("meta", {}).get("type") == "conversation"]

            if not conv_memories:
                return []

            query_vector = self._get_embedding(query)

            # Vector search within conversations
            if query_vector:
                scored = []
                for mem in conv_memories:
                    if "vector" in mem and mem["vector"]:
                        score = self._cosine_similarity(query_vector, mem["vector"])
                        if score > 0.4:
                            scored.append((score, mem))
                scored.sort(key=lambda x: x[0], reverse=True)
                return [m for _, m in scored[:top_k]]

            # Keyword fallback
            keywords = query.lower().split()
            results = []
            for mem in conv_memories:
                text = mem.get("text", "").lower()
                match_count = sum(1 for k in keywords if k in text)
                if match_count > 0:
                    results.append((match_count, mem))
            results.sort(key=lambda x: x[0], reverse=True)
            return [m for _, m in results[:top_k]]

    def importance_score(self, text: str) -> float:
        """
        Calculate importance score (0.0 - 1.0) based on:
        - Text length (longer = slightly more important)
        - Presence of importance keywords
        - Question marks (questions are important to remember)
        - Exclamation marks (emphasis)
        - Code indicators (backticks, def, class)
        """
        if not text:
            return 0.0

        score = 0.0
        text_lower = text.lower()

        # Length factor (0 - 0.2): longer texts up to 500 chars get more weight
        length_factor = min(len(text) / 500.0, 1.0) * 0.2
        score += length_factor

        # Keyword factor (0 - 0.4): presence of important keywords
        keyword_hits = sum(1 for kw in IMPORTANCE_KEYWORDS if kw in text_lower)
        keyword_factor = min(keyword_hits / 5.0, 1.0) * 0.4
        score += keyword_factor

        # Question marks (0 - 0.15): questions are worth remembering
        question_count = text.count("?")
        question_factor = min(question_count / 3.0, 1.0) * 0.15
        score += question_factor

        # Exclamation marks (0 - 0.1): emphasis
        excl_count = text.count("!")
        excl_factor = min(excl_count / 3.0, 1.0) * 0.1
        score += excl_factor

        # Code indicators (0 - 0.15): technical content
        code_indicators = ["```", "def ", "class ", "import ", "function ", "const ", "var "]
        code_hits = sum(1 for ci in code_indicators if ci in text)
        code_factor = min(code_hits / 3.0, 1.0) * 0.15
        score += code_factor

        return round(min(score, 1.0), 3)

    # =============================================
    # Memory Consolidation
    # =============================================

    def consolidate_memories(self, similarity_threshold: float = 0.85) -> int:
        """Merge very similar memories to reduce redundancy. Returns number merged."""
        self._lazy_load_encoder()
        if not self._model or len(self.memories) < 2:
            return 0

        merged_count = 0
        to_remove = set()

        # Sort by timestamp, check adjacent memories within 7-day window
        sorted_mems = sorted(self.memories, key=lambda m: m.get("timestamp", ""))

        for i in range(len(sorted_mems) - 1):
            if i in to_remove:
                continue
            for j in range(i + 1, min(i + 20, len(sorted_mems))):  # check next 20
                if j in to_remove:
                    continue

                # Time window check — only consolidate within 7 days
                ts_i = sorted_mems[i].get("timestamp", "")
                ts_j = sorted_mems[j].get("timestamp", "")
                try:
                    if isinstance(ts_i, str) and isinstance(ts_j, str) and ts_i and ts_j:
                        dt_i = datetime.fromisoformat(ts_i)
                        dt_j = datetime.fromisoformat(ts_j)
                        t_diff = abs((dt_j - dt_i).total_seconds())
                        if t_diff > 7 * 24 * 3600:
                            break
                except (ValueError, TypeError):
                    pass

                # Similarity check
                if sorted_mems[i].get("vector") and sorted_mems[j].get("vector"):
                    sim = self._cosine_similarity(sorted_mems[i]["vector"], sorted_mems[j]["vector"])
                    if sim > similarity_threshold:
                        # Keep higher importance one
                        imp_i = sorted_mems[i].get("meta", {}).get("importance", 0.5)
                        imp_j = sorted_mems[j].get("meta", {}).get("importance", 0.5)
                        if imp_i >= imp_j:
                            sorted_mems[i]["text"] += f" [consolidated: {sorted_mems[j]['text'][:100]}]"
                            to_remove.add(j)
                        else:
                            sorted_mems[j]["text"] += f" [consolidated: {sorted_mems[i]['text'][:100]}]"
                            to_remove.add(i)
                        merged_count += 1

        # Remove merged
        if to_remove:
            self.memories = [m for idx, m in enumerate(sorted_mems) if idx not in to_remove]
            self._save()
        return merged_count

    # =============================================
    # Memory Compression (Async, AI-powered)
    # =============================================

    async def compress_old_memories(self, age_days: int = 14, brain=None) -> int:
        """Compress old long memories using AI summarization.
        Requires a brain instance with generate_response method.
        """
        if brain is None:
            return 0

        compressed = 0
        current_time = time.time()
        cutoff = current_time - (age_days * 24 * 3600)

        for mem in self.memories:
            if mem.get("meta", {}).get("compressed"):
                continue

            # Parse timestamp
            ts = mem.get("timestamp", "")
            try:
                if isinstance(ts, str) and ts:
                    mem_time = datetime.fromisoformat(ts).timestamp()
                else:
                    mem_time = current_time
            except (ValueError, TypeError):
                mem_time = current_time

            if mem_time > cutoff:
                continue
            if len(mem.get("text", "")) < 500:
                continue

            try:
                summary = await asyncio.wait_for(
                    brain.generate_response(
                        f"Summarize in 2-3 sentences:\n{mem['text'][:2000]}",
                        mode="FAST"
                    ),
                    timeout=10.0
                )
                if summary and len(summary) < len(mem["text"]):
                    mem["text"] = summary
                    mem["meta"] = mem.get("meta", {})
                    mem["meta"]["compressed"] = True
                    # Re-compute embedding
                    self._lazy_load_encoder()
                    if self._model:
                        mem["vector"] = self._model.encode(summary).tolist()
                    compressed += 1
            except Exception:
                continue

        if compressed > 0:
            self._save()
        return compressed

    # =============================================
    # Memory Relationship Graph
    # =============================================

    def build_memory_graph(self, top_n: int = 100) -> Dict:
        """Build adjacency list of related memories (top N most recent)."""
        self._lazy_load_encoder()
        recent = sorted(self.memories, key=lambda m: m.get("timestamp", ""), reverse=True)[:top_n]
        graph = {}

        for i, mem_i in enumerate(recent):
            if not mem_i.get("vector"):
                continue
            mem_id_i = mem_i.get("id", str(i))
            relations = []
            for j, mem_j in enumerate(recent):
                if i == j or not mem_j.get("vector"):
                    continue
                sim = self._cosine_similarity(mem_i["vector"], mem_j["vector"])
                if sim > 0.6:
                    mem_id_j = mem_j.get("id", str(j))
                    relations.append({
                        "id": mem_id_j,
                        "similarity": round(sim, 3),
                        "text_preview": mem_j["text"][:80]
                    })
            if relations:
                relations.sort(key=lambda r: -r["similarity"])
                graph[mem_id_i] = {
                    "text_preview": mem_i["text"][:80],
                    "relations": relations[:5]
                }

        # Save graph to disk
        graph_path = os.path.join(self.data_dir, "memory_graph.json")
        try:
            with open(graph_path, 'w', encoding='utf-8') as f:
                json.dump(graph, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return graph

    def get_related_memories(self, memory_id: str, depth: int = 2) -> List[Dict]:
        """BFS traversal of memory graph to find related memories."""
        graph_path = os.path.join(self.data_dir, "memory_graph.json")
        if not os.path.exists(graph_path):
            self.build_memory_graph()

        try:
            with open(graph_path, 'r', encoding='utf-8') as f:
                graph = json.load(f)
        except Exception:
            return []

        visited = set()
        queue = [(memory_id, 0)]
        results = []

        while queue:
            node_id, d = queue.pop(0)
            if node_id in visited or d > depth:
                continue
            visited.add(node_id)
            node = graph.get(node_id)
            if node and d > 0:
                results.append(node)
            if node and d < depth:
                for rel in node.get("relations", []):
                    if rel["id"] not in visited:
                        queue.append((rel["id"], d + 1))
        return results

    # =============================================
    # Context-Aware Retrieval
    # =============================================

    def search_with_context(self, query: str, context: str, top_k: int = 5) -> List[Dict]:
        """Search using blended query + context embedding (70/30 split)."""
        self._lazy_load_encoder()
        if not self._model:
            return self.search(query, top_k=top_k)

        try:
            q_vec = self._model.encode(query).tolist()
            c_vec = self._model.encode(context[:500]).tolist()
            # Blend: 70% query, 30% context
            blended = [q * 0.7 + c * 0.3 for q, c in zip(q_vec, c_vec)]

            current_time = time.time()
            results = []
            for mem in self.memories:
                if not mem.get("vector"):
                    continue
                sim = self._cosine_similarity(blended, mem["vector"])
                decay = self._apply_decay(mem, current_time)
                adjusted_sim = sim * decay
                if adjusted_sim > self.similarity_threshold:
                    results.append({**mem, "similarity": round(adjusted_sim, 4)})
            results.sort(key=lambda x: -x["similarity"])
            return results[:top_k]
        except Exception:
            return self.search(query, top_k=top_k)


memory_core = VectorMemory()
