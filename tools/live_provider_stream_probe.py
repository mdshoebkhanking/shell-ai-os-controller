from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


PROVIDER_KEYS = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
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


def _estimate_ui_render_cadence(chunk_times_ms: list[float]) -> dict[str, object]:
    try:
        batch_ms = max(0, min(50, int(os.environ.get("SHELL_STREAM_RENDER_BATCH_MS", "16"))))
    except Exception:
        batch_ms = 16
    if not chunk_times_ms:
        return {
            "batch_ms": batch_ms,
            "estimated_first_visible_ms": None,
            "estimated_render_count": 0,
        }
    if batch_ms <= 0:
        return {
            "batch_ms": batch_ms,
            "estimated_first_visible_ms": chunk_times_ms[0],
            "estimated_render_count": len(chunk_times_ms),
        }
    render_count = 1
    next_flush_at = chunk_times_ms[0] + batch_ms
    for ts in chunk_times_ms[1:]:
        if ts >= next_flush_at:
            render_count += 1
            next_flush_at = ts + batch_ms
    return {
        "batch_ms": batch_ms,
        "estimated_first_visible_ms": chunk_times_ms[0],
        "estimated_render_count": render_count,
    }


async def _run_provider_stream(provider_name: str, prompt: str, mode: str) -> dict[str, object]:
    from brain.core import MultiAIBrain
    from brain.provider_transport import close_aiohttp_sessions, provider_transport_stats
    from brain.router import SmartRouter

    original_sequence = SmartRouter.get_provider_sequence
    original_model = SmartRouter.get_model_for_provider
    SmartRouter.get_provider_sequence = staticmethod(lambda selected_mode="SMART": [provider_name])
    try:
        brain = MultiAIBrain()
        if provider_name not in brain.providers:
            return {
                "ok": False,
                "provider": provider_name,
                "skipped": True,
                "reason": f"{provider_name} is not registered; key may be missing or provider disabled",
                "key_present": _key_present(provider_name),
            }

        started = time.perf_counter()
        chunks: list[str] = []
        chunk_times_ms: list[float] = []
        try:
            async for chunk in brain.generate_response_stream(prompt, mode=mode):
                if not chunk:
                    continue
                chunks.append(str(chunk))
                chunk_times_ms.append(round((time.perf_counter() - started) * 1000.0, 3))
        finally:
            transport_before_close = provider_transport_stats()
            closed_sessions = await close_aiohttp_sessions()

        intervals = [
            round(chunk_times_ms[idx] - chunk_times_ms[idx - 1], 3)
            for idx in range(1, len(chunk_times_ms))
        ]
        metrics = brain.get_last_stream_metrics()
        return {
            "ok": bool(chunks),
            "provider": provider_name,
            "mode": mode,
            "key_present": _key_present(provider_name),
            "chunk_count": len(chunks),
            "char_count": len("".join(chunks)),
            "first_chunk_ms": chunk_times_ms[0] if chunk_times_ms else None,
            "completion_ms": chunk_times_ms[-1] if chunk_times_ms else None,
            "chunk_times_ms": chunk_times_ms[:50],
            "cadence": {
                "interval_count": len(intervals),
                "avg_interval_ms": round(statistics.mean(intervals), 3) if intervals else None,
                "max_interval_ms": max(intervals) if intervals else None,
            },
            "ui_render_estimate": _estimate_ui_render_cadence(chunk_times_ms),
            "brain_metrics": metrics,
            "transport_before_close": transport_before_close,
            "closed_sessions": closed_sessions,
            "preview": "".join(chunks)[:160],
        }
    finally:
        SmartRouter.get_provider_sequence = original_sequence
        SmartRouter.get_model_for_provider = original_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely measure real provider streaming latency.")
    parser.add_argument("--provider", default="groq", choices=sorted(PROVIDER_KEYS), help="Provider to probe.")
    parser.add_argument("--mode", default="FAST", help="Router mode to use for model selection.")
    parser.add_argument(
        "--prompt",
        default="Reply in one short sentence: Shell streaming latency test.",
        help="Low-cost validation prompt.",
    )
    parser.add_argument("--json-out", default="", help="Optional path to write JSON report.")
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Required to make a real external provider request.",
    )
    args = parser.parse_args()

    _load_env()
    if not args.allow_live:
        report = {
            "ok": False,
            "skipped": True,
            "reason": "pass --allow-live to run a real external provider request",
            "provider": args.provider,
            "key_present": _key_present(args.provider),
        }
    else:
        report = asyncio.run(_run_provider_stream(args.provider, args.prompt, args.mode))

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report.get("ok") or report.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
