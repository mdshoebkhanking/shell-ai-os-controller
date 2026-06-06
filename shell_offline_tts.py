"""Offline TTS detection and playback for Shell.

This module never downloads models at runtime. Natural offline voice only becomes
available when a supported model/runtime has already been packaged with Shell or
explicitly pointed to through environment variables.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
RUNTIME_TTS_DIR = PROJECT_ROOT / ".shell_runtime" / "tts_audio"
DEFAULT_ENGINE_ORDER = ("kokoro",)
PLAYBACK_STARTUP_GRACE_S = 0.12
SUPPORTED_SHELL_LANGUAGE_ORDER = ("hinglish", "english", "hindi")
SUPPORTED_SHELL_LANGUAGES = set(SUPPORTED_SHELL_LANGUAGE_ORDER)
KOKORO_MODEL_FAMILY = "Kokoro-82M"
KOKORO_LANGUAGE_LOCALES = {
    "english": "en-us",
    "hinglish": "en-us",
    "hindi": "hi",
}
KOKORO_DEFAULT_VOICES = {
    "english": "af_heart",
    "hinglish": "af_heart",
    "hindi": "hf_alpha",
}
KOKORO_REALISTIC_FEMALE_VOICE = "af_heart"
KOKORO_HINDI_NATIVE_VOICE = "hf_alpha"
HINGLISH_ROUTING_HINTS = frozenset(
    {
        "aap",
        "ab",
        "abhi",
        "acha",
        "achha",
        "achhi",
        "awaaz",
        "awaz",
        "baat",
        "badiya",
        "bhai",
        "bigad",
        "bol",
        "bolo",
        "bolne",
        "bolna",
        "bolra",
        "bolta",
        "bolti",
        "chahiye",
        "dekho",
        "fir",
        "hai",
        "hain",
        "han",
        "haan",
        "hoga",
        "ho",
        "hoon",
        "horra",
        "hoti",
        "hotti",
        "hun",
        "ja",
        "jaa",
        "jarra",
        "ka",
        "kaam",
        "kar",
        "karra",
        "karri",
        "karna",
        "karo",
        "ke",
        "kaise",
        "kaisa",
        "ki",
        "ko",
        "kya",
        "kyun",
        "lagra",
        "lagta",
        "main",
        "mai",
        "mat",
        "mujhe",
        "na",
        "nahi",
        "nai",
        "pahle",
        "raha",
        "rahe",
        "rahi",
        "samjhe",
        "sahi",
        "sab",
        "se",
        "shuru",
        "theek",
        "thik",
        "tum",
        "tumhe",
        "yah",
        "yeh",
    }
)
HINGLISH_SHORT_CLAUSE_HINTS = frozenset(
    {
        "acha",
        "achha",
        "achhi",
        "awaaz",
        "awaz",
        "bhai",
        "haan",
        "han",
        "kaise",
        "kya",
        "nahi",
        "nai",
        "samjhe",
        "sahi",
    }
)
ROMAN_HINDI_PRONUNCIATION_WORDS = {
    "aap": "आप",
    "ab": "अब",
    "abhi": "अभी",
    "acha": "अच्छा",
    "achha": "अच्छा",
    "achhi": "अच्छी",
    "accent": "एक्सेंट",
    "acsent": "एक्सेंट",
    "api": "ए पी आई",
    "awaaz": "आवाज",
    "awaz": "आवाज",
    "baat": "बात",
    "badiya": "बढ़िया",
    "bhai": "भाई",
    "bigad": "बिगड़",
    "bol": "बोल",
    "bolo": "बोलो",
    "bolna": "बोलना",
    "bolne": "बोलने",
    "bolra": "बोल रहा",
    "bolta": "बोलता",
    "bolti": "बोलती",
    "chahiye": "चाहिए",
    "dekho": "देखो",
    "gemini": "जेमिनी",
    "hai": "है",
    "hain": "हैं",
    "han": "हां",
    "haan": "हां",
    "hoga": "होगा",
    "ho": "हो",
    "hoon": "हूं",
    "horra": "हो रहा",
    "hoti": "होती",
    "hotti": "होती",
    "hun": "हूं",
    "ja": "जा",
    "jaa": "जा",
    "jarra": "जा रहा",
    "ka": "का",
    "kaam": "काम",
    "kar": "कर",
    "karna": "करना",
    "karo": "करो",
    "karra": "कर रहा",
    "karri": "कर रही",
    "ke": "के",
    "key": "की",
    "ki": "की",
    "ko": "को",
    "kaise": "कैसे",
    "kaisa": "कैसा",
    "kya": "क्या",
    "kyun": "क्यों",
    "lagra": "लग रहा",
    "lagta": "लगता",
    "main": "मैं",
    "mai": "मैं",
    "mat": "मत",
    "mujhe": "मुझे",
    "na": "ना",
    "nahi": "नहीं",
    "nai": "नहीं",
    "offline": "ऑफलाइन",
    "online": "ऑनलाइन",
    "pahle": "पहले",
    "problem": "प्रॉब्लम",
    "raha": "रहा",
    "rahe": "रहे",
    "rahi": "रही",
    "route": "रूट",
    "sab": "सब",
    "samjhe": "समझे",
    "sahi": "सही",
    "se": "से",
    "shell": "शेल",
    "shuru": "शुरू",
    "theek": "ठीक",
    "thik": "ठीक",
    "tum": "तुम",
    "tumhe": "तुम्हें",
    "user": "यूजर",
    "voice": "वॉइस",
    "work": "वर्क",
    "yah": "यह",
    "yeh": "यह",
}


@dataclass(frozen=True)
class OfflineTTSCandidate:
    engine: str
    label: str
    model_dir: Path | None
    available: bool
    reason: str
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "engine": self.engine,
            "label": self.label,
            "modelDir": str(self.model_dir) if self.model_dir else "",
            "available": self.available,
            "reason": self.reason,
        }
        if self.metadata:
            payload.update(self.metadata)
        return payload


@dataclass(frozen=True)
class KokoroTTSSegment:
    text: str
    language: str
    locale: str
    voice: str

    def as_dict(self) -> dict[str, str]:
        return {
            "text": self.text,
            "language": self.language,
            "locale": self.locale,
            "voice": self.voice,
        }


def _env_disabled() -> bool:
    value = os.environ.get("SHELL_OFFLINE_TTS", os.environ.get("SHELL_NATURAL_TTS", "1"))
    return str(value).strip().lower() in {"0", "false", "no", "off", "disabled"}


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            key = str(path.expanduser().resolve())
            normalized = Path(key)
        except Exception:
            normalized = path.expanduser()
            key = str(normalized)
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _runtime_roots() -> list[Path]:
    """Candidate install roots for source, PyInstaller, and installed layouts."""
    roots: list[Path] = []
    for env_name in ("SHELL_APP_ROOT", "SHELL_INSTALL_ROOT"):
        explicit_root = os.environ.get(env_name, "").strip()
        if explicit_root:
            roots.append(Path(explicit_root).expanduser())

    if getattr(sys, "frozen", False):
        try:
            exe_dir = Path(sys.executable).resolve().parent
            roots.extend([exe_dir, exe_dir.parent])
        except Exception:
            pass
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            try:
                meipass_dir = Path(str(meipass)).resolve()
                roots.extend([meipass_dir, meipass_dir.parent])
            except Exception:
                pass

    roots.extend([PROJECT_ROOT, PROJECT_ROOT.parent, Path.cwd()])
    return _unique_paths(roots)


def _runtime_writable_root() -> Path:
    explicit = os.environ.get("SHELL_RUNTIME_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    if getattr(sys, "frozen", False):
        try:
            return Path(sys.executable).resolve().parent.parent / ".shell_runtime"
        except Exception:
            pass
    return PROJECT_ROOT / ".shell_runtime"


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
    return _kokoro_locale_for(_shell_language())


def _kokoro_locale_for(language: str) -> str:
    specific = os.environ.get(f"SHELL_NATURAL_TTS_LANGUAGE_{language.upper()}", "").strip().lower()
    if specific:
        return specific
    return KOKORO_LANGUAGE_LOCALES.get(language, "en-us")


def _kokoro_voice_for(language: str) -> str:
    specific = os.environ.get(f"SHELL_NATURAL_TTS_VOICE_{language.upper()}", "").strip()
    if specific:
        return specific
    shared = os.environ.get("SHELL_NATURAL_TTS_VOICE", "").strip()
    if shared:
        return shared
    return KOKORO_DEFAULT_VOICES.get(language, KOKORO_DEFAULT_VOICES["hinglish"])


def _kokoro_routing_mode() -> str:
    mode = os.environ.get("SHELL_HINGLISH_TTS_ROUTING", "bilingual").strip().lower()
    allowed_modes = {"balanced", "bilingual", "aggressive", "english", "native-hindi"}
    return mode if mode in allowed_modes else "bilingual"


def _kokoro_metadata(model: Path | None = None, voices: Path | None = None) -> dict[str, Any]:
    language = _shell_language()
    payload: dict[str, Any] = {
        "modelFamily": KOKORO_MODEL_FAMILY,
        "runtime": "kokoro_onnx",
        "languageSupport": list(SUPPORTED_SHELL_LANGUAGE_ORDER),
        "routing": _kokoro_routing_mode(),
        "activeVoice": _kokoro_voice_for(language),
        "voices": {lang: _kokoro_voice_for(lang) for lang in SUPPORTED_SHELL_LANGUAGE_ORDER},
        "preferredVoiceProfile": "realistic-female",
        "preferredFemaleVoice": KOKORO_REALISTIC_FEMALE_VOICE,
        "nativeHindiVoice": KOKORO_HINDI_NATIVE_VOICE,
        "hinglishStrategy": (
            "English clauses use af_heart; Hindi/Hinglish clauses use hf_alpha with "
            "native Hindi pronunciation rewriting for a cleaner bilingual accent."
        ),
    }
    if model:
        payload["modelPath"] = str(model)
    if voices:
        payload["voicesPath"] = str(voices)
    return payload


def _short_runtime_error(exc: BaseException) -> str:
    message = f"{type(exc).__name__}: {exc}"
    return message if len(message) <= 500 else message[:497] + "..."


def _candidate_model_dirs(engine: str) -> list[Path]:
    dirs: list[Path] = []
    explicit = os.environ.get("SHELL_NATURAL_TTS_MODEL_DIR") or os.environ.get("SHELL_OFFLINE_TTS_MODEL_DIR")
    if explicit:
        dirs.append(Path(explicit).expanduser())
    language = _shell_language()
    for root in _runtime_roots():
        dirs.extend(
            [
                root / "models" / "tts" / engine / language,
                root / "assets" / "voice" / engine / language,
                root / ".shell_runtime" / "models" / "tts" / engine / language,
                root / "models" / "tts" / engine,
                root / "assets" / "voice" / engine,
                root / ".shell_runtime" / "models" / "tts" / engine,
            ]
        )
    return _unique_paths(dirs)


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
            _kokoro_metadata(model, voices),
        )
    try:
        import kokoro_onnx  # noqa: F401
    except Exception as exc:
        metadata = _kokoro_metadata(model, voices)
        metadata["runtimeError"] = _short_runtime_error(exc)
        return OfflineTTSCandidate(
            "kokoro",
            "Kokoro ONNX natural offline voice",
            model_dir,
            False,
            f"kokoro_onnx runtime is not installed in the app bundle: {_short_runtime_error(exc)}",
            metadata,
        )
    return OfflineTTSCandidate(
        "kokoro",
        "Kokoro ONNX natural offline voice",
        model_dir,
        True,
        "ready",
        _kokoro_metadata(model, voices),
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
    # Shell's packaged offline voice is Kokoro. Do not silently switch to
    # platform/system voices because they steal focus in the Windows EXE.
    return [_kokoro_status()]


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
        metadata = available.metadata or {}
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
            **metadata,
        }

    return {
        "success": True,
        "available": False,
        "engine": "kokoro",
        "label": "Kokoro offline voice unavailable",
        "language": _shell_language(),
        "locale": _tts_locale(),
        "reason": "Kokoro offline voice is not ready. Shell will not use local OS TTS fallback.",
        "candidates": [candidate.as_dict() for candidate in candidates],
    }


def _playback_command(wav_path: Path) -> list[str] | None:
    system = platform.system().lower()
    if system == "darwin":
        afplay = shutil.which("afplay") or ("/usr/bin/afplay" if Path("/usr/bin/afplay").exists() else "")
        return [afplay, str(wav_path)] if afplay else None
    if system == "windows":
        return None
    for exe_name in ("paplay", "aplay", "pw-play"):
        exe = shutil.which(exe_name)
        if exe:
            return [exe, str(wav_path)]
    return None


class _WindowsWinsoundPlayback:
    def __init__(self, wav_path: Path) -> None:
        import winsound

        self._winsound = winsound
        self._stopped = threading.Event()
        self._wav_path = wav_path
        winsound.PlaySound(
            str(wav_path),
            winsound.SND_FILENAME | winsound.SND_ASYNC,
        )

    def poll(self) -> int | None:
        return 0 if self._stopped.is_set() else None

    def terminate(self) -> None:
        self._stopped.set()
        try:
            self._winsound.PlaySound(None, self._winsound.SND_PURGE)
        except Exception:
            pass

    def wait(self, timeout: float | None = None) -> int:
        if timeout:
            self._stopped.wait(timeout)
        return 0 if self._stopped.is_set() else 0

    def kill(self) -> None:
        self.terminate()


def _play_wav_with_winsound(wav_path: Path) -> Any | None:
    if platform.system().lower() != "windows":
        return None
    try:
        return _WindowsWinsoundPlayback(wav_path)
    except Exception:
        return None


def _play_wav_async(wav_path: Path) -> Any | None:
    winsound_playback = _play_wav_with_winsound(wav_path)
    if winsound_playback is not None:
        return winsound_playback

    command = _playback_command(wav_path)
    if not command:
        return None
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        return None
    time.sleep(PLAYBACK_STARTUP_GRACE_S)
    return None if process.poll() not in (None, 0) else process


def _tts_audio_path(engine: str) -> Path:
    runtime_tts_dir = _runtime_writable_root() / "tts_audio"
    runtime_tts_dir.mkdir(parents=True, exist_ok=True)
    return runtime_tts_dir / f"{engine}-{int(time.time() * 1000)}.wav"


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


def _audio_reactivity_metadata(samples: Any, sample_rate: int) -> dict[str, Any]:
    try:
        import numpy as np

        audio = np.asarray(samples, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.reshape(-1)
        audio = np.clip(audio, -1.0, 1.0)
        rate = max(1, int(sample_rate or 0))
        if audio.size == 0:
            return {"durationMs": 0, "amplitudeFrameMs": 80, "amplitudeFrames": []}

        frame_ms = 70
        frame_size = max(1, int(rate * frame_ms / 1000))
        rms_values = []
        for start in range(0, int(audio.size), frame_size):
            frame = audio[start : start + frame_size]
            if frame.size == 0:
                continue
            rms_values.append(float(np.sqrt(np.mean(np.square(frame)))))

        if not rms_values:
            return {
                "durationMs": int(round(audio.size / rate * 1000)),
                "amplitudeFrameMs": frame_ms,
                "amplitudeFrames": [],
            }

        normalizer = max(float(np.percentile(rms_values, 90)), 0.015)
        frames = [round(max(0.0, min(1.0, (value / normalizer) * 0.82)), 3) for value in rms_values[:220]]
        return {
            "durationMs": int(round(audio.size / rate * 1000)),
            "amplitudeFrameMs": frame_ms,
            "amplitudeFrames": frames,
        }
    except Exception:
        return {"durationMs": 0, "amplitudeFrameMs": 80, "amplitudeFrames": []}


def _wav_reactivity_metadata(wav_path: Path) -> dict[str, Any]:
    try:
        import numpy as np

        with wave.open(str(wav_path), "rb") as wav_file:
            sample_rate = int(wav_file.getframerate())
            channels = max(1, int(wav_file.getnchannels()))
            sample_width = int(wav_file.getsampwidth())
            frames = wav_file.readframes(wav_file.getnframes())
        if sample_width != 2 or not frames:
            return {"durationMs": 0, "amplitudeFrameMs": 80, "amplitudeFrames": []}
        audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1)
        return _audio_reactivity_metadata(audio, sample_rate)
    except Exception:
        return {"durationMs": 0, "amplitudeFrameMs": 80, "amplitudeFrames": []}


def _contains_devanagari(text: str) -> bool:
    return any(0x0900 <= ord(char) <= 0x097F for char in text)


def _roman_hindi_score(text: str) -> tuple[int, int]:
    words = re.findall(r"[a-zA-Z]+", text.lower())
    score = sum(1 for word in words if word in HINGLISH_ROUTING_HINTS)
    return score, len(words)


def _classify_hinglish_clause(text: str) -> str:
    if _contains_devanagari(text):
        return "hindi"
    mode = _kokoro_routing_mode()
    score, word_count = _roman_hindi_score(text)
    if mode == "balanced":
        return "english"
    if mode == "native-hindi" and score > 0:
        return "hindi"
    if mode == "aggressive" and score > 0:
        return "hindi"
    if mode == "bilingual" and score >= 2:
        return "hindi"
    if mode == "bilingual" and score == 1 and word_count <= 4:
        words = re.findall(r"[a-zA-Z]+", text.lower())
        if any(word in HINGLISH_SHORT_CLAUSE_HINTS for word in words):
            return "hindi"
    return "english"


def _kokoro_synthesis_text_for(segment: KokoroTTSSegment) -> str:
    if segment.language != "hindi" or _contains_devanagari(segment.text):
        return segment.text

    def replace_word(match: re.Match[str]) -> str:
        return ROMAN_HINDI_PRONUNCIATION_WORDS.get(match.group(0).lower(), match.group(0))

    rewritten = re.sub(r"[a-zA-Z]+", replace_word, segment.text)
    if _contains_devanagari(rewritten):
        return rewritten
    return segment.text


def _split_speech_clauses(text: str) -> list[str]:
    parts = re.split(r"([.!?;:,]+)", text)
    clauses: list[str] = []
    current = ""
    for part in parts:
        if not part:
            continue
        if re.fullmatch(r"[.!?;:,]+", part):
            current = f"{current}{part}".strip()
            if current:
                clauses.append(current)
                current = ""
            continue
        if current:
            clauses.append(current.strip())
        current = part.strip()
    if current.strip():
        clauses.append(current.strip())
    return [clause for clause in clauses if clause]


def _merge_adjacent_segments(segments: list[KokoroTTSSegment]) -> list[KokoroTTSSegment]:
    merged: list[KokoroTTSSegment] = []
    for segment in segments:
        if not merged:
            merged.append(segment)
            continue
        previous = merged[-1]
        if previous.language == segment.language and previous.locale == segment.locale and previous.voice == segment.voice:
            merged[-1] = KokoroTTSSegment(
                text=f"{previous.text} {segment.text}".strip(),
                language=previous.language,
                locale=previous.locale,
                voice=previous.voice,
            )
            continue
        merged.append(segment)
    return merged


def _prepare_kokoro_segments(text: str) -> list[KokoroTTSSegment]:
    speech_text = " ".join(str(text or "").strip().split())
    if not speech_text:
        return []

    shell_language = _shell_language()
    if shell_language != "hinglish" or _kokoro_routing_mode() == "english":
        language = "english" if _kokoro_routing_mode() == "english" else shell_language
        return [
            KokoroTTSSegment(
                text=speech_text,
                language=language,
                locale=_kokoro_locale_for(language),
                voice=_kokoro_voice_for(language),
            )
        ]

    segments = [
        KokoroTTSSegment(
            text=clause,
            language=(language := _classify_hinglish_clause(clause)),
            locale=_kokoro_locale_for(language),
            voice=_kokoro_voice_for(language),
        )
        for clause in _split_speech_clauses(speech_text)
    ]
    return _merge_adjacent_segments(segments)


def _join_kokoro_audio(rendered_segments: list[tuple[Any, int]]) -> tuple[Any, int]:
    import numpy as np

    if not rendered_segments:
        return np.asarray([], dtype=np.float32), 24000
    if len(rendered_segments) == 1:
        return rendered_segments[0]

    sample_rate = int(rendered_segments[0][1])
    silence = np.zeros(int(sample_rate * 0.08), dtype=np.float32)
    pieces = []
    for index, (samples, segment_rate) in enumerate(rendered_segments):
        if int(segment_rate) != sample_rate:
            raise ValueError("Kokoro returned inconsistent sample rates across routed segments.")
        pieces.append(np.asarray(samples, dtype=np.float32).reshape(-1))
        if index < len(rendered_segments) - 1:
            pieces.append(silence)
    return np.concatenate(pieces), sample_rate


def _kokoro_espeak_config() -> Any | None:
    try:
        import espeakng_loader
        from kokoro_onnx.config import EspeakConfig

        if hasattr(espeakng_loader, "make_library_available"):
            espeakng_loader.make_library_available()
        data_path = Path(str(espeakng_loader.get_data_path()))
        library_path = Path(str(espeakng_loader.get_library_path()))
        _prepare_kokoro_espeak_data_layout(data_path)
        _patch_kokoro_espeak_absolute_data_path()
        os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", str(library_path))
        os.environ.setdefault("PHONEMIZER_ESPEAK_DATA_PATH", str(data_path))
        return EspeakConfig(
            lib_path=str(library_path),
            data_path=str(data_path),
        )
    except Exception:
        return None


def _kokoro_espeak_native_data_arg(data_path: Any) -> Any:
    if platform.system().lower() != "darwin" or data_path is None:
        return data_path
    try:
        candidate = Path(os.fsdecode(data_path))
    except TypeError:
        return data_path
    if not candidate.is_absolute() or candidate.name != "espeak-ng-data" or not (candidate / "phontab").exists():
        return data_path
    try:
        relative = os.path.relpath(candidate, Path.cwd())
    except ValueError:
        return data_path
    return relative if Path(relative).is_dir() else data_path


def _patch_kokoro_espeak_absolute_data_path() -> None:
    if platform.system().lower() != "darwin":
        return
    try:
        from phonemizer.backend.espeak.api import EspeakAPI
    except Exception:
        return
    if getattr(EspeakAPI, "_shellai_relative_data_path_patch", False):
        return

    original_init = EspeakAPI.__init__

    def shellai_init(self: Any, library: Any, data_path: Any) -> None:
        original_init(self, library, _kokoro_espeak_native_data_arg(data_path))

    EspeakAPI.__init__ = shellai_init
    EspeakAPI._shellai_relative_data_path_patch = True


def _prepare_kokoro_espeak_data_layout(data_path: Path) -> None:
    if not data_path.exists() or not (data_path / "phontab").exists():
        return
    compat_root = data_path.parent.parent
    if (compat_root / "phontab").exists():
        return
    # PyInstaller copies this layout during build. For source/dev runs, create
    # the same compatibility layout expected by the packaged espeak library.
    if getattr(sys, "frozen", False):
        return
    for item in data_path.iterdir():
        target = compat_root / item.name
        if target.exists():
            continue
        try:
            relative = Path(data_path.name) / item.name if data_path.parent == compat_root else item
            target.symlink_to(relative, target_is_directory=item.is_dir())
        except Exception:
            try:
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
            except Exception:
                continue


def _speak_kokoro(text: str) -> dict[str, Any]:
    model, voices, _model_dir = _find_kokoro_model(_candidate_model_dirs("kokoro"))
    if not model or not voices:
        return {"success": False, "available": False, "engine": "kokoro", "message": "Kokoro model assets are missing."}
    try:
        from kokoro_onnx import Kokoro
    except Exception as exc:
        return {"success": False, "available": False, "engine": "kokoro", "message": f"kokoro_onnx unavailable: {exc}"}

    speed = float(os.environ.get("SHELL_NATURAL_TTS_SPEED", "1.0") or "1.0")
    wav_path = _tts_audio_path("kokoro")

    espeak_config = _kokoro_espeak_config()
    try:
        engine = Kokoro(str(model), str(voices), espeak_config=espeak_config)
    except TypeError:
        engine = Kokoro(str(model), str(voices))
    segments = _prepare_kokoro_segments(text)
    rendered_segments = [
        engine.create(_kokoro_synthesis_text_for(segment), voice=segment.voice, speed=speed, lang=segment.locale)
        for segment in segments
    ]
    samples, sample_rate = _join_kokoro_audio(rendered_segments)
    _write_float_wav(wav_path, samples, int(sample_rate))
    reactivity = _audio_reactivity_metadata(samples, int(sample_rate))
    process = _play_wav_async(wav_path)
    if not process:
        return {"success": False, "available": True, "engine": "kokoro", "message": "No local WAV playback command found."}
    return {
        "success": True,
        "available": True,
        "engine": "kokoro",
        "voice": segments[0].voice if segments else _kokoro_voice_for(_shell_language()),
        "voices": sorted({segment.voice for segment in segments}),
        "segments": [segment.as_dict() for segment in segments],
        "chars": len(text),
        "audioPath": str(wav_path),
        **reactivity,
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
    reactivity = _wav_reactivity_metadata(wav_path)
    return {
        "success": True,
        "available": True,
        "engine": "piper",
        "chars": len(text),
        "audioPath": str(wav_path),
        **reactivity,
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
    except Exception as exc:
        return {"success": False, "available": True, "engine": engine, "message": str(exc)}

    return {"success": False, "available": False, "engine": engine, "message": f"Unsupported offline TTS engine: {engine}"}


__all__ = ["offline_tts_status", "speak_offline_tts"]
