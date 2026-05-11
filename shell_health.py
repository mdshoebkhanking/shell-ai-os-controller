"""
Shell Health - Health Monitoring Dashboard
--------------------------------------------
Tracks per-tool health, validates API keys, checks dependencies.

Usage:
    from shell_health import HealthMonitor
    monitor = HealthMonitor.get()
    monitor.record_success("weather_tool", 150.5)
    print(monitor.summary())
"""

import time
import threading
import logging
from dataclasses import dataclass, field
from enum import Enum

# Soft import to avoid circular imports (shell_health is infrastructure)
try:
    from shell_config import config as _config
except ImportError:
    _config = None

try:
    from shell_logger import get_logger
    logger = get_logger("shell_health")
except ImportError:
    logger = logging.getLogger("shell_health")


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ToolHealth:
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_success: float = 0.0
    last_failure: float = 0.0
    last_error: str = ""
    total_calls: int = 0
    total_errors: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        successful = self.total_calls - self.total_errors
        if successful <= 0:
            return 0.0
        return round(self.total_latency_ms / successful, 1)

    @property
    def error_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return round(self.total_errors / self.total_calls * 100, 1)


class HealthMonitor:
    """Singleton health monitor for all Shell AI tools."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._tools: dict[str, ToolHealth] = {}
        self._api_key_status: dict[str, bool] = {}
        self._dependency_status: dict[str, bool] = {}
        self._data_lock = threading.Lock()
        self._initialized = True

    @classmethod
    def get(cls) -> "HealthMonitor":
        return cls()

    def _get_tool(self, name: str) -> ToolHealth:
        if name not in self._tools:
            self._tools[name] = ToolHealth(name=name)
        return self._tools[name]

    def record_success(self, tool_name: str, latency_ms: float):
        """Record a successful tool execution."""
        with self._data_lock:
            tool = self._get_tool(tool_name)
            tool.total_calls += 1
            tool.total_latency_ms += latency_ms
            tool.last_success = time.time()
            # Update status
            if tool.error_rate < 10:
                tool.status = HealthStatus.HEALTHY
            elif tool.error_rate < 50:
                tool.status = HealthStatus.DEGRADED

    def record_failure(self, tool_name: str, error: str):
        """Record a failed tool execution."""
        with self._data_lock:
            tool = self._get_tool(tool_name)
            tool.total_calls += 1
            tool.total_errors += 1
            tool.last_failure = time.time()
            tool.last_error = error[:200]
            # Update status
            if tool.error_rate > 50:
                tool.status = HealthStatus.UNHEALTHY
            elif tool.error_rate > 10:
                tool.status = HealthStatus.DEGRADED

    def validate_api_keys(self) -> dict:
        """Check which API keys are present and non-empty."""
        keys_to_check = [
            ("GOOGLE_API_KEY", True),
            ("GOOGLE_SEARCH_API_KEY", False),
            ("SEARCH_ENGINE_ID", False),
            ("OPENWEATHER_API_KEY", False),
            ("NEWS_API_KEY", False),
            ("OPENAI_API_KEY", False),
            ("GROQ_API_KEY", False),
            ("LIVEKIT_API_KEY", True),
            ("LIVEKIT_API_SECRET", True),
            ("LIVEKIT_URL", True),
            ("TELEGRAM_BOT_TOKEN", False),
            ("HF_API_KEY", False),
        ]
        self._api_key_status = {}
        if _config is not None:
            for key, _critical in keys_to_check:
                val = _config.get_str(key, "")
                self._api_key_status[key] = bool(val.strip())
        else:
            import os
            for key, _critical in keys_to_check:
                val = os.getenv(key, "")
                self._api_key_status[key] = bool(val.strip())
        return self._api_key_status

    def check_dependencies(self) -> dict:
        """Check which optional dependencies are installed.

        Tuple entries denote alternatives — the dependency is "healthy"
        as long as at least one of the listed imports succeeds.
        """
        deps: list = [
            "PIL", "selenium", "pytesseract", "pyautogui",
            "instagrapi", "fuzzywuzzy", "aiohttp", "GPUtil",
            # Accept either the new (google-genai) or legacy
            # (google-generativeai) SDK — they are mutually compatible.
            ("google.genai", "google.generativeai"),
            "openai",
            "livekit", "sentence_transformers", "cv2",
        ]
        self._dependency_status = {}
        for dep in deps:
            if isinstance(dep, tuple):
                label = " | ".join(dep)
                status = False
                for candidate in dep:
                    try:
                        __import__(candidate)
                        status = True
                        break
                    except ImportError:
                        continue
                self._dependency_status[label] = status
            else:
                try:
                    __import__(dep)
                    self._dependency_status[dep] = True
                except ImportError:
                    self._dependency_status[dep] = False
        return self._dependency_status

    def get_tool_health(self, tool_name: str) -> ToolHealth:
        with self._data_lock:
            return self._get_tool(tool_name)

    def summary(self) -> str:
        """Human-readable health summary."""
        lines = []
        lines.append("=" * 50)
        lines.append("  SHELL AI HEALTH DASHBOARD")
        lines.append("=" * 50)

        # API Keys
        if self._api_key_status:
            active = sum(1 for v in self._api_key_status.values() if v)
            total = len(self._api_key_status)
            lines.append(f"\nAPI Keys: {active}/{total} configured")
            for key, present in self._api_key_status.items():
                icon = "OK" if present else "MISSING"
                lines.append(f"  [{icon}] {key}")

        # Dependencies
        if self._dependency_status:
            installed = sum(1 for v in self._dependency_status.values() if v)
            total = len(self._dependency_status)
            lines.append(f"\nDependencies: {installed}/{total} installed")
            missing = [k for k, v in self._dependency_status.items() if not v]
            if missing:
                lines.append(f"  Missing: {', '.join(missing)}")

        # Tool Health
        if self._tools:
            lines.append(f"\nTool Health ({len(self._tools)} tracked):")
            # Sort by error rate descending
            sorted_tools = sorted(
                self._tools.values(),
                key=lambda t: t.error_rate,
                reverse=True,
            )
            for tool in sorted_tools[:20]:  # Top 20
                icon = {
                    HealthStatus.HEALTHY: "OK",
                    HealthStatus.DEGRADED: "WARN",
                    HealthStatus.UNHEALTHY: "FAIL",
                    HealthStatus.UNKNOWN: "??",
                }[tool.status]
                lines.append(
                    f"  [{icon}] {tool.name}: "
                    f"{tool.total_calls} calls, "
                    f"{tool.error_rate}% errors, "
                    f"avg {tool.avg_latency_ms}ms"
                )

        lines.append("=" * 50)
        return "\n".join(lines)

    def dashboard_data(self) -> dict:
        """JSON-serializable data for shell_hub dashboard."""
        return {
            "api_keys": self._api_key_status,
            "dependencies": self._dependency_status,
            "tools": {
                name: {
                    "status": tool.status.value,
                    "calls": tool.total_calls,
                    "errors": tool.total_errors,
                    "error_rate": tool.error_rate,
                    "avg_latency_ms": tool.avg_latency_ms,
                }
                for name, tool in self._tools.items()
            },
        }
