"""
Shell Error Tracker — Centralized Error Aggregation
------------------------------------------------------
Tracks all tool errors, detects patterns, provides insights.
Works with god_tier_tool and Phoenix self-heal engine.

Usage:
    from shell_error_tracker import ErrorTracker

    tracker = ErrorTracker.get()
    tracker.record("google_search", error, traceback_str)
    report = tracker.get_report()
    patterns = tracker.detect_patterns()
"""

from __future__ import annotations

import time
import logging
import threading
from collections import defaultdict
from typing import Optional

logger = logging.getLogger("shell_error_tracker")


class ErrorEntry:
    __slots__ = ("tool_name", "error_type", "message", "timestamp", "traceback", "context")

    def __init__(self, tool_name: str, error_type: str, message: str,
                 traceback: str = "", context: Optional[dict] = None):
        self.tool_name = tool_name
        self.error_type = error_type
        self.message = message
        self.timestamp = time.time()
        self.traceback = traceback
        self.context = context or {}

    def to_dict(self) -> dict:
        return {
            "tool": self.tool_name,
            "type": self.error_type,
            "message": self.message[:200],
            "time": self.timestamp,
            "context": self.context,
        }


class ErrorTracker:
    """Singleton error tracker with pattern detection."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, max_entries: int = 500):
        self._errors: list[ErrorEntry] = []
        self._max_entries = max_entries
        self._tool_counts: dict[str, int] = defaultdict(int)
        self._type_counts: dict[str, int] = defaultdict(int)
        # Reentrant lock so helpers like get_stats() can call
        # get_top_failing_tools() / detect_patterns() from inside a locked
        # region without deadlocking on the same thread.
        self._lock = threading.RLock()
        self._start_time = time.time()

    @classmethod
    def get(cls) -> "ErrorTracker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def record(self, tool_name: str, error: Exception | str,
               traceback_str: str = "", context: Optional[dict] = None):
        """Record an error occurrence."""
        if isinstance(error, Exception):
            error_type = type(error).__name__
            message = str(error)
        else:
            error_type = "Error"
            message = str(error)

        entry = ErrorEntry(
            tool_name=tool_name,
            error_type=error_type,
            message=message,
            traceback=traceback_str,
            context=context,
        )

        with self._lock:
            self._errors.append(entry)
            self._tool_counts[tool_name] += 1
            self._type_counts[error_type] += 1

            # Evict old entries if over limit
            if len(self._errors) > self._max_entries:
                self._errors = self._errors[-self._max_entries:]

    def get_errors(self, tool_name: Optional[str] = None,
                   last_n: int = 20) -> list[dict]:
        """Get recent errors, optionally filtered by tool."""
        with self._lock:
            filtered = self._errors
            if tool_name:
                filtered = [e for e in filtered if e.tool_name == tool_name]
            return [e.to_dict() for e in filtered[-last_n:]]

    def detect_patterns(self) -> list[dict]:
        """Detect error patterns — repeated failures, cascading errors, etc."""
        patterns = []
        now = time.time()

        with self._lock:
            # Pattern 1: Tools failing repeatedly in last 5 minutes
            recent = [e for e in self._errors if now - e.timestamp < 300]
            tool_recent = defaultdict(int)
            for e in recent:
                tool_recent[e.tool_name] += 1

            for tool, count in tool_recent.items():
                if count >= 3:
                    patterns.append({
                        "type": "repeated_failure",
                        "tool": tool,
                        "count": count,
                        "window": "5min",
                        "severity": "high" if count >= 5 else "medium",
                        "suggestion": f"Tool '{tool}' failed {count}x in 5min. Check dependency or API key.",
                    })

            # Pattern 2: Same error type across multiple tools
            type_tools = defaultdict(set)
            for e in recent:
                type_tools[e.error_type].add(e.tool_name)

            for err_type, tools in type_tools.items():
                if len(tools) >= 3:
                    patterns.append({
                        "type": "cascading_error",
                        "error_type": err_type,
                        "affected_tools": list(tools),
                        "severity": "critical",
                        "suggestion": f"'{err_type}' hitting {len(tools)} tools — likely a shared dependency issue.",
                    })

            # Pattern 3: Timeout epidemic
            timeout_count = sum(1 for e in recent if "timeout" in e.message.lower())
            if timeout_count >= 3:
                patterns.append({
                    "type": "timeout_epidemic",
                    "count": timeout_count,
                    "severity": "high",
                    "suggestion": "Multiple timeouts detected. Check network connectivity or API rate limits.",
                })

            # Pattern 4: Import errors (missing dependencies)
            import_errors = [e for e in self._errors if e.error_type in ("ImportError", "ModuleNotFoundError")]
            if import_errors:
                missing_modules = set()
                for e in import_errors:
                    msg = e.message.lower()
                    if "no module named" in msg:
                        parts = msg.split("'")
                        if len(parts) >= 2:
                            missing_modules.add(parts[1])
                if missing_modules:
                    patterns.append({
                        "type": "missing_dependencies",
                        "modules": list(missing_modules),
                        "severity": "medium",
                        "suggestion": f"Missing: {', '.join(missing_modules)}. Run: pip install {' '.join(missing_modules)}",
                    })

        return patterns

    def get_top_failing_tools(self, n: int = 10) -> list[tuple[str, int]]:
        """Get tools with most errors."""
        with self._lock:
            sorted_tools = sorted(self._tool_counts.items(), key=lambda x: x[1], reverse=True)
            return sorted_tools[:n]

    def get_report(self) -> str:
        """Human-readable error report."""
        with self._lock:
            total = len(self._errors)
            uptime = time.time() - self._start_time

        lines = [
            "Error Tracker Report",
            "=" * 50,
            f"Total Errors Tracked: {total}",
            f"Uptime: {uptime/3600:.1f}h",
        ]

        # Top failing tools
        top = self.get_top_failing_tools(5)
        if top:
            lines.append("\nTop Failing Tools:")
            for tool, count in top:
                lines.append(f"  {tool}: {count} errors")

        # Error types
        with self._lock:
            top_types = sorted(self._type_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        if top_types:
            lines.append("\nTop Error Types:")
            for etype, count in top_types:
                lines.append(f"  {etype}: {count}")

        # Patterns
        patterns = self.detect_patterns()
        if patterns:
            lines.append(f"\nActive Patterns ({len(patterns)}):")
            for p in patterns:
                lines.append(f"  [{p['severity'].upper()}] {p['type']}: {p['suggestion']}")

        return "\n".join(lines)

    def clear(self):
        """Clear all tracked errors."""
        with self._lock:
            self._errors.clear()
            self._tool_counts.clear()
            self._type_counts.clear()

    def get_stats(self) -> dict:
        """Machine-readable stats."""
        with self._lock:
            return {
                "total_errors": len(self._errors),
                "unique_tools": len(self._tool_counts),
                "unique_types": len(self._type_counts),
                "top_tools": dict(self.get_top_failing_tools(5)),
                "patterns": self.detect_patterns(),
                "uptime_hours": round((time.time() - self._start_time) / 3600, 2),
            }
