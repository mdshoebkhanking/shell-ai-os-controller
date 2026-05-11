"""
SHELL MODEL CONTEXT PROTOCOL (MCP) SERVER
The Central Nervous System for Data Retrieval.
Standardizes all data access (Memory, Files, Knowledge, System) into Resource URIs.
"""

import os
import json
import logging
import datetime
import platform
import time
from typing import List, Optional, Dict
from shell_safe_executor import god_tier_tool as function_tool
from shell_brain.infinite_context import INFINITE_KNOWLEDGE_BASE
from brain.memory_core import memory_core
import psutil

logger = logging.getLogger("shell_mcp")

# Track server start time for uptime calculation
_MCP_SERVER_START_TIME = time.time()

class ShellMCPServer:
    """
    🌐 Shell MCP Server -> The Universal Resource Broker.
    Protocol: scheme://path
    Schemes:
      - akashic://  -> Static Infinite Knowledge
      - memory://   -> Vector Long-Term Memory
      - file://     -> Local File System
      - sys://      -> Live System Status
    """
    
    def __init__(self):
        self.name = "Shell-Nexus-v1"
        logger.info(f"✅ MCP Server '{self.name}' Online.")

    def list_resources(self, scheme: str = None) -> List[str]:
        """Lists available resources, optionally filtered by scheme."""
        resources = []
        
        # 1. AKASHIC RESOURCES
        if not scheme or scheme == "akashic":
            for category, items in INFINITE_KNOWLEDGE_BASE.items():
                for key in items.keys():
                    resources.append(f"akashic://{category}/{key}")

        # 2. SYSTEM RESOURCES
        if not scheme or scheme == "sys":
            resources.extend([
                "sys://cpu",
                "sys://ram",
                "sys://battery",
                "sys://processes",
                "sys://disk",
                "sys://network",
                "sys://uptime"
            ])
            
        # 3. MEMORY (Virtual List)
        if not scheme or scheme == "memory":
            resources.append("memory://<search_query>")
            
        return resources

    def read_resource(self, uri: str) -> str:
        """
        Retrieves the content of a resource URI.
        """
        try:
            logger.info(f"📥 MCP Read Request: {uri}")
            
            # --- AKASHIC PROTOCOL ---
            if uri.startswith("akashic://"):
                # Format: akashic://CATEGORY/Key
                parts = uri.replace("akashic://", "").split("/")
                if len(parts) < 2: return "❌ Invalid URI Format"
                category, key = parts[0], parts[1]
                
                # Fuzzy match in static DB
                cat_data = INFINITE_KNOWLEDGE_BASE.get(category, {})
                # Try exact match first
                if key in cat_data:
                    return cat_data[key]
                
                # Try finding key in any category if direct fail
                for k, v in cat_data.items():
                    if k.lower() == key.lower():
                        return v
                return "❌ Key not found in Akashic Records."

            # --- MEMORY PROTOCOL ---
            elif uri.startswith("memory://"):
                query = uri.replace("memory://", "")
                results = memory_core.search_memory(query, top_k=5)
                if not results: return "📭 No memories found."
                return "\n".join([f"- {r['text']} (Source: {r['meta'].get('source')})" for r in results])

            # --- FILE PROTOCOL ---
            elif uri.startswith("file://"):
                path = uri.replace("file://", "")
                if os.path.exists(path):
                    stat = os.stat(path)
                    size_bytes = stat.st_size
                    if size_bytes < 1024:
                        size_str = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
                    modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    header = f"📄 File: {os.path.basename(path)}\n📏 Size: {size_str}\n🕐 Last Modified: {modified}\n{'─' * 40}\n"
                    with open(path, "r", encoding="utf-8", errors='ignore') as f:
                        content = f.read(2100)
                    if len(content) > 2000:
                        content = content[:2000] + "\n\n[TRUNCATED - File bahut bada hai, pura content nahi dikha sakte]"
                    return header + content
                return "❌ File not found."

            # --- SYSTEM PROTOCOL ---
            elif uri.startswith("sys://"):
                subtype = uri.replace("sys://", "")
                if subtype == "cpu":
                    return f"CPU Usage: {psutil.cpu_percent()}%"
                elif subtype == "ram":
                    mem = psutil.virtual_memory()
                    return f"RAM: {mem.percent}% Used ({mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB)"
                elif subtype == "battery":
                    bat = psutil.sensors_battery()
                    return f"Battery: {bat.percent}% ({'Plugged In' if bat.power_plugged else 'Draining'})" if bat else "No Battery Detected"
                elif subtype == "processes":
                    procs = [p.info for p in psutil.process_iter(['pid', 'name', 'username'])][:10]
                    return json.dumps(procs, indent=2)
                elif subtype == "disk":
                    partitions = psutil.disk_partitions()
                    result = "💾 Disk Usage:\n"
                    for p in partitions:
                        try:
                            usage = psutil.disk_usage(p.mountpoint)
                            result += f"  {p.device} ({p.mountpoint}): {usage.percent}% used — {usage.used // (1024**3)}GB / {usage.total // (1024**3)}GB\n"
                        except PermissionError:
                            result += f"  {p.device} ({p.mountpoint}): Access Denied\n"
                    return result.strip()
                elif subtype == "network":
                    net = psutil.net_io_counters()
                    result = (
                        f"🌐 Network Stats:\n"
                        f"  📤 Bytes Sent: {net.bytes_sent / (1024**2):.1f} MB\n"
                        f"  📥 Bytes Recv: {net.bytes_recv / (1024**2):.1f} MB\n"
                        f"  📦 Packets Sent: {net.packets_sent}\n"
                        f"  📦 Packets Recv: {net.packets_recv}\n"
                        f"  ❌ Errors In: {net.errin} | Errors Out: {net.errout}"
                    )
                    return result
                elif subtype == "uptime":
                    boot_time = psutil.boot_time()
                    uptime_secs = time.time() - boot_time
                    days = int(uptime_secs // 86400)
                    hours = int((uptime_secs % 86400) // 3600)
                    minutes = int((uptime_secs % 3600) // 60)
                    boot_str = datetime.datetime.fromtimestamp(boot_time).strftime("%Y-%m-%d %H:%M:%S")
                    return f"⏱️ System Uptime: {days}d {hours}h {minutes}m\n🟢 Boot Time: {boot_str}"

            return "❌ Unknown Protocol Scheme"

        except Exception as e:
            logger.error(f"MCP Read Error: {e}")
            return f"❌ Internal MCP Error: {e}"

# Singleton Instance
mcp_server = ShellMCPServer()

# --- MCP TOOLS FOR AGENT ---

@function_tool
async def list_mcp_resources_tool(scheme: str = None) -> str:
    """
    🌐 MCP: Lists available data resources (Akashic, System, Files, Memory).
    Har scheme ka count aur emoji ke saath formatted list deta hai.
    Args:
        scheme: Optional filter ('akashic', 'sys', 'file', 'memory').
    """
    res = mcp_server.list_resources(scheme)
    if not res:
        return "❌ Koi resources nahi mile. No resources found for the given scheme."

    # Emoji map per scheme type
    scheme_emojis = {
        "akashic": "📚",
        "sys": "🖥️",
        "file": "📁",
        "memory": "🧠",
    }

    # Group by scheme and count
    grouped: Dict[str, list] = {}
    for r in res:
        s = r.split("://")[0] if "://" in r else "unknown"
        grouped.setdefault(s, []).append(r)

    # Build formatted output
    output = "🌐 **MCP Resources Overview**\n" + "═" * 40 + "\n"
    for s, items in grouped.items():
        emoji = scheme_emojis.get(s, "🔗")
        output += f"\n{emoji} **{s.upper()}** — {len(items)} resource(s)\n"
        for item in items[:15]:
            output += f"  ├─ {item}\n"
        if len(items) > 15:
            output += f"  └─ ... aur {len(items) - 15} aur hain\n"

    output += f"\n{'─' * 40}\n📊 Total: {len(res)} resources across {len(grouped)} scheme(s)"
    return output

@function_tool
async def read_mcp_resource_tool(uri: str) -> str:
    """
    📖 MCP: Kisi bhi resource URI ka content read karta hai.
    Reads the content of a specific resource URI with enhanced details.
    Args:
        uri: The full URI (e.g., 'akashic://SCIENCE_PHYSICS/Quantum Mechanics', 'sys://cpu', 'sys://disk').
    """
    result = mcp_server.read_resource(uri)
    scheme = uri.split("://")[0] if "://" in uri else "unknown"
    return f"📖 MCP Read — `{uri}` ({scheme} scheme)\n{'─' * 40}\n{result}"


@function_tool
async def search_mcp_resources_tool(query: str) -> str:
    """
    🔍 MCP: Saare schemes mein resources search karta hai query string se.
    Searches across all schemes for resources matching query string with fuzzy matching.
    Args:
        query: Search query string to match against resource URIs and akashic content.
    """
    try:
        query_lower = query.lower()
        matches = []

        # 1. Search Akashic URIs and content
        for category, items in INFINITE_KNOWLEDGE_BASE.items():
            for key, value in items.items():
                uri = f"akashic://{category}/{key}"
                score = 0
                # URI match
                if query_lower in uri.lower():
                    score += 3
                # Key match
                if query_lower in key.lower():
                    score += 2
                # Content match (fuzzy in value text)
                content_str = str(value).lower() if value else ""
                if query_lower in content_str:
                    score += 1
                if score > 0:
                    matches.append((score, uri, "akashic"))

        # 2. Search System resources
        sys_resources = ["sys://cpu", "sys://ram", "sys://battery", "sys://processes", "sys://disk", "sys://network", "sys://uptime"]
        for sr in sys_resources:
            if query_lower in sr.lower():
                matches.append((2, sr, "sys"))

        # 3. Search Memory
        try:
            mem_results = memory_core.search_memory(query, top_k=5)
            for i, r in enumerate(mem_results or []):
                matches.append((2, f"memory://{query} (result {i+1})", "memory"))
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)

        # Sort by score descending, take top 10
        matches.sort(key=lambda x: x[0], reverse=True)
        top = matches[:10]

        if not top:
            return f"🔍 '{query}' ke liye koi matching resource nahi mila. Try a different query."

        output = f"🔍 **Search Results for '{query}'** — Top {len(top)} matches\n{'═' * 40}\n"
        for i, (score, uri, scheme) in enumerate(top, 1):
            stars = "★" * min(score, 5)
            output += f"  {i}. [{stars}] {uri}  (scheme: {scheme})\n"
        output += f"{'─' * 40}\n💡 Total matches found: {len(matches)} | Showing top {len(top)}"
        return output

    except Exception as e:
        logger.error(f"MCP Search Error: {e}")
        return f"❌ Search mein error aa gaya: {e}"


@function_tool
async def get_mcp_stats_tool() -> str:
    """
    📊 MCP: Server stats dikhata hai — server name, total resources per scheme, system snapshot, uptime.
    Shows MCP server statistics including resource counts, system status, and uptime.
    """
    try:
        # Server info
        output = f"📊 **MCP Server Stats**\n{'═' * 40}\n"
        output += f"🏷️ Server Name: {mcp_server.name}\n"

        # Resource count per scheme
        all_res = mcp_server.list_resources()
        grouped: Dict[str, int] = {}
        for r in all_res:
            s = r.split("://")[0] if "://" in r else "unknown"
            grouped[s] = grouped.get(s, 0) + 1

        output += f"\n📦 **Resources per Scheme:**\n"
        scheme_emojis = {"akashic": "📚", "sys": "🖥️", "file": "📁", "memory": "🧠"}
        for s, count in grouped.items():
            emoji = scheme_emojis.get(s, "🔗")
            output += f"  {emoji} {s}: {count}\n"
        output += f"  📊 Total: {len(all_res)}\n"

        # System snapshot
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        output += f"\n🖥️ **System Snapshot:**\n"
        output += f"  ⚡ CPU: {cpu}%\n"
        output += f"  🧠 RAM: {mem.percent}% ({mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB)\n"

        # MCP Server uptime
        server_uptime = time.time() - _MCP_SERVER_START_TIME
        s_hours = int(server_uptime // 3600)
        s_mins = int((server_uptime % 3600) // 60)
        s_secs = int(server_uptime % 60)
        output += f"\n⏱️ **MCP Server Uptime:** {s_hours}h {s_mins}m {s_secs}s\n"

        # System uptime
        boot_time = psutil.boot_time()
        sys_uptime = time.time() - boot_time
        days = int(sys_uptime // 86400)
        hours = int((sys_uptime % 86400) // 3600)
        mins = int((sys_uptime % 3600) // 60)
        output += f"🟢 **System Uptime:** {days}d {hours}h {mins}m"

        return output

    except Exception as e:
        logger.error(f"MCP Stats Error: {e}")
        return f"❌ Stats fetch karne mein error: {e}"
