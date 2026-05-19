from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _process_events(app, duration_s: float = 0.15) -> None:
    deadline = time.time() + duration_s
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _first_event(events: list[dict[str, object]], *names: str) -> Optional[dict[str, object]]:
    wanted = set(names)
    for event in events:
        if event.get("event") in wanted:
            return event
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Shell UI and validate the real TTS path.")
    parser.add_argument("--tts-text", default="Shell full UI premium voice validation.")
    parser.add_argument("--timeout-s", type=float, default=18.0)
    parser.add_argument("--warmup-timeout-s", type=float, default=5.0)
    parser.add_argument("--json-out", default="/private/tmp/shell_voice_ui_validation.json")
    parser.add_argument("--visible", action="store_true", help="Render using the real display.")
    args = parser.parse_args()

    if not args.visible:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    from shell_ui.app_bootstrap import configure_qt_application
    from shell_ui.shell_cinematic_full import ShellHoloUI

    app = QApplication.instance() or QApplication(sys.argv)
    configure_qt_application(app)

    window = ShellHoloUI()
    window.resize(1260, 720)
    window.show()
    _process_events(app, 0.5)

    events: list[dict[str, object]] = []
    state = {"finished": False}

    def _latency_event(event, payload):
        item: dict[str, object] = {"event": str(event)}
        if isinstance(payload, dict):
            item.update(payload)
        events.append(item)

    window._tts.latency_event.connect(_latency_event)
    window._tts.speaking_finished.connect(lambda: state.__setitem__("finished", True))
    window._tts.warmup()

    warm_started = time.perf_counter()
    warm_deadline = time.time() + max(1.0, float(args.warmup_timeout_s))
    while time.time() < warm_deadline and _first_event(events, "warmup") is None:
        _process_events(app, 0.03)
    warmup_wait_ms = round((time.perf_counter() - warm_started) * 1000.0, 3)

    started = time.perf_counter()
    window._tts.speak(args.tts_text, force=True)
    deadline = time.time() + max(1.0, float(args.timeout_s))
    while time.time() < deadline and not state["finished"]:
        _process_events(app, 0.03)
    total_ms = round((time.perf_counter() - started) * 1000.0, 3)

    queued = _first_event(events, "queued")
    audible = _first_event(events, "gemini_live_first_audible_chunk", "openai_pcm_first_chunk")
    playback = _first_event(events, "playback_started")
    selected = _first_event(events, "tts_backend_selected")

    def _delta_from_queue(event: dict[str, object] | None):
        if not queued or not event:
            return None
        try:
            return round((float(event["ts"]) - float(queued["ts"])) * 1000.0, 3)
        except Exception:
            return None

    report = {
        "ok": bool(state["finished"] and playback),
        "finished": bool(state["finished"]),
        "total_ms": total_ms,
        "warmup_completed": _first_event(events, "warmup") is not None,
        "warmup_wait_ms": warmup_wait_ms,
        "backend": (selected or {}).get("backend"),
        "voice": (selected or {}).get("voice"),
        "model": (selected or {}).get("model"),
        "first_audible_ms": (audible or {}).get("elapsed_ms"),
        "first_playback_ms": (playback or {}).get("elapsed_ms"),
        "queue_to_first_audible_ms": _delta_from_queue(audible),
        "queue_to_playback_ms": _delta_from_queue(playback),
        "voice_identity": window._tts.voice_identity_snapshot(),
        "events": events,
    }

    try:
        window._stop_backend_command_workers()
    except Exception:
        pass
    try:
        window._tts.shutdown()
        window._tts.wait(1500)
    except Exception:
        pass
    window.close()
    _process_events(app, 0.2)

    Path(args.json_out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
