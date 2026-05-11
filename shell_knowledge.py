from shell_safe_executor import god_tier_tool as function_tool
import logging
import os
from brain.memory_core import memory_core

logger = logging.getLogger("shell_knowledge")

@function_tool
async def add_knowledge_tool(fact: str, tags: str = "") -> str:
    """
    Saves a piece of information to Shell's Long-Term Memory (Vector DB).
    Args:
        fact: The information to save (e.g., "The Wi-Fi password is 1234").
        tags: Optional context or source.
    """
    try:
        meta = {"tags": tags, "source": "user_command"}
        memory_core.add_memory(fact, meta=meta)
        return f"✅ Knowledge Saved to Brain: '{fact}'"
    except Exception as e:
        return f"❌ Save Error: {e}"

@function_tool
async def recall_knowledge_tool(query: str, top_k: int = 5) -> str:
    """
    Semantic Search (RAG): Finds information from Long-Term Memory and Akashic Knowledge.
    Args:
        query: What you want to find (e.g., "Quantum Mechanics", "wifi password").
        top_k: Number of results to return (default 5).
    """
    response = ""

    # 1. Vector Memory Search (primary)
    try:
        results = memory_core.search_memory(query, top_k=top_k)
        if results:
            response += f"🧠 [MEMORY STREAM] — {len(results)} result(s) found:\n"
            for i, r in enumerate(results, 1):
                text = r.get('text', 'N/A')
                source = r.get('meta', {}).get('source', 'unknown')
                tags = r.get('meta', {}).get('tags', '')
                timestamp = r.get('timestamp', 'unknown')

                # Build score info if available
                score_info = ""
                if 'score' in r:
                    score_pct = round(r['score'] * 100, 1)
                    score_info = f" | Relevance: {score_pct}%"

                line = f"  {i}. {text}"
                line += f"\n     📁 Source: {source}"
                if tags:
                    line += f" | 🏷️ Tags: {tags}"
                line += f" | 🕐 {timestamp}{score_info}"
                response += line + "\n"
            response += "\n"
    except Exception as e:
        logger.warning(f"Memory search failed: {e}")

    # 2. Static Akashic Knowledge (fallback)
    try:
        from shell_brain.infinite_context import get_knowledge
        static_result = get_knowledge(query)
        if static_result:
            response += f"🌌 [AKASHIC RECORD]:\n{static_result}\n"
    except ImportError:
        logger.warning("Akashic module not available, skipping static knowledge.")
    except Exception as e:
        logger.warning(f"Akashic search failed: {e}")

    if not response:
        return "❌ No relevant data found in the Neural Network."

    return response

@function_tool
async def learn_from_file_tool(file_path: str) -> str:
    """
    RAG: Ingests a specific file into the Knowledge Base.
    Args:
        file_path: Absolute path to the file (pdf, txt, md, py, etc).
    """
    return memory_core.ingest_file(file_path)

@function_tool
async def learn_from_folder_tool(folder_path: str) -> str:
    """
    RAG: Ingests an entire folder into the Knowledge Base.
    Args:
        folder_path: Absolute path to the folder.
    """
    return memory_core.ingest_folder(folder_path)

@function_tool
async def search_knowledge_by_tag_tool(tag: str) -> str:
    """
    Searches knowledge entries by tag. Finds all memories that match the given tag.
    Args:
        tag: The tag to search for (e.g., "work", "personal", "project").
    """
    try:
        tag_lower = tag.lower().strip()
        if not tag_lower:
            return "❌ Please provide a tag to search for."

        matched = []
        with memory_core._lock:
            for mem in memory_core.memories:
                mem_tags = mem.get('meta', {}).get('tags', '')
                if isinstance(mem_tags, str) and tag_lower in mem_tags.lower():
                    matched.append(mem)
                elif isinstance(mem_tags, list):
                    if any(tag_lower in t.lower() for t in mem_tags):
                        matched.append(mem)

        if not matched:
            return f"❌ No knowledge entries found with tag: '{tag}'"

        output = f"🏷️ [TAG SEARCH: '{tag}'] — {len(matched)} result(s):\n"
        for i, mem in enumerate(matched, 1):
            text = mem.get('text', 'N/A')
            source = mem.get('meta', {}).get('source', 'unknown')
            tags = mem.get('meta', {}).get('tags', '')
            timestamp = mem.get('timestamp', 'unknown')
            output += f"  {i}. {text}\n"
            output += f"     📁 Source: {source} | 🏷️ Tags: {tags} | 🕐 {timestamp}\n"

        return output
    except Exception as e:
        return f"❌ Tag Search Error: {e}"

