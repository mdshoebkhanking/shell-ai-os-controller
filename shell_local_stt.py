#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from shell_safe_executor import god_tier_tool as function_tool


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def local_stt_enabled() -> bool:
    return _truthy(os.environ.get("SHELL_LOCAL_STT_ENABLED"))


def sherpa_onnx_installed() -> bool:
    return importlib.util.find_spec("sherpa_onnx") is not None


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _path_from_env(name: str) -> Path | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    return Path(raw).expanduser()


def _prefer_int8_key(path: Path) -> tuple[int, str]:
    return (0 if "int8" in path.name.lower() else 1, path.name.lower())


def _first_existing(paths: Iterable[Path | None]) -> Path | None:
    for path in paths:
        if path and path.is_file():
            return path
    return None


def _find_model_file(model_dir: Path | None, *patterns: str) -> Path | None:
    if model_dir is None or not model_dir.exists():
        return None
    found: list[Path] = []
    for pattern in patterns:
        found.extend(path for path in model_dir.rglob(pattern) if path.is_file())
    if not found:
        return None
    return sorted(found, key=_prefer_int8_key)[0]


@dataclass(frozen=True)
class LocalSTTConfig:
    enabled: bool = False
    model_kind: str = "auto"
    model_dir: Path | None = None
    tokens: Path | None = None
    encoder: Path | None = None
    decoder: Path | None = None
    joiner: Path | None = None
    zipformer2_ctc: Path | None = None
    paraformer_encoder: Path | None = None
    paraformer_decoder: Path | None = None
    wenet_ctc: Path | None = None
    sample_rate: int = 16000
    feature_dim: int = 80
    num_threads: int = 1
    provider: str = "cpu"
    decoding_method: str = "greedy_search"
    max_active_paths: int = 4
    tail_padding_s: float = 0.30
    hotwords_file: str = ""
    hotwords_score: float = 1.5

    @classmethod
    def from_environment(cls) -> "LocalSTTConfig":
        model_dir = _path_from_env("SHELL_LOCAL_STT_MODEL_DIR")
        tokens = _first_existing(
            [
                _path_from_env("SHELL_LOCAL_STT_TOKENS"),
                _find_model_file(model_dir, "tokens.txt"),
            ]
        )
        return cls(
            enabled=local_stt_enabled(),
            model_kind=str(os.environ.get("SHELL_LOCAL_STT_MODEL_KIND", "auto") or "auto").strip().lower(),
            model_dir=model_dir,
            tokens=tokens,
            encoder=_first_existing(
                [
                    _path_from_env("SHELL_LOCAL_STT_ENCODER"),
                    _find_model_file(model_dir, "encoder*.onnx"),
                ]
            ),
            decoder=_first_existing(
                [
                    _path_from_env("SHELL_LOCAL_STT_DECODER"),
                    _find_model_file(model_dir, "decoder*.onnx"),
                ]
            ),
            joiner=_first_existing(
                [
                    _path_from_env("SHELL_LOCAL_STT_JOINER"),
                    _find_model_file(model_dir, "joiner*.onnx"),
                ]
            ),
            zipformer2_ctc=_first_existing(
                [
                    _path_from_env("SHELL_LOCAL_STT_ZIPFORMER2_CTC"),
                    _find_model_file(model_dir, "*ctc*.onnx"),
                ]
            ),
            paraformer_encoder=_first_existing(
                [
                    _path_from_env("SHELL_LOCAL_STT_PARAFORMER_ENCODER"),
                    _find_model_file(model_dir, "encoder*.onnx"),
                ]
            ),
            paraformer_decoder=_first_existing(
                [
                    _path_from_env("SHELL_LOCAL_STT_PARAFORMER_DECODER"),
                    _find_model_file(model_dir, "decoder*.onnx"),
                ]
            ),
            wenet_ctc=_first_existing(
                [
                    _path_from_env("SHELL_LOCAL_STT_WENET_CTC"),
                    _find_model_file(model_dir, "*wenet*.onnx", "model-streaming.onnx"),
                ]
            ),
            sample_rate=_env_int("SHELL_LOCAL_STT_SAMPLE_RATE", 16000, minimum=8000, maximum=48000),
            feature_dim=_env_int("SHELL_LOCAL_STT_FEATURE_DIM", 80, minimum=40, maximum=128),
            num_threads=_env_int("SHELL_LOCAL_STT_THREADS", 1, minimum=1, maximum=8),
            provider=str(os.environ.get("SHELL_LOCAL_STT_PROVIDER", "cpu") or "cpu").strip().lower(),
            decoding_method=str(
                os.environ.get("SHELL_LOCAL_STT_DECODING_METHOD", "greedy_search") or "greedy_search"
            ).strip(),
            max_active_paths=_env_int("SHELL_LOCAL_STT_MAX_ACTIVE_PATHS", 4, minimum=1, maximum=32),
            tail_padding_s=_env_float("SHELL_LOCAL_STT_TAIL_PADDING_S", 0.30, minimum=0.05, maximum=1.0),
            hotwords_file=str(os.environ.get("SHELL_LOCAL_STT_HOTWORDS_FILE", "") or ""),
            hotwords_score=_env_float("SHELL_LOCAL_STT_HOTWORDS_SCORE", 1.5, minimum=0.0, maximum=10.0),
        )

    def configured_kind(self) -> str:
        kind = self.model_kind
        if kind == "auto":
            if self.tokens and self.encoder and self.decoder and self.joiner:
                return "transducer"
            if self.tokens and self.zipformer2_ctc:
                return "zipformer2_ctc"
            if self.tokens and self.paraformer_encoder and self.paraformer_decoder:
                return "paraformer"
            if self.tokens and self.wenet_ctc:
                return "wenet_ctc"
        return kind

    def missing_reason(self) -> str:
        if not self.enabled:
            return "SHELL_LOCAL_STT_ENABLED=0"
        if not sherpa_onnx_installed():
            return "sherpa-onnx is not installed"
        kind = self.configured_kind()
        if kind == "transducer" and self.tokens and self.encoder and self.decoder and self.joiner:
            return ""
        if kind == "zipformer2_ctc" and self.tokens and self.zipformer2_ctc:
            return ""
        if kind == "paraformer" and self.tokens and self.paraformer_encoder and self.paraformer_decoder:
            return ""
        if kind == "wenet_ctc" and self.tokens and self.wenet_ctc:
            return ""
        return "streaming model files are missing; set SHELL_LOCAL_STT_MODEL_DIR or explicit model paths"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "installed": sherpa_onnx_installed(),
            "model_kind": self.configured_kind(),
            "model_dir": str(self.model_dir) if self.model_dir else "",
            "tokens": str(self.tokens) if self.tokens else "",
            "encoder": str(self.encoder) if self.encoder else "",
            "decoder": str(self.decoder) if self.decoder else "",
            "joiner": str(self.joiner) if self.joiner else "",
            "zipformer2_ctc": str(self.zipformer2_ctc) if self.zipformer2_ctc else "",
            "paraformer_encoder": str(self.paraformer_encoder) if self.paraformer_encoder else "",
            "paraformer_decoder": str(self.paraformer_decoder) if self.paraformer_decoder else "",
            "wenet_ctc": str(self.wenet_ctc) if self.wenet_ctc else "",
            "sample_rate": self.sample_rate,
            "feature_dim": self.feature_dim,
            "num_threads": self.num_threads,
            "provider": self.provider,
            "decoding_method": self.decoding_method,
            "ready": self.missing_reason() == "",
            "missing_reason": self.missing_reason(),
        }


