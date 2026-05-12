from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _rss_mb() -> float:
    try:
        import psutil

        return round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 3)
    except Exception:
        return -1.0


def _snapshot(name: str, started: float | None = None, **extra: Any) -> dict[str, Any]:
    gc.collect()
    item = {
        "name": name,
        "rss_mb": _rss_mb(),
        "timestamp": time.time(),
    }
    if started is not None:
        item["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    item.update(extra)
    return item


def _delta(current: float, previous: float) -> float:
    if current < 0 or previous < 0:
        return -1.0
    return round(current - previous, 3)


def _tool_execution_probe(*, iterations: int = 1) -> dict[str, Any]:
    from shell_tool_gateway import execute_tool_sync

    result = {}
    for _ in range(max(1, iterations)):
        result = execute_tool_sync("shell_calculator:calculate_tool", {"expression": "2 + 3 * 4"})
    return {
        "status": result.get("status"),
        "has_result": bool(result.get("result")),
        "iterations": max(1, iterations),
    }


def _ui_probe() -> dict[str, Any]:
    from PyQt6.QtWidgets import QApplication
    from shell_ui.app_bootstrap import configure_qt_application
    from shell_ui.shell_cinematic_full import ShellHoloUI

    app = QApplication.instance() or QApplication(sys.argv)
    configure_qt_application(app)
    window = ShellHoloUI()
    window.resize(1100, 680)
    window.show()
    deadline = time.time() + 0.35
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    pages = window.pages.count()
    modules = {
        "socketio": "socketio" in sys.modules,
        "engineio": "engineio" in sys.modules,
        "aiohttp": "aiohttp" in sys.modules,
        "brain_core": "brain.core" in sys.modules,
        "livekit_rtc": "livekit.rtc" in sys.modules,
    }
    window.close()
    app.processEvents()
    return {"pages": pages, "modules": modules}


def _tts_probe() -> dict[str, Any]:
    from shell_voice_runtime import TTSSpeaker

    speaker = TTSSpeaker()
    command = speaker._detect_system_tts_command()
    speaker.shutdown()
    return {"system_tts_command": command}


def _listener_probe() -> dict[str, Any]:
    import numpy as np

    from shell_voice_listener_runtime import VoiceListenerThread, _SD_AVAILABLE, _SR_AVAILABLE

    class FakeSoundDevice:
        @staticmethod
        def rec(frames, samplerate, channels, dtype, blocking):
            time.sleep(0.02)
            return np.zeros((frames, channels), dtype=dtype)

    class FakeSpeechRecognition:
        class Recognizer:
            pass

    listener = VoiceListenerThread()
    listener._load_audio_modules = lambda: (
        FakeSoundDevice,
        FakeSpeechRecognition,
        np,
        (__import__("io"), __import__("wave")),
        "",
    )
    thread_count_before = threading.active_count()
    listener.start()
    time.sleep(0.15)
    listener.stop_listening()
    listener.wait(1500)
    thread_count_after = threading.active_count()
    return {
        "sounddevice_available": _SD_AVAILABLE,
        "speech_recognition_available": _SR_AVAILABLE,
        "thread_count_before": thread_count_before,
        "thread_count_after": thread_count_after,
        "thread_cleaned_up": not listener.isRunning(),
    }


def _realtime_probe() -> dict[str, Any]:
    import shell_realtime_audio_runtime as realtime
    from shell_realtime_audio_runtime import LiveKitAudioClient

    class ProbeLiveKitAudioClient(LiveKitAudioClient):
        async def _run(self, asyncio_module):
            self.probe_started = True
            while self.running:
                await asyncio_module.sleep(0.01)

    modules_before = {
        "aiohttp": "aiohttp" in sys.modules,
        "numpy": "numpy" in sys.modules,
        "livekit_rtc": "livekit.rtc" in sys.modules,
    }
    old_available = realtime.LIVEKIT_AVAILABLE
    realtime.LIVEKIT_AVAILABLE = True
    try:
        client = ProbeLiveKitAudioClient(token_url="http://127.0.0.1/token")
        client.probe_started = False
        thread_count_before = threading.active_count()
        client.start()
        deadline = time.time() + 0.5
        while time.time() < deadline and not client.probe_started:
            time.sleep(0.01)
        client.stop()
        client.wait(1500)
        thread_count_after = threading.active_count()
    finally:
        realtime.LIVEKIT_AVAILABLE = old_available
    return {
        "thread_count_before": thread_count_before,
        "thread_count_after": thread_count_after,
        "thread_cleaned_up": not client.isRunning(),
        "started": bool(client.probe_started),
        "modules_before": modules_before,
        "modules_after": {
            "aiohttp": "aiohttp" in sys.modules,
            "numpy": "numpy" in sys.modules,
            "livekit_rtc": "livekit.rtc" in sys.modules,
        },
    }


def _network_probe() -> dict[str, Any]:
    from shell_network_runtime import SocketIOClient

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.connected = False
            self.emitted = []
            self.handlers = {}
            self.shutdown_called = False

        def event(self, fn):
            self.handlers[fn.__name__] = fn
            return fn

        def connect(self, *args, **kwargs):
            self.connected = True
            handler = self.handlers.get("connect")
            if handler is not None:
                handler()

        def disconnect(self):
            self.connected = False
            handler = self.handlers.get("disconnect")
            if handler is not None:
                handler()

        def emit(self, event, payload):
            self.emitted.append((event, payload))

        def shutdown(self):
            self.shutdown_called = True

    class FakeSocketIO:
        @staticmethod
        def Client(*args, **kwargs):
            return FakeClient(*args, **kwargs)

    modules_before = {
        "socketio": "socketio" in sys.modules,
        "engineio": "engineio" in sys.modules,
        "aiohttp": "aiohttp" in sys.modules,
    }
    client = SocketIOClient(
        hub_url="http://127.0.0.1:5000",
        socketio_module_factory=lambda: (FakeSocketIO, ""),
        auth_factory=lambda: None,
    )
    thread_count_before = threading.active_count()
    client.start()
    deadline = time.time() + 0.5
    while time.time() < deadline and not client.is_connected:
        time.sleep(0.01)
    connected_before_stop = bool(client.is_connected)
    emit_ok = client.emit_gui_input({"type": "probe"})
    client.stop()
    client.wait(1500)
    thread_count_after = threading.active_count()
    return {
        "connected_before_stop": connected_before_stop,
        "final_connected": bool(client.is_connected),
        "emit_ok": bool(emit_ok),
        "thread_count_before": thread_count_before,
        "thread_count_after": thread_count_after,
        "thread_cleaned_up": not client.isRunning(),
        "modules_before": modules_before,
        "modules_after": {
            "socketio": "socketio" in sys.modules,
            "engineio": "engineio" in sys.modules,
            "aiohttp": "aiohttp" in sys.modules,
        },
    }


def _ai_runtime_probe() -> dict[str, Any]:
    modules_before = {
        "brain_core": "brain.core" in sys.modules,
        "aiohttp": "aiohttp" in sys.modules,
    }
    from shell_ai_runtime import brain_has_providers, brain_load_metrics, has_configured_ai_key

    return {
        "configured_key": has_configured_ai_key(),
        "providers_loaded": brain_has_providers(load=False),
        "metrics": brain_load_metrics(),
        "modules_before": modules_before,
        "modules_after": {
            "brain_core": "brain.core" in sys.modules,
            "aiohttp": "aiohttp" in sys.modules,
        },
    }


def build_report(
    *,
    include_ui: bool,
    include_tts: bool,
    include_listener: bool = False,
    include_realtime: bool = False,
    include_network: bool = False,
    include_ai_runtime: bool = False,
    stress_iterations: int = 10,
) -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SHELL_V2_TIMEOUT_S", "1")

    snapshots: list[dict[str, Any]] = []
    snapshots.append(_snapshot("process_start"))

    started = time.perf_counter()
    import shell_tool_catalog

    snapshots.append(_snapshot("after_import_tool_catalog", started))

    started = time.perf_counter()
    catalog = shell_tool_catalog.discover_capabilities()
    snapshots.append(_snapshot("after_catalog_discovery", started, catalog_items=len(catalog.get("catalog", []))))

    started = time.perf_counter()
    tool_result = _tool_execution_probe()
    snapshots.append(_snapshot("after_calculator_tool", started, tool_result=tool_result))

    started = time.perf_counter()
    for _ in range(max(1, stress_iterations)):
        catalog = shell_tool_catalog.discover_capabilities()
    snapshots.append(
        _snapshot(
            "after_catalog_stress",
            started,
            catalog_items=len(catalog.get("catalog", [])),
            iterations=max(1, stress_iterations),
        )
    )

    started = time.perf_counter()
    tool_stress = _tool_execution_probe(iterations=max(1, stress_iterations))
    snapshots.append(_snapshot("after_tool_stress", started, tool_result=tool_stress))

    if include_tts:
        started = time.perf_counter()
        tts = _tts_probe()
        snapshots.append(_snapshot("after_tts_probe", started, tts=tts))

    if include_listener:
        started = time.perf_counter()
        listener = _listener_probe()
        snapshots.append(_snapshot("after_listener_probe", started, listener=listener))

    if include_realtime:
        started = time.perf_counter()
        realtime = _realtime_probe()
        snapshots.append(_snapshot("after_realtime_probe", started, realtime=realtime))

    if include_network:
        started = time.perf_counter()
        network = _network_probe()
        snapshots.append(_snapshot("after_network_probe", started, network=network))

    if include_ai_runtime:
        started = time.perf_counter()
        ai_runtime = _ai_runtime_probe()
        snapshots.append(_snapshot("after_ai_runtime_probe", started, ai_runtime=ai_runtime))

    if include_ui:
        started = time.perf_counter()
        ui = _ui_probe()
        snapshots.append(_snapshot("after_ui_first_paint", started, ui=ui))

    previous = snapshots[0]["rss_mb"]
    for item in snapshots:
        current = item["rss_mb"]
        item["delta_from_start_mb"] = _delta(current, snapshots[0]["rss_mb"])
        item["delta_from_previous_mb"] = _delta(current, previous)
        previous = current

    peak = max((item["rss_mb"] for item in snapshots), default=-1.0)
    return {
        "ok": all(item["rss_mb"] >= 0 for item in snapshots),
        "pid": os.getpid(),
        "include_ui": include_ui,
        "include_tts": include_tts,
        "include_listener": include_listener,
        "include_realtime": include_realtime,
        "include_network": include_network,
        "include_ai_runtime": include_ai_runtime,
        "peak_rss_mb": peak,
        "snapshots": snapshots,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure Shell startup, UI, tool, and TTS memory usage.")
    parser.add_argument("--ui", action="store_true", help="Instantiate the PyQt UI offscreen and measure first paint memory.")
    parser.add_argument("--tts", action="store_true", help="Initialize the TTS helper and measure its memory impact.")
    parser.add_argument("--listener", action="store_true", help="Run a synthetic voice listener thread cleanup probe.")
    parser.add_argument("--realtime", action="store_true", help="Run a synthetic realtime audio thread cleanup probe.")
    parser.add_argument("--network", action="store_true", help="Run a synthetic Socket.IO runtime cleanup probe.")
    parser.add_argument("--ai-runtime", action="store_true", help="Verify the AI brain lazy runtime stays unloaded.")
    parser.add_argument("--stress-iterations", type=int, default=10, help="Repeated catalog/tool iterations for retention checks.")
    parser.add_argument("--json-out", default="", help="Optional JSON output path.")
    args = parser.parse_args(argv)

    report = build_report(
        include_ui=args.ui,
        include_tts=args.tts,
        include_listener=args.listener,
        include_realtime=args.realtime,
        include_network=args.network,
        include_ai_runtime=args.ai_runtime,
        stress_iterations=args.stress_iterations,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
