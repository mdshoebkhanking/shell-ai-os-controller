#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_memory")

MEMORY_FILE = os.path.join(os.path.expanduser("~"), ".shell_smart_memory.json")

def _memory_v2_active() -> bool:
    try:
        from shell_memory_v2 import memory_v2_enabled
        return bool(memory_v2_enabled())
    except Exception as e:
        logger.debug("Memory v2 unavailable, using legacy JSON memory: %s", e)
        return False

def load_memory() -> Dict[str, Any]:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
    return {
        "personal_info": {},
        "preferences": {},
        "goals_projects": {},
        "routine_habits": {},
        "important_events": {}
    }

def save_memory(data: Dict[str, Any]) -> bool:
    """Atomically save memory to disk. Returns True on success, False on failure.

    Uses ``os.replace`` which is atomic on POSIX and Windows — the old
    remove-then-rename pattern could lose the file if the process crashed
    between the two calls. Backup creation is best-effort and never blocks
    the save itself.
    """
    try:
        # 1. Write new data to a temp sibling file.
        temp_file = MEMORY_FILE + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # 2. Best-effort backup of the existing file (atomic replace).
        if os.path.exists(MEMORY_FILE):
            try:
                os.replace(MEMORY_FILE, MEMORY_FILE + ".bak")
            except OSError as _bak:
                logger.debug("memory backup skipped: %s", _bak)

        # 3. Atomic swap-in of the new file — no crash window.
        os.replace(temp_file, MEMORY_FILE)
        return True
    except Exception as e:
        logger.error(f"Error saving memory: {e}")
        return False

@function_tool
async def update_memory_tool(category: str, key: str, value: str) -> str:
    """
    Saves or updates high-value information in Shell's long-term memory.
    Sirf bohot zaroori baatein save karein (Personal Info, Preferences, Goals, Routine, Events).
    Random chat ya jokes save na karein.

    Args:
        category: 'personal_info', 'preferences', 'goals_projects', 'routine_habits', or 'important_events'.
        key: The specific item (e.g., 'nickname', 'music_choice', 'python_goal').
        value: The information to remember.
    """
    if _memory_v2_active():
        try:
            from shell_memory_v2 import save_memory as save_memory_v2

            result = save_memory_v2(
                f"{key}: {value}",
                tags=[category, key],
                source="legacy_memory_tool",
                metadata={"legacy_category": category, "legacy_key": key},
            )
            memory_id = result.get("memory", {}).get("memory_id", "")
            logger.info("Memory v2 updated: [%s] %s id=%s", category, key, memory_id)
            return f"✅ Done boss! Memory v2 mein yaad ho gaya. id={memory_id}"
        except Exception as e:
            logger.warning("Memory v2 save failed, falling back to legacy JSON: %s", e)

    memory = load_memory()
    if category not in memory:
        return f"❌ Invalid category: {category}"

    memory[category][key] = value
    save_memory(memory)
    logger.info(f"🧠 Memory Updated: [{category}] {key} = {value}")
    return f"✅ Done boss! Maine ye '{category}' mein yaad kar liya hai."

