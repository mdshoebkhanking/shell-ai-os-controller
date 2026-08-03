from __future__ import annotations

import asyncio
import time
import pytest


def _brain_with_providers(providers):
    from brain.core import MultiAIBrain

    brain = MultiAIBrain()
    brain.providers = providers
    return brain


def test_brain_stream_records_first_token_metrics(monkeypatch) -> None:
    from brain.router import SmartRouter

    class StreamingProvider:
        async def generate_response_stream_async(self, messages, model=None):
            await asyncio.sleep(0.01)
            yield "he"
            await asyncio.sleep(0.01)
            yield "llo"

        def supports_streaming(self):
            return True

    monkeypatch.setattr(SmartRouter, "get_provider_sequence", staticmethod(lambda mode="SMART": ["streamer"]))
    monkeypatch.setattr(SmartRouter, "get_model_for_provider", staticmethod(lambda mode, provider_name: "fake-model"))

    async def scenario():
        brain = _brain_with_providers({"streamer": StreamingProvider()})
        chunks = []
        async for chunk in brain.generate_response_stream("hello", mode="FAST"):
            chunks.append(chunk)
        return chunks, brain.get_last_stream_metrics()

    chunks, metrics = asyncio.run(scenario())

    assert chunks == ["he", "llo"]
    assert metrics["selected_provider"] == "streamer"
    assert metrics["chunks"] == 2
    assert metrics["first_token_ms"] is not None
    assert metrics["completion_ms"] >= metrics["first_token_ms"]


def test_brain_stream_fallback_timeout_moves_to_next_provider(monkeypatch) -> None:
    from brain.router import SmartRouter

    class SlowProvider:
        async def generate_response_async(self, messages, model=None):
            await asyncio.sleep(1.0)
            return "too late"

    class FastProvider:
        async def generate_response_async(self, messages, model=None):
            await asyncio.sleep(0.01)
            return "fast response"

    monkeypatch.setenv("SHELL_AI_STREAM_FALLBACK_TIMEOUT_S", "0.25")
    monkeypatch.setattr(SmartRouter, "get_provider_sequence", staticmethod(lambda mode="SMART": ["slow", "fast"]))
    monkeypatch.setattr(SmartRouter, "get_model_for_provider", staticmethod(lambda mode, provider_name: "fake-model"))

    async def scenario():
        brain = _brain_with_providers({"slow": SlowProvider(), "fast": FastProvider()})
        started = time.perf_counter()
        chunks = []
        async for chunk in brain.generate_response_stream("hello", mode="FAST"):
            chunks.append(chunk)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        return chunks, elapsed_ms, brain.get_last_stream_metrics()

    chunks, elapsed_ms, metrics = asyncio.run(scenario())

    assert chunks == ["fast response"]
    assert elapsed_ms < 800
    assert metrics["providers_attempted"] == ["slow", "fast"]
    assert metrics["selected_provider"] == "fast"
    assert metrics["fallback_timeout_s"] == 0.25
    assert any("slow fallback" in err for err in metrics["errors"])


def test_brain_stream_fallback_rejects_provider_error_string(monkeypatch) -> None:
    from brain.router import SmartRouter

    class ErrorProvider:
        async def generate_response_async(self, messages, model=None):
            return "Gemini Error: quota or rate limit reached. Try again later."

    class FastProvider:
        async def generate_response_async(self, messages, model=None):
            return "healthy fallback"

    monkeypatch.setattr(SmartRouter, "get_provider_sequence", staticmethod(lambda mode="SMART": ["bad", "fast"]))
    monkeypatch.setattr(SmartRouter, "get_model_for_provider", staticmethod(lambda mode, provider_name: "fake-model"))

    async def scenario():
        brain = _brain_with_providers({"bad": ErrorProvider(), "fast": FastProvider()})
        chunks = []
        async for chunk in brain.generate_response_stream("hello", mode="FAST"):
            chunks.append(chunk)
        return chunks, brain.get_last_stream_metrics()

    chunks, metrics = asyncio.run(scenario())

    assert chunks == ["healthy fallback"]
    assert metrics["providers_attempted"] == ["bad", "fast"]
    assert metrics["selected_provider"] == "fast"
    assert any("bad fallback" in err and "Gemini Error" in err for err in metrics["errors"])


