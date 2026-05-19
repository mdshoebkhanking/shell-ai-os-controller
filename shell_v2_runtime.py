from __future__ import annotations

import asyncio
import json
import queue
import socket
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, AsyncIterator, Callable, Iterator


BrainFactory = Callable[[], Any]


def encode_sse_event(event: str, payload: dict[str, Any]) -> bytes:
    """Encode one Server-Sent Events frame with compact JSON payload."""
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n".encode("utf-8")


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 3)


def _set_tcp_nodelay(sock: socket.socket) -> bool:
    """Prefer immediate delivery for local realtime SSE frames."""
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return True
    except OSError:
        return False


def _default_brain_factory() -> Any:
    from brain.core import MultiAIBrain

    return MultiAIBrain.get_instance()


async def iter_shell_v2_events(
    text: str,
    *,
    mode: str = "FAST",
    agent: str = "",
    provider: str = "",
    brain_factory: BrainFactory | None = None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Yield Shell-v2 compatible stream events for one user message.

    Heavy AI modules load only when this function is actually executed. Tests
    can inject a tiny brain factory so the HTTP/SSE layer stays deterministic.
    """
    started = time.perf_counter()
    prompt = (text or "").strip()
    if not prompt:
        yield "error", {
            "message": "empty message",
            "server_elapsed_ms": _elapsed_ms(started),
        }
        return

    brain_factory = brain_factory or _default_brain_factory
    router_cls = None
    original_sequence = None
    original_model = None
    if provider:
        from brain.router import SmartRouter

        router_cls = SmartRouter
        original_sequence = SmartRouter.get_provider_sequence
        original_model = SmartRouter.get_model_for_provider
        SmartRouter.get_provider_sequence = staticmethod(lambda selected_mode="SMART": [provider])

    chunks: list[str] = []
    chunk_count = 0
    first_delta_ms: float | None = None
    try:
        brain = brain_factory()
        stream = brain.generate_response_stream(prompt, mode=mode)
        async for raw_chunk in stream:
            chunk = str(raw_chunk or "")
            if not chunk:
                continue
            chunk_count += 1
            chunks.append(chunk)
            now_ms = _elapsed_ms(started)
            if first_delta_ms is None:
                first_delta_ms = now_ms
            yield "delta", {
                "text": chunk,
                "chunk_index": chunk_count,
                "server_elapsed_ms": now_ms,
                "agent": agent,
            }

        full_reply = "".join(chunks)
        if not full_reply.strip():
            yield "error", {
                "message": "empty provider response",
                "server_elapsed_ms": _elapsed_ms(started),
            }
            return

        provider_metrics = {}
        get_metrics = getattr(brain, "get_last_stream_metrics", None)
        if callable(get_metrics):
            try:
                provider_metrics = dict(get_metrics() or {})
            except Exception:
                provider_metrics = {}

        done_ms = _elapsed_ms(started)
        yield "end", {
            "full_reply": full_reply,
            "chunks": chunk_count,
            "server_elapsed_ms": done_ms,
            "server_metrics": {
                "mode": mode,
                "provider": provider,
                "agent": agent,
                "first_delta_ms": first_delta_ms,
                "completion_ms": done_ms,
                "chunks": chunk_count,
            },
            "provider_metrics": provider_metrics,
        }
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        yield "error", {
            "message": str(exc)[:240],
            "server_elapsed_ms": _elapsed_ms(started),
        }
    finally:
        if router_cls is not None and original_sequence is not None:
            router_cls.get_provider_sequence = original_sequence
        if router_cls is not None and original_model is not None:
            router_cls.get_model_for_provider = original_model


async def collect_shell_v2_reply(
    text: str,
    *,
    mode: str = "FAST",
    agent: str = "",
    provider: str = "",
    brain_factory: BrainFactory | None = None,
) -> dict[str, Any]:
    full_reply = ""
    final_payload: dict[str, Any] = {}
    async for event, payload in iter_shell_v2_events(
        text,
        mode=mode,
        agent=agent,
        provider=provider,
        brain_factory=brain_factory,
    ):
        if event == "delta":
            full_reply += str(payload.get("text") or "")
        elif event == "end":
            final_payload = payload
            full_reply = str(payload.get("full_reply") or full_reply)
        elif event == "error":
            return {"ok": False, "error": payload.get("message") or "stream error", "metrics": payload}
    return {
        "ok": bool(full_reply.strip()),
        "reply": full_reply,
        "metrics": final_payload.get("server_metrics", {}),
        "provider_metrics": final_payload.get("provider_metrics", {}),
    }


class ShellV2Runtime:
    """Owns the async runtime used by the local Shell-v2 bridge."""

    def __init__(self, *, brain_factory: BrainFactory | None = None, provider: str = "", mode: str = "FAST") -> None:
        self._brain_factory = brain_factory
        self._provider = provider
        self._mode = mode
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="shell-v2-runtime", daemon=True)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stream_events(self, text: str, *, agent: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
        if not self._started:
            self.start()

        out: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue()

        async def produce() -> None:
            async for event, payload in iter_shell_v2_events(
                text,
                mode=self._mode,
                agent=agent,
                provider=self._provider,
                brain_factory=self._brain_factory,
            ):
                out.put((event, payload))
            out.put(None)

        future = asyncio.run_coroutine_threadsafe(produce(), self._loop)
        try:
            while True:
                try:
                    item = out.get(timeout=0.1)
                except queue.Empty:
                    if future.done():
                        future.result()
                        break
                    continue
                if item is None:
                    future.result()
                    break
                yield item
        finally:
            if not future.done():
                future.cancel()

    def collect_reply(self, text: str, *, agent: str = "") -> dict[str, Any]:
        if not self._started:
            self.start()
        future = asyncio.run_coroutine_threadsafe(
            collect_shell_v2_reply(
                text,
                mode=self._mode,
                agent=agent,
                provider=self._provider,
                brain_factory=self._brain_factory,
            ),
            self._loop,
        )
        return future.result(timeout=60)

    def close(self) -> int:
        if not self._started:
            return 0

        async def cleanup() -> int:
            closed_sessions = 0
            try:
                from brain.provider_transport import close_aiohttp_sessions

                closed_sessions = await close_aiohttp_sessions()
            except Exception:
                closed_sessions = 0
            try:
                await self._loop.shutdown_asyncgens()
            except Exception:
                pass
            try:
                await self._loop.shutdown_default_executor()
            except Exception:
                pass
            return int(closed_sessions or 0)

        closed = 0
        try:
            closed = asyncio.run_coroutine_threadsafe(cleanup(), self._loop).result(timeout=5)
        except Exception:
            closed = 0
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()
        self._started = False
        return int(closed or 0)


class _ShellV2HTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, runtime: ShellV2Runtime):
        super().__init__(server_address, RequestHandlerClass)
        self.runtime = runtime

    def server_bind(self) -> None:
        _set_tcp_nodelay(self.socket)
        super().server_bind()


class ShellV2BridgeHandler(BaseHTTPRequestHandler):
    server: _ShellV2HTTPServer

    def setup(self) -> None:
        super().setup()
        _set_tcp_nodelay(self.connection)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._write_json(200, {"ok": True, "service": "shell-v2-runtime"})
            return
        self._write_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        try:
            body = self._read_json_body()
        except Exception as exc:
            self._write_json(400, {"ok": False, "error": f"invalid json: {exc}"})
            return

        text = str(body.get("text") or "")
        agent = str(body.get("agent") or "")
        if self.path.rstrip("/") == "/api/say-stream":
            self._write_sse(text, agent=agent)
            return
        if self.path.rstrip("/") == "/api/say":
            self._write_json(200, self.server.runtime.collect_reply(text, agent=agent))
            return
        self._write_json(404, {"ok": False, "error": "not found"})

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("request body must be an object")
        return data

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _write_sse(self, text: str, *, agent: str = "") -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for event, payload in self.server.runtime.stream_events(text, agent=agent):
                self.wfile.write(encode_sse_event(event, payload))
                self.wfile.flush()
                if event in {"end", "error"}:
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.close_connection = True


@dataclass
class ShellV2BridgeServer:
    server: _ShellV2HTTPServer
    runtime: ShellV2Runtime
    thread: threading.Thread

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}"

    def close(self) -> int:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
        return self.runtime.close()


def start_shell_v2_bridge(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    brain_factory: BrainFactory | None = None,
    provider: str = "",
    mode: str = "FAST",
) -> ShellV2BridgeServer:
    runtime = ShellV2Runtime(brain_factory=brain_factory, provider=provider, mode=mode)
    runtime.start()
    server = _ShellV2HTTPServer((host, int(port)), ShellV2BridgeHandler, runtime)
    thread = threading.Thread(target=server.serve_forever, name="shell-v2-http", daemon=True)
    thread.start()
    return ShellV2BridgeServer(server=server, runtime=runtime, thread=thread)


__all__ = [
    "ShellV2BridgeServer",
    "ShellV2Runtime",
    "collect_shell_v2_reply",
    "encode_sse_event",
    "iter_shell_v2_events",
    "start_shell_v2_bridge",
]
