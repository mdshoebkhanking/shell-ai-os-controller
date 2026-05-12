from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time


def test_realtime_runtime_import_stays_lightweight() -> None:
    code = (
        "import json, sys; "
        "import shell_realtime_audio_runtime; "
        "print(json.dumps({"
        "'ui_loaded': 'shell_ui.shell_cinematic_full' in sys.modules, "
        "'aiohttp_loaded': 'aiohttp' in sys.modules, "
        "'numpy_loaded': 'numpy' in sys.modules, "
        "'livekit_rtc_loaded': 'livekit.rtc' in sys.modules"
        "}))"
    )

    proc = subprocess.run(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr[-1200:]
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data == {
        "ui_loaded": False,
        "aiohttp_loaded": False,
        "numpy_loaded": False,
        "livekit_rtc_loaded": False,
    }


def test_ui_reexports_realtime_audio_client() -> None:
    from shell_realtime_audio_runtime import LiveKitAudioClient as RuntimeLiveKitAudioClient
    from shell_ui.shell_cinematic_full import LiveKitAudioClient as UiLiveKitAudioClient

    assert UiLiveKitAudioClient is RuntimeLiveKitAudioClient


def test_realtime_audio_client_thread_stops_cleanly(monkeypatch) -> None:
    import shell_realtime_audio_runtime as realtime
    from shell_realtime_audio_runtime import LiveKitAudioClient

    monkeypatch.setattr(realtime, "LIVEKIT_AVAILABLE", True)
    started = []
    client = LiveKitAudioClient(token_url="http://127.0.0.1/token")

    async def fake_run(asyncio_module):
        started.append(True)
        while client.running:
            await asyncio_module.sleep(0.01)

    monkeypatch.setattr(client, "_run", fake_run)

    client.start()
    deadline = time.time() + 0.5
    while time.time() < deadline and not started:
        time.sleep(0.01)
    client.stop()
    client.wait(1000)

    assert started
    assert not client.isRunning()


def test_realtime_audio_client_cancels_tracked_tasks() -> None:
    from shell_realtime_audio_runtime import LiveKitAudioClient

    async def run_probe():
        client = LiveKitAudioClient(token_url="http://127.0.0.1/token")
        task = asyncio.create_task(asyncio.sleep(30))
        client._track_audio_task(task)
        await client._cancel_audio_tasks(asyncio)
        assert task.cancelled()
        assert client._audio_tasks == set()

    asyncio.run(run_probe())
