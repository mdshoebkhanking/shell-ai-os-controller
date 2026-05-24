"""Wake-word and VAD pipeline primitives for Shell voice input.

The module intentionally keeps heavy audio/ML dependencies behind lazy imports.
Default flags are off, so importing this file does not load openWakeWord,
Silero, torch, onnxruntime, sounddevice, or the desktop UI.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol


logger = logging.getLogger("shell_voice_pipeline")
PROJECT_ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = PROJECT_ROOT / ".shell_settings.json"


def _now() -> float:
    return time.perf_counter()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _read_setting(key: str, default: Any) -> Any:
    try:
        if not SETTINGS_PATH.exists():
            return default
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default
        value = data.get(key, default)
        return default if value is None else value
    except Exception:
        return default


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in str(value).split(",") if item.strip())


def _sensitivity_to_threshold(value: float) -> float:
    """Map 0..1 sensitivity to a prediction threshold.

    Higher sensitivity means a lower score threshold. The clamp keeps testing
    practical while avoiding extremely noisy defaults.
    """

    sensitivity = max(0.0, min(1.0, float(value)))
    return max(0.25, min(0.85, 0.9 - (sensitivity * 0.65)))


@dataclass(frozen=True)
class VoicePipelineConfig:
    sample_rate: int = 16000
    wake_enabled: bool = False
    vad_enabled: bool = False
    wake_words: tuple[str, ...] = ("hey shell",)
    wake_word_models: tuple[str, ...] = ()
    wake_threshold: float = 0.5
    wake_idle_frame_ms: float = 80.0
    vad_threshold: float = 0.5
    vad_min_silence_ms: int = 350
    vad_speech_pad_ms: int = 30
    vad_window_samples: int = 512
    manual_button_bypasses_wake: bool = True

    @classmethod
    def from_environment(cls) -> "VoicePipelineConfig":
        setting_sensitivity = _read_setting("wake_word_sensitivity", 65)
        try:
            setting_sensitivity = float(setting_sensitivity) / 100.0
        except Exception:
            setting_sensitivity = 0.65
        raw_sensitivity = os.environ.get("SHELL_WAKE_WORD_SENSITIVITY")
        if raw_sensitivity in {None, ""}:
            sensitivity = setting_sensitivity
        else:
            try:
                sensitivity = float(raw_sensitivity)
                if sensitivity > 1.0:
                    sensitivity = sensitivity / 100.0
            except Exception:
                sensitivity = setting_sensitivity
        sensitivity = max(0.0, min(1.0, sensitivity))
        default_threshold = _sensitivity_to_threshold(sensitivity)
        wake_models = (
            _csv(os.environ.get("SHELL_WAKE_WORD_MODEL_PATHS"))
            or _csv(os.environ.get("SHELL_WAKE_WORD_MODELS"))
        )
        wake_words = _csv(os.environ.get("SHELL_WAKE_WORDS")) or ("hey shell",)
        return cls(
            wake_enabled=_env_bool("SHELL_WAKE_WORD_ENABLED", False),
            vad_enabled=_env_bool("SHELL_VAD_ENABLED", False),
            wake_words=wake_words,
            wake_word_models=wake_models,
            wake_threshold=_env_float(
                "SHELL_WAKE_WORD_THRESHOLD",
                default_threshold,
                minimum=0.05,
                maximum=0.99,
            ),
            wake_idle_frame_ms=_env_float(
                "SHELL_WAKE_IDLE_FRAME_MS",
                80.0,
                minimum=40.0,
                maximum=250.0,
            ),
            vad_threshold=_env_float("SHELL_VAD_THRESHOLD", 0.5, minimum=0.05, maximum=0.95),
            vad_min_silence_ms=int(
                _env_float("SHELL_VAD_MIN_SILENCE_MS", 350.0, minimum=80.0, maximum=2000.0)
            ),
            vad_speech_pad_ms=int(
                _env_float("SHELL_VAD_SPEECH_PAD_MS", 30.0, minimum=0.0, maximum=300.0)
            ),
            vad_window_samples=int(
                _env_float("SHELL_VAD_WINDOW_SAMPLES", 512.0, minimum=256.0, maximum=1536.0)
            ),
            manual_button_bypasses_wake=_env_bool("SHELL_VOICE_BUTTON_BYPASSES_WAKE", True),
        )


@dataclass(frozen=True)
class WakeWordResult:
    detected: bool
    score: float = 0.0
    label: str = ""
    elapsed_ms: float = 0.0
    error: str = ""


@dataclass(frozen=True)
class VADResult:
    speech_started: bool = False
    speech_ended: bool = False
    probability: float = 0.0
    elapsed_ms: float = 0.0
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VoicePipelineEvent:
    event: str
    state: str
    elapsed_ms: float = 0.0
    score: float = 0.0
    label: str = ""
    error: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class WakeWordDetector(Protocol):
    def detect(self, audio_frame: Any) -> WakeWordResult:
        ...


class VoiceActivityDetector(Protocol):
    def process(self, audio_frame: Any) -> VADResult:
        ...

    def reset(self) -> None:
        ...


class OpenWakeWordDetector:
    """Thin openWakeWord adapter.

    Use `SHELL_WAKE_WORD_MODEL_PATHS` for a custom "Hey Shell" model. If no
    model path is provided, the adapter tries the configured wake-word labels and
    degrades gracefully if the installed openWakeWord build cannot load them.
    """

    def __init__(self, config: VoicePipelineConfig):
        started = _now()
        try:
            from openwakeword.model import Model  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"openWakeWord unavailable: {exc}") from exc

        model_specs = list(config.wake_word_models or config.wake_words)
        kwargs: dict[str, Any] = {}
        if model_specs:
            kwargs["wakeword_models"] = model_specs
        kwargs["inference_framework"] = str(
            os.environ.get("SHELL_OPENWAKEWORD_INFERENCE", "onnx") or "onnx"
        ).strip().lower()
        internal_vad = os.environ.get("SHELL_OPENWAKEWORD_INTERNAL_VAD_THRESHOLD")
        if internal_vad not in {None, ""}:
            kwargs["vad_threshold"] = _env_float(
                "SHELL_OPENWAKEWORD_INTERNAL_VAD_THRESHOLD",
                0.5,
                minimum=0.0,
                maximum=1.0,
            )
        try:
            self._model = Model(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"openWakeWord model load failed: {exc}") from exc
        self._threshold = float(config.wake_threshold)
        self._load_ms = round((_now() - started) * 1000.0, 3)

    @staticmethod
    def _as_int16_mono(audio_frame: Any):
        import numpy as np

        if isinstance(audio_frame, (bytes, bytearray, memoryview)):
            arr = np.frombuffer(audio_frame, dtype=np.int16)
        else:
            arr = np.asarray(audio_frame)
        if arr.ndim > 1:
            arr = arr.reshape(-1)
        if arr.dtype != np.int16:
            if np.issubdtype(arr.dtype, np.floating):
                arr = np.clip(arr, -1.0, 1.0)
                arr = (arr * 32767.0).astype(np.int16)
            else:
                arr = arr.astype(np.int16, copy=False)
        return arr

    def detect(self, audio_frame: Any) -> WakeWordResult:
        started = _now()
        try:
            prediction = self._model.predict(self._as_int16_mono(audio_frame))
            best_label = ""
            best_score = 0.0
            if isinstance(prediction, dict):
                for label, value in prediction.items():
                    if isinstance(value, dict):
                        score = max(float(v or 0.0) for v in value.values()) if value else 0.0
                    else:
                        score = float(value or 0.0)
                    if score > best_score:
                        best_label = str(label)
                        best_score = score
            elapsed = round((_now() - started) * 1000.0, 3)
            return WakeWordResult(
                detected=best_score >= self._threshold,
                score=best_score,
                label=best_label,
                elapsed_ms=elapsed,
            )
        except Exception as exc:
            elapsed = round((_now() - started) * 1000.0, 3)
            return WakeWordResult(False, elapsed_ms=elapsed, error=str(exc))


class SileroVADDetector:
    """Streaming Silero VAD adapter using VADIterator."""

    def __init__(self, config: VoicePipelineConfig):
        try:
            from silero_vad import VADIterator, load_silero_vad  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"Silero VAD unavailable: {exc}") from exc

        try:
            self._model = load_silero_vad(onnx=True)
        except TypeError:
            self._model = load_silero_vad()
        except Exception as exc:
            raise RuntimeError(f"Silero VAD model load failed: {exc}") from exc

        self._sample_rate = int(config.sample_rate)
        self._window = int(config.vad_window_samples)
        self._buffer = None
        self._iterator = VADIterator(
            self._model,
            threshold=float(config.vad_threshold),
            sampling_rate=self._sample_rate,
            min_silence_duration_ms=int(config.vad_min_silence_ms),
            speech_pad_ms=int(config.vad_speech_pad_ms),
        )

    @staticmethod
    def _as_float_array(audio_frame: Any):
        import numpy as np

        if isinstance(audio_frame, (bytes, bytearray, memoryview)):
            arr = np.frombuffer(audio_frame, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            arr = np.asarray(audio_frame)
            if arr.ndim > 1:
                arr = arr.reshape(-1)
            if np.issubdtype(arr.dtype, np.integer):
                arr = arr.astype(np.float32) / 32768.0
            else:
                arr = arr.astype(np.float32, copy=False)
        if arr.ndim > 1:
            arr = arr.reshape(-1)
        return arr

    def process(self, audio_frame: Any) -> VADResult:
        started = _now()
        try:
            import numpy as np
            import torch

            arr = self._as_float_array(audio_frame)
            if self._buffer is not None and len(self._buffer):
                arr = np.concatenate([self._buffer, arr])
            last_event: dict[str, Any] = {}
            offset = 0
            while offset + self._window <= len(arr):
                chunk = arr[offset:offset + self._window]
                tensor = torch.from_numpy(chunk.astype(np.float32, copy=False))
                speech_dict = self._iterator(tensor, return_seconds=False)
                if speech_dict:
                    last_event.update(dict(speech_dict))
                offset += self._window
            self._buffer = arr[offset:].copy() if offset < len(arr) else None
            elapsed = round((_now() - started) * 1000.0, 3)
            return VADResult(
                speech_started="start" in last_event,
                speech_ended="end" in last_event,
                elapsed_ms=elapsed,
                raw=last_event,
            )
        except Exception as exc:
            elapsed = round((_now() - started) * 1000.0, 3)
            return VADResult(elapsed_ms=elapsed, error=str(exc))

    def reset(self) -> None:
        self._buffer = None
        try:
            self._iterator.reset_states()
        except Exception:
            try:
                self._model.reset_states()
            except Exception:
                pass


class VoicePipelineManager:
    """Transport-agnostic wake word -> VAD -> STT state manager."""

    def __init__(
        self,
        config: VoicePipelineConfig | None = None,
        *,
        wake_detector: WakeWordDetector | None = None,
        vad_detector: VoiceActivityDetector | None = None,
        wake_detector_factory=None,
        vad_detector_factory=None,
        manual_trigger: bool = False,
    ):
        self.config = config or VoicePipelineConfig.from_environment()
        self.state = "idle"
        self.errors: list[str] = []
        self.events: list[VoicePipelineEvent] = []
        self.wake_available = False
        self.vad_available = False
        self._wake_detector = wake_detector
        self._vad_detector = vad_detector
        self._wake_started_at = 0.0
        self._speech_started_at = 0.0
        self._wake_detection_count = 0
        self._wake_frame_count = 0

        if self.config.wake_enabled:
            try:
                if self._wake_detector is None:
                    factory = wake_detector_factory or OpenWakeWordDetector
                    self._wake_detector = factory(self.config)
                self.wake_available = True
            except Exception as exc:
                self.errors.append(str(exc))
                logger.warning("Wake word disabled; falling back to button mode: %s", exc)

        if self.config.vad_enabled:
            try:
                if self._vad_detector is None:
                    factory = vad_detector_factory or SileroVADDetector
                    self._vad_detector = factory(self.config)
                self.vad_available = True
            except Exception as exc:
                self.errors.append(str(exc))
                logger.warning("Silero VAD disabled; falling back to timing mode: %s", exc)

        self.reset(manual_trigger=manual_trigger)

    @classmethod
    def from_environment(cls, *, manual_trigger: bool = False) -> "VoicePipelineManager":
        return cls(VoicePipelineConfig.from_environment(), manual_trigger=manual_trigger)

    def _record(self, event: VoicePipelineEvent) -> VoicePipelineEvent:
        self.events.append(event)
        if len(self.events) > 120:
            self.events = self.events[-120:]
        return event

    def reset(self, *, manual_trigger: bool = False) -> None:
        try:
            if self._vad_detector is not None:
                self._vad_detector.reset()
        except Exception:
            pass
        self._speech_started_at = 0.0
        if manual_trigger or not (self.config.wake_enabled and self.wake_available):
            self.state = "armed"
        else:
            self.state = "waiting_for_wake"
            self._wake_started_at = _now()

    def waiting_for_wake(self) -> bool:
        return self.state == "waiting_for_wake"

    def should_use_vad(self) -> bool:
        return bool(self.config.vad_enabled and self.vad_available)

    def manual_trigger(self) -> VoicePipelineEvent:
        self.state = "armed"
        return self._record(VoicePipelineEvent("manual_trigger", self.state))

    def interrupt(self, reason: str = "barge_in") -> VoicePipelineEvent:
        self.state = "interrupted"
        return self._record(
            VoicePipelineEvent("interrupted", self.state, payload={"reason": str(reason or "barge_in")})
        )

    def process_wake_frame(self, audio_frame: Any) -> VoicePipelineEvent:
        if not self.waiting_for_wake() or self._wake_detector is None:
            return VoicePipelineEvent("wake_ignored", self.state)
        self._wake_frame_count += 1
        result = self._wake_detector.detect(audio_frame)
        if result.error:
            self.errors.append(result.error)
            self.state = "armed"
            return self._record(
                VoicePipelineEvent(
                    "wake_error_fallback",
                    self.state,
                    elapsed_ms=result.elapsed_ms,
                    error=result.error,
                )
            )
        if result.detected:
            self._wake_detection_count += 1
            self.state = "armed"
            activation_ms = round((_now() - self._wake_started_at) * 1000.0, 3) if self._wake_started_at else 0.0
            return self._record(
                VoicePipelineEvent(
                    "wake_detected",
                    self.state,
                    elapsed_ms=result.elapsed_ms,
                    score=result.score,
                    label=result.label,
                    payload={"activation_ms": activation_ms},
                )
            )
        return self._record(
            VoicePipelineEvent(
                "wake_frame",
                self.state,
                elapsed_ms=result.elapsed_ms,
                score=result.score,
                label=result.label,
            )
        )

    def process_vad_frame(self, audio_frame: Any) -> VoicePipelineEvent:
        if not self.should_use_vad() or self._vad_detector is None:
            return VoicePipelineEvent("vad_ignored", self.state)
        result = self._vad_detector.process(audio_frame)
        if result.error:
            self.errors.append(result.error)
            self.vad_available = False
            return self._record(
                VoicePipelineEvent(
                    "vad_error_fallback",
                    self.state,
                    elapsed_ms=result.elapsed_ms,
                    error=result.error,
                )
            )
        if result.speech_started:
            self.state = "speech"
            self._speech_started_at = _now()
            return self._record(
                VoicePipelineEvent(
                    "vad_speech_started",
                    self.state,
                    elapsed_ms=result.elapsed_ms,
                    payload=result.raw,
                )
            )
        if result.speech_ended:
            self.state = "processing"
            return self._record(
                VoicePipelineEvent(
                    "vad_speech_ended",
                    self.state,
                    elapsed_ms=result.elapsed_ms,
                    payload=result.raw,
                )
            )
        return self._record(
            VoicePipelineEvent("vad_frame", self.state, elapsed_ms=result.elapsed_ms)
        )

    def finish_turn(self, *, manual_trigger: bool = False) -> None:
        self.reset(manual_trigger=manual_trigger)

    def false_positive_rate(self, frames: Iterable[Any]) -> dict[str, float | int]:
        start_count = self._wake_detection_count
        start_frames = self._wake_frame_count
        original_state = self.state
        if self.config.wake_enabled and self.wake_available:
            self.state = "waiting_for_wake"
            self._wake_started_at = _now()
        for frame in frames:
            event = self.process_wake_frame(frame)
            if event.event == "wake_detected":
                self.state = "waiting_for_wake"
        detections = self._wake_detection_count - start_count
        frames_seen = max(0, self._wake_frame_count - start_frames)
        self.state = original_state
        return {
            "frames": frames_seen,
            "false_positives": detections,
            "rate": (detections / frames_seen) if frames_seen else 0.0,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "wake_enabled": self.config.wake_enabled,
            "wake_available": self.wake_available,
            "vad_enabled": self.config.vad_enabled,
            "vad_available": self.vad_available,
            "wake_words": list(self.config.wake_words),
            "wake_threshold": self.config.wake_threshold,
            "vad_threshold": self.config.vad_threshold,
            "errors": list(self.errors[-5:]),
            "events": [event.__dict__ for event in self.events[-20:]],
        }


__all__ = [
    "OpenWakeWordDetector",
    "SileroVADDetector",
    "VADResult",
    "VoicePipelineConfig",
    "VoicePipelineEvent",
    "VoicePipelineManager",
    "WakeWordResult",
]
