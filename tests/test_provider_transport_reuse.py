from __future__ import annotations

import asyncio
import os
import sys


class FakeResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return '{"choices":[{"message":{"content":"ok"}}]}'

    async def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


class FakeSession:
    def __init__(self, owner: str, timeout_s: float):
        self.owner = owner
        self.timeout_s = timeout_s
        self.closed = False
        self.posts = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeResponse()

    async def close(self):
        self.closed = True


def test_provider_transport_reuses_and_closes_session() -> None:
    from brain.provider_transport import (
        close_aiohttp_sessions,
        get_aiohttp_session,
        provider_transport_stats,
        set_session_factory_for_tests,
    )

    created: list[FakeSession] = []

    async def scenario():
        set_session_factory_for_tests(lambda owner, timeout_s: created.append(FakeSession(owner, timeout_s)) or created[-1])
        try:
            first = await get_aiohttp_session("groq", timeout_s=12)
            second = await get_aiohttp_session("groq", timeout_s=12)
            assert first is second
            assert len(created) == 1
            stats = provider_transport_stats()
            assert stats["session_count"] == 1
            assert stats["sessions"][0]["owner"] == "groq"
            assert stats["sessions"][0]["uses"] == 2
            closed = await close_aiohttp_sessions()
            assert closed == 1
            assert created[0].closed is True
            assert provider_transport_stats()["session_count"] == 0
        finally:
            set_session_factory_for_tests(None)
            await close_aiohttp_sessions()

    asyncio.run(scenario())


def test_groq_provider_reuses_transport_without_importing_aiohttp(monkeypatch) -> None:
    from brain.provider_transport import (
        close_aiohttp_sessions,
        provider_transport_stats,
        set_session_factory_for_tests,
    )
    from brain.providers.groq_p import GroqProvider

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    sys.modules.pop("aiohttp", None)
    created: list[FakeSession] = []

    async def scenario():
        set_session_factory_for_tests(lambda owner, timeout_s: created.append(FakeSession(owner, timeout_s)) or created[-1])
        try:
            provider = GroqProvider()
            first = await provider.generate_response_async([{"role": "user", "content": "hi"}])
            second = await provider.generate_response_async([{"role": "user", "content": "again"}])
            assert first == "ok"
            assert second == "ok"
            assert len(created) == 1
            assert len(created[0].posts) == 2
            assert provider_transport_stats()["sessions"][0]["uses"] == 2
            assert "aiohttp" not in sys.modules
            await close_aiohttp_sessions()
            assert created[0].closed is True
        finally:
            set_session_factory_for_tests(None)
            await close_aiohttp_sessions()

    asyncio.run(scenario())


def test_missing_provider_key_does_not_create_transport(monkeypatch) -> None:
    from brain.provider_transport import (
        close_aiohttp_sessions,
        provider_transport_stats,
        set_session_factory_for_tests,
    )
    from brain.providers.groq_p import GroqProvider

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    sys.modules.pop("aiohttp", None)
    created: list[FakeSession] = []

    async def scenario():
        set_session_factory_for_tests(lambda owner, timeout_s: created.append(FakeSession(owner, timeout_s)) or created[-1])
        try:
            provider = GroqProvider()
            try:
                await provider.generate_response_async([{"role": "user", "content": "hi"}])
            except Exception as exc:
                assert "Groq API Key missing" in str(exc)
            else:
                raise AssertionError("expected missing-key failure")
            assert created == []
            assert provider_transport_stats()["session_count"] == 0
            assert "aiohttp" not in sys.modules
        finally:
            set_session_factory_for_tests(None)
            await close_aiohttp_sessions()

    asyncio.run(scenario())
