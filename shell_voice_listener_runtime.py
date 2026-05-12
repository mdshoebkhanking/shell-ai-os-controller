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

from PyQt6.QtCore import QThread, pyqtSignal


_SD_AVAILABLE = importlib.util.find_spec("sounddevice") is not None
_SR_AVAILABLE = importlib.util.find_spec("speech_recognition") is not None


class VoiceListenerThread(QThread):
    """Listen to microphone audio and emit recognized text."""

    text_recognized = pyqtSignal(str)
    amplitude_changed = pyqtSignal(float)
    listening_started = pyqtSignal()
    listening_stopped = pyqtSignal()
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._muted = False
        self._sample_rate = 16000
        self._channels = 1
        self._silence_threshold = 0.02
        self._speech_timeout = 2.0
        self._min_speech_duration = 0.5
        self._max_speech_duration = 30.0

    def set_muted(self, muted):
        self._muted = bool(muted)

    def stop_listening(self):
        self._running = False

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
                    self.msleep(100)
                    continue

                try:
                    self.status_changed.emit("LISTENING")
                    speech_frames = []
                    silence_count = 0
                    speech_started = False
                    total_frames = 0
                    max_frames = int(self._max_speech_duration * self._sample_rate)
                    chunk_size = int(self._sample_rate * 0.1)

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
                                self.status_changed.emit("HEARING YOU...")
                            speech_frames.append(audio_chunk.copy())
                            silence_count = 0
                            total_frames += chunk_size
                        elif speech_started:
                            speech_frames.append(audio_chunk.copy())
                            silence_count += 1
                            total_frames += chunk_size
                            if silence_count >= int(self._speech_timeout / 0.1):
                                break

                        if total_frames >= max_frames:
                            break

                    if not speech_frames or not speech_started:
                        continue

                    duration = len(speech_frames) * 0.1
                    if duration < self._min_speech_duration:
                        continue

                    self.status_changed.emit("PROCESSING...")
                    self.amplitude_changed.emit(0.0)

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
                        text = recognizer.recognize_google(audio, language="en-US")
                        if text and text.strip():
                            self.text_recognized.emit(text.strip())
                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError as exc:
                        self.error_occurred.emit(f"Speech API error: {exc}")

                except Exception as exc:
                    logging.warning("VoiceListener error: %s", exc)
                    self.msleep(500)
        finally:
            self.listening_stopped.emit()
            self.amplitude_changed.emit(0.0)
