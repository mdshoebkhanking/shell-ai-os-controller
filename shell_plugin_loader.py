"""
Shell Plugin Loader — Auto-Discovery System
---------------------------------------------
Scans all shell_*.py files and auto-discovers tools decorated with @god_tier_tool.
Replaces 400+ lines of manual imports in agent.py.

Usage:
    from shell_plugin_loader import PluginLoader

    loader = PluginLoader()
    tools = loader.load_all()       # Returns list of tool objects
    report = loader.get_report()    # Returns load summary
"""

import os
import sys
import importlib
import logging
import time
from typing import Optional

logger = logging.getLogger("shell_plugin_loader")

# Modules that are manually loaded in agent.py's __init__ (core, always required)
_CORE_MODULES = frozenset({
    "shell_safe_executor",
    "shell_config",
    "shell_logger",
    "shell_cache",
    "shell_validator",
    "shell_rate_limiter",
    "shell_http",
    "shell_health",
    "shell_startup",
    "shell_prompts",
    "shell_plugin_loader",
    "shell_tool_registry",
    "shell_error_tracker",
    "shell_middleware",
    "shell_async_utils",
})

# Modules that need special handling (imported manually in agent.py)
_MANUAL_MODULES = frozenset({
    "shell_hub",
    "shell_console_client",
    "shell_mcp_server",
})

# Module load order priorities (lower = loaded first)
_PRIORITY = {
    "shell_google_search": 1,
    "shell_get_whether": 1,
    "shell_window_CTRL": 1,
    "shell_browser_CTRL": 2,
    "shell_system_pro": 2,
    "shell_image_ai": 3,
    "shell_code_engine": 3,
}


