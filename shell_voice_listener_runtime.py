"""
Lightweight Shell microphone listener runtime.

This module owns microphone capture, voice activity detection, and speech
recognition threading without importing the full desktop UI. Heavy audio
libraries are loaded lazily inside the listener thread when a voice session
actually starts.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import re
import time

from PyQt6.QtCore import QThread, pyqtSignal


_SD_AVAILABLE = importlib.util.find_spec("sounddevice") is not None
_SR_AVAILABLE = importlib.util.find_spec("speech_recognition") is not None

_HESITATION_PATTERNS = (
    "um",
    "uh",
    "erm",
    "hmm",
    "let me think",
    "one second",
    "hold on",
    "wait",
)
_CONTINUATION_WORDS = {
    "and",
    "or",
    "but",
    "because",
    "so",
    "then",
    "if",
    "when",
    "while",
    "with",
    "to",
    "for",
    "from",
    "about",
    "like",
}
_SHORT_COMMANDS = {
    "yes",
    "no",
    "stop",
    "cancel",
    "close",
    "open",
    "send",
    "run",
    "search",
    "thanks",
    "thank you",
}


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


class VoiceListenerThread(QThread):
    """Listen to microphone audio and emit recognized text."""

    text_recognized = pyqtSignal(str)
    amplitude_changed = pyqtSignal(float)
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    latency_event = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._muted = False
        self._sample_rate = 16000
        self._channels = 1
        self._silence_threshold = _env_float(
            "SHELL_VOICE_SILENCE_THRESHOLD", 0.018, minimum=0.005, maximum=0.2
        )
        self._speech_timeout = _env_float(
            "SHELL_VOICE_END_SILENCE_MS", 750.0, minimum=250.0, maximum=2500.0
        ) / 1000.0
        self._min_speech_duration = _env_float(
            "SHELL_VOICE_MIN_SPEECH_MS", 300.0, minimum=150.0, maximum=1500.0
        ) / 1000.0
        self._max_speech_duration = 30.0
        self._chunk_duration = _env_float(
            "SHELL_VOICE_CHUNK_MS", 50.0, minimum=20.0, maximum=250.0
        ) / 1000.0
        self._adaptive_endpointing = _env_bool("SHELL_VOICE_ADAPTIVE_ENDPOINTING", True)
        self._endpoint_min_s = _env_float(
            "SHELL_VOICE_ENDPOINT_MIN_MS", 500.0, minimum=350.0, maximum=1200.0
        ) / 1000.0
        self._endpoint_max_s = _env_float(
            "SHELL_VOICE_ENDPOINT_MAX_MS", 900.0, minimum=600.0, maximum=2500.0
        ) / 1000.0
        if self._endpoint_max_s < self._endpoint_min_s:
            self._endpoint_max_s = self._endpoint_min_s
        self._semantic_pacing = _env_bool("SHELL_VOICE_SEMANTIC_PACING", True)
        self._semantic_endpoint_bias_s = 0.0
        self._semantic_rhythm_alpha = _env_float(
            "SHELL_VOICE_SEMANTIC_RHYTHM_ALPHA", 0.35, minimum=0.05, maximum=0.8
        )
        self._semantic_rhythm_bias_s = 0.0
        self._semantic_rhythm_profile = {
            "turns": 0,
            "style": "balanced",
            "avg_duration_s": 0.0,
            "complete_score": 0.0,
            "hesitation_score": 0.0,
            "continuation_score": 0.0,
            "short_command_score": 0.0,
            "empty_score": 0.0,
            "rhythm_bias_ms": 0.0,
        }
        self._last_semantic_endpoint = {
            "completion": "unknown",
            "confidence": 0.0,
            "bias_ms": 0.0,
            "reason": "none",
            "rhythm_style": "balanced",
            "rhythm_bias_ms": 0.0,
            "turns": 0,
        }
        self._noise_floor = 0.0
        self._last_endpoint_timeout = self._speech_timeout

    def set_muted(self, muted):
        self._muted = bool(muted)

    def stop_listening(self):
        self._running = False

    def _emit_latency(self, event: str, started: float, **payload):
        try:
            now = time.perf_counter()
            payload["ts"] = round(now, 6)
            payload["elapsed_ms"] = round((now - started) * 1000.0, 2)
            self.latency_event.emit(str(event), payload)
        except Exception:
            pass

    def _adaptive_speech_timeout(self, speech_duration_s: float, *, noise_floor: float = 0.0) -> float:
        if not self._adaptive_endpointing:
            return self._speech_timeout

        timeout = self._speech_timeout
        if speech_duration_s < 1.2:
            timeout -= 0.18
        elif speech_duration_s < 2.5:
            timeout -= 0.10
        elif speech_duration_s > 5.0:
            timeout += 0.10

        noise_ratio = 0.0
        if self._silence_threshold > 0:
            noise_ratio = max(0.0, noise_floor / self._silence_threshold)
        if noise_ratio >= 0.75:
            timeout += 0.15
        elif noise_ratio >= 0.55:
            timeout += 0.08

        if self._semantic_pacing:
            timeout += self._semantic_endpoint_bias_s
            timeout += self._semantic_rhythm_bias_s

        return max(self._endpoint_min_s, min(self._endpoint_max_s, timeout))

    @staticmethod
    def _tokenize_semantic_text(text: str) -> list[str]:
        return re.findall(r"[a-z0-9']+", (text or "").lower())

    def _analyze_semantic_completion(self, text: str, *, duration_s: float = 0.0) -> dict[str, object]:
        stripped = (text or "").strip()
        tokens = self._tokenize_semantic_text(stripped)
        normalized = " ".join(tokens)
        if not tokens:
            return {
                "completion": "empty",
                "confidence": 0.6,
                "bias_ms": 120.0,
                "reason": "no_recognized_words",
                "tokens": 0,
            }

        tail = " ".join(tokens[-3:])
        if any(tail.endswith(pattern) or normalized.endswith(pattern) for pattern in _HESITATION_PATTERNS):
            return {
                "completion": "hesitation",
                "confidence": 0.74,
                "bias_ms": 220.0,
                "reason": "hesitation_or_thinking_phrase",
                "tokens": len(tokens),
            }

        if normalized in _SHORT_COMMANDS or (len(tokens) <= 2 and tokens[-1] not in _CONTINUATION_WORDS):
            return {
                "completion": "short_command",
                "confidence": 0.72,
                "bias_ms": -80.0,
                "reason": "brief_complete_intent",
                "tokens": len(tokens),
            }

        if tokens[-1] in _CONTINUATION_WORDS:
            return {
                "completion": "continuation",
                "confidence": 0.7,
                "bias_ms": 180.0,
                "reason": "trailing_continuation_word",
                "tokens": len(tokens),
            }

        if duration_s < 1.0 and len(tokens) <= 3:
            return {
                "completion": "short_command",
                "confidence": 0.64,
                "bias_ms": -60.0,
                "reason": "short_turn_complete",
                "tokens": len(tokens),
            }

        return {
            "completion": "complete",
            "confidence": 0.62,
            "bias_ms": -30.0,
            "reason": "default_complete",
            "tokens": len(tokens),
        }

    def _remember_semantic_turn(self, text: str, *, duration_s: float = 0.0) -> dict[str, object]:
        analysis = self._analyze_semantic_completion(text, duration_s=duration_s)
        if not self._semantic_pacing:
            analysis = dict(analysis)
            analysis["bias_ms"] = 0.0
            analysis["reason"] = "semantic_pacing_disabled"
            self._last_semantic_endpoint = analysis
            self._semantic_endpoint_bias_s = 0.0
            return analysis

        target_bias_s = float(analysis.get("bias_ms", 0.0)) / 1000.0
        blended = (self._semantic_endpoint_bias_s * 0.55) + (target_bias_s * 0.45)
        self._semantic_endpoint_bias_s = max(-0.12, min(0.25, blended))
        remembered = dict(analysis)
        remembered["bias_ms"] = round(self._semantic_endpoint_bias_s * 1000.0, 2)
        remembered.update(self._update_semantic_rhythm(remembered, duration_s=duration_s))
        self._last_semantic_endpoint = remembered
        return remembered

    def _update_semantic_rhythm(self, analysis: dict[str, object], *, duration_s: float = 0.0) -> dict[str, object]:
        completion = str(analysis.get("completion", "unknown"))
        turns = int(self._semantic_rhythm_profile.get("turns", 0)) + 1
        alpha = self._semantic_rhythm_alpha if turns > 1 else 1.0

        def blend(key: str, value: float) -> float:
            old = float(self._semantic_rhythm_profile.get(key, 0.0))
            return (old * (1.0 - alpha)) + (value * alpha)

        complete_score = blend("complete_score", 1.0 if completion == "complete" else 0.0)
        hesitation_score = blend("hesitation_score", 1.0 if completion == "hesitation" else 0.0)
        continuation_score = blend("continuation_score", 1.0 if completion == "continuation" else 0.0)
        short_command_score = blend("short_command_score", 1.0 if completion == "short_command" else 0.0)
        empty_score = blend("empty_score", 1.0 if completion == "empty" else 0.0)
        avg_duration_s = blend("avg_duration_s", max(0.0, float(duration_s or 0.0)))

        target_bias_s = (
            (hesitation_score * 0.04)
            + (continuation_score * 0.035)
            + (empty_score * 0.025)
            - (short_command_score * 0.035)
            - (complete_score * 0.015)
        )
        if avg_duration_s >= 3.5:
            target_bias_s += 0.025
        elif 0.0 < avg_duration_s <= 0.9:
            target_bias_s -= 0.015
        target_bias_s = max(-0.06, min(0.08, target_bias_s))
        self._semantic_rhythm_bias_s = (
            self._semantic_rhythm_bias_s * 0.55
        ) + (target_bias_s * 0.45)

        if hesitation_score + continuation_score >= 0.45:
            style = "patient"
        elif short_command_score >= 0.45:
            style = "fast"
        elif avg_duration_s >= 3.5:
            style = "reflective"
        else:
            style = "balanced"

        self._semantic_rhythm_profile = {
            "turns": turns,
            "style": style,
            "avg_duration_s": round(avg_duration_s, 3),
            "complete_score": round(complete_score, 3),
            "hesitation_score": round(hesitation_score, 3),
            "continuation_score": round(continuation_score, 3),
            "short_command_score": round(short_command_score, 3),
            "empty_score": round(empty_score, 3),
            "rhythm_bias_ms": round(self._semantic_rhythm_bias_s * 1000.0, 2),
        }
        return {
            "rhythm_style": style,
            "rhythm_bias_ms": self._semantic_rhythm_profile["rhythm_bias_ms"],
            "turns": turns,
        }

    @staticmethod
    def _load_audio_modules():
        try:
            import sounddevice as sd
        except ImportError:
            return None, None, None, None, "sounddevice not installed"
        except Exception as exc:
            return None, None, None, None, f"sounddevice unavailable: {exc}"

        try:
            import speech_recognition as sr
        except ImportError:
            return None, None, None, None, "SpeechRecognition not installed"
        except Exception as exc:
            return None, None, None, None, f"SpeechRecognition unavailable: {exc}"

        try:
            import io
            import wave

            import numpy as np
        except Exception as exc:
            return None, None, None, None, f"audio processing unavailable: {exc}"

        return sd, sr, np, (io, wave), ""

    def run(self):
        sd, sr, np, io_wave, error = self._load_audio_modules()
        if error:
            self.error_occurred.emit(error)
            return

        io, wave = io_wave
        try:
            recognizer = sr.Recognizer()
        except Exception as exc:
            self.error_occurred.emit(f"Speech recognizer unavailable: {exc}")
            return

        self._running = True
        self.listening_started.emit()

        try:
            while self._running:
                if self._muted:
                    self.amplitude_changed.emit(0.0)
                    self.msleep(50)
                    continue

                try:
                    self.status_changed.emit("LISTENING")
                    speech_frames = []
                    silence_count = 0
                    speech_started = False
                    speech_started_at = 0.0
                    speech_ended_at = 0.0
                    total_frames = 0
                    max_frames = int(self._max_speech_duration * self._sample_rate)
                    chunk_size = max(1, int(self._sample_rate * self._chunk_duration))
                    silence_limit = max(1, int(self._speech_timeout / self._chunk_duration))
                    noise_floor = self._noise_floor
                    self._last_endpoint_timeout = self._speech_timeout

                    while self._running and not self._muted:
                        try:
                            audio_chunk = sd.rec(
                                chunk_size,
                                samplerate=self._sample_rate,
                                channels=self._channels,
                                dtype="int16",
                                blocking=True,
                            )
                        except Exception:
                            self.msleep(200)
                            continue

                        amp = float(np.abs(audio_chunk).mean()) / 32768.0
                        self.amplitude_changed.emit(min(1.0, amp * 5.0))

                        if amp > self._silence_threshold:
                            if not speech_started:
                                speech_started = True
                                speech_started_at = time.perf_counter()
                                self.status_changed.emit("HEARING YOU...")
                                self._emit_latency(
                                    "speech_started",
                                    speech_started_at,
                                    chunk_ms=round(self._chunk_duration * 1000.0, 2),
                                    threshold=round(self._silence_threshold, 4),
                                )
                            speech_frames.append(audio_chunk.copy())
                            silence_count = 0
                            total_frames += chunk_size
                        elif not speech_started:
                            if noise_floor <= 0:
                                noise_floor = amp
                            else:
                                noise_floor = (noise_floor * 0.92) + (amp * 0.08)
                            self._noise_floor = noise_floor
                        elif speech_started:
                            speech_frames.append(audio_chunk.copy())
                            silence_count += 1
                            total_frames += chunk_size
                            speech_duration_s = total_frames / float(self._sample_rate)
                            effective_timeout = self._adaptive_speech_timeout(
                                speech_duration_s,
                                noise_floor=noise_floor,
                            )
                            self._last_endpoint_timeout = effective_timeout
                            silence_limit = max(1, int(effective_timeout / self._chunk_duration))
                            if silence_count >= silence_limit:
                                speech_ended_at = time.perf_counter()
                                break

                        if total_frames >= max_frames:
                            speech_ended_at = time.perf_counter()
                            break

                    if not speech_frames or not speech_started:
                        continue

                    duration = len(speech_frames) * self._chunk_duration
                    if duration < self._min_speech_duration:
                        continue

                    if speech_ended_at <= 0:
                        speech_ended_at = time.perf_counter()
                    self._emit_latency(
                        "speech_ended",
                        speech_started_at or speech_ended_at,
                        duration_ms=round(duration * 1000.0, 2),
                        trailing_silence_ms=round(silence_count * self._chunk_duration * 1000.0, 2),
                        endpoint_timeout_ms=round(self._last_endpoint_timeout * 1000.0, 2),
                        adaptive_endpointing=bool(self._adaptive_endpointing),
                        semantic_pacing=bool(self._semantic_pacing),
                        semantic_bias_ms=round(self._semantic_endpoint_bias_s * 1000.0, 2),
                        semantic_rhythm_bias_ms=round(self._semantic_rhythm_bias_s * 1000.0, 2),
                        semantic_rhythm_style=self._semantic_rhythm_profile.get("style", "balanced"),
                        semantic_completion=self._last_semantic_endpoint.get("completion", "unknown"),
                        noise_floor=round(noise_floor, 4),
                    )
                    self.status_changed.emit("PROCESSING...")
                    self.amplitude_changed.emit(0.0)
                    self._emit_latency("speech_end_to_processing", speech_ended_at)

                    audio_data = np.concatenate(speech_frames)
                    wav_buffer = io.BytesIO()
                    with wave.open(wav_buffer, "wb") as wf:
                        wf.setnchannels(self._channels)
                        wf.setsampwidth(2)
                        wf.setframerate(self._sample_rate)
                        wf.writeframes(audio_data.tobytes())

                    wav_buffer.seek(0)
                    with sr.AudioFile(wav_buffer) as source:
                        audio = recognizer.record(source)

                    try:
                        recognition_started = time.perf_counter()
                        text = recognizer.recognize_google(audio, language="en-US")
                        self._emit_latency("recognition_done", recognition_started)
                        self._emit_latency("speech_end_to_text", speech_ended_at)
                        if text and text.strip():
                            semantic = self._remember_semantic_turn(text.strip(), duration_s=duration)
                            self._emit_latency(
                                "semantic_turn_analyzed",
                                speech_ended_at,
                                completion=semantic.get("completion", "unknown"),
                                confidence=semantic.get("confidence", 0.0),
                                bias_ms=semantic.get("bias_ms", 0.0),
                                reason=semantic.get("reason", ""),
                                rhythm_bias_ms=semantic.get("rhythm_bias_ms", 0.0),
                                rhythm_style=semantic.get("rhythm_style", "balanced"),
                                turns=semantic.get("turns", 0),
                                tokens=semantic.get("tokens", 0),
                            )
                            self.text_recognized.emit(text.strip())
                    except sr.UnknownValueError:
                        semantic = self._remember_semantic_turn("", duration_s=duration)
                        self._emit_latency("recognition_empty", recognition_started)
                        self._emit_latency(
                            "semantic_turn_analyzed",
                            speech_ended_at,
                            completion=semantic.get("completion", "empty"),
                            confidence=semantic.get("confidence", 0.0),
                            bias_ms=semantic.get("bias_ms", 0.0),
                            reason=semantic.get("reason", ""),
                            rhythm_bias_ms=semantic.get("rhythm_bias_ms", 0.0),
                            rhythm_style=semantic.get("rhythm_style", "balanced"),
                            turns=semantic.get("turns", 0),
                            tokens=0,
                        )
                        pass
                    except sr.RequestError as exc:
                        self._emit_latency("recognition_error", recognition_started)
                        self.error_occurred.emit(f"Speech API error: {exc}")

                except Exception as exc:
                    logging.warning("VoiceListener error: %s", exc)
                    self.msleep(500)
        finally:
            self.listening_stopped.emit()
            self.amplitude_changed.emit(0.0)