@function_tool
async def get_full_memory() -> str:
    """
    Retrieves all high-value information Shell remembers about the user.
    Shows entry counts per category, file size, and last modified date.
    Use this to personalize your conversation.
    """
    if _memory_v2_active():
        try:
            from core.memory.v2 import MemoryV2Store, default_memory_v2_path

            store = MemoryV2Store(default_memory_v2_path())
            stats = store.stats()
            memories = [item.to_dict() for item in store.recall_memory("", limit=50)]
            if not memories:
                return "🧠 Memory v2 empty hai (koi zaroori baat yaad nahi)."
            output = "--- MEMORY V2 DATA ---\n"
            output += (
                f"Store: {stats['path']} | Active: {stats['active_memories']} | "
                f"Recall audit: {stats['audit_entries']}\n"
            )
            for index, row in enumerate(memories, 1):
                tags = ", ".join(row.get("tags") or [])
                output += f"\n{index}. {row.get('redacted_text') or row.get('text')}\n"
                output += f"   importance={row.get('importance')} | tags={tags}\n"
            return output[:3900] + ("\n\n... [TRUNCATED DUE TO SIZE] ..." if len(output) > 3900 else "")
        except Exception as e:
            logger.warning("Memory v2 full read failed, falling back to legacy JSON: %s", e)

    memory = load_memory()

    # File metadata
    file_size = "N/A"
    last_modified = "N/A"
    if os.path.exists(MEMORY_FILE):
        size_bytes = os.path.getsize(MEMORY_FILE)
        if size_bytes < 1024:
            file_size = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            file_size = f"{size_bytes / 1024:.1f} KB"
        else:
            file_size = f"{size_bytes / (1024 * 1024):.2f} MB"

        mod_timestamp = os.path.getmtime(MEMORY_FILE)
        last_modified = datetime.fromtimestamp(mod_timestamp).strftime("%Y-%m-%d %H:%M:%S")

    # Count total entries
    total_entries = sum(len(items) for items in memory.values())

    # Build output
    output = "--- SMART MEMORY DATA ---\n"
    output += f"💾 File Size: {file_size} | 🕐 Last Modified: {last_modified}\n"
    output += f"📦 Total Entries: {total_entries}\n"

    for cat, items in memory.items():
        entry_count = len(items)
        if items:
            output += f"\n[{cat.upper()}] ({entry_count} entries):\n"
            for k, v in items.items():
                output += f"  • {k}: {v}\n"
        else:
            output += f"\n[{cat.upper()}] (0 entries)\n"

    if total_entries == 0:
        return "🧠 Memory empty hai (Koi zaroori baat yaad nahi)."

    # Phase 7: Context Window Protection (Max 4000 characters for LLM)
    if len(output) > 4000:
        logger.warning("🧠 Memory too large! Truncating for AI context.")
        return output[:3900] + "\n\n... [TRUNCATED DUE TO SIZE] ...\n(Direct the user to 'clear memory' if it's too bloated.)"

    return output

@function_tool
async def delete_memory_tool(category: str, key: str) -> str:
    """
    Deletes a specific memory entry by category and key.
    Args:
        category: The category to delete from (e.g., 'personal_info', 'preferences').
        key: The specific key to delete (e.g., 'nickname', 'music_choice').
    """
    if _memory_v2_active():
        try:
            from shell_memory_v2 import forget_memory as forget_memory_v2

            result = forget_memory_v2(query=key, tag=category)
            count = int(result.get("forgotten") or 0)
            if count <= 0:
                return f"❌ Memory v2 mein '{category}/{key}' match nahi mila."
            logger.info("Memory v2 deleted: [%s] %s count=%s", category, key, count)
            return f"🗑️ Memory v2 se {count} entrie(s) delete ho gayi."
        except Exception as e:
            logger.warning("Memory v2 delete failed, falling back to legacy JSON: %s", e)

    memory = load_memory()

    if category not in memory:
        valid_cats = ", ".join(memory.keys())
        return f"❌ Invalid category: '{category}'. Valid categories: {valid_cats}"

    if key not in memory[category]:
        if not memory[category]:
            return f"❌ Category '{category}' is empty. Nothing to delete."
        available_keys = ", ".join(memory[category].keys())
        return f"❌ Key '{key}' not found in '{category}'. Available keys: {available_keys}"

    deleted_value = memory[category].pop(key)
    save_memory(memory)
    logger.info(f"🗑️ Memory Deleted: [{category}] {key}")
    return f"🗑️ Deleted from '{category}': {key} = {deleted_value}"

