from __future__ import annotations

import json
import subprocess
import sys
import time


def test_network_runtime_import_stays_lightweight() -> None:
    code = (
        "import json, sys; "
        "import shell_network_runtime; "
        "print(json.dumps({"
        "'socketio_loaded': 'socketio' in sys.modules, "
        "'engineio_loaded': 'engineio' in sys.modules, "
        "'aiohttp_loaded': 'aiohttp' in sys.modules"
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
    assert data == {
        "socketio_loaded": False,
        "engineio_loaded": False,
        "aiohttp_loaded": False,
    }


def test_ai_runtime_import_does_not_load_brain_core() -> None:
    code = (
        "import json, sys; "
        "import shell_ai_runtime; "
        "print(json.dumps({"
        "'brain_core_loaded': 'brain.core' in sys.modules, "
        "'aiohttp_loaded': 'aiohttp' in sys.modules"
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
    assert data == {"brain_core_loaded": False, "aiohttp_loaded": False}


def test_socketio_client_thread_stops_cleanly_without_real_socketio() -> None:
    from shell_network_runtime import SocketIOClient

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.connected = False
            self.handlers = {}
            self.emitted = []
            self.shutdown_called = False

        def event(self, fn):
            self.handlers[fn.__name__] = fn
            return fn

        def connect(self, *args, **kwargs):
            self.connected = True
            if self.handlers.get("connect"):
                self.handlers["connect"]()

        def disconnect(self):
            self.connected = False
            if self.handlers.get("disconnect"):
                self.handlers["disconnect"]()

        def emit(self, event, payload):
            self.emitted.append((event, payload))

        def shutdown(self):
            self.shutdown_called = True

    class FakeSocketIO:
        @staticmethod
        def Client(*args, **kwargs):
            return FakeClient(*args, **kwargs)

    client = SocketIOClient(
        hub_url="http://127.0.0.1:5000",
        socketio_module_factory=lambda: (FakeSocketIO, ""),
        auth_factory=lambda: None,
    )
    client.start()
    deadline = time.time() + 0.5
    while time.time() < deadline and not client.is_connected:
        time.sleep(0.01)

    assert client.is_connected is True
    assert client.emit_gui_input({"type": "probe"}) is True

    client.stop()
    client.wait(1000)

    assert not client.isRunning()
    assert client.sio is not None
    assert client.sio.shutdown_called is True
