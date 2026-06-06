import subprocess
import sys
import asyncio


class FakeRect:
    left = 10
    top = 20
    right = 310
    bottom = 220


class FakeElementInfo:
    process_id = 1234
    name = "Untitled - Notepad"


class FakeWindow:
    def __init__(self, title="Untitled - Notepad"):
        self.title = title
        self.element_info = FakeElementInfo()
        self.focused = False
        self.closed = False
        self.minimized = False
        self.maximized = False
        self.moved_to = None

    def window_text(self):
        return self.title

    def rectangle(self):
        return FakeRect()

    def restore(self):
        return None

    def set_focus(self):
        self.focused = True

    def close(self):
        self.closed = True

    def minimize(self):
        self.minimized = True

    def maximize(self):
        self.maximized = True

    def move_window(self, x, y, width, height, repaint=True):
        self.moved_to = (x, y, width, height, repaint)


class FakeApplication:
    started_commands = []

    def __init__(self, backend="uia"):
        self.backend = backend

    def start(self, command):
        self.started_commands.append(command)
        return self


class FakeDesktop:
    windows_list = [FakeWindow()]

    def __init__(self, backend="uia"):
        self.backend = backend

    def windows(self, *args, **kwargs):
        return list(self.windows_list)


def _driver(monkeypatch):
    monkeypatch.setenv("SHELL_PYWINAUTO_ENABLED", "1")
    from core.automation.windows_pywinauto import PywinautoWindowsDriver

    FakeApplication.started_commands = []
    FakeDesktop.windows_list = [FakeWindow()]
    return PywinautoWindowsDriver(
        platform="win32",
        application_cls=FakeApplication,
        desktop_cls=FakeDesktop,
        timeout_s=0.2,
    )


def test_pywinauto_import_is_lazy():
    code = (
        "import sys; "
        "import core.automation.windows_pywinauto; "
        "print('pywinauto' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    assert result.stdout.strip() == "False"


def test_pywinauto_flag_default_off_on_windows(monkeypatch):
    monkeypatch.delenv("SHELL_PYWINAUTO_ENABLED", raising=False)
    from core.automation.windows_pywinauto import pywinauto_enabled

    assert pywinauto_enabled("win32") is False


def test_common_windows_app_plan_covers_required_apps():
    from core.automation.windows_pywinauto import common_windows_app_test_plan

    apps = {row["app"] for row in common_windows_app_test_plan()}

    assert {"notepad", "calculator", "file explorer"}.issubset(apps)


def test_open_app_uses_common_app_command_and_focuses(monkeypatch):
    driver = _driver(monkeypatch)

    result = driver.open_app("notepad", "notepad")

    assert result.ok is True
    assert "pywinauto" in result.message
    assert FakeApplication.started_commands == ["notepad.exe"]
    assert FakeDesktop.windows_list[0].focused is True


def test_focus_close_resize_and_list_windows(monkeypatch):
    driver = _driver(monkeypatch)
    window = FakeDesktop.windows_list[0]

    focus = driver.focus_window("notepad")
    close = driver.close_window("notepad")
    resize = driver.resize_window("notepad", 800, 600)
    listed = driver.list_windows()

    assert focus.ok is True
    assert close.ok is True
    assert resize.ok is True
    assert listed.ok is True
    assert window.focused is True
    assert window.closed is True
    assert window.moved_to == (10, 20, 800, 600, True)
    assert listed.details["windows"][0]["process_id"] == 1234


def test_missing_window_allows_legacy_fallback(monkeypatch):
    driver = _driver(monkeypatch)
    FakeDesktop.windows_list = [FakeWindow("Other App")]

    result = driver.close_window("calculator")

    assert result.ok is False
    assert result.details["fallback_allowed"] is True


def test_shell_window_ctrl_routes_reference_pywinauto_flag():
    source = open("shell_window_CTRL.py", encoding="utf-8").read()

    assert "_get_pywinauto_driver" in source
    assert "_run_pywinauto" in source
    assert "open_app" in source


def test_shell_window_ctrl_normalizes_common_app_typos():
    import shell_window_CTRL as ctrl

    assert ctrl._normalize_app_title("calculater") == "calculator"
    assert ctrl._normalize_app_title("windows settings app") == "settings"
    assert ctrl._normalize_app_title("google chrome") == "chrome"
    assert ctrl._normalize_app_title("note pad") == "notepad"


def test_open_app_windows_uses_structured_start_fallback(monkeypatch):
    import shell_window_CTRL as ctrl

    calls = []

    class FakeProcess:
        pid = 4321

    async def fake_pywinauto(*_args):
        return None

    async def fake_focus(_title):
        return False

    def fake_popen(command, *_args, **_kwargs):
        calls.append(command)
        if command == ["mystery"]:
            raise FileNotFoundError("missing")
        return FakeProcess()

    monkeypatch.setattr(ctrl.sys, "platform", "win32")
    monkeypatch.setattr(ctrl, "_run_pywinauto", fake_pywinauto)
    monkeypatch.setattr(ctrl, "find_app_path", lambda _command: None)
    monkeypatch.setattr(ctrl, "_find_app_install_path", lambda _title: None)
    monkeypatch.setattr(ctrl, "focus_window", fake_focus)
    monkeypatch.setattr(ctrl.subprocess, "Popen", fake_popen)

    result = asyncio.run(ctrl.open_app("mystery"))

    assert calls == [["mystery"], ["cmd", "/c", "start", "", "mystery"]]
    assert "launch requested" in result


def test_open_app_windows_uses_normalized_path_lookup(monkeypatch):
    import shell_window_CTRL as ctrl

    calls = []

    class FakeProcess:
        pid = 1234

    async def fake_pywinauto(*_args):
        return None

    async def fake_focus(_title):
        return True

    monkeypatch.setattr(ctrl.sys, "platform", "win32")
    monkeypatch.setattr(ctrl, "_run_pywinauto", fake_pywinauto)
    monkeypatch.setattr(ctrl, "find_app_path", lambda command: r"C:\Windows\System32\calc.exe" if command == "calc" else None)
    monkeypatch.setattr(ctrl, "_find_app_install_path", lambda _title: None)
    monkeypatch.setattr(ctrl, "focus_window", fake_focus)
    monkeypatch.setattr(ctrl.subprocess, "Popen", lambda command, *_args, **_kwargs: calls.append(command) or FakeProcess())

    result = asyncio.run(ctrl.open_app("calculater"))

    assert calls == [[r"C:\Windows\System32\calc.exe"]]
    assert "App launched and focused: calculator" in result
