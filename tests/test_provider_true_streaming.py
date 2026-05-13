from __future__ import annotations

import asyncio
import sys


class FakeStreamContent:
    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def __aiter__(self):
        self._iter = iter(self._lines)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class FakeStreamResponse:
    status = 200

    def __init__(self):
        self.content = FakeStreamContent([
            b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n',
            b'data: {"choices":[{"delta":{"content":"lo"}}]}\n',
            b"data: [DONE]\n",
        ])

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return ""


class FakeStreamSession:
    closed = False

    def __init__(self):
        self.posts = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeStreamResponse()

    async def close(self):
        self.closed = True


def test_groq_provider_streams_sse_chunks_without_importing_aiohttp(monkeypatch) -> None:
    from brain.provider_transport import close_aiohttp_sessions, set_session_factory_for_tests
    from brain.providers.groq_p import GroqProvider

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    sys.modules.pop("aiohttp", None)
    created: list[FakeStreamSession] = []

    async def scenario():
        set_session_factory_for_tests(lambda owner, timeout_s: created.append(FakeStreamSession()) or created[-1])
        try:
            provider = GroqProvider()
            chunks = []
            async for chunk in provider.generate_response_stream_async([{"role": "user", "content": "hi"}]):
                chunks.append(chunk)
            assert chunks == ["Hel", "lo"]
            assert provider.supports_streaming() is True
            assert len(created) == 1
            assert created[0].posts[0][1]["json"]["stream"] is True
            assert "aiohttp" not in sys.modules
        finally:
            set_session_factory_for_tests(None)
            await close_aiohttp_sessions()

    asyncio.run(scenario())


def test_lazy_provider_proxy_delegates_true_streaming(monkeypatch) -> None:
    from brain.provider_runtime import ProviderSpec, LazyProviderProxy

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    spec = ProviderSpec("groq", "brain.providers.groq_p", "GroqProvider")
    proxy = LazyProviderProxy(spec)

    assert proxy.loaded is False
    assert proxy.supports_streaming() is True
    assert proxy.loaded is True
