import json
import subprocess
import sys
import asyncio


def test_ui_import_does_not_eager_load_livekit_rtc():
    code = (
        "import os, sys, json; "
        "os.environ.setdefault('QT_QPA_PLATFORM','offscreen'); "
        "import shell_ui.shell_cinematic_full; "
        "print(json.dumps({"
        "'socketio_loaded': 'socketio' in sys.modules, "
        "'engineio_loaded': 'engineio' in sys.modules, "
        "'aiohttp_loaded': 'aiohttp' in sys.modules, "
        "'brain_core_loaded': 'brain.core' in sys.modules, "
        "'numpy_loaded': 'numpy' in sys.modules, "
        "'livekit_rtc_loaded': 'livekit.rtc' in sys.modules"
        "}))"
    )

    proc = subprocess.run(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr[-1200:]
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data["socketio_loaded"] is False
    assert data["engineio_loaded"] is False
    assert data["aiohttp_loaded"] is False
    assert data["brain_core_loaded"] is False
    assert data["numpy_loaded"] is False
    assert data["livekit_rtc_loaded"] is False


def test_ui_first_paint_does_not_autoload_network_or_brain():
    code = (
        "import os, sys, json, time; "
        "os.environ.setdefault('QT_QPA_PLATFORM','offscreen'); "
        "from PyQt6.QtWidgets import QApplication; "
        "from shell_ui.app_bootstrap import configure_qt_application; "
        "import shell_ui.shell_cinematic_full as ui; "
        "app=QApplication.instance() or QApplication(sys.argv); "
        "configure_qt_application(app); "
        "w=ui.ShellHoloUI(); w.resize(900,600); w.show(); "
        "app.processEvents(); "
        "print(json.dumps({"
        "'socketio_loaded': 'socketio' in sys.modules, "
        "'engineio_loaded': 'engineio' in sys.modules, "
        "'aiohttp_loaded': 'aiohttp' in sys.modules, "
        "'brain_core_loaded': 'brain.core' in sys.modules"
        "})); "
        "w.close(); app.processEvents(); app.quit()"
    )

    proc = subprocess.run(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr[-1200:]
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data == {
        "socketio_loaded": False,
        "engineio_loaded": False,
        "aiohttp_loaded": False,
        "brain_core_loaded": False,
    }


def test_ui_idle_startup_does_not_autostart_socketio():
    code = """
import json
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.pop("SHELL_AUTO_START_SOCKETIO", None)
os.environ.pop("SHELL_HUB_AUTOCONNECT", None)

from PyQt6.QtWidgets import QApplication
from shell_ui.app_bootstrap import configure_qt_application
import shell_ui.shell_cinematic_full as ui

app = QApplication.instance() or QApplication(sys.argv)
configure_qt_application(app)
w = ui.ShellHoloUI()
w.resize(900, 600)
w.show()
deadline = time.time() + 3.4
while time.time() < deadline:
    app.processEvents()
    time.sleep(0.01)
print(json.dumps({
    "socketio_loaded": "socketio" in sys.modules,
    "engineio_loaded": "engineio" in sys.modules,
    "aiohttp_loaded": "aiohttp" in sys.modules,
    "brain_core_loaded": "brain.core" in sys.modules,
}))
w.close()
app.processEvents()
app.quit()
"""

    proc = subprocess.run(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=25,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr[-1200:]
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data == {
        "socketio_loaded": False,
        "engineio_loaded": False,
        "aiohttp_loaded": False,
        "brain_core_loaded": False,
    }


def test_oracle_network_scan_is_opt_in(monkeypatch):
    from shell_oracle import Oracle

    monkeypatch.delenv("SHELL_ORACLE_NET_SCAN", raising=False)

    oracle = Oracle()

    assert oracle.net_scan_enabled is False


def test_oracle_start_is_idempotent(monkeypatch):
    from shell_oracle import Oracle

    monkeypatch.setenv("SHELL_ORACLE_ENABLED", "1")
    oracle = Oracle()
    oracle.running = True

    oracle.start(object())

    assert oracle.running is True


def test_productivity_timer_alert_is_cross_platform():
    from shell_productivity import _safe_alert_beep

    asyncio.run(_safe_alert_beep())


def test_local_tool_gateway_cleans_background_tasks():
    code = (
        "import json; "
        "from shell_tool_gateway import execute_tool_sync; "
        "result = execute_tool_sync('shell_productivity:pomodoro_tool', "
        "{'work_minutes': 1, 'break_minutes': 1, 'cycles': 1}); "
        "print(json.dumps({'status': result.get('status')}))"
    )

    proc = subprocess.run(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr[-1200:]
    assert "Task was destroyed but it is pending" not in proc.stderr
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data["status"] == "success"
