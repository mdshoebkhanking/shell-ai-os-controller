from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


PROVIDER_KEYS = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


class _FakeBrain:
    async def generate_response_stream(self, prompt: str, mode: str = "FAST"):
        import asyncio

        await asyncio.sleep(0.01)
        yield "Shell "
        await asyncio.sleep(0.01)
        yield "streaming "
        await asyncio.sleep(0.01)
        yield "is ready."

    def get_last_stream_metrics(self) -> dict[str, Any]:
        return {
            "selected_provider": "fake",
            "first_token_ms": 10.0,
            "completion_ms": 30.0,
            "chunks": 3,
        }


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except Exception:
        pass


def _key_present(provider: str) -> bool:
    key_name = PROVIDER_KEYS.get(provider.lower(), "")
    return bool(key_name and os.getenv(key_name, "").strip())


def _rss_mb() -> float | None:
    try:
        import resource

        rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if sys.platform == "darwin":
            rss = rss / (1024 * 1024)
        else:
            rss = rss / 1024
        return round(rss, 1)
    except Exception:
        return None


def _event_payload(events: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for item in events:
        if item.get("event") == name:
            payload = item.get("payload")
            return payload if isinstance(payload, dict) else {}
    return {}


def _cadence(times_ms: list[float]) -> dict[str, Any]:
    intervals = [round(times_ms[idx] - times_ms[idx - 1], 3) for idx in range(1, len(times_ms))]
    return {
        "chunk_count": len(times_ms),
        "interval_count": len(intervals),
        "avg_interval_ms": round(statistics.mean(intervals), 3) if intervals else None,
        "max_interval_ms": max(intervals) if intervals else None,
        "chunk_times_ms": times_ms[:50],
    }


def _run_worker_probe(url: str, prompt: str, timeout_s: float) -> dict[str, Any]:
    from shell_v2_worker import ShellV2Worker

    old_url = ShellV2Worker.SHELL_V2_URL
    old_timeout = ShellV2Worker.TIMEOUT_S
    ShellV2Worker.SHELL_V2_URL = url.rstrip("/")
    ShellV2Worker.TIMEOUT_S = float(timeout_s)

    worker = ShellV2Worker(prompt)
    started = time.perf_counter()
    chunks: list[str] = []
    chunk_times_ms: list[float] = []
    replies: list[str] = []
    errors: list[str] = []
    done: list[bool] = []
    latency_events: list[dict[str, Any]] = []

    def on_chunk(chunk: str) -> None:
        chunks.append(chunk)
        chunk_times_ms.append(round((time.perf_counter() - started) * 1000.0, 3))

    worker.chunk_received.connect(on_chunk)
    worker.reply_ready.connect(replies.append)
    worker.reply_error.connect(errors.append)
    worker.stream_done.connect(lambda: done.append(True))
    worker.latency_event.connect(lambda event, payload: latency_events.append({"event": event, "payload": dict(payload)}))

    try:
        worker.run()
    finally:
        ShellV2Worker.SHELL_V2_URL = old_url
        ShellV2Worker.TIMEOUT_S = old_timeout

    first_text = _event_payload(latency_events, "first_text_chunk")
    stream_done = _event_payload(latency_events, "stream_done")
    server_metrics = stream_done.get("server_metrics") if isinstance(stream_done.get("server_metrics"), dict) else {}
    provider_metrics = stream_done.get("provider_metrics") if isinstance(stream_done.get("provider_metrics"), dict) else {}
    server_first_delta_ms = first_text.get("server_elapsed_ms")
    first_visible_ms = first_text.get("elapsed_ms")
    transport_to_worker_ms = None
    if isinstance(server_first_delta_ms, (int, float)) and isinstance(first_visible_ms, (int, float)):
        transport_to_worker_ms = round(float(first_visible_ms) - float(server_first_delta_ms), 3)

    return {
        "ok": bool(replies) and not errors and bool(done),
        "reply": replies[0] if replies else "",
        "errors": errors,
        "chunks": chunks,
        "latency_events": latency_events,
        "worker_chunk_cadence": _cadence(chunk_times_ms),
        "first_visible_ms": first_visible_ms,
        "server_first_delta_ms": server_first_delta_ms,
        "transport_to_worker_ms": transport_to_worker_ms,
        "stream_completion_ms": stream_done.get("elapsed_ms"),
        "server_metrics": server_metrics,
        "provider_metrics": provider_metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure full Shell-v2 SSE -> UI worker streaming latency.")
    parser.add_argument("--provider", default="groq", choices=sorted(PROVIDER_KEYS), help="Provider for live mode.")
    parser.add_argument("--mode", default="FAST", help="Router mode.")
    parser.add_argument("--prompt", default="Reply in one short sentence: Shell full-pipeline stream test.")
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--json-out", default="", help="Optional path to write JSON report.")
    parser.add_argument("--allow-live", action="store_true", help="Use a real external provider request.")
    args = parser.parse_args()

    _load_env()
    if args.allow_live and not _key_present(args.provider):
        report = {
            "ok": False,
            "skipped": True,
            "reason": f"{args.provider} key is not configured",
            "provider": args.provider,
            "key_present": False,
        }
    else:
        from shell_v2_runtime import start_shell_v2_bridge

        threads_before = len(threading.enumerate())
        rss_before_mb = _rss_mb()
        bridge = start_shell_v2_bridge(
            port=0,
            brain_factory=None if args.allow_live else _FakeBrain,
            provider=args.provider if args.allow_live else "",
            mode=args.mode,
        )
        try:
            probe = _run_worker_probe(bridge.url, args.prompt, args.timeout_s)
        finally:
            closed_sessions = bridge.close()
            time.sleep(0.05)
        threads_after = len(threading.enumerate())
        rss_after_mb = _rss_mb()

        provider_metrics = probe.get("provider_metrics") if isinstance(probe.get("provider_metrics"), dict) else {}
        server_metrics = probe.get("server_metrics") if isinstance(probe.get("server_metrics"), dict) else {}
        provider_first_token_ms = provider_metrics.get("first_token_ms")
        server_first_delta_ms = server_metrics.get("first_delta_ms")
        provider_to_sse_ms = None
        if isinstance(provider_first_token_ms, (int, float)) and isinstance(server_first_delta_ms, (int, float)):
            provider_to_sse_ms = round(float(server_first_delta_ms) - float(provider_first_token_ms), 3)

        report = {
            "ok": bool(probe.get("ok")),
            "live": bool(args.allow_live),
            "provider": args.provider if args.allow_live else "fake",
            "key_present": _key_present(args.provider),
            "bridge_url": bridge.url,
            "first_visible_ms": probe.get("first_visible_ms"),
            "provider_first_token_ms": provider_first_token_ms,
            "server_first_delta_ms": server_first_delta_ms,
            "provider_to_sse_ms": provider_to_sse_ms,
            "transport_to_worker_ms": probe.get("transport_to_worker_ms"),
            "stream_completion_ms": probe.get("stream_completion_ms"),
            "worker_chunk_cadence": probe.get("worker_chunk_cadence"),
            "server_metrics": server_metrics,
            "provider_metrics": provider_metrics,
            "reply_preview": str(probe.get("reply") or "")[:180],
            "errors": probe.get("errors"),
            "resource": {
                "rss_before_mb": rss_before_mb,
                "rss_after_mb": rss_after_mb,
                "threads_before": threads_before,
                "threads_after": threads_after,
                "thread_names_after": [thread.name for thread in threading.enumerate()],
                "closed_sessions": closed_sessions,
            },
        }

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report.get("ok") or report.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