@function_tool
async def search_memory_tool(query: str) -> str:
    """
    Searches across all memory categories for matching keys or values.
    Case-insensitive fuzzy matching.
    Args:
        query: The search term to find across all memory entries.
    """
    if not query or not query.strip():
        return "❌ Please provide a search query."

    if _memory_v2_active():
        try:
            from shell_memory_v2 import format_recall_results, recall_memory as recall_memory_v2

            result = recall_memory_v2(query, limit=10)
            return format_recall_results(result, empty_message=f"❌ No Memory v2 entries found matching: '{query}'")
        except Exception as e:
            logger.warning("Memory v2 search failed, falling back to legacy JSON: %s", e)

    query_lower = query.lower().strip()
    memory = load_memory()
    results = []

    for category, items in memory.items():
        for key, value in items.items():
            key_str = str(key).lower()
            value_str = str(value).lower()

            # Check for fuzzy match in key or value
            match_score = 0
            match_locations = []

            # Exact substring match
            if query_lower in key_str:
                match_score += 3
                match_locations.append("key")
            if query_lower in value_str:
                match_score += 2
                match_locations.append("value")

            # Word-level fuzzy matching
            if match_score == 0:
                query_words = query_lower.split()
                for word in query_words:
                    if len(word) >= 3:  # Skip very short words
                        if word in key_str:
                            match_score += 1
                            if "key(partial)" not in match_locations:
                                match_locations.append("key(partial)")
                        if word in value_str:
                            match_score += 1
                            if "value(partial)" not in match_locations:
                                match_locations.append("value(partial)")

            if match_score > 0:
                results.append({
                    "category": category,
                    "key": key,
                    "value": value,
                    "score": match_score,
                    "matched_in": match_locations
                })

    if not results:
        return f"❌ No memory entries found matching: '{query}'"

    # Sort by match score (highest first)
    results.sort(key=lambda x: x['score'], reverse=True)

    output = f"🔍 [MEMORY SEARCH: '{query}'] — {len(results)} result(s):\n\n"
    for i, r in enumerate(results, 1):
        matched_in = ", ".join(r['matched_in'])
        output += f"  {i}. [{r['category']}] {r['key']}: {r['value']}\n"
        output += f"     Matched in: {matched_in}\n"

    return output

@function_tool
async def export_memory_tool(format: str = "json") -> str:
    """
    Exports all memory to a file. Saves to Documents/Shell_Exports/.
    Args:
        format: Export format - 'json' or 'txt' (default: 'json').
    """
    format_lower = format.lower().strip()
    if format_lower not in ("json", "txt"):
        return "❌ Invalid format. Supported formats: 'json', 'txt'"

    memory = load_memory()
    total_entries = sum(len(items) for items in memory.values())

    if total_entries == 0:
        return "❌ Memory is empty. Nothing to export."

    # Create export directory
    export_dir = os.path.join(os.path.expanduser("~"), "Documents", "Shell_Exports")
    try:
        os.makedirs(export_dir, exist_ok=True)
    except Exception as e:
        return f"❌ Could not create export directory: {e}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        if format_lower == "json":
            filename = f"shell_memory_export_{timestamp}.json"
            filepath = os.path.join(export_dir, filename)
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "total_entries": total_entries,
                "memory": memory
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)

        elif format_lower == "txt":
            filename = f"shell_memory_export_{timestamp}.txt"
            filepath = os.path.join(export_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"=== SHELL MEMORY EXPORT ===\n")
                f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Entries: {total_entries}\n")
                f.write(f"{'=' * 40}\n\n")

                for category, items in memory.items():
                    f.write(f"[{category.upper()}] ({len(items)} entries)\n")
                    f.write(f"{'-' * 30}\n")
                    if items:
                        for key, value in items.items():
                            f.write(f"  {key}: {value}\n")
                    else:
                        f.write(f"  (empty)\n")
                    f.write("\n")

        file_size = os.path.getsize(filepath)
        size_str = f"{file_size} B" if file_size < 1024 else f"{file_size / 1024:.1f} KB"

        return (
            f"✅ Memory exported successfully!\n"
            f"   📄 File: {filepath}\n"
            f"   📦 Entries: {total_entries}\n"
            f"   💾 Size: {size_str}\n"
            f"   📂 Format: {format_lower.upper()}"
        )
    except Exception as e:
        return f"❌ Export Error: {e}"

__all__ = ['update_memory_tool', 'get_full_memory', 'delete_memory_tool', 'search_memory_tool', 'export_memory_tool']