@function_tool
async def get_knowledge_stats_tool() -> str:
    """
    Shows statistics about the Knowledge Base: total entries, categories/tags breakdown,
    last added entry, and memory file size.
    """
    try:
        with memory_core._lock:
            total = len(memory_core.memories)

            if total == 0:
                return "📊 Knowledge Base is empty. No entries stored yet."

            # Tags breakdown
            tag_counts = {}
            source_counts = {}
            for mem in memory_core.memories:
                meta = mem.get('meta', {})
                # Count tags
                tags = meta.get('tags', '')
                if isinstance(tags, str) and tags.strip():
                    for t in tags.split(','):
                        t = t.strip()
                        if t:
                            tag_counts[t] = tag_counts.get(t, 0) + 1
                elif isinstance(tags, list):
                    for t in tags:
                        t = str(t).strip()
                        if t:
                            tag_counts[t] = tag_counts.get(t, 0) + 1

                # Count sources
                source = meta.get('source', 'unknown')
                source_counts[source] = source_counts.get(source, 0) + 1

            # Last added entry
            last_entry = memory_core.memories[-1]
            last_text = last_entry.get('text', 'N/A')[:80]
            last_time = last_entry.get('timestamp', 'unknown')

            # Memory file size
            file_size = "N/A"
            if os.path.exists(memory_core.memory_path):
                size_bytes = os.path.getsize(memory_core.memory_path)
                if size_bytes < 1024:
                    file_size = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    file_size = f"{size_bytes / 1024:.1f} KB"
                else:
                    file_size = f"{size_bytes / (1024 * 1024):.2f} MB"

            # Build output
            output = "📊 === KNOWLEDGE BASE STATS ===\n\n"
            output += f"📦 Total Entries: {total}\n"
            output += f"💾 Memory File Size: {file_size}\n"
            output += f"🕐 Last Added: {last_time}\n"
            output += f"   └─ \"{last_text}{'...' if len(last_entry.get('text', '')) > 80 else ''}\"\n\n"

            if source_counts:
                output += f"📁 Sources ({len(source_counts)}):\n"
                for src, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                    output += f"  • {src}: {count} entries\n"
                output += "\n"

            if tag_counts:
                output += f"🏷️ Tags ({len(tag_counts)}):\n"
                for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:15]:
                    output += f"  • {tag}: {count} entries\n"
            else:
                output += "🏷️ Tags: No tags found\n"

            return output
    except Exception as e:
        return f"❌ Stats Error: {e}"

@function_tool
async def clear_knowledge_tool(confirm: str = "no") -> str:
    """
    Clears ALL knowledge entries from the Vector DB. This action is irreversible.
    Args:
        confirm: Must be "yes" to execute. Safety check to prevent accidental deletion.
    """
    if confirm.lower().strip() != "yes":
        return (
            "⚠️ SAFETY CHECK: This will permanently delete ALL knowledge entries.\n"
            "To confirm, call this tool with confirm='yes'.\n"
            "This action CANNOT be undone."
        )

    try:
        with memory_core._lock:
            entry_count = len(memory_core.memories)

            # Create backup before clearing
            if os.path.exists(memory_core.memory_path):
                backup_path = memory_core.memory_path + ".pre_clear.bak"
                try:
                    import shutil
                    shutil.copy2(memory_core.memory_path, backup_path)
                    logger.info(f"📋 Backup created at: {backup_path}")
                except Exception as e:
                    logger.warning(f"Backup failed (proceeding anyway): {e}")

            memory_core.memories.clear()
            memory_core._unsaved_count = 0
            memory_core._save_memory()

        return (
            f"🗑️ Knowledge Base CLEARED.\n"
            f"   Deleted: {entry_count} entries\n"
            f"   Backup saved to: {memory_core.memory_path}.pre_clear.bak"
        )
    except Exception as e:
        return f"❌ Clear Error: {e}"
