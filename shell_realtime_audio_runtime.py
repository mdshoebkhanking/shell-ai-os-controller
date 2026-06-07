"""
Lightweight realtime network audio runtime.

The desktop UI owns visual state. This module owns the optional LiveKit audio
bridge and keeps realtime networking, provider clients, and numpy processing
off the non-realtime startup path.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path

from shell_async_signals import WorkerThread
from shell_async_signals import signal as runtime_signal


logger = logging.getLogger("shell.realtime_audio")
LIVEKIT_AVAILABLE = importlib.util.find_spec("livekit") is not None
_PROJECT_ROOT = Path(__file__).resolve().parent


def _hub_base_url_candidates(default_url: str = "http://localhost:5000") -> list[str]:
    candidates: list[str] = []
    env_url = str(os.environ.get("SHELL_HUB_URL", "")).strip()
    if env_url:
        candidates.append(env_url.rstrip("/"))
    try:
        hint = _PROJECT_ROOT / ".shell_hub_port"
        if hint.exists():
            txt = hint.read_text(encoding="utf-8").strip()
            if txt.isdigit():
                candidates.append(f"http://127.0.0.1:{int(txt)}")
    except Exception as exc:
        logger.debug("hub port hint read failed: %s", exc)
    candidates.append(default_url.rstrip("/"))
    for port in (5000, 5001, 5002, 5003):
        candidates.append(f"http://127.0.0.1:{port}")
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        normalized = candidate.strip().rstrip("/")
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _resolve_hub_base_url(default_url: str = "http://localhost:5000") -> str:
    return _hub_base_url_candidates(default_url)[0]


def _resolve_token_url() -> str:
    env = str(os.environ.get("SHELL_TOKEN_URL", "")).strip()
    return env if env else f"{_resolve_hub_base_url()}/token"


def _hub_auth_token() -> str:
    return (os.environ.get("SHELL_HUB_TOKEN") or os.environ.get("SHELL_API_TOKEN") or "").strip()


def _hub_auth_headers(extra=None) -> dict[str, str]:
    headers = dict(extra or {})
    token = _hub_auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


class LiveKitAudioClient(WorkerThread):
    """Optional LiveKit audio bridge for realtime voice amplitude updates."""

    audio_amplitude = runtime_signal(float)

    def __init__(self, token_url=None, *, token_url_resolver=None, auth_headers_factory=None):
        super().__init__()
        self._dyn = token_url is None
        self._token_url_resolver = token_url_resolver or _resolve_token_url
        self._auth_headers_factory = auth_headers_factory or _hub_auth_headers
        self.token_url = token_url or self._token_url_resolver()
        self.running = True
        self._loop = None
        self._audio_tasks = set()

    @staticmethod
    def _load_realtime_modules():
        try:
            import aiohttp
        except Exception as exc:
            return None, None, None, f"aiohttp unavailable: {exc}"
        try:
            import numpy as np
        except Exception as exc:
            return None, None, None, f"numpy unavailable: {exc}"
        try:
            from livekit import rtc
        except Exception as exc:
            return None, None, None, f"livekit.rtc unavailable: {exc}"
        return aiohttp, np, rtc, ""

    def _track_audio_task(self, task):
        self._audio_tasks.add(task)
        task.add_done_callback(self._audio_tasks.discard)
        return task

    async def _cancel_audio_tasks(self, asyncio_module):
        tasks = [task for task in list(self._audio_tasks) if not task.done()]
        if not tasks:
            self._audio_tasks.clear()
            return
        for task in tasks:
            task.cancel()
        await asyncio_module.gather(*tasks, return_exceptions=True)
        self._audio_tasks.clear()

    async def _run(self, asyncio_module):
        aiohttp, np, rtc, error = self._load_realtime_modules()
        if error:
            logger.info("LiveKit audio bridge disabled: %s", error)
            return

        while self.running:
            room = None
            try:
                if self._dyn:
                    self.token_url = self._token_url_resolver()
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.token_url,
                        headers=self._auth_headers_factory(),
                    ) as response:
                        if response.status != 200:
                            await asyncio_module.sleep(1.5)
                            continue
                        data = await response.json()
                        token = data["token"]
                        url = data.get("url", "wss://sell-ejcqoa9w.livekit.cloud")

                room = rtc.Room()
                await room.connect(url, token)

                @room.on("track_subscribed")
                def _sub(track, pub, part):
                    if track.kind == rtc.TrackKind.KIND_AUDIO:
                        self._track_audio_task(
                            asyncio_module.create_task(self._audio(track, rtc, np))
                        )

                for participant in room.remote_participants.values():
                    for pub in participant.track_publications.values():
                        if pub.track and pub.track.kind == rtc.TrackKind.KIND_AUDIO:
                            self._track_audio_task(
                                asyncio_module.create_task(self._audio(pub.track, rtc, np))
                            )

                while self.running:
                    await asyncio_module.sleep(0.1)
            except asyncio_module.CancelledError:
                raise
            except Exception as exc:
                logger.debug("LiveKit audio loop failed: %s", exc)
                await asyncio_module.sleep(1.5)
            finally:
                await self._cancel_audio_tasks(asyncio_module)
                if room:
                    try:
                        await room.disconnect()
                    except Exception as exc:
                        logger.debug("LiveKit room disconnect failed: %s", exc)

    async def _audio(self, track, rtc, np):
        stream = rtc.AudioStream(track)
        async for frame in stream:
            if not self.running:
                break
            samples = np.frombuffer(frame.data, dtype=np.int16)
            self.audio_amplitude.emit(float(np.abs(samples).mean() / 32768.0))

    def run(self):
        if not LIVEKIT_AVAILABLE:
            return
        import asyncio

        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run(asyncio))
        finally:
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            if pending:
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            self._loop = None

    def stop(self):
        self.running = False
        loop = getattr(self, "_loop", None)
        if loop is not None and loop.is_running():
            try:
                loop.call_soon_threadsafe(lambda: None)
            except Exception as exc:
                logger.debug("LiveKit wake on stop failed: %s", exc)


__all__ = [
    "LIVEKIT_AVAILABLE",
    "LiveKitAudioClient",
    "_hub_auth_headers",
    "_resolve_token_url",
]
