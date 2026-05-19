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


def test_shell_v2_default_brain_factory_uses_singleton(monkeypatch) -> None:
    import shell_v2_runtime

    class FakeBrain:
        pass

    calls = []
    monkeypatch.setattr(
        "brain.core.MultiAIBrain.get_instance",
        staticmethod(lambda: calls.append(1) or FakeBrain()),
    )

    assert isinstance(shell_v2_runtime._default_brain_factory(), FakeBrain)
    assert calls == [1]


def test_shell_v2_runtime_reuses_provider_transport_within_session() -> None:
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

    created = []

    class FakeBrain:
        async def generate_response_stream(self, prompt: str, mode: str = "FAST"):
            from brain.provider_transport import get_aiohttp_session

            await get_aiohttp_session("shell_v2_probe", timeout_s=5)
            yield prompt

        def get_last_stream_metrics(self):
            return {"selected_provider": "fake"}

    set_session_factory_for_tests(lambda owner, timeout_s: created.append(FakeSession()) or created[-1])
    runtime = ShellV2Runtime(brain_factory=FakeBrain)
    try:
        assert [event for event, _payload in runtime.stream_events("one")] == ["delta", "end"]
        assert [event for event, _payload in runtime.stream_events("two")] == ["delta", "end"]
        stats = provider_transport_stats()
        sessions = [item for item in stats["sessions"] if item["owner"] == "shell_v2_probe"]
        assert len(sessions) == 1
        assert sessions[0]["uses"] == 2
        assert len(created) == 1
    finally:
        closed = runtime.close()
        set_session_factory_for_tests(None)
        asyncio.run(close_aiohttp_sessions())

    assert closed == 1


def test_shell_v2_ui_autostart_only_for_default_local_endpoint(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import ShellHoloUI, ShellV2Worker

    old_url = ShellV2Worker.SHELL_V2_URL
    try:
        ShellV2Worker.SHELL_V2_URL = "http://127.0.0.1:8765"
        assert ShellHoloUI._shell_v2_local_endpoint() == ("127.0.0.1", 8765)

        ShellV2Worker.SHELL_V2_URL = "http://127.0.0.1:8766"
        assert ShellHoloUI._shell_v2_local_endpoint() is None

        ShellV2Worker.SHELL_V2_URL = "https://example.com"
        assert ShellHoloUI._shell_v2_local_endpoint() is None
    finally:
        ShellV2Worker.SHELL_V2_URL = old_url


def test_shell_v2_autostart_respects_disable_env(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SHELL_V2_AUTOSTART", "0")

    from shell_ui.shell_cinematic_full import ShellHoloUI

    assert ShellHoloUI._shell_v2_autostart_enabled() is False
