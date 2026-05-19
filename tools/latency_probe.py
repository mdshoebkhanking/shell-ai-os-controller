from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
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
    try:
        warmup_wait_s = max(1.0, min(5.0, float(os.environ.get("SHELL_TTS_WARMUP_WAIT_S", "3"))))
    except Exception:
        warmup_wait_s = 3.0
    warm_started = time.perf_counter()
    warm_deadline = time.time() + warmup_wait_s
    while time.time() < warm_deadline and not any(e.get("event") == "warmup" for e in events):
        app.processEvents()
        time.sleep(0.01)
    warmup_wait_ms = round((time.perf_counter() - warm_started) * 1000.0, 3)
    warmup_completed = any(e.get("event") == "warmup" for e in events)

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
    audible_events = [
        e
        for e in events
        if e.get("event") in {"gemini_live_first_audible_chunk", "openai_pcm_first_chunk"}
    ]
    first_audible_ms = audible_events[0].get("elapsed_ms") if audible_events else first_playback_ms
    queued_events = [e for e in events if e.get("event") == "queued"]
    queue_to_playback_ms = None
    queue_to_first_audible_ms = None
    if queued_events and playback_events:
        try:
            queue_to_playback_ms = round(
                (float(playback_events[0]["ts"]) - float(queued_events[0]["ts"])) * 1000.0,
                3,
            )
        except Exception:
            queue_to_playback_ms = None
    if queued_events and audible_events:
        try:
            queue_to_first_audible_ms = round(
                (float(audible_events[0]["ts"]) - float(queued_events[0]["ts"])) * 1000.0,
                3,
            )
        except Exception:
            queue_to_first_audible_ms = None
    return {
        "finished": bool(state["finished"]),
        "total_ms": total_ms,
        "first_playback_ms": first_playback_ms,
        "first_audible_ms": first_audible_ms,
        "queue_to_playback_ms": queue_to_playback_ms,
        "queue_to_first_audible_ms": queue_to_first_audible_ms,
        "warmup_completed": warmup_completed,
        "warmup_wait_ms": warmup_wait_ms,
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


def _shell_v2_worker_cancel_probe():
    from shell_ui.shell_cinematic_full import ShellV2Worker

    class FakeSSEResponse:
        status = 200

        def __init__(self) -> None:
            lines: list[bytes] = []
            for idx, chunk in enumerate(["A", "B", "C"], start=1):
                frame = f"event: delta\ndata: {json.dumps({'text': chunk, 'chunk_index': idx})}\n\n"
                lines.extend(line.encode("utf-8") for line in frame.splitlines(keepends=True))
            end = f"event: end\ndata: {json.dumps({'full_reply': 'ABC'})}\n\n"
            lines.extend(line.encode("utf-8") for line in end.splitlines(keepends=True))
            self._lines = lines
            self._idx = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def readline(self) -> bytes:
            if self._idx >= len(self._lines):
                return b""
            line = self._lines[self._idx]
            self._idx += 1
            return line

    old_url = ShellV2Worker.SHELL_V2_URL
    old_timeout = ShellV2Worker.TIMEOUT_S
    old_urlopen = urllib.request.urlopen

    def fake_urlopen(request, timeout=0):
        if not str(getattr(request, "full_url", "")).endswith("/api/say-stream"):
            raise RuntimeError("probe expected Shell-v2 SSE endpoint")
        return FakeSSEResponse()

    urllib.request.urlopen = fake_urlopen
    try:
        ShellV2Worker.SHELL_V2_URL = "http://127.0.0.1:8765"
        ShellV2Worker.TIMEOUT_S = 3
        worker = ShellV2Worker("hello")
        chunks: list[str] = []
        events: list[dict[str, object]] = []
        replies: list[str] = []
        done: list[bool] = []

        def _on_chunk(chunk):
            chunks.append(str(chunk))
            worker.requestInterruption()

        def _latency(event, payload):
            item = {"event": str(event)}
            if isinstance(payload, dict):
                item.update(payload)
            events.append(item)

        worker.chunk_received.connect(_on_chunk)
        worker.reply_ready.connect(replies.append)
        worker.stream_done.connect(lambda: done.append(True))
        worker.latency_event.connect(_latency)
        started = time.perf_counter()
        worker.run()
        total_ms = round((time.perf_counter() - started) * 1000.0, 3)
        cancel_event = next((e for e in events if e.get("event") == "stream_cancelled"), {})
        return {
            "chunks": chunks,
            "reply_count": len(replies),
            "done": bool(done),
            "total_ms": total_ms,
            "cancel_event": cancel_event,
            "events": events,
        }
    finally:
        urllib.request.urlopen = old_urlopen
        ShellV2Worker.SHELL_V2_URL = old_url
        ShellV2Worker.TIMEOUT_S = old_timeout


def _shell_v2_runtime_reuse_probe():
    import asyncio

    from brain.provider_transport import (
        close_aiohttp_sessions,
        provider_transport_stats,
        set_session_factory_for_tests,
    )
    from shell_v2_runtime import ShellV2Runtime

    class FakeSession:
        closed = False

        async def close(self):
            self.closed = True

    created: list[FakeSession] = []

    class FakeBrain:
        async def generate_response_stream(self, prompt: str, mode: str = "FAST"):
            from brain.provider_transport import get_aiohttp_session

            await get_aiohttp_session("shell_v2_reuse_probe", timeout_s=5)
            yield prompt

        def get_last_stream_metrics(self):
            return {"selected_provider": "fake"}

    started = time.perf_counter()
    set_session_factory_for_tests(lambda owner, timeout_s: created.append(FakeSession()) or created[-1])
    runtime = ShellV2Runtime(brain_factory=FakeBrain)
    closed = 0
    try:
        first = list(runtime.stream_events("one"))
        second = list(runtime.stream_events("two"))
        stats_before_close = provider_transport_stats()
        closed = runtime.close()
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        sessions = [
            item for item in stats_before_close["sessions"]
            if item["owner"] == "shell_v2_reuse_probe"
        ]
        return {
            "elapsed_ms": elapsed_ms,
            "first_events": [event for event, _payload in first],
            "second_events": [event for event, _payload in second],
            "created_sessions": len(created),
            "closed_sessions": closed,
            "reuse_session": bool(len(sessions) == 1 and sessions[0].get("uses") == 2),
            "stats_before_close": stats_before_close,
        }
    finally:
        set_session_factory_for_tests(None)
        try:
            if closed <= 0:
                runtime.close()
        except Exception:
            pass
        try:
            asyncio.run(close_aiohttp_sessions())
        except Exception:
            pass


def _voice_turn_cancel_probe():
    from shell_ui.shell_cinematic_full import ShellHoloUI

    class FakeSignal:
        def __init__(self):
            self.disconnects = 0

        def disconnect(self):
            self.disconnects += 1

    class FakeWorker:
        def __init__(self):
            self.reply_ready = FakeSignal()
            self.reply_error = FakeSignal()
            self.chunk_received = FakeSignal()
            self.stream_done = FakeSignal()
            self.latency_event = FakeSignal()
            self.interrupted = False

        def isRunning(self):
            return True

        def requestInterruption(self):
            self.interrupted = True

    class FakeTTS:
        def __init__(self):
            self.stopped = False

        def is_speaking(self):
            return True

        def stop_speaking(self):
            self.stopped = True

    class FakeSystemPage:
        def __init__(self):
            self.logs = []

        def add_log_entry(self, *args):
            self.logs.append(args)

    ui = ShellHoloUI.__new__(ShellHoloUI)
    ui._voice_turn_id = 7
    ui._voice_streaming_text = "stale partial reply"
    ui._voice_stream_spoken_upto = 8
    ui._voice_turn_query_started = time.time()
    ui._voice_first_chunk_seen = True
    ui._backend_command_workers = []
    ui._voice_backend_command_workers = []
    ui._tts = FakeTTS()
    ui._voice_worker = FakeWorker()
    ui.system_page = FakeSystemPage()

    started = time.perf_counter()
    cancelled = ui._cancel_active_voice_reply("probe")
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)

    signal_disconnects = sum(
        getattr(ui._voice_worker, name).disconnects
        for name in ("reply_ready", "reply_error", "chunk_received", "stream_done", "latency_event")
    )
    return {
        "cancelled": bool(cancelled),
        "elapsed_ms": elapsed_ms,
        "turn_id": ui._voice_turn_id,
        "turn_advanced": ui._voice_turn_id == 8,
        "tts_stopped": ui._tts.stopped,
        "worker_interrupted": ui._voice_worker.interrupted,
        "signal_disconnects": signal_disconnects,
        "stream_cleared": ui._voice_streaming_text == "" and ui._voice_stream_spoken_upto == 0,
        "logs": len(ui.system_page.logs),
    }