def test_brain_true_stream_rejects_provider_error_chunk(monkeypatch) -> None:
    from brain.router import SmartRouter

    class ErrorStreamingProvider:
        async def generate_response_stream_async(self, messages, model=None):
            yield "OpenAI Error: rate limit"

        def supports_streaming(self):
            return True

    class FastProvider:
        async def generate_response_async(self, messages, model=None):
            return "healthy fallback"

    monkeypatch.setattr(SmartRouter, "get_provider_sequence", staticmethod(lambda mode="SMART": ["bad_stream", "fast"]))
    monkeypatch.setattr(SmartRouter, "get_model_for_provider", staticmethod(lambda mode, provider_name: "fake-model"))

    async def scenario():
        brain = _brain_with_providers({"bad_stream": ErrorStreamingProvider(), "fast": FastProvider()})
        chunks = []
        async for chunk in brain.generate_response_stream("hello", mode="FAST"):
            chunks.append(chunk)
        return chunks, brain.get_last_stream_metrics()

    chunks, metrics = asyncio.run(scenario())

    assert chunks == ["healthy fallback"]
    assert metrics["providers_attempted"] == ["bad_stream", "fast"]
    assert metrics["selected_provider"] == "fast"
    assert any("bad_stream stream" in err and "OpenAI Error" in err for err in metrics["errors"])


@pytest.mark.skip(reason="AIChatWorker removed during PyQt6 cleanup")
def test_ai_chat_worker_emits_first_token_latency() -> None:
    # AIChatWorker removed (PyQt6 cleanup)

    class FakeBrain:
        providers = {"fake": object()}

        async def generate_response_stream(self, prompt, system_prompt=None, mode="SMART"):
            yield "A"
            yield "B"

    worker = AIChatWorker(FakeBrain(), "hello", history=[])
    chunks = []
    events = []
    done = []
    worker.chunk_received.connect(chunks.append)
    worker.stream_done.connect(lambda: done.append(True))
    worker.latency_event.connect(lambda event, payload: events.append((event, payload)))

    worker.run()

    assert chunks == ["A", "B"]
    assert done == [True]
    event_names = [event for event, _payload in events]
    assert "inprocess_stream_start" in event_names
    assert "first_text_chunk" in event_names
    assert "stream_done" in event_names
    first_payload = next(payload for event, payload in events if event == "first_text_chunk")
    assert first_payload["elapsed_ms"] >= 0


@pytest.mark.skip(reason="AIChatWorker removed during PyQt6 cleanup")
def test_ai_chat_worker_cancels_stream_on_interruption() -> None:
    # AIChatWorker removed (PyQt6 cleanup)

    class FakeBrain:
        providers = {"fake": object()}

        async def generate_response_stream(self, prompt, system_prompt=None, mode="SMART"):
            yield "A"
            yield "B"

        async def close_provider_sessions(self):
            self.closed = True

    brain = FakeBrain()
    worker = AIChatWorker(brain, "hello", history=[])
    chunks = []
    replies = []
    errors = []
    done = []
    events = []

    def _on_chunk(chunk: str) -> None:
        chunks.append(chunk)
        worker.requestInterruption()

    worker.chunk_received.connect(_on_chunk)
    worker.reply_ready.connect(replies.append)
    worker.reply_error.connect(errors.append)
    worker.stream_done.connect(lambda: done.append(True))
    worker.latency_event.connect(lambda event, payload: events.append((event, payload)))

    worker.run()

    assert chunks == ["A"]
    assert replies == []
    assert errors == []
    assert done == []
    assert getattr(brain, "closed", False) is True
    cancelled = next(payload for event, payload in events if event == "stream_cancelled")
    assert cancelled["chars"] == 1