@dataclass(frozen=True)
class LocalSTTResult:
    ok: bool
    text: str = ""
    partial: bool = False
    elapsed_ms: float = 0.0
    source: str = "sherpa-onnx"
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "text": self.text,
            "partial": self.partial,
            "elapsed_ms": self.elapsed_ms,
            "source": self.source,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


class SherpaOnnxStreamingSTT:
    def __init__(self, config: LocalSTTConfig | None = None):
        self.config = config or LocalSTTConfig.from_environment()
        reason = self.config.missing_reason()
        if reason:
            raise RuntimeError(reason)
        started = time.perf_counter()
        self._recognizer = self._create_recognizer()
        self._stream = self._recognizer.create_stream()
        self._last_text = ""
        self.load_ms = round((time.perf_counter() - started) * 1000.0, 3)

    @classmethod
    def from_environment(cls) -> "SherpaOnnxStreamingSTT":
        return cls(LocalSTTConfig.from_environment())

    def _create_recognizer(self):
        import sherpa_onnx  # type: ignore

        cfg = self.config
        kind = cfg.configured_kind()
        common = {
            "tokens": str(cfg.tokens),
            "num_threads": cfg.num_threads,
            "provider": cfg.provider,
            "sample_rate": cfg.sample_rate,
            "feature_dim": cfg.feature_dim,
            "decoding_method": cfg.decoding_method,
        }
        if kind == "transducer":
            return sherpa_onnx.OnlineRecognizer.from_transducer(
                **common,
                encoder=str(cfg.encoder),
                decoder=str(cfg.decoder),
                joiner=str(cfg.joiner),
                max_active_paths=cfg.max_active_paths,
                hotwords_file=cfg.hotwords_file,
                hotwords_score=cfg.hotwords_score,
            )
        if kind == "zipformer2_ctc":
            return sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(
                **common,
                model=str(cfg.zipformer2_ctc),
            )
        if kind == "paraformer":
            return sherpa_onnx.OnlineRecognizer.from_paraformer(
                **common,
                encoder=str(cfg.paraformer_encoder),
                decoder=str(cfg.paraformer_decoder),
            )
        if kind == "wenet_ctc":
            return sherpa_onnx.OnlineRecognizer.from_wenet_ctc(
                **common,
                model=str(cfg.wenet_ctc),
            )
        raise RuntimeError(f"Unsupported local STT model kind: {kind}")

    @staticmethod
    def _as_float32(audio_frame: Any):
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

    @staticmethod
    def _result_text(result: Any) -> str:
        if result is None:
            return ""
        text = getattr(result, "text", None)
        if text is not None:
            return str(text or "").strip()
        if isinstance(result, dict):
            return str(result.get("text") or result.get("result") or "").strip()
        return str(result or "").strip()

    def _decode_ready(self) -> None:
        guard = 0
        while self._recognizer.is_ready(self._stream):
            self._recognizer.decode_stream(self._stream)
            guard += 1
            if guard > 1000:
                break

    def accept_audio(self, audio_frame: Any, *, sample_rate: int | None = None) -> LocalSTTResult:
        started = time.perf_counter()
        samples = self._as_float32(audio_frame)
        if len(samples) <= 0:
            return LocalSTTResult(True, self._last_text, partial=True, elapsed_ms=0.0)
        actual_rate = int(sample_rate or self.config.sample_rate)
        self._stream.accept_waveform(actual_rate, samples)
        self._decode_ready()
        text = self._result_text(self._recognizer.get_result(self._stream))
        changed = text != self._last_text
        self._last_text = text
        return LocalSTTResult(
            True,
            text,
            partial=True,
            elapsed_ms=round((time.perf_counter() - started) * 1000.0, 3),
            metadata={"changed": changed},
        )

    def finish(self, *, sample_rate: int | None = None) -> LocalSTTResult:
        import numpy as np

        started = time.perf_counter()
        actual_rate = int(sample_rate or self.config.sample_rate)
        tail = np.zeros(int(max(1, actual_rate * self.config.tail_padding_s)), dtype=np.float32)
        self._stream.accept_waveform(actual_rate, tail)
        try:
            self._stream.input_finished()
        except Exception:
            pass
        self._decode_ready()
        text = self._result_text(self._recognizer.get_result(self._stream))
        result = LocalSTTResult(
            True,
            text,
            partial=False,
            elapsed_ms=round((time.perf_counter() - started) * 1000.0, 3),
        )
        self.reset()
        return result

    def transcribe(self, audio_frame: Any, *, sample_rate: int | None = None) -> LocalSTTResult:
        started = time.perf_counter()
        self.accept_audio(audio_frame, sample_rate=sample_rate)
        result = self.finish(sample_rate=sample_rate)
        return LocalSTTResult(
            result.ok,
            result.text,
            partial=False,
            elapsed_ms=round((time.perf_counter() - started) * 1000.0, 3),
            source=result.source,
            error=result.error,
            metadata={"load_ms": self.load_ms, **dict(result.metadata or {})},
        )

    def reset(self) -> None:
        self._stream = self._recognizer.create_stream()
        self._last_text = ""


@function_tool(category="voice")
async def local_stt_status_tool() -> dict[str, Any]:
    """Return offline sherpa-onnx STT readiness and resolved model paths."""
    cfg = LocalSTTConfig.from_environment()
    return {"ok": True, **cfg.to_dict()}


__all__ = [
    "LocalSTTConfig",
    "LocalSTTResult",
    "SherpaOnnxStreamingSTT",
    "local_stt_enabled",
    "local_stt_status_tool",
    "sherpa_onnx_installed",
]