def _realtime_voice_session_probe():
    from shell_realtime_voice_session import RealtimeVoiceSession

    started = time.perf_counter()
    session = RealtimeVoiceSession(session_id="probe")
    session.start()
    session.user_speech_started()
    prewarm_before = session.should_prewarm()
    session.prewarm_started()
    session.prewarm_done(elapsed_ms=2.5, shell_v2_ready=True, provider_count=7)
    prewarm_after = session.should_prewarm()
    session.user_speech_ended()
    session.text_committed("hello", turn_id=3)
    session.assistant_speech_started(transport="shell_v2")
    session.interrupt("probe")
    session.assistant_speech_done()
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    snapshot = session.snapshot()
    snapshot["control_overhead_ms"] = elapsed_ms
    snapshot["prewarm_before"] = prewarm_before
    snapshot["prewarm_after"] = prewarm_after
    return snapshot


def _agent_first_orchestration_probe():
    from core.agent_orchestrator import AgentFirstOrchestrator

    prompts = [
        "what is 2+3*4",
        "open calculator",
        "search google for pyqt qthread cleanup",
        "developer agent fix login",
    ]
    orchestrator = AgentFirstOrchestrator()
    rows = []
    for prompt in prompts:
        samples_ms = []
        plan = orchestrator.orchestrate(prompt)
        for _ in range(100):
            started = time.perf_counter()
            orchestrator.orchestrate(prompt)
            samples_ms.append((time.perf_counter() - started) * 1000.0)
        rows.append({
            "prompt": prompt,
            "agent": plan.selected_agent_id,
            "capability": plan.capability,
            "low_level_tool_id": plan.low_level_tool_id,
            "median_ms": round(statistics.median(samples_ms), 4),
            "p95_ms": round(sorted(samples_ms)[94], 4),
        })
    return rows


