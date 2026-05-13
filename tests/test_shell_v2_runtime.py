from __future__ import annotations

import json

import pytest

from shell_v2_runtime import encode_sse_event, iter_shell_v2_events


class _FakeBrain:
    async def generate_response_stream(self, prompt: str, mode: str = "FAST"):
        assert prompt == "hello"
        assert mode == "FAST"
        yield "Hel"
        yield "lo"

    def get_last_stream_metrics(self):
        return {
            "selected_provider": "fake",
            "first_token_ms": 1.5,
            "completion_ms": 2.5,
            "chunks": 2,
        }


@pytest.mark.asyncio
async def test_shell_v2_events_include_server_and_provider_metrics() -> None:
    events = [
        (event, payload)
        async for event, payload in iter_shell_v2_events(
            "hello",
            brain_factory=_FakeBrain,
            provider="",
            mode="FAST",
        )
    ]

    assert [event for event, _payload in events] == ["delta", "delta", "end"]
    assert events[0][1]["text"] == "Hel"
    assert events[0][1]["chunk_index"] == 1
    assert events[0][1]["server_elapsed_ms"] >= 0
    assert events[1][1]["text"] == "lo"

    end_payload = events[-1][1]
    assert end_payload["full_reply"] == "Hello"
    assert end_payload["chunks"] == 2
    assert end_payload["server_metrics"]["chunks"] == 2
    assert end_payload["server_metrics"]["first_delta_ms"] >= 0
    assert end_payload["provider_metrics"]["selected_provider"] == "fake"


@pytest.mark.asyncio
async def test_shell_v2_events_reports_empty_prompt_error() -> None:
    events = [(event, payload) async for event, payload in iter_shell_v2_events("   ", brain_factory=_FakeBrain)]

    assert events == [
        (
            "error",
            {
                "message": "empty message",
                "server_elapsed_ms": events[0][1]["server_elapsed_ms"],
            },
        )
    ]
    assert events[0][1]["server_elapsed_ms"] >= 0


def test_encode_sse_event_is_compact_valid_json_frame() -> None:
    frame = encode_sse_event("delta", {"text": "Hi", "chunk_index": 1})

    assert frame.startswith(b"event: delta\n")
    assert frame.endswith(b"\n\n")
    data_line = next(line for line in frame.decode("utf-8").splitlines() if line.startswith("data: "))
    assert json.loads(data_line[len("data: "):]) == {"text": "Hi", "chunk_index": 1}
