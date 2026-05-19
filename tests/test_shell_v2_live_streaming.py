from __future__ import annotations

import json
import time
import urllib.request


class _FakeSSEResponse:
    status = 200

    def __init__(self, chunks: list[str], *, delay_s: float = 0.01) -> None:
        full = ""
        lines: list[bytes] = []
        for chunk in chunks:
            full += chunk
            frame = f"event: delta\ndata: {json.dumps({'text': chunk, 'server_elapsed_ms': 1.2, 'chunk_index': len(full)})}\n\n"
            lines.extend(line.encode("utf-8") for line in frame.splitlines(keepends=True))
        end = f"event: end\ndata: {json.dumps({'full_reply': full, 'server_elapsed_ms': 2.4, 'server_metrics': {'chunks': len(chunks)}, 'provider_metrics': {'selected_provider': 'fake'}})}\n\n"
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


def test_shell_v2_worker_records_real_sse_timing(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import ShellV2Worker

    def fake_urlopen(request, timeout=0):
        assert request.full_url.endswith("/api/say-stream")
        assert timeout == 3
        return _FakeSSEResponse(["Hel", "lo"], delay_s=0.001)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(ShellV2Worker, "SHELL_V2_URL", "http://127.0.0.1:8765")
    monkeypatch.setattr(ShellV2Worker, "TIMEOUT_S", 3)

    worker = ShellV2Worker("hello")
    chunks: list[str] = []
    replies: list[str] = []
    done: list[bool] = []
    errors: list[str] = []
    events: list[tuple[str, dict]] = []

    worker.chunk_received.connect(chunks.append)
    worker.reply_ready.connect(replies.append)
    worker.stream_done.connect(lambda: done.append(True))
    worker.reply_error.connect(errors.append)
    worker.latency_event.connect(lambda event, payload: events.append((event, dict(payload))))

    worker.run()

    assert chunks == ["Hel", "lo"]
    assert replies == ["Hello"]
    assert done == [True]
    assert errors == []

    event_names = [event for event, _payload in events]
    for required in (
        "request_prepared",
        "stream_connect_start",
        "stream_headers",
        "first_sse_line",
        "first_sse_frame",
        "first_text_chunk",
        "stream_done",
    ):
        assert required in event_names

    first_chunk = next(payload for event, payload in events if event == "first_text_chunk")
    stream_done = next(payload for event, payload in events if event == "stream_done")

    assert first_chunk["elapsed_ms"] >= 0
    assert first_chunk["chars"] == 3
    assert first_chunk["chunks"] == 1
    assert first_chunk["sse_frames"] >= 1
    assert first_chunk["bytes"] > 0
    assert first_chunk["server_elapsed_ms"] == 1.2
    assert stream_done["chunks"] == 2
    assert stream_done["chars"] == 5
    assert stream_done["sse_frames"] >= 3
    assert stream_done["server_elapsed_ms"] == 2.4
    assert stream_done["server_metrics"]["chunks"] == 2
    assert stream_done["provider_metrics"]["selected_provider"] == "fake"
    assert stream_done["elapsed_ms"] >= first_chunk["elapsed_ms"]


def test_shell_v2_worker_cancels_stream_on_interruption(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import ShellV2Worker

    def fake_urlopen(request, timeout=0):
        assert request.full_url.endswith("/api/say-stream")
        return _FakeSSEResponse(["A", "B", "C"], delay_s=0.001)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(ShellV2Worker, "SHELL_V2_URL", "http://127.0.0.1:8765")
    monkeypatch.setattr(ShellV2Worker, "TIMEOUT_S", 3)

    worker = ShellV2Worker("hello")
    chunks: list[str] = []
    replies: list[str] = []
    done: list[bool] = []
    errors: list[str] = []
    events: list[tuple[str, dict]] = []

    def _on_chunk(chunk: str) -> None:
        chunks.append(chunk)
        worker.requestInterruption()

    worker.chunk_received.connect(_on_chunk)
    worker.reply_ready.connect(replies.append)
    worker.stream_done.connect(lambda: done.append(True))
    worker.reply_error.connect(errors.append)
    worker.latency_event.connect(lambda event, payload: events.append((event, dict(payload))))

    worker.run()

    assert chunks == ["A"]
    assert replies == []
    assert done == []
    assert errors == []

    cancelled = next(payload for event, payload in events if event == "stream_cancelled")
    assert cancelled["chunks"] == 1
    assert cancelled["chars"] == 1
