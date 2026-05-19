"""
Lightweight Shell voice runtime.

This module owns text-to-speech queueing, backend selection, playback helpers,
and latency events without importing the full desktop UI. The UI should treat it
as a service layer and keep visual state updates outside this runtime.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import re
import time as _time
from collections import deque

from PyQt6.QtCore import QThread, pyqtSignal


_EDGE_TTS_AVAILABLE = importlib.util.find_spec("edge_tts") is not None


def _system_tts_available() -> bool:
    try:
        import platform
        import shutil

        system = platform.system().lower()
        if system == "darwin":
            return shutil.which("say") is not None
        if system == "windows":
            return (
                importlib.util.find_spec("pyttsx3") is not None
                or shutil.which("powershell") is not None
                or shutil.which("powershell.exe") is not None
            )
        return any(shutil.which(name) for name in ("spd-say", "espeak-ng", "espeak"))
    except Exception:
        return False


_LOCAL_TTS_AVAILABLE = _EDGE_TTS_AVAILABLE or _system_tts_available()

_NEURAL_VOICES = {
    "aether": "en-US-AndrewMultilingualNeural",
    "andrew": "en-US-AndrewMultilingualNeural",
    "brian": "en-US-BrianMultilingualNeural",
    "aria": "en-US-AriaNeural",
    "guy": "en-US-GuyNeural",
    "prabhat": "en-IN-PrabhatNeural",
    "neerja": "en-IN-NeerjaNeural",
    "aoede": "en-IN-NeerjaNeural",
    "puck": "en-US-AndrewMultilingualNeural",
    "charon": "en-US-BrianMultilingualNeural",
    "kore": "en-US-AriaNeural",
    "fenrir": "en-US-GuyNeural",
}
_DEFAULT_VOICE = "en-US-AndrewMultilingualNeural"
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


class TTSSpeaker(QThread):
    """Background thread that speaks Shell replies through the selected backend."""

    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()
    latency_event = pyqtSignal(str, object)
    speech_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        import threading

        self._queue = deque()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._enabled = True
        self._rate = "+8%"
        self._volume = "+0%"
        self._running = True
        self._stop_requested = threading.Event()
        self._voice = _DEFAULT_VOICE
        self._engine = os.environ.get("SHELL_TTS_ENGINE", "fast").strip().lower() or "fast"
        self._current_process = None
        self._warmup_requested = False
        self._system_tts_command = None
        self._pyttsx3_engine = None
        self._pyttsx3_failed = False
        self._gemini_voice_name = "Aoede"
        self._last_error = ""
        self._speaking = False
        self._current_backend = ""
        self._current_voice_label = ""
        self._audio_output_probe_ok = None
        self._audio_output_probe_error = ""
        self._audio_output_probe_until = 0.0
        try:
            self._audio_output_probe_ttl_s = max(
                0.0, min(300.0, float(os.environ.get("SHELL_AUDIO_PROBE_TTL_S", "60")))
            )
        except Exception:
            self._audio_output_probe_ttl_s = 60.0
        self._temp_dir = os.path.join(os.environ.get("TEMP", "/tmp"), "shell_tts")
        os.makedirs(self._temp_dir, exist_ok=True)

    def _voice_mode(self):
        """Return cloud/local/auto from env or persisted UI settings."""
        raw = os.environ.get("SHELL_VOICE_MODE")
        if not raw:
            try:
                import json

                cfg_path = os.path.join(_PROJECT_ROOT, ".shell_settings.json")
                if os.path.exists(cfg_path):
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        raw = (json.load(f) or {}).get("voice_mode")
            except Exception as exc:
                logging.debug("voice mode read failed: %s", exc)
        mode = str(raw or "cloud").strip().lower()
        return mode if mode in {"cloud", "local", "auto"} else "cloud"

    def _latency_mode(self):
        """Return instant/balanced/quality for voice startup tradeoffs."""
        raw = os.environ.get("SHELL_TTS_LATENCY_MODE", "instant")
        mode = str(raw or "instant").strip().lower()
        return mode if mode in {"instant", "balanced", "quality"} else "instant"

    @staticmethod
    def _truthy_env(name, default="0"):
        return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}

    def set_enabled(self, on):
        self._enabled = on

    @staticmethod
    def _edge_relative_percent(value, *, neutral=100, min_delta=-100, max_delta=100):
        """Convert UI slider percentages into edge-tts relative percentages."""
        if isinstance(value, str):
            raw = value.strip()
            if raw.endswith("%") and raw[:1] in ("+", "-"):
                return raw
            try:
                value = float(raw.rstrip("%"))
            except Exception:
                return "+0%"
        try:
            delta = int(round(float(value) - neutral))
        except Exception:
            delta = 0
        delta = max(min_delta, min(max_delta, delta))
        return f"{delta:+d}%"

    def set_rate(self, rate_pct):
        self._rate = self._edge_relative_percent(
            rate_pct, neutral=100, min_delta=-90, max_delta=100
        )

    def set_volume(self, vol_pct):
        self._volume = self._edge_relative_percent(
            vol_pct, neutral=100, min_delta=-100, max_delta=100
        )

    def set_voice(self, voice_name):
        """Set voice by name or full voice ID."""
        cleaned = str(voice_name or "").split("·", 1)[0].strip()
        if cleaned:
            self._gemini_voice_name = cleaned
        key = cleaned.lower()
        if key in _NEURAL_VOICES:
            self._voice = _NEURAL_VOICES[key]
        elif voice_name:
            self._voice = voice_name

    def speak(self, text, force=False):
        """Queue text to speak."""
        if not force and not self._enabled:
            return
        queued_at = _time.perf_counter()
        clean = re.sub(r"```[\s\S]*?```", "", text)
        clean = re.sub(r"`[^`]*`", "", clean)
        clean = re.sub(r"[*_~>#\-\[\]()]", "", clean)
        clean = re.sub(r"\n{2,}", ". ", clean)
        clean = re.sub(r"\n", " ", clean)
        clean = clean.strip()
        if clean:
            with self._lock:
                self._queue.append((clean, queued_at))
            self._wake.set()
            self._emit_latency("queued", queued_at, chars=len(clean), force=bool(force))

    def warmup(self):
        """Wake the TTS thread and cache the chosen local speech path."""
        self._warmup_requested = True
        self._wake.set()

    def stop_speaking(self):
        """Clear queue and stop current speech."""
        self._stop_requested.set()
        with self._lock:
            self._queue.clear()
        try:
            if self._pyttsx3_engine is not None:
                self._pyttsx3_engine.stop()
        except Exception:
            pass
        proc = getattr(self, "_current_process", None)
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

    def is_speaking(self):
        return bool(self._speaking or getattr(self, "_current_process", None) is not None)

    def shutdown(self):
        self._running = False
        with self._lock:
            self._queue.clear()
        self._wake.set()
        self.stop_speaking()

    def _emit_latency(self, event, started, **payload):
        try:
            payload["ts"] = round(_time.perf_counter(), 6)
            payload["elapsed_ms"] = round((_time.perf_counter() - started) * 1000.0, 2)
            payload["engine"] = self._engine
            payload.setdefault("configured_engine", self._engine)
            payload.setdefault("voice_mode", self._voice_mode())
            payload.setdefault("gemini_voice", self._gemini_voice_identity())
            payload.setdefault("openai_voice", self._openai_tts_voice())
            payload.setdefault("persona", self._voice_persona_identity())
            payload.setdefault("premium_voice_first", self._premium_voice_first())
            payload.setdefault("cloud_fallback_allowed", self._cloud_fallback_allowed())
            payload.setdefault("active_backend", getattr(self, "_current_backend", ""))
            payload.setdefault("active_voice", getattr(self, "_current_voice_label", ""))
            self.latency_event.emit(str(event), payload)
        except Exception:
            pass

    def _emit_voice_event(self, event, started=None, **payload):
        self._emit_latency(event, started or _time.perf_counter(), **payload)

    def _mark_tts_backend(self, backend, voice="", premium=False, started=None, **payload):
        self._current_backend = str(backend or "")
        self._current_voice_label = str(voice or "")
        payload.setdefault("backend", self._current_backend)
        payload.setdefault("voice", self._current_voice_label)
        payload.setdefault("premium_voice", bool(premium))
        self._emit_voice_event("tts_backend_selected", started, **payload)

    def voice_identity_snapshot(self):
        return {
            "configured_engine": self._engine,
            "voice_mode": self._voice_mode(),
            "gemini_voice": self._gemini_voice_identity(),
            "openai_voice": self._openai_tts_voice(),
            "persona": self._voice_persona_identity(),
            "premium_voice_first": self._premium_voice_first(),
            "cloud_fallback_allowed": self._cloud_fallback_allowed(),
        }

    def _gemini_voice_identity(self):
        try:
            from shell_voice import resolve_voice

            return str(resolve_voice(self._gemini_voice_name))
        except Exception:
            return str(self._gemini_voice_name or "Aoede")

    def _voice_persona_identity(self):
        try:
            from shell_voice import resolve_persona

            return str(resolve_persona(os.environ.get("VOICE_PERSONA")).name)
        except Exception:
            return str(os.environ.get("VOICE_PERSONA") or "Hinglish")

    def _cloud_fallback_allowed(self):
        return self._truthy_env("SHELL_CLOUD_TTS_LOCAL_FALLBACK")

    def _premium_voice_first(self):
        return self._truthy_env("SHELL_TTS_PREMIUM_FIRST", "1")

    def run(self):
        while self._running:
            item = None
            with self._lock:
                if self._queue:
                    item = self._queue.popleft()
            if item:
                text, queued_at = item
                self._emit_latency("dequeued", queued_at, chars=len(text))
                self.speaking_started.emit()
                try:
                    speak_started = _time.perf_counter()
                    self._stop_requested.clear()
                    self._speaking = True
                    ok = self._do_speak(text)
                    self._emit_latency("finished", speak_started, chars=len(text))
                    if not ok:
                        self.speech_error.emit(
                            self._last_error or "No usable audio output device was found."
                        )
                except Exception as e:
                    logging.warning("TTS error: %s", e)
                    self.speech_error.emit(str(e))
                finally:
                    self._speaking = False
                self.speaking_finished.emit()
            else:
                if self._warmup_requested:
                    self._warmup_requested = False
                    started = _time.perf_counter()
                    self._system_tts_command = self._detect_system_tts_command()
                    if self._system_tts_command == "pyttsx3":
                        self._prepare_pyttsx3()
                    elif self._system_tts_command in {"say", "afplay"}:
                        self._mac_audio_output_available(force=True)
                    self._emit_latency("warmup", started)
                self._wake.wait(0.02)
                self._wake.clear()

    def _do_speak(self, text):
        """Speak with the selected backend."""
        self._last_error = ""
        started = _time.perf_counter()
        try:
            max_chars = max(180, int(os.environ.get("SHELL_TTS_MAX_CHARS", "700")))
        except Exception:
            max_chars = 700
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        engine = self._engine
        voice_mode = self._voice_mode()
        latency_mode = self._latency_mode()
        premium_first = self._premium_voice_first()

        if engine in {"openai", "openai-stream", "openai-pcm", "pcm"}:
            return self._speak_openai_streaming_tts(text)

        if engine in {"gemini", "cloud"} or voice_mode == "cloud":
            if self._speak_gemini_tts(text):
                return True
            if self._stop_requested.is_set():
                return True
            if not self._cloud_fallback_allowed():
                self._emit_voice_event(
                    "tts_fallback_blocked",
                    started,
                    from_backend="gemini",
                    to_backend="system",
                    reason=self._last_error,
                    voice=self._gemini_voice_identity(),
                )
                return False
            self._emit_voice_event(
                "tts_fallback_activated",
                started,
                from_backend="gemini",
                to_backend="system",
                reason=self._last_error,
                voice=self._gemini_voice_identity(),
            )

        fast_start_cloud = (
            latency_mode == "instant"
            and not premium_first
            and engine in {"fast", "system", "auto"}
            and voice_mode == "auto"
            and self._gemini_tts_configured()
        )
        if fast_start_cloud and self._speak_system(text):
            return True

        if voice_mode == "auto" and premium_first and self._gemini_tts_configured():
            if self._speak_gemini_tts(text):
                return True
            if self._stop_requested.is_set():
                return True
            self._emit_voice_event(
                "tts_fallback_activated",
                started,
                from_backend="gemini",
                to_backend="system",
                reason=self._last_error,
                voice=self._gemini_voice_identity(),
            )

        if engine in {"pyttsx3", "sapi"} and self._speak_pyttsx3(text):
            return True

        if engine in {"fast", "system", "auto"} and self._speak_system(text):
            return True

        if _EDGE_TTS_AVAILABLE and engine in {"edge", "edge-tts", "auto"}:
            try:
                import asyncio
                import edge_tts as _edge_tts

                tmp_path = os.path.join(
                    self._temp_dir,
                    f"shell_voice_{id(self)}_{_time.monotonic_ns()}.mp3",
                )
                self._mark_tts_backend("edge_tts", self._voice, False, _time.perf_counter())
                loop = asyncio.new_event_loop()
                try:
                    comm = _edge_tts.Communicate(
                        text, self._voice, rate=self._rate, volume=self._volume
                    )
                    loop.run_until_complete(comm.save(tmp_path))
                finally:
                    loop.close()

                if os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 0:
                    played = self._play_audio_file(tmp_path)
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    if played:
                        return True
            except Exception as e:
                logging.warning("edge-tts failed: %s", e)

        return bool(self._speak_system(text))

    def _gemini_tts_configured(self):
        key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
        if not key or key.lower() in {"your_google_api_key_here", "your_gemini_api_key_here"}:
            return False
        return len(key) >= 20

    def _openai_tts_configured(self):
        key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if not key or key.lower() in {"your_openai_api_key_here", "sk-your-key-here"}:
            return False
        return len(key) >= 20

    @staticmethod
    def _openai_tts_voice():
        voice = str(os.environ.get("OPENAI_TTS_VOICE", "coral") or "coral").strip().lower()
        allowed = {
            "alloy", "ash", "ballad", "coral", "echo", "fable", "nova",
            "onyx", "sage", "shimmer", "verse", "marin", "cedar",
        }
        return voice if voice in allowed else "coral"

    def _speak_openai_streaming_tts(self, text):
        """Stream raw 24kHz PCM from OpenAI TTS directly to the local audio device."""
        if not self._openai_tts_configured():
            self._last_error = (
                "OpenAI streaming voice is selected, but OPENAI_API_KEY is missing or invalid."
            )
            return False
        try:
            import asyncio
            import numpy as np
            from openai import AsyncOpenAI
            from openai.helpers import LocalAudioPlayer
        except Exception as exc:
            self._last_error = f"OpenAI streaming voice dependencies unavailable: {exc}"
            return False

        started = _time.perf_counter()
        model = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
        voice = self._openai_tts_voice()
        instructions = os.environ.get(
            "OPENAI_TTS_INSTRUCTIONS",
            "Speak naturally, warmly, and conversationally with low latency.",
        )
        self._mark_tts_backend("openai_pcm", voice, True, started, model=model)
        try:
            chunk_size = max(480, min(9600, int(os.environ.get("OPENAI_TTS_PCM_CHUNK_BYTES", "2400"))))
        except Exception:
            chunk_size = 2400

        chunk_count = 0
        byte_count = 0

        async def _pcm_buffers():
            nonlocal chunk_count, byte_count
            client = AsyncOpenAI(api_key=(os.environ.get("OPENAI_API_KEY") or "").strip())
            async with client.audio.speech.with_streaming_response.create(
                model=model,
                voice=voice,
                input=text,
                instructions=instructions,
                response_format="pcm",
            ) as response:
                self._emit_latency("openai_tts_headers", started, model=model, voice=voice)
                async for chunk in response.iter_bytes(chunk_size=chunk_size):
                    if self._stop_requested.is_set():
                        break
                    if not chunk:
                        continue
                    chunk_count += 1
                    byte_count += len(chunk)
                    if chunk_count == 1:
                        self._emit_latency(
                            "openai_pcm_first_chunk",
                            started,
                            bytes=len(chunk),
                            model=model,
                            voice=voice,
                        )
                        self._emit_latency(
                            "playback_started",
                            started,
                            command="openai_pcm_stream",
                            model=model,
                            voice=voice,
                        )
                    frames = np.frombuffer(chunk, dtype=np.int16)
                    if frames.size:
                        yield frames.reshape(-1, 1)
            yield None

        async def _run_player():
            player = LocalAudioPlayer(should_stop=lambda: self._stop_requested.is_set())
            await player.play_stream(_pcm_buffers())

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_run_player())
            if chunk_count:
                self._emit_latency("openai_pcm_done", started, chunks=chunk_count, bytes=byte_count)
                return True
            if self._stop_requested.is_set():
                self._emit_latency("openai_pcm_cancelled", started, chunks=chunk_count, bytes=byte_count)
                return True
            self._last_error = "OpenAI streaming voice returned no PCM audio."
            return False
        except Exception as exc:
            self._last_error = f"OpenAI streaming voice failed: {exc}"
            logging.warning("OpenAI streaming TTS failed: %s", exc)
            return False
        finally:
            loop.close()

    def _speak_gemini_tts(self, text):
        if not self._gemini_tts_configured():
            self._last_error = (
                "Gemini voice is selected, but GOOGLE_API_KEY is missing or invalid. "
                "Open Settings > API Keys and save a valid Google AI Studio key."
            )
            return False
        if not self._audio_output_available_for_file_playback():
            return False
        started = _time.perf_counter()
        try:
            from google import genai
            from google.genai import types
            from shell_voice import build_persona_instruction, resolve_voice

            voice_name = resolve_voice(getattr(self, "_gemini_voice_name", None))
            model = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
            prompt = build_persona_instruction(text, os.environ.get("VOICE_PERSONA"))
            self._mark_tts_backend("gemini", voice_name, True, started, model=model)
            if self._stop_requested.is_set():
                self._emit_latency("gemini_tts_cancelled", started, voice=voice_name)
                return True
            client = genai.Client(api_key=(os.environ.get("GOOGLE_API_KEY") or "").strip())
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["audio"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name,
                            )
                        )
                    ),
                ),
            )
            data, mime_type = self._extract_gemini_audio(response)
            if not data:
                self._last_error = "Gemini voice returned no audio data."
                return False
            path = os.path.join(self._temp_dir, f"shell_gemini_{_time.monotonic_ns()}.wav")
            self._write_gemini_audio_file(data, mime_type, path)
            self._emit_latency("gemini_tts_ready", started, voice=voice_name)
            if self._stop_requested.is_set():
                self._emit_latency("gemini_tts_cancelled", started, voice=voice_name)
                try:
                    os.remove(path)
                except Exception:
                    pass
                return True
            try:
                return self._play_audio_file(path)
            finally:
                try:
                    os.remove(path)
                except Exception:
                    pass
        except Exception as exc:
            self._last_error = f"Gemini voice failed: {exc}"
            logging.warning("Gemini TTS failed: %s", exc)
            return False

    def _audio_output_available_for_file_playback(self):
        import platform

        system = platform.system().lower()
        if system == "darwin":
            return self._mac_audio_output_available()
        return True

    @staticmethod
    def _extract_gemini_audio(response):
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                inline = getattr(part, "inline_data", None)
                data = getattr(inline, "data", None) if inline is not None else None
                if data:
                    return data, str(getattr(inline, "mime_type", "") or "")
        for part in getattr(response, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline is not None else None
            if data:
                return data, str(getattr(inline, "mime_type", "") or "")
        return b"", ""

    @staticmethod
    def _write_gemini_audio_file(data, mime_type, path):
        raw = bytes(data)
        mt = str(mime_type or "").lower()
        if raw[:4] == b"RIFF" or "wav" in mt:
            with open(path, "wb") as f:
                f.write(raw)
            return
        import re as _re
        import wave as _wave

        match = _re.search(r"rate=(\d+)", mt)
        sample_rate = int(match.group(1)) if match else 24000
        with _wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(raw)

    @staticmethod
    def _parse_edge_delta_percent(value):
        try:
            raw = str(value or "").strip().rstrip("%")
            return float(raw)
        except Exception:
            return 0.0

    def _speech_rate_wpm(self):
        delta = self._parse_edge_delta_percent(self._rate)
        return str(int(max(120, min(320, 190 * (1.0 + delta / 100.0)))))

    def _speech_rate_int(self):
        try:
            return int(self._speech_rate_wpm())
        except Exception:
            return 190

    def _run_speech_command(self, argv, timeout=45):
        import subprocess

        started = _time.perf_counter()
        try:
            proc = subprocess.Popen(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._current_process = proc
            self._emit_latency(
                "playback_started",
                started,
                command=os.path.basename(str(argv[0])),
                backend=getattr(self, "_current_backend", ""),
                voice=getattr(self, "_current_voice_label", ""),
            )
            _stdout, stderr = proc.communicate(timeout=timeout)
            if self._stop_requested.is_set():
                self._emit_latency(
                    "playback_cancelled",
                    started,
                    command=os.path.basename(str(argv[0])),
                    backend=getattr(self, "_current_backend", ""),
                    voice=getattr(self, "_current_voice_label", ""),
                )
                return True
            if proc.returncode != 0:
                err = (stderr or b"").decode("utf-8", errors="replace").strip()
                self._last_error = (
                    err or f"{os.path.basename(str(argv[0]))} exited with code {proc.returncode}"
                )
            return proc.returncode == 0
        except Exception as e:
            try:
                proc = getattr(self, "_current_process", None)
                if proc is not None:
                    proc.terminate()
            except Exception:
                pass
            self._last_error = str(e)
            logging.warning("TTS command failed: %s", e)
            return False
        finally:
            self._current_process = None

    def _run_probe_command(self, argv, timeout=3):
        import subprocess

        try:
            proc = subprocess.run(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            if proc.returncode != 0:
                err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
                self._last_error = (
                    err or f"{os.path.basename(str(argv[0]))} exited with code {proc.returncode}"
                )
            return proc.returncode == 0
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def _silent_wav_probe_path(self):
        path = os.path.join(self._temp_dir, "shell_audio_probe_silence.wav")
        if os.path.exists(path):
            return path
        try:
            import wave

            sample_rate = 8000
            frames = b"\x00\x00" * int(sample_rate * 0.05)
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(frames)
        except Exception as exc:
            self._last_error = f"Could not create audio probe file: {exc}"
        return path

    def _mac_audio_output_available(self, force=False):
        import shutil

        if not shutil.which("afplay"):
            self._last_error = "macOS afplay command not found."
            return False
        now = _time.monotonic()
        if (
            not force
            and self._audio_output_probe_ok is not None
            and now < self._audio_output_probe_until
        ):
            if not self._audio_output_probe_ok and self._audio_output_probe_error:
                self._last_error = self._audio_output_probe_error
            return bool(self._audio_output_probe_ok)
        ok = self._run_probe_command(["afplay", self._silent_wav_probe_path()], timeout=3)
        if not ok:
            detail = self._last_error or "AudioQueueStart failed"
            self._last_error = (
                "macOS audio output unavailable. CoreAudio could not start playback "
                f"({detail}). Check Audio MIDI Setup / Chrome Remote Desktop audio output."
            )
        self._audio_output_probe_ok = bool(ok)
        self._audio_output_probe_error = "" if ok else self._last_error
        self._audio_output_probe_until = now + float(self._audio_output_probe_ttl_s)
        return ok

    def _detect_system_tts_command(self):
        import platform
        import shutil

        system = platform.system().lower()
        if system == "darwin" and shutil.which("say"):
            return "say"
        if system == "windows" and importlib.util.find_spec("pyttsx3"):
            return "pyttsx3"
        if system == "windows":
            return shutil.which("powershell") or shutil.which("powershell.exe")
        for name in ("spd-say", "espeak-ng", "espeak"):
            if shutil.which(name):
                return name
        return ""

    def _prepare_pyttsx3(self):
        if self._pyttsx3_failed:
            return None
        if self._pyttsx3_engine is not None:
            return self._pyttsx3_engine
        started = _time.perf_counter()
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", self._speech_rate_int())
            engine.setProperty("volume", 1.0)
            self._pyttsx3_engine = engine
            self._emit_latency("pyttsx3_ready", started)
            return engine
        except Exception as exc:
            self._pyttsx3_failed = True
            logging.warning("pyttsx3 TTS unavailable: %s", exc)
            return None

    def _speak_pyttsx3(self, text):
        engine = self._prepare_pyttsx3()
        if engine is None:
            return False
        started = _time.perf_counter()
        self._mark_tts_backend("pyttsx3", "system:pyttsx3", False, started)
        try:
            try:
                engine.setProperty("rate", self._speech_rate_int())
                engine.setProperty("volume", 1.0)
            except Exception:
                pass
            engine.say(text)
            self._emit_latency("playback_started", started, command="pyttsx3")
            engine.runAndWait()
            return True
        except Exception as exc:
            logging.warning("pyttsx3 speech failed: %s", exc)
            self._pyttsx3_failed = True
            return False

    def _speak_system(self, text):
        import platform
        import shutil

        system = platform.system().lower()
        if system == "darwin" and shutil.which("say"):
            if not self._mac_audio_output_available():
                return False
            self._mark_tts_backend("system", "system:say", False, _time.perf_counter())
            return self._run_speech_command(["say", "-r", self._speech_rate_wpm(), text])
        if system == "windows":
            if self._speak_pyttsx3(text):
                return True
            powershell = shutil.which("powershell") or shutil.which("powershell.exe")
            if powershell:
                self._mark_tts_backend("system", "system:powershell", False, _time.perf_counter())
                safe = text.replace("'", "''").replace('"', '`"')
                if len(safe) > 700:
                    safe = safe[:700] + "..."
                cmd = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "$s.Rate = 2; $s.Volume = 100; "
                    f"$s.Speak('{safe}'); $s.Dispose()"
                )
                return self._run_speech_command(
                    [powershell, "-NoProfile", "-NonInteractive", "-Command", cmd]
                )
        if shutil.which("spd-say"):
            self._mark_tts_backend("system", "system:spd-say", False, _time.perf_counter())
            return self._run_speech_command(["spd-say", text])
        if shutil.which("espeak-ng"):
            self._mark_tts_backend("system", "system:espeak-ng", False, _time.perf_counter())
            return self._run_speech_command(["espeak-ng", text])
        if shutil.which("espeak"):
            self._mark_tts_backend("system", "system:espeak", False, _time.perf_counter())
            return self._run_speech_command(["espeak", text])
        return False

    def _play_audio_file(self, path):
        import platform
        import shutil

        system = platform.system().lower()
        if system == "darwin" and shutil.which("afplay"):
            return self._run_speech_command(["afplay", path])
        if system == "windows":
            powershell = shutil.which("powershell") or shutil.which("powershell.exe")
            if powershell:
                ps_script = (
                    f"$p = New-Object System.Windows.Media.MediaPlayer; "
                    f"$p.Open([Uri]'{path}'); "
                    f"$p.Play(); "
                    f"Start-Sleep -Milliseconds 250; "
                    f"while($p.Position -lt $p.NaturalDuration.TimeSpan) {{ Start-Sleep -Milliseconds 100 }}; "
                    "$p.Close();"
                )
                return self._run_speech_command(
                    [
                        powershell,
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        f"Add-Type -AssemblyName PresentationCore; {ps_script}",
                    ]
                )
        for player in ("ffplay", "mpg123", "mpv"):
            if shutil.which(player):
                if player == "ffplay":
                    return self._run_speech_command(
                        [player, "-nodisp", "-autoexit", "-loglevel", "quiet", path]
                    )
                return self._run_speech_command([player, path])
        return False
