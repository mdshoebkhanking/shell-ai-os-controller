"""Offline TTS detection and playback for Shell.

This module never downloads models at runtime. Natural offline voice only becomes
available when a supported model/runtime has already been packaged with Shell or
explicitly pointed to through environment variables.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
RUNTIME_TTS_DIR = PROJECT_ROOT / ".shell_runtime" / "tts_audio"
DEFAULT_ENGINE_ORDER = ("kokoro", "piper")
SUPPORTED_SHELL_LANGUAGES = {"hinglish", "english", "hindi"}


@dataclass(frozen=True)
class OfflineTTSCandidate:
    engine: str
    label: str
    model_dir: Path | None
    available: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "label": self.label,
            "modelDir": str(self.model_dir) if self.model_dir else "",
            "available": self.available,
            "reason": self.reason,
        }


def _env_disabled() -> bool:
    value = os.environ.get("SHELL_OFFLINE_TTS", os.environ.get("SHELL_NATURAL_TTS", "1"))
    return str(value).strip().lower() in {"0", "false", "no", "off", "disabled"}


def _engine_setting() -> str:
    return os.environ.get("SHELL_NATURAL_TTS_ENGINE", os.environ.get("SHELL_OFFLINE_TTS_ENGINE", "auto")).strip().lower() or "auto"


def _shell_language() -> str:
    language = os.environ.get("SHELL_LANGUAGE", "").strip().lower()
    if language in SUPPORTED_SHELL_LANGUAGES:
        return language
    try:
        from shell_settings_manager import get_settings

        stored = str(get_settings().get("shell_language") or get_settings().get("language") or "").strip().lower()
        if stored in SUPPORTED_SHELL_LANGUAGES:
            return stored
    except Exception:
        pass
    return "hinglish"


def _tts_locale() -> str:
    explicit = os.environ.get("SHELL_NATURAL_TTS_LANGUAGE", "").strip().lower()
    if explicit:
        return explicit
    language = _shell_language()
    if language == "hindi":
        return "hi"
    return "en-us"


def _candidate_model_dirs(engine: str) -> list[Path]:
    dirs: list[Path] = []
    explicit = os.environ.get("SHELL_NATURAL_TTS_MODEL_DIR") or os.environ.get("SHELL_OFFLINE_TTS_MODEL_DIR")
    if explicit:
        dirs.append(Path(explicit).expanduser())
    language = _shell_language()
    dirs.extend(
        [
            PROJECT_ROOT / "models" / "tts" / engine / language,
            PROJECT_ROOT / "assets" / "voice" / engine / language,
            PROJECT_ROOT / ".shell_runtime" / "models" / "tts" / engine / language,
            PROJECT_ROOT / "models" / "tts" / engine,
            PROJECT_ROOT / "assets" / "voice" / engine,
            PROJECT_ROOT / ".shell_runtime" / "models" / "tts" / engine,
        ]
    )
    return dirs


def _find_first_existing(paths: list[Path], patterns: tuple[str, ...]) -> Path | None:
    for base in paths:
        if not base.exists():
            continue
        for pattern in patterns:
            matches = sorted(base.glob(pattern))
            if matches:
                return matches[0]
    return None


def _find_kokoro_model(paths: list[Path]) -> tuple[Path | None, Path | None, Path | None]:
    model = _find_first_existing(paths, ("kokoro*.onnx", "model*.onnx", "*.onnx"))
    voices = _find_first_existing(paths, ("voices*.bin", "voices*.json", "*.bin"))
    model_dir = model.parent if model else (voices.parent if voices else None)
    return model, voices, model_dir


def _find_piper_model(paths: list[Path]) -> tuple[Path | None, Path | None, Path | None]:
    model = _find_first_existing(paths, ("*.onnx",))
    config = _find_first_existing(paths, ("*.onnx.json", "*.json"))
    model_dir = model.parent if model else (config.parent if config else None)
    return model, config, model_dir


def _kokoro_status() -> OfflineTTSCandidate:
    paths = _candidate_model_dirs("kokoro")
    model, voices, model_dir = _find_kokoro_model(paths)
    if not model or not voices:
        return OfflineTTSCandidate(
            "kokoro",
            "Kokoro ONNX natural offline voice",
            model_dir,
            False,
            "Kokoro model and voices file are not bundled.",
        )
    try:
        import kokoro_onnx  # noqa: F401
    except Exception:
        return OfflineTTSCandidate(
            "kokoro",
            "Kokoro ONNX natural offline voice",
            model_dir,
            False,
            "kokoro_onnx runtime is not installed in the app bundle.",
        )
    return OfflineTTSCandidate(
        "kokoro",
        "Kokoro ONNX natural offline voice",
        model_dir,
        True,
        "ready",
    )


def _piper_status() -> OfflineTTSCandidate:
    paths = _candidate_model_dirs("piper")
    model, _config, model_dir = _find_piper_model(paths)
    piper_bin = os.environ.get("PIPER_BIN") or shutil.which("piper")
    if not model:
        return OfflineTTSCandidate(
            "piper",
            "Piper offline voice",
            model_dir,
            False,
            "Piper voice model is not bundled.",
        )
    if not piper_bin:
        return OfflineTTSCandidate(
            "piper",
            "Piper offline voice",
            model_dir,
            False,
            "Piper executable is not installed in the app bundle.",
        )
    return OfflineTTSCandidate("piper", "Piper offline voice", model_dir, True, "ready")


def _candidate_statuses() -> list[OfflineTTSCandidate]:
    return [_kokoro_status(), _piper_status()]


def offline_tts_status() -> dict[str, Any]:
    """Return structured natural/offline TTS readiness without side effects."""
    if _env_disabled():
        return {
            "success": True,
            "available": False,
            "engine": "disabled",
            "label": "Offline TTS disabled",
            "language": _shell_language(),
            "locale": _tts_locale(),
            "reason": "SHELL_OFFLINE_TTS is disabled.",
            "candidates": [],
        }

    requested = _engine_setting()
    candidates = _candidate_statuses()
    if requested != "auto":
        candidates = [candidate for candidate in candidates if candidate.engine == requested]
        if not candidates:
            return {
                "success": True,
                "available": False,
                "engine": requested,
                "label": requested,
                "language": _shell_language(),
                "locale": _tts_locale(),
                "reason": f"Unsupported offline TTS engine: {requested}",
                "candidates": [],
            }

    available = next((candidate for candidate in candidates if candidate.available), None)
    if available:
        return {
            "success": True,
            "available": True,
            "engine": available.engine,
            "label": available.label,
            "language": _shell_language(),
            "locale": _tts_locale(),
            "modelDir": str(available.model_dir) if available.model_dir else "",
            "reason": "ready",
            "candidates": [candidate.as_dict() for candidate in candidates],
        }

    return {
        "success": True,
        "available": False,
        "engine": "fallback",
        "label": "OS TTS fallback",
        "language": _shell_language(),
        "locale": _tts_locale(),
        "reason": "No packaged natural offline TTS model is ready; Shell will use local OS voice fallback.",
        "candidates": [candidate.as_dict() for candidate in candidates],
    }


def _playback_command(wav_path: Path) -> list[str] | None:
    system = platform.system().lower()
    if system == "darwin":
        afplay = shutil.which("afplay") or ("/usr/bin/afplay" if Path("/usr/bin/afplay").exists() else "")
        return [afplay, str(wav_path)] if afplay else None
    if system == "windows":
        powershell = shutil.which("powershell") or shutil.which("powershell.exe")
        if not powershell:
            return None
        escaped = str(wav_path).replace("'", "''")
        script = (
            f"$player = New-Object Media.SoundPlayer '{escaped}'; "
            "$player.Load(); "
            "$player.PlaySync()"
        )
        return [powershell, "-NoProfile", "-Command", script]
    for exe_name in ("paplay", "aplay", "pw-play"):
        exe = shutil.which(exe_name)
        if exe:
            return [exe, str(wav_path)]
    return None


def _play_wav_async(wav_path: Path) -> subprocess.Popen[Any] | None:
    command = _playback_command(wav_path)
    if not command:
        return None
    return subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def _tts_audio_path(engine: str) -> Path:
    RUNTIME_TTS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_TTS_DIR / f"{engine}-{int(time.time() * 1000)}.wav"


def _write_float_wav(path: Path, samples: Any, sample_rate: int) -> None:
    import numpy as np

    audio = np.asarray(samples, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.reshape(-1)
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(int(sample_rate))
        wav_file.writeframes(pcm)


def _speak_kokoro(text: str) -> dict[str, Any]:
    model, voices, _model_dir = _find_kokoro_model(_candidate_model_dirs("kokoro"))
    if not model or not voices:
        return {"success": False, "available": False, "engine": "kokoro", "message": "Kokoro model assets are missing."}
    try:
        from kokoro_onnx import Kokoro
    except Exception as exc:
        return {"success": False, "available": False, "engine": "kokoro", "message": f"kokoro_onnx unavailable: {exc}"}

    voice = os.environ.get("SHELL_NATURAL_TTS_VOICE", "af_heart").strip() or "af_heart"
    language = _tts_locale()
    speed = float(os.environ.get("SHELL_NATURAL_TTS_SPEED", "1.0") or "1.0")
    wav_path = _tts_audio_path("kokoro")

    engine = Kokoro(str(model), str(voices))
    samples, sample_rate = engine.create(text, voice=voice, speed=speed, lang=language)
    _write_float_wav(wav_path, samples, int(sample_rate))
    process = _play_wav_async(wav_path)
    if not process:
        return {"success": False, "available": True, "engine": "kokoro", "message": "No local WAV playback command found."}
    return {
        "success": True,
        "available": True,
        "engine": "kokoro",
        "voice": voice,
        "chars": len(text),
        "audioPath": str(wav_path),
        "_process": process,
    }


def _speak_piper(text: str) -> dict[str, Any]:
    model, _config, _model_dir = _find_piper_model(_candidate_model_dirs("piper"))
    piper_bin = os.environ.get("PIPER_BIN") or shutil.which("piper")
    if not model:
        return {"success": False, "available": False, "engine": "piper", "message": "Piper model assets are missing."}
    if not piper_bin:
        return {"success": False, "available": False, "engine": "piper", "message": "Piper executable is missing."}

    wav_path = _tts_audio_path("piper")
    timeout_s = float(os.environ.get("SHELL_NATURAL_TTS_TIMEOUT_S", "20") or "20")
    completed = subprocess.run(
        [piper_bin, "--model", str(model), "--output_file", str(wav_path)],
        input=text,
        text=True,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    if completed.returncode != 0 or not wav_path.exists():
        message = (completed.stderr or completed.stdout or f"Piper failed with exit code {completed.returncode}").strip()
        return {"success": False, "available": True, "engine": "piper", "message": message}

    process = _play_wav_async(wav_path)
    if not process:
        return {"success": False, "available": True, "engine": "piper", "message": "No local WAV playback command found."}
    return {
        "success": True,
        "available": True,
        "engine": "piper",
        "chars": len(text),
        "audioPath": str(wav_path),
        "_process": process,
    }


def speak_offline_tts(text: str) -> dict[str, Any]:
    """Speak text through packaged offline TTS when available."""
    speech_text = " ".join(str(text or "").strip().split())
    if not speech_text:
        return {"success": False, "available": False, "engine": "", "message": "No speech text provided."}

    status = offline_tts_status()
    if not status.get("available"):
        return {
            "success": False,
            "available": False,
            "engine": status.get("engine", "fallback"),
            "message": status.get("reason", "Offline TTS is unavailable."),
            "status": status,
        }

    engine = str(status.get("engine") or "").lower()
    try:
        if engine == "kokoro":
            return _speak_kokoro(speech_text)
        if engine == "piper":
            return _speak_piper(speech_text)
    except Exception as exc:
        return {"success": False, "available": True, "engine": engine, "message": str(exc)}

    return {"success": False, "available": False, "engine": engine, "message": f"Unsupported offline TTS engine: {engine}"}


__all__ = ["offline_tts_status", "speak_offline_tts"]
