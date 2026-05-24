"""Windows UI automation driver using pywinauto.

The driver is Windows-only and disabled by default. Set
`SHELL_PYWINAUTO_ENABLED=1` to prefer it over legacy pywin32/pygetwindow
helpers; callers should keep their existing fallback path for portability.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off", "disabled"}


def is_windows(platform: str | None = None) -> bool:
    return (platform or sys.platform).lower().startswith("win")


def pywinauto_enabled(platform: str | None = None) -> bool:
    return is_windows(platform) and _env_bool("SHELL_PYWINAUTO_ENABLED", False)


def pywinauto_installed() -> bool:
    return importlib.util.find_spec("pywinauto") is not None


COMMON_WINDOWS_APPS: dict[str, dict[str, str]] = {
    "notepad": {
        "command": "notepad.exe",
        "title": "notepad",
        "title_re": r".*notepad.*",
    },
    "calculator": {
        "command": "calc.exe",
        "title": "calculator",
        "title_re": r".*calculator.*",
    },
    "calc": {
        "command": "calc.exe",
        "title": "calculator",
        "title_re": r".*calculator.*",
    },
    "file explorer": {
        "command": "explorer.exe",
        "title": "explorer",
        "title_re": r".*(file explorer|explorer).*",
    },
    "explorer": {
        "command": "explorer.exe",
        "title": "explorer",
        "title_re": r".*(file explorer|explorer).*",
    },
}


@dataclass(frozen=True)
class WindowsAutomationResult:
    ok: bool
    action: str
    message: str
    backend: str = "pywinauto"
    details: dict[str, Any] = field(default_factory=dict)


def common_windows_app_test_plan() -> list[dict[str, str]]:
    return [
        {"app": "notepad", "command": "notepad.exe", "expected_title": "notepad"},
        {"app": "calculator", "command": "calc.exe", "expected_title": "calculator"},
        {"app": "file explorer", "command": "explorer.exe", "expected_title": "explorer"},
    ]


class PywinautoWindowsDriver:
    def __init__(
        self,
        *,
        backend: str = "uia",
        timeout_s: float = 5.0,
        platform: str | None = None,
        application_cls: Any | None = None,
        desktop_cls: Any | None = None,
    ):
        self.backend = backend or "uia"
        self.timeout_s = max(0.2, float(timeout_s or 5.0))
        self.platform = platform or sys.platform
        self._application_cls = application_cls
        self._desktop_cls = desktop_cls

    def enabled(self) -> bool:
        return pywinauto_enabled(self.platform)

    def available(self) -> bool:
        if not self.enabled():
            return False
        if self._application_cls is not None and self._desktop_cls is not None:
            return True
        return pywinauto_installed()

    def _load(self) -> tuple[Any, Any]:
        if self._application_cls is not None and self._desktop_cls is not None:
            return self._application_cls, self._desktop_cls
        try:
            from pywinauto import Desktop  # type: ignore
            from pywinauto.application import Application  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"pywinauto unavailable: {exc}") from exc
        return Application, Desktop

    @staticmethod
    def _window_text(window: Any) -> str:
        for attr in ("window_text", "texts"):
            try:
                value = getattr(window, attr)
                if callable(value):
                    text = value()
                    if isinstance(text, (list, tuple)):
                        text = " ".join(str(item) for item in text)
                    if str(text or "").strip():
                        return str(text).strip()
            except Exception:
                pass
        try:
            return str(getattr(getattr(window, "element_info", None), "name", "") or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _process_id(window: Any) -> int | None:
        try:
            return int(getattr(getattr(window, "element_info", None), "process_id", 0) or 0) or None
        except Exception:
            return None

    @staticmethod
    def _rectangle(window: Any) -> dict[str, int]:
        try:
            rect = window.rectangle()
            left = int(getattr(rect, "left", 0))
            top = int(getattr(rect, "top", 0))
            right = int(getattr(rect, "right", left))
            bottom = int(getattr(rect, "bottom", top))
            return {
                "x": left,
                "y": top,
                "width": max(0, right - left),
                "height": max(0, bottom - top),
            }
        except Exception:
            return {"x": 0, "y": 0, "width": 0, "height": 0}

    @staticmethod
    def _safe_re(keyword: str) -> str:
        value = str(keyword or "").strip()
        if not value:
            return ".*"
        return rf".*{re.escape(value)}.*"

    @staticmethod
    def _common_app(app_title: str) -> dict[str, str]:
        key = str(app_title or "").strip().lower()
        return COMMON_WINDOWS_APPS.get(key, {})

    def _desktop(self):
        _, desktop_cls = self._load()
        return desktop_cls(backend=self.backend)

    def _windows(self) -> list[Any]:
        desktop = self._desktop()
        try:
            return list(desktop.windows())
        except TypeError:
            return list(desktop.windows(visible_only=True))

    def _find_window(self, title_keyword: str) -> Any | None:
        needle = str(title_keyword or "").strip().lower()
        if not needle:
            return None
        for window in self._windows():
            title = self._window_text(window).lower()
            if title and needle in title:
                return window
        return None

    def _focus(self, window: Any) -> None:
        for method_name in ("restore", "set_focus"):
            try:
                method = getattr(window, method_name, None)
                if callable(method):
                    method()
            except Exception:
                if method_name == "set_focus":
                    raise

    def focus_window(self, title_keyword: str) -> WindowsAutomationResult:
        if not self.available():
            return WindowsAutomationResult(
                False,
                "focus_window",
                "pywinauto unavailable or disabled",
                details={"fallback_allowed": True},
            )
        try:
            window = self._find_window(title_keyword)
            if window is None:
                return WindowsAutomationResult(
                    False,
                    "focus_window",
                    f"Window not found via pywinauto: {title_keyword}",
                    details={"fallback_allowed": True},
                )
            self._focus(window)
            title = self._window_text(window)
            return WindowsAutomationResult(True, "focus_window", f"Focused via pywinauto: {title}", details={"title": title})
        except Exception as exc:
            return WindowsAutomationResult(False, "focus_window", f"pywinauto focus failed: {exc}", details={"fallback_allowed": True})

    def open_app(self, app_title: str, command: str | None = None, install_path: str | None = None) -> WindowsAutomationResult:
        if not self.available():
            return WindowsAutomationResult(
                False,
                "open_app",
                "pywinauto unavailable or disabled",
                details={"fallback_allowed": True},
            )
        common = self._common_app(app_title)
        launch_command = install_path or common.get("command") or command or app_title
        title_hint = common.get("title") or app_title
        title_re = common.get("title_re") or self._safe_re(title_hint)
        started = time.perf_counter()
        try:
            application_cls, _ = self._load()
            app = application_cls(backend=self.backend)
            app.start(str(launch_command))
            focused = False
            title = ""
            deadline = time.perf_counter() + self.timeout_s
            while time.perf_counter() < deadline:
                focus_result = self.focus_window(title_hint)
                if focus_result.ok:
                    focused = True
                    title = str(focus_result.details.get("title") or title_hint)
                    break
                time.sleep(0.15)
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
            if focused:
                return WindowsAutomationResult(
                    True,
                    "open_app",
                    f"App launched and focused via pywinauto: {app_title}",
                    details={"command": str(launch_command), "title": title, "title_re": title_re, "elapsed_ms": elapsed_ms},
                )
            return WindowsAutomationResult(
                True,
                "open_app",
                f"App launched via pywinauto: {app_title} (focus pending)",
                details={"command": str(launch_command), "title_re": title_re, "elapsed_ms": elapsed_ms, "focused": False},
            )
        except Exception as exc:
            return WindowsAutomationResult(False, "open_app", f"pywinauto open failed: {exc}", details={"fallback_allowed": True, "command": str(launch_command)})

    def close_window(self, title_keyword: str) -> WindowsAutomationResult:
        if not self.available():
            return WindowsAutomationResult(False, "close_window", "pywinauto unavailable or disabled", details={"fallback_allowed": True})
        try:
            window = self._find_window(title_keyword)
            if window is None:
                return WindowsAutomationResult(False, "close_window", f"Window not found via pywinauto: {title_keyword}", details={"fallback_allowed": True})
            title = self._window_text(window)
            window.close()
            return WindowsAutomationResult(True, "close_window", f"Window closed via pywinauto: {title}", details={"title": title})
        except Exception as exc:
            return WindowsAutomationResult(False, "close_window", f"pywinauto close failed: {exc}", details={"fallback_allowed": True})

    def minimize_window(self, title_keyword: str) -> WindowsAutomationResult:
        return self._window_method("minimize_window", title_keyword, "minimize", "minimized")

    def maximize_window(self, title_keyword: str) -> WindowsAutomationResult:
        return self._window_method("maximize_window", title_keyword, "maximize", "maximized")

    def _window_method(self, action: str, title_keyword: str, method_name: str, verb: str) -> WindowsAutomationResult:
        if not self.available():
            return WindowsAutomationResult(False, action, "pywinauto unavailable or disabled", details={"fallback_allowed": True})
        try:
            window = self._find_window(title_keyword)
            if window is None:
                return WindowsAutomationResult(False, action, f"Window not found via pywinauto: {title_keyword}", details={"fallback_allowed": True})
            method = getattr(window, method_name)
            method()
            title = self._window_text(window)
            return WindowsAutomationResult(True, action, f"Window {verb} via pywinauto: {title}", details={"title": title})
        except Exception as exc:
            return WindowsAutomationResult(False, action, f"pywinauto {verb} failed: {exc}", details={"fallback_allowed": True})

    def resize_window(self, title_keyword: str, width: int, height: int) -> WindowsAutomationResult:
        if not self.available():
            return WindowsAutomationResult(False, "resize_window", "pywinauto unavailable or disabled", details={"fallback_allowed": True})
        try:
            window = self._find_window(title_keyword)
            if window is None:
                return WindowsAutomationResult(False, "resize_window", f"Window not found via pywinauto: {title_keyword}", details={"fallback_allowed": True})
            rect = self._rectangle(window)
            window.move_window(rect["x"], rect["y"], int(width), int(height), repaint=True)
            title = self._window_text(window)
            return WindowsAutomationResult(True, "resize_window", f"Window resized via pywinauto: {title} -> {int(width)}x{int(height)}", details={"title": title, "width": int(width), "height": int(height)})
        except Exception as exc:
            return WindowsAutomationResult(False, "resize_window", f"pywinauto resize failed: {exc}", details={"fallback_allowed": True})

    def list_windows(self) -> WindowsAutomationResult:
        if not self.available():
            return WindowsAutomationResult(False, "list_windows", "pywinauto unavailable or disabled", details={"fallback_allowed": True})
        try:
            rows = []
            for window in self._windows():
                title = self._window_text(window)
                if not title:
                    continue
                rect = self._rectangle(window)
                rows.append(
                    {
                        "title": title,
                        "process_id": self._process_id(window),
                        "position": f"({rect['x']}, {rect['y']})",
                        "size": f"{rect['width']}x{rect['height']}",
                    }
                )
            return WindowsAutomationResult(True, "list_windows", f"{len(rows)} visible windows via pywinauto", details={"windows": rows})
        except Exception as exc:
            return WindowsAutomationResult(False, "list_windows", f"pywinauto list windows failed: {exc}", details={"fallback_allowed": True})


def create_pywinauto_driver(*, platform: str | None = None) -> PywinautoWindowsDriver | None:
    driver = PywinautoWindowsDriver(platform=platform)
    if not driver.available():
        return None
    return driver


__all__ = [
    "COMMON_WINDOWS_APPS",
    "PywinautoWindowsDriver",
    "WindowsAutomationResult",
    "common_windows_app_test_plan",
    "create_pywinauto_driver",
    "is_windows",
    "pywinauto_enabled",
    "pywinauto_installed",
]
