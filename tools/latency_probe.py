from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _measure(name: str, fn):
    started = time.perf_counter()
    try:
        value = fn()
        ok = True
        error = ""
    except Exception as exc:
        value = None
        ok = False
        error = f"{type(exc).__name__}: {exc}"
    return {
        "name": name,
        "ok": ok,
        "duration_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "value": value,
        "error": error,
    }


def _tts_playback_probe(text: str, timeout_s: float = 10.0):
    from PyQt6.QtCore import QCoreApplication
    from shell_voice_runtime import TTSSpeaker

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    speaker = TTSSpeaker()
    events: list[dict[str, object]] = []
    state = {"finished": False}

    def _latency_event(event, payload):
        item = {"event": str(event)}
        if isinstance(payload, dict):
            item.update(payload)
        events.append(item)

    speaker.latency_event.connect(_latency_event)
    speaker.speaking_finished.connect(lambda: state.__setitem__("finished", True))
    speaker.start()
    speaker.warmup()
    warm_deadline = time.time() + 1.0
    while time.time() < warm_deadline and not any(e.get("event") == "warmup" for e in events):
        app.processEvents()
        time.sleep(0.01)

    started = time.perf_counter()
    speaker.speak(text, force=True)
    deadline = time.time() + timeout_s
    while time.time() < deadline and not state["finished"]:
        app.processEvents()
        time.sleep(0.01)

    total_ms = round((time.perf_counter() - started) * 1000.0, 3)
    speaker.shutdown()
    speaker.wait(1500)
    app.processEvents()

    playback_events = [e for e in events if e.get("event") == "playback_started"]
    first_playback_ms = playback_events[0].get("elapsed_ms") if playback_events else None
    return {
        "finished": bool(state["finished"]),
        "total_ms": total_ms,
        "first_playback_ms": first_playback_ms,
        "events": events,
    }


def _provider_runtime_probe():
    modules_before = {
        "brain_core": "brain.core" in sys.modules,
        "openai": "openai" in sys.modules,
        "google_genai": "google.genai" in sys.modules,
        "aiohttp": "aiohttp" in sys.modules,
        "openai_provider": "brain.providers.openai_p" in sys.modules,
        "gemini_provider": "brain.providers.gemini_p" in sys.modules,
        "groq_provider": "brain.providers.groq_p" in sys.modules,
    }
    started = time.perf_counter()
    from brain.core import MultiAIBrain

    brain = MultiAIBrain.get_instance()
    init_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return {
        "provider_count": len(brain.providers),
        "provider_names": sorted(brain.providers.keys()),
        "init_ms": init_ms,
        "modules_before": modules_before,
        "modules_after": {
            "brain_core": "brain.core" in sys.modules,
            "openai": "openai" in sys.modules,
            "google_genai": "google.genai" in sys.modules,
            "aiohttp": "aiohttp" in sys.modules,
            "openai_provider": "brain.providers.openai_p" in sys.modules,
            "gemini_provider": "brain.providers.gemini_p" in sys.modules,
            "groq_provider": "brain.providers.groq_p" in sys.modules,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Shell low-latency hot paths.")
    parser.add_argument("--ui", action="store_true", help="Also instantiate the PyQt UI offscreen.")
    parser.add_argument("--tts-playback", action="store_true", help="Play a short audible TTS sample and measure playback start.")
    parser.add_argument("--tts-text", default="Shell voice test. Awaaz aa rahi hai?")
    parser.add_argument("--provider-runtime", action="store_true", help="Measure lazy AI provider runtime initialization.")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SHELL_V2_TIMEOUT_S", "1")
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except Exception:
        pass

    import shell_tool_catalog
    from shell_ui.shell_cinematic_full import ShellHoloUI, ShellV2Worker
    from shell_voice_runtime import TTSSpeaker, _EDGE_TTS_AVAILABLE

    samples = []
    samples.append(_measure("catalog.discovery", lambda: len(shell_tool_catalog.discover_capabilities().get("catalog", []))))
    samples.append(_measure("chat.fast_candidate", lambda: len(ShellHoloUI._fast_local_reply_candidate("hello") or "")))
    samples.append(_measure("chat.local_reply", lambda: len(ShellHoloUI._local_reply("hello"))))
    samples.append(_measure("tts.system_command", lambda: TTSSpeaker()._detect_system_tts_command()))
    if args.tts_playback:
        samples.append(_measure("tts.playback_probe", lambda: _tts_playback_probe(args.tts_text)))
    samples.append(_measure("shell_v2.connect_1s", lambda: urllib.request.urlopen(
        urllib.request.Request(
            ShellV2Worker.SHELL_V2_URL + "/api/say",
            data=b"{\"text\":\"ping\"}",
            headers={"Content-Type": "application/json"},
            method="POST",
        ),
        timeout=1,
    ).status))

    if args.ui:
        def _ui_init():
            from PyQt6.QtWidgets import QApplication
            from shell_ui.app_bootstrap import configure_qt_application

            app = QApplication.instance() or QApplication(sys.argv)
            configure_qt_application(app)
            window = ShellHoloUI()
            window.resize(1100, 680)
            window.show()
            deadline = time.time() + 0.4
            while time.time() < deadline:
                app.processEvents()
                time.sleep(0.01)
            window.close()
            app.processEvents()
            return {"pages": window.pages.count()}

        samples.append(_measure("ui.init_first_paint", _ui_init))

    if args.provider_runtime:
        samples.append(_measure("ai.provider_runtime_init", _provider_runtime_probe))

    report = {
        "ok": all(sample["ok"] for sample in samples if sample["name"] != "shell_v2.connect_1s"),
        "settings": {
            "shell_v2_stream_default": ShellV2Worker.stream_enabled(),
            "shell_v2_timeout_s": ShellV2Worker.TIMEOUT_S,
            "edge_tts_available": _EDGE_TTS_AVAILABLE,
            "pyttsx3_available": bool(importlib.util.find_spec("pyttsx3")),
            "tts_engine": os.environ.get("SHELL_TTS_ENGINE", "fast"),
        },
        "samples": samples,
    }

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