def _platform_supervisor_probe():
    from core.platform_supervisor import build_platform_snapshot

    snapshot = build_platform_snapshot(include_catalog=False)
    return {
        "score": snapshot.get("score"),
        "status": snapshot.get("status"),
        "snapshot_ms": snapshot.get("process", {}).get("snapshot_ms"),
        "domains": [
            {
                "name": domain.get("name"),
                "status": domain.get("status"),
                "score": domain.get("score"),
            }
            for domain in snapshot.get("domains", [])
        ],
    }


def _voice_adaptive_endpointing_probe():
    from shell_voice_listener_runtime import VoiceListenerThread

    listener = VoiceListenerThread()
    short_clean = listener._adaptive_speech_timeout(0.8, noise_floor=0.0)
    medium_clean = listener._adaptive_speech_timeout(1.8, noise_floor=0.0)
    long_clean = listener._adaptive_speech_timeout(6.0, noise_floor=0.0)
    short_noisy = listener._adaptive_speech_timeout(
        0.8,
        noise_floor=listener._silence_threshold * 0.8,
    )
    hesitation_listener = VoiceListenerThread()
    hesitation = hesitation_listener._remember_semantic_turn("um let me think", duration_s=0.8)
    after_hesitation = hesitation_listener._adaptive_speech_timeout(0.8, noise_floor=0.0)
    continuation_listener = VoiceListenerThread()
    continuation = continuation_listener._remember_semantic_turn(
        "can you open the file and",
        duration_s=1.5,
    )
    after_continuation = continuation_listener._adaptive_speech_timeout(0.8, noise_floor=0.0)
    command_listener = VoiceListenerThread()
    command = command_listener._remember_semantic_turn("stop", duration_s=0.4)
    after_short_command = command_listener._adaptive_speech_timeout(1.8, noise_floor=0.0)
    patient_listener = VoiceListenerThread()
    patient_listener._remember_semantic_turn("um let me think", duration_s=0.8)
    patient_listener._remember_semantic_turn("can you open the file and", duration_s=1.5)
    after_patient_rhythm = patient_listener._adaptive_speech_timeout(0.8, noise_floor=0.0)
    fast_listener = VoiceListenerThread()
    fast_listener._remember_semantic_turn("stop", duration_s=0.4)
    fast_listener._remember_semantic_turn("yes", duration_s=0.4)
    after_fast_rhythm = fast_listener._adaptive_speech_timeout(1.8, noise_floor=0.0)
    return {
        "adaptive_enabled": bool(listener._adaptive_endpointing),
        "semantic_pacing_enabled": bool(listener._semantic_pacing),
        "base_ms": round(listener._speech_timeout * 1000.0, 2),
        "short_clean_ms": round(short_clean * 1000.0, 2),
        "medium_clean_ms": round(medium_clean * 1000.0, 2),
        "long_clean_ms": round(long_clean * 1000.0, 2),
        "short_noisy_ms": round(short_noisy * 1000.0, 2),
        "after_hesitation_ms": round(after_hesitation * 1000.0, 2),
        "after_continuation_ms": round(after_continuation * 1000.0, 2),
        "after_short_command_ms": round(after_short_command * 1000.0, 2),
        "after_patient_rhythm_ms": round(after_patient_rhythm * 1000.0, 2),
        "after_fast_rhythm_ms": round(after_fast_rhythm * 1000.0, 2),
        "hesitation": hesitation,
        "continuation": continuation,
        "short_command": command,
        "patient_rhythm": patient_listener._semantic_rhythm_profile,
        "fast_rhythm": fast_listener._semantic_rhythm_profile,
        "min_ms": round(listener._endpoint_min_s * 1000.0, 2),
        "max_ms": round(listener._endpoint_max_s * 1000.0, 2),
        "threshold": round(listener._silence_threshold, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Shell low-latency hot paths.")
    parser.add_argument("--ui", action="store_true", help="Also instantiate the PyQt UI offscreen.")
    parser.add_argument("--tts-playback", action="store_true", help="Play a short audible TTS sample and measure playback start.")
    parser.add_argument("--tts-text", default="Shell voice test. Awaaz aa rahi hai?")
    parser.add_argument("--tts-timeout-s", type=float, default=20.0)
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
    samples.append(_measure("tts.voice_identity", lambda: TTSSpeaker().voice_identity_snapshot()))
    if args.tts_playback:
        samples.append(_measure(
            "tts.playback_probe",
            lambda: _tts_playback_probe(args.tts_text, timeout_s=max(1.0, float(args.tts_timeout_s))),
        ))
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
            bridge_started = getattr(window, "_shell_v2_bridge", None) is not None
            shell_v2_health_ok = False
            if bridge_started:
                try:
                    shell_v2_health_ok = urllib.request.urlopen(
                        ShellV2Worker.SHELL_V2_URL + "/health",
                        timeout=0.5,
                    ).status == 200
                except Exception:
                    shell_v2_health_ok = False
            window.close()
            app.processEvents()
            return {
                "pages": window.pages.count(),
                "shell_v2_bridge_started": bridge_started,
                "shell_v2_health_ok": shell_v2_health_ok,
            }

        samples.append(_measure("ui.init_first_paint", _ui_init))

    if args.provider_runtime:
        samples.append(_measure("ai.provider_runtime_init", _provider_runtime_probe))
        samples.append(_measure("ai.provider_transport_reuse", _provider_transport_probe))
    samples.append(_measure("ai.streaming_first_token", _streaming_first_token_probe))
    samples.append(_measure("ai.streaming_fallback", _streaming_fallback_probe))
    samples.append(_measure("shell_v2.sse_client_stream", _shell_v2_sse_client_probe))
    samples.append(_measure("shell_v2.worker_cancel", _shell_v2_worker_cancel_probe))
    samples.append(_measure("shell_v2.runtime_reuse", _shell_v2_runtime_reuse_probe))
    samples.append(_measure("agent.first_orchestration", _agent_first_orchestration_probe))
    samples.append(_measure("platform.supervisor_snapshot", _platform_supervisor_probe))
    samples.append(_measure("voice.turn_cancel", _voice_turn_cancel_probe))
    samples.append(_measure("voice.realtime_session", _realtime_voice_session_probe))
    samples.append(_measure("voice.adaptive_endpointing", _voice_adaptive_endpointing_probe))

    report = {
        "ok": all(sample["ok"] for sample in samples if sample["name"] != "shell_v2.connect_1s"),
        "settings": {
            "shell_v2_stream_default": ShellV2Worker.stream_enabled(),
            "shell_v2_timeout_s": ShellV2Worker.TIMEOUT_S,
            "edge_tts_available": _EDGE_TTS_AVAILABLE,
            "pyttsx3_available": bool(importlib.util.find_spec("pyttsx3")),
            "tts_engine": os.environ.get("SHELL_TTS_ENGINE", "fast"),
            "tts_premium_voice_first": os.environ.get("SHELL_TTS_PREMIUM_FIRST", "1"),
            "tts_premium_streaming_voice": os.environ.get("SHELL_GEMINI_LIVE_TTS", "1"),
            "gemini_live_tts_model": os.environ.get("GEMINI_LIVE_TTS_MODEL", "gemini-3.1-flash-live-preview"),
            "tts_cloud_fallback_allowed": os.environ.get("SHELL_CLOUD_TTS_LOCAL_FALLBACK", "0"),
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
