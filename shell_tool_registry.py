"""
Shell Tool Registry — Enhanced Tool Management
-------------------------------------------------
Central registry with categories, metadata, search, and tool info API.

Usage:
    from shell_tool_registry import ToolRegistry

    registry = ToolRegistry.get()
    registry.register("google_search", tool_obj, category="web", description="Search Google")
    tools = registry.get_by_category("web")
    info = registry.search("email")
"""

import time
import logging
import threading
from typing import Optional

logger = logging.getLogger("shell_tool_registry")


class ToolInfo:
    """Metadata container for a registered tool."""
    __slots__ = ("name", "tool_obj", "category", "description", "module",
                 "registered_at", "call_count", "enabled", "metadata", "readiness")

    def __init__(self, name: str, tool_obj, category: str = "general",
                 description: str = "", module: str = ""):
        self.name = name
        self.tool_obj = tool_obj
        self.category = category
        self.description = description or self._extract_description(tool_obj)
        self.module = module
        self.registered_at = time.time()
        self.call_count = 0
        self.enabled = True
        try:
            from core.tools.metadata import infer_tool_metadata

            meta = infer_tool_metadata({
                "id": f"{module}:{name}" if module else name,
                "name": name,
                "module": module,
                "category": category,
                "description": self.description,
                "kind": "tool",
            }).to_dict()
        except Exception:
            meta = {
                "tool_id": f"{module}:{name}" if module else name,
                "category": category,
                "enabled": True,
                "readiness": {"state": "READY", "ok": True, "reasons": [], "requirements": []},
            }
        self.metadata = meta
        self.readiness = dict(meta.get("readiness") or {})

    @staticmethod
    def _extract_description(obj) -> str:
        """Try to get description from tool object."""
        # LiveKit function_tool stores description
        desc = getattr(obj, "description", "")
        if desc:
            return str(desc)[:200]
        # Try docstring
        doc = getattr(obj, "__doc__", "")
        if doc:
            return str(doc).strip().split("\n")[0][:200]
        return ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "module": self.module,
            "call_count": self.call_count,
            "enabled": self.enabled,
            "metadata": dict(self.metadata),
            "readiness": dict(self.readiness),
        }


class ToolRegistry:
    """Singleton enhanced tool registry."""

    _instance = None
    _cls_lock = threading.Lock()

    # Standard categories
    CATEGORIES = {
        "web": "Browser & Web Tools",
        "system": "System & OS Control",
        "media": "Image, Video, Audio",
        "communication": "Email, Telegram, WhatsApp",
        "productivity": "Timer, Planner, Tasks",
        "knowledge": "Memory, Knowledge, Learning",
        "code": "Code Engine & Execution",
        "brain": "AI Brain & Neural",
        "vision": "Screen Reading & OCR",
        "input": "Keyboard & Mouse Control",
        "utility": "General Utilities",
        "security": "Security & Diagnostics",
        "social": "Social Media",
        "general": "Uncategorized",
    }

    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}
        self._categories: dict[str, list[str]] = {}  # category -> [tool_names]
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> "ToolRegistry":
        if cls._instance is None:
            with cls._cls_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, name: str, tool_obj, category: str = "general",
                 description: str = "", module: str = "") -> None:
        """Register a tool with metadata."""
        with self._lock:
            info = ToolInfo(
                name=name,
                tool_obj=tool_obj,
                category=category,
                description=description,
                module=module,
            )
            self._tools[name] = info

            # Update category index
            if category not in self._categories:
                self._categories[category] = []
            if name not in self._categories[category]:
                self._categories[category].append(name)

    def register_bulk(self, tools: list, category: str = "general",
                      module: str = "") -> int:
        """Register multiple tools at once. Returns count registered."""
        count = 0
        for tool in tools:
            name = getattr(tool, "name", getattr(tool, "__name__", None))
            if not name:
                continue
            self.register(name, tool, category=category, module=module)
            count += 1
        return count

    def get_tool(self, name: str) -> Optional[ToolInfo]:
        """Get tool info by name."""
        return self._tools.get(name)

    def get_tool_obj(self, name: str):
        """Get the actual tool object by name."""
        info = self._tools.get(name)
        return info.tool_obj if info else None

    def get_by_category(self, category: str) -> list[ToolInfo]:
        """Get all tools in a category."""
        with self._lock:
            names = self._categories.get(category, [])
            return [self._tools[n] for n in names if n in self._tools]

    def get_all_tools(self) -> list:
        """Get all tool objects (for passing to Agent)."""
        with self._lock:
            return [info.tool_obj for info in self._tools.values() if info.enabled]

    def get_enabled_tools(self) -> list:
        """Get only enabled tool objects."""
        with self._lock:
            return [info.tool_obj for info in self._tools.values() if info.enabled]

    def search(self, query: str) -> list[ToolInfo]:
        """Search tools by name or description."""
        query_lower = query.lower()
        results = []
        with self._lock:
            for info in self._tools.values():
                if (query_lower in info.name.lower() or
                        query_lower in info.description.lower() or
                        query_lower in info.category.lower()):
                    results.append(info)
        return results

    def enable(self, name: str) -> bool:
        """Enable a tool."""
        info = self._tools.get(name)
        if info:
            info.enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a tool (won't be returned in get_all_tools)."""
        info = self._tools.get(name)
        if info:
            info.enabled = False
            return True
        return False

    def record_call(self, name: str):
        """Increment call counter for a tool."""
        info = self._tools.get(name)
        if info:
            info.call_count += 1

    def get_summary(self) -> str:
        """Human-readable summary."""
        with self._lock:
            total = len(self._tools)
            enabled = sum(1 for t in self._tools.values() if t.enabled)

        lines = [
            "Tool Registry Summary",
            "=" * 50,
            f"Total Tools: {total} ({enabled} enabled)",
            "\nBy Category:",
        ]

        with self._lock:
            for cat, names in sorted(self._categories.items()):
                active = [n for n in names if self._tools.get(n, ToolInfo("", None)).enabled]
                label = self.CATEGORIES.get(cat, cat)
                lines.append(f"  {label}: {len(active)}/{len(names)}")

        # Most used tools
        with self._lock:
            top = sorted(self._tools.values(), key=lambda t: t.call_count, reverse=True)[:5]
        if any(t.call_count > 0 for t in top):
            lines.append("\nMost Used:")
            for t in top:
                if t.call_count > 0:
                    lines.append(f"  {t.name}: {t.call_count} calls")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        """Machine-readable stats."""
        with self._lock:
            return {
                "total": len(self._tools),
                "enabled": sum(1 for t in self._tools.values() if t.enabled),
                "categories": {k: len(v) for k, v in self._categories.items()},
                "total_calls": sum(t.call_count for t in self._tools.values()),
            }

    def export_tool_list(self) -> list[dict]:
        """Export all tool info as list of dicts."""
        with self._lock:
            return [info.to_dict() for info in self._tools.values()]
