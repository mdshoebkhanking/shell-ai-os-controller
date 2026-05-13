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


def _provider_transport_probe():
    from brain.provider_transport import (
        close_aiohttp_sessions,
        get_aiohttp_session,
        provider_transport_stats,
        set_session_factory_for_tests,
    )

    class FakeSession:
        closed = False

        async def close(self):
            self.closed = True

    created = []

    async def _run():
        set_session_factory_for_tests(lambda owner, timeout_s: created.append(FakeSession()) or created[-1])
        try:
            first = await get_aiohttp_session("latency_probe", timeout_s=5)
            second = await get_aiohttp_session("latency_probe", timeout_s=5)
            stats = provider_transport_stats()
            closed = await close_aiohttp_sessions()
            return {
                "reused": first is second,
                "created": len(created),
                "closed": closed,
                "stats_before_close": stats,
                "stats_after_close": provider_transport_stats(),
                "aiohttp_loaded": "aiohttp" in sys.modules,
            }
        finally:
            set_session_factory_for_tests(None)
            await close_aiohttp_sessions()

    import asyncio

    return asyncio.run(_run())


def _streaming_first_token_probe():
    import asyncio

    from brain.core import MultiAIBrain
    from brain.router import SmartRouter

    class StreamingProvider:
        async def generate_response_stream_async(self, messages, model=None):
            await asyncio.sleep(0.01)
            yield "Hel"
            await asyncio.sleep(0.01)
            yield "lo"

        def supports_streaming(self):
            return True

    original_sequence = SmartRouter.get_provider_sequence
    original_model = SmartRouter.get_model_for_provider
    SmartRouter.get_provider_sequence = staticmethod(lambda mode="SMART": ["probe_stream"])
    SmartRouter.get_model_for_provider = staticmethod(lambda mode, provider_name: "probe-model")
    try:
        async def _run():
            brain = MultiAIBrain()
            brain.providers = {"probe_stream": StreamingProvider()}
            chunks = []
            async for chunk in brain.generate_response_stream("hello", mode="FAST"):
                chunks.append(chunk)
            return {
                "chunks": chunks,
                "metrics": brain.get_last_stream_metrics(),
            }

        return asyncio.run(_run())
    finally:
        SmartRouter.get_provider_sequence = original_sequence
        SmartRouter.get_model_for_provider = original_model


def _streaming_fallback_probe():
    import asyncio

    from brain.core import MultiAIBrain
    from brain.router import SmartRouter

    class SlowProvider:
        async def generate_response_async(self, messages, model=None):
            await asyncio.sleep(1.0)
            return "slow"

    class FastProvider:
        async def generate_response_async(self, messages, model=None):
            await asyncio.sleep(0.01)
            return "fast"

    old_timeout = os.environ.get("SHELL_AI_STREAM_FALLBACK_TIMEOUT_S")
    os.environ["SHELL_AI_STREAM_FALLBACK_TIMEOUT_S"] = "0.25"
    original_sequence = SmartRouter.get_provider_sequence
    original_model = SmartRouter.get_model_for_provider
    SmartRouter.get_provider_sequence = staticmethod(lambda mode="SMART": ["slow", "fast"])
    SmartRouter.get_model_for_provider = staticmethod(lambda mode, provider_name: "probe-model")
    try:
        async def _run():
            brain = MultiAIBrain()
            brain.providers = {"slow": SlowProvider(), "fast": FastProvider()}
            chunks = []
            async for chunk in brain.generate_response_stream("hello", mode="FAST"):
                chunks.append(chunk)
            return {
                "chunks": chunks,
                "metrics": brain.get_last_stream_metrics(),
            }

        return asyncio.run(_run())
    finally:
        if old_timeout is None:
            os.environ.pop("SHELL_AI_STREAM_FALLBACK_TIMEOUT_S", None)
        else:
            os.environ["SHELL_AI_STREAM_FALLBACK_TIMEOUT_S"] = old_timeout
        SmartRouter.get_provider_sequence = original_sequence
        SmartRouter.get_model_for_provider = original_model


def _shell_v2_sse_client_probe():
    from shell_ui.shell_cinematic_full import ShellV2Worker

    class FakeSSEResponse:
        status = 200

        def __init__(self, chunks: list[str], *, delay_s: float = 0.01) -> None:
            full = ""
            lines: list[bytes] = []
            for chunk in chunks:
                full += chunk
                frame = f"event: delta\ndata: {json.dumps({'text': chunk})}\n\n"
                lines.extend(line.encode("utf-8") for line in frame.splitlines(keepends=True))
            end = f"event: end\ndata: {json.dumps({'full_reply': full})}\n\n"
            lines.extend(line.encode("utf-8") for line in end.splitlines(keepends=True))
            self._lines = lines
            self._delay_s = delay_s
            self._idx = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def readline(self) -> bytes:
            if self._idx >= len(self._lines):
                return b""
            if self._delay_s:
                time.sleep(self._delay_s)
            line = self._lines[self._idx]
            self._idx += 1
            return line

    old_url = ShellV2Worker.SHELL_V2_URL
    old_timeout = ShellV2Worker.TIMEOUT_S
    old_urlopen = urllib.request.urlopen

    def fake_urlopen(request, timeout=0):
        if not str(getattr(request, "full_url", "")).endswith("/api/say-stream"):
            raise RuntimeError("probe expected Shell-v2 SSE endpoint")
        return FakeSSEResponse(["Hel", "lo"], delay_s=0.01)

    urllib.request.urlopen = fake_urlopen
    try:
        ShellV2Worker.SHELL_V2_URL = "http://127.0.0.1:8765"
        ShellV2Worker.TIMEOUT_S = 3
        worker = ShellV2Worker("hello")
        chunks: list[str] = []
        replies: list[str] = []
        errors: list[str] = []
        done: list[bool] = []
        events: list[dict[str, object]] = []

        worker.chunk_received.connect(chunks.append)
        worker.reply_ready.connect(replies.append)
        worker.reply_error.connect(errors.append)
        worker.stream_done.connect(lambda: done.append(True))

        def _latency(event, payload):
            item = {"event": str(event)}
            if isinstance(payload, dict):
                item.update(payload)
            events.append(item)

        worker.latency_event.connect(_latency)
        worker.run()
        return {
            "chunks": chunks,
            "reply": replies[0] if replies else "",
            "errors": errors,
            "done": bool(done),
            "events": events,
        }
    finally:
        urllib.request.urlopen = old_urlopen
        ShellV2Worker.SHELL_V2_URL = old_url
        ShellV2Worker.TIMEOUT_S = old_timeout


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
        samples.append(_measure("ai.provider_transport_reuse", _provider_transport_probe))
        samples.append(_measure("ai.streaming_first_token", _streaming_first_token_probe))
        samples.append(_measure("ai.streaming_fallback", _streaming_fallback_probe))
        samples.append(_measure("shell_v2.sse_client_stream", _shell_v2_sse_client_probe))

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