class PluginLoader:
    """Auto-discovers and loads shell_*.py tool modules."""

    def __init__(self, search_dir: Optional[str] = None):
        self._search_dir = search_dir or os.path.dirname(os.path.abspath(__file__))
        self._loaded: dict[str, dict] = {}   # module_name -> {tools, time_ms, error}
        self._failed: dict[str, str] = {}    # module_name -> error_msg
        self._total_time_ms = 0

    def discover_modules(self) -> list[str]:
        """Find all shell_*.py files that could contain tools.

        Filenames are validated against a strict `^shell_[a-z0-9_]+\\.py$`
        regex AND their resolved realpath must live inside the search
        directory — this blocks symlink escapes where an attacker plants
        a symlink named `shell_evil.py` pointing somewhere outside the
        project tree.
        """
        import re as _re
        safe_name = _re.compile(r"^shell_[a-z0-9_]+\.py$")
        base_real = os.path.realpath(self._search_dir)
        modules = []
        for fname in os.listdir(self._search_dir):
            if not safe_name.match(fname):
                continue
            candidate = os.path.realpath(os.path.join(self._search_dir, fname))
            if not (candidate + os.sep).startswith(base_real + os.sep) and candidate != base_real:
                logger.warning("plugin_loader: rejecting %r — realpath escapes search dir", fname)
                continue
            mod_name = fname[:-3]
            if mod_name in _CORE_MODULES or mod_name in _MANUAL_MODULES:
                continue
            modules.append(mod_name)

        # Sort by priority then alphabetically
        modules.sort(key=lambda m: (_PRIORITY.get(m, 99), m))
        return modules

    def _extract_tools(self, module) -> list:
        """Extract tool objects from a loaded module."""
        tools = []

        # Method 1: Check shell_safe_executor registry for tools from this module
        try:
            from shell_safe_executor import get_registered_tools_info
            mod_file = getattr(module, "__file__", "")
            for name, obj in get_registered_tools_info():
                # Check if the tool's original function came from this module
                inner = getattr(obj, "__wrapped__", None) or getattr(obj, "_original_func", None)
                if inner:
                    inner_mod = getattr(inner, "__module__", "")
                    if inner_mod == module.__name__:
                        tools.append(obj)
                        continue
                # Fallback: check by name matching module exports
                if hasattr(module, name):
                    mod_obj = getattr(module, name)
                    if mod_obj is obj or id(mod_obj) == id(obj):
                        tools.append(obj)
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)

        if tools:
            return tools

        # Method 2: Look for objects that look like livekit function_tools
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            obj = getattr(module, attr_name)
            # LiveKit function_tool wraps into FunctionTool or similar
            if callable(obj) and (
                hasattr(obj, "name") and hasattr(obj, "description")
                or getattr(obj, "_lk_tool", False)
                or "function_tool" in str(type(obj)).lower()
                or "functiontool" in str(type(obj)).lower()
            ):
                tools.append(obj)

        return tools

    def load_module(self, module_name: str) -> list:
        """Load a single module and extract its tools."""
        start = time.time()
        try:
            # Ensure search dir is in path
            if self._search_dir not in sys.path:
                sys.path.insert(0, self._search_dir)

            mod = importlib.import_module(module_name)
            tools = self._extract_tools(mod)
            elapsed_ms = round((time.time() - start) * 1000)

            self._loaded[module_name] = {
                "tools": tools,
                "tool_names": [getattr(t, "name", getattr(t, "__name__", "?")) for t in tools],
                "time_ms": elapsed_ms,
                "error": None,
            }
            if tools:
                logger.info(f"Loaded {module_name}: {len(tools)} tools ({elapsed_ms}ms)")
            else:
                logger.debug(f"Loaded {module_name}: 0 tools ({elapsed_ms}ms)")

            return tools

        except Exception as e:
            elapsed_ms = round((time.time() - start) * 1000)
            error_msg = f"{type(e).__name__}: {e}"
            self._failed[module_name] = error_msg
            self._loaded[module_name] = {
                "tools": [],
                "tool_names": [],
                "time_ms": elapsed_ms,
                "error": error_msg,
            }
            logger.warning(f"Failed to load {module_name}: {error_msg}")
            return []

    def load_all(self, exclude: Optional[set] = None) -> list:
        """Load all discovered modules and return flat list of tools."""
        exclude = exclude or set()
        all_tools = []
        start = time.time()

        modules = self.discover_modules()
        for mod_name in modules:
            if mod_name in exclude:
                continue
            tools = self.load_module(mod_name)
            all_tools.extend(tools)

        self._total_time_ms = round((time.time() - start) * 1000)
        logger.info(
            f"Plugin loading complete: {len(all_tools)} tools from "
            f"{len(self._loaded) - len(self._failed)}/{len(self._loaded)} modules "
            f"({self._total_time_ms}ms)"
        )
        return all_tools

    def load_selective(self, module_names: list[str]) -> list:
        """Load only specified modules."""
        all_tools = []
        start = time.time()
        for mod_name in module_names:
            tools = self.load_module(mod_name)
            all_tools.extend(tools)
        self._total_time_ms = round((time.time() - start) * 1000)
        return all_tools

    def get_report(self) -> str:
        """Get human-readable load report."""
        lines = [
            f"Plugin Loader Report",
            f"{'=' * 50}",
            f"Total Tools: {sum(len(v['tools']) for v in self._loaded.values())}",
            f"Modules Loaded: {len(self._loaded) - len(self._failed)}/{len(self._loaded)}",
            f"Load Time: {self._total_time_ms}ms",
        ]

        if self._failed:
            lines.append(f"\nFailed Modules ({len(self._failed)}):")
            for mod, err in self._failed.items():
                lines.append(f"  {mod}: {err}")

        lines.append(f"\nSuccessful Modules:")
        for mod, info in self._loaded.items():
            if info["error"]:
                continue
            if info["tools"]:
                names = ", ".join(info["tool_names"][:5])
                extra = f" +{len(info['tool_names'])-5} more" if len(info["tool_names"]) > 5 else ""
                lines.append(f"  {mod}: {len(info['tools'])} tools ({info['time_ms']}ms) [{names}{extra}]")

        return "\n".join(lines)

    def get_loaded_tools_flat(self) -> list:
        """Get flat list of all successfully loaded tools."""
        tools = []
        for info in self._loaded.values():
            if not info["error"]:
                tools.extend(info["tools"])
        return tools

    def get_stats(self) -> dict:
        """Get machine-readable stats."""
        return {
            "total_tools": sum(len(v["tools"]) for v in self._loaded.values()),
            "modules_ok": len(self._loaded) - len(self._failed),
            "modules_failed": len(self._failed),
            "total_time_ms": self._total_time_ms,
            "failed": dict(self._failed),
        }


# Convenience function
def auto_discover_tools(exclude: Optional[set] = None) -> tuple[list, PluginLoader]:
    """One-call auto-discovery. Returns (tools_list, loader_instance)."""
    loader = PluginLoader()
    tools = loader.load_all(exclude=exclude)
    return tools, loader
