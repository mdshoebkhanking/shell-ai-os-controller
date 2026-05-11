"""
Shell Speech Tools — Voice I/O for Shell AI
--------------------------------------------------------------
Two layers of TTS, exposed as agent tools:

 * Realtime Gemini voice (primary) — switch/list/diagnose via
   shell_voice helpers. This is what the user hears during a live
   LiveKit session.

 * Offline local TTS (pyttsx3 / gTTS / Windows SAPI fallback) —
   used for file output and as a fallback when realtime fails.

Keeping both in one module so the agent's tool registry gets a
clean, single import surface.
"""

import asyncio
import json
import logging
import os
import platform
import re
import shutil
import wave

from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("SHELL_SPEECH")

# ── Soft imports ─────────────────────────────────────
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

# ── Global engine state ──────────────────────────────
_voice_settings = {"rate": 175, "volume": 1.0}


def _detect_gtts_lang(text: str) -> str:
    """Best-effort language code picker for gTTS. Returns 'hi' when text has
    a meaningful share of Devanagari chars, else 'en'. This keeps Hinglish
    file output sounding natural without requiring a full langdetect dep.
    """
    if not text:
        return "en"
    total = sum(1 for ch in text if ch.strip())
    if total == 0:
        return "en"
    devanagari = sum(1 for ch in text if "\u0900" <= ch <= "\u097F")
    return "hi" if devanagari / total > 0.2 else "en"


def _get_engine():
    """Create a fresh pyttsx3 engine with current settings."""
    engine = pyttsx3.init()
    engine.setProperty("rate", _voice_settings["rate"])
    engine.setProperty("volume", _voice_settings["volume"])
    return engine


async def _run_powershell(script: str) -> str:
    """Run a PowerShell script and return stdout."""
    proc = await asyncio.create_subprocess_shell(
        f'powershell -Command "{script}"',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode("utf-8", errors="replace").strip()


async def _run_tts_command(argv: list[str], timeout: float = 45.0) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.terminate()
            await proc.wait()
            return False
        return proc.returncode == 0
    except Exception as exc:
        logger.debug("system TTS command failed: %s", exc)
        return False


def _silent_wav_probe_path() -> str:
    root = os.path.join(os.environ.get("TEMP", "/tmp"), "shell_tts")
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, "shell_audio_probe_silence.wav")
    if os.path.exists(path):
        return path
    sample_rate = 8000
    frames = b"\x00\x00" * int(sample_rate * 0.05)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return path


async def _mac_audio_output_available() -> tuple[bool, str]:
    if not shutil.which("afplay"):
        return False, "macOS afplay command not found."
    proc = await asyncio.create_subprocess_exec(
        "afplay",
        _silent_wav_probe_path(),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await proc.communicate()
    if proc.returncode == 0:
        return True, ""
    detail = (stderr or b"").decode("utf-8", errors="replace").strip()
    return (
        False,
        "macOS audio output unavailable. CoreAudio could not start playback "
        f"({detail or proc.returncode}). Check Audio MIDI Setup / Chrome Remote Desktop audio output.",
    )


def _speech_rate_wpm() -> str:
    try:
        return str(int(max(120, min(320, _voice_settings["rate"]))))
    except Exception:
        return "175"


async def _speak_system_tts(text: str) -> tuple[bool, str]:
    system = platform.system().lower()
    if system == "darwin" and shutil.which("say"):
        audio_ok, audio_error = await _mac_audio_output_available()
        if not audio_ok:
            return False, audio_error
        ok = await _run_tts_command(["say", "-r", _speech_rate_wpm(), text])
        return ok, "macOS say"
    if system == "windows":
        powershell = shutil.which("powershell") or shutil.which("powershell.exe")
        if powershell:
            safe_text = text.replace("'", "''").replace('"', '`"')
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$synth.Rate = {max(-10, min(10, (_voice_settings['rate'] - 175) // 25))}; "
                f"$synth.Volume = {int(_voice_settings['volume'] * 100)}; "
                f"$synth.Speak('{safe_text}'); $synth.Dispose()"
            )
            ok = await _run_tts_command([powershell, "-NoProfile", "-NonInteractive", "-Command", script])
            return ok, "Windows SAPI"
    for name in ("spd-say", "espeak-ng", "espeak"):
        if shutil.which(name):
            ok = await _run_tts_command([name, text])
            return ok, name
    return False, ""


def _voice_mode() -> str:
    raw = os.environ.get("SHELL_VOICE_MODE")
    if not raw:
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".shell_settings.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    raw = (json.load(f) or {}).get("voice_mode")
        except Exception as exc:
            logger.debug("voice mode read failed: %s", exc)
    mode = str(raw or "cloud").strip().lower()
    return mode if mode in {"cloud", "local", "auto"} else "cloud"


def _truthy_env(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def _gemini_tts_configured() -> bool:
    key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key or key.lower() in {"your_google_api_key_here", "your_gemini_api_key_here"}:
        return False
    return len(key) >= 20


def _extract_gemini_audio(response) -> tuple[bytes, str]:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline is not None else None
            if data:
                return bytes(data), str(getattr(inline, "mime_type", "") or "")
    for part in getattr(response, "parts", None) or []:
        inline = getattr(part, "inline_data", None)
        data = getattr(inline, "data", None) if inline is not None else None
        if data:
            return bytes(data), str(getattr(inline, "mime_type", "") or "")
    return b"", ""


def _write_gemini_audio_file(data: bytes, mime_type: str, path: str) -> None:
    raw = bytes(data)
    mt = str(mime_type or "").lower()
    if raw[:4] == b"RIFF" or "wav" in mt:
        with open(path, "wb") as f:
            f.write(raw)
        return
    match = re.search(r"rate=(\d+)", mt)
    sample_rate = int(match.group(1)) if match else 24000
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)


async def _play_audio_file(path: str) -> bool:
    system = platform.system().lower()
    if system == "darwin" and shutil.which("afplay"):
        return await _run_tts_command(["afplay", path])
    if system == "windows":
        powershell = shutil.which("powershell") or shutil.which("powershell.exe")
        if powershell:
            safe_path = path.replace("'", "''")
            script = (
                "Add-Type -AssemblyName PresentationCore; "
                "$p = New-Object System.Windows.Media.MediaPlayer; "
                f"$p.Open([Uri]'{safe_path}'); $p.Play(); "
                "Start-Sleep -Milliseconds 250; "
                "while($p.Position -lt $p.NaturalDuration.TimeSpan) { Start-Sleep -Milliseconds 100 }; "
                "$p.Close();"
            )
            return await _run_tts_command([powershell, "-NoProfile", "-NonInteractive", "-Command", script])
    for player in ("ffplay", "mpg123", "mpv"):
        if shutil.which(player):
            if player == "ffplay":
                return await _run_tts_command([player, "-nodisp", "-autoexit", "-loglevel", "quiet", path])
            return await _run_tts_command([player, path])
    return False


async def _speak_gemini_tts(text: str) -> tuple[bool, str]:
    if not _gemini_tts_configured():
        return (
            False,
            "Gemini voice is selected, but GOOGLE_API_KEY is missing or invalid. "
            "Open Settings > API Keys and save a valid Google AI Studio key.",
        )
    if platform.system().lower() == "darwin":
        audio_ok, audio_error = await _mac_audio_output_available()
        if not audio_ok:
            return False, audio_error

    def _generate() -> tuple[bytes, str]:
        from google import genai
        from google.genai import types
        from shell_voice import build_persona_instruction, resolve_voice

        voice_name = resolve_voice(os.environ.get("VOICE_NAME"))
        model = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
        prompt = build_persona_instruction(text, os.environ.get("VOICE_PERSONA"))
        client = genai.Client(api_key=(os.environ.get("GOOGLE_API_KEY") or "").strip())
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["audio"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                    )
                ),
            ),
        )
        return _extract_gemini_audio(response)

    try:
        data, mime_type = await asyncio.to_thread(_generate)
        if not data:
            return False, "Gemini voice returned no audio data."
        root = os.path.join(os.environ.get("TEMP", "/tmp"), "shell_tts")
        os.makedirs(root, exist_ok=True)
        path = os.path.join(root, f"shell_gemini_{os.getpid()}_{id(data)}.wav")
        try:
            _write_gemini_audio_file(data, mime_type, path)
            if await _play_audio_file(path):
                return True, "Gemini Aoede"
            return False, "Gemini audio was generated, but playback failed."
        finally:
            try:
                os.remove(path)
            except Exception:
                pass
    except Exception as exc:
        return False, f"Gemini voice failed: {exc}"


@function_tool
async def speak_tool(text: str) -> str:
    """
    Speak text aloud using offline TTS engine (pyttsx3).
    Args:
        text: The text to speak aloud.
    """
    try:
        if not text.strip():
            return "Error: Text cannot be empty."

        mode = _voice_mode()
        engine = str(os.environ.get("SHELL_TTS_ENGINE", "")).strip().lower()
        if mode == "cloud" or engine in {"cloud", "gemini"}:
            ok, detail = await _speak_gemini_tts(text)
            if ok:
                return f"Spoke ({detail}): \"{text[:100]}{'...' if len(text) > 100 else ''}\""
            if not _truthy_env("SHELL_CLOUD_TTS_LOCAL_FALLBACK"):
                return f"Error speaking text: {detail}"

        if mode == "auto" and _gemini_tts_configured():
            ok, detail = await _speak_gemini_tts(text)
            if ok:
                return f"Spoke ({detail}): \"{text[:100]}{'...' if len(text) > 100 else ''}\""

        system_ok, system_name = await _speak_system_tts(text)
        if system_ok:
            return f"Spoke ({system_name}): \"{text[:100]}{'...' if len(text) > 100 else ''}\""
        if platform.system().lower() == "darwin" and "audio output unavailable" in system_name.lower():
            return f"Error speaking text: {system_name}"

        if PYTTSX3_AVAILABLE:
            def _speak():
                engine = _get_engine()
                engine.say(text)
                engine.runAndWait()
                engine.stop()

            await asyncio.to_thread(_speak)
            return f"Spoke: \"{text[:100]}{'...' if len(text) > 100 else ''}\""

        return "Error: No local TTS engine available. Install pyttsx3, edge-tts, or an OS speech command."

    except Exception as e:
        logger.error(f"speak_tool error: {e}")
        return f"Error speaking text: {e}"


@function_tool
async def speak_save_tool(text: str, filename: str) -> str:
    """
    Save spoken text to an audio file.
    Args:
        text: The text to convert to speech.
        filename: Output file path (e.g. 'speech.wav' for pyttsx3, 'speech.mp3' for gTTS).
    """
    try:
        if not text.strip():
            return "Error: Text cannot be empty."

        # Use pyttsx3 for .wav output
        if PYTTSX3_AVAILABLE and filename.lower().endswith(".wav"):
            def _save():
                engine = _get_engine()
                engine.save_to_file(text, filename)
                engine.runAndWait()
                engine.stop()

            await asyncio.to_thread(_save)

            if os.path.isfile(filename):
                size_kb = round(os.path.getsize(filename) / 1024, 1)
                return f"Speech saved (pyttsx3): {filename} ({size_kb} KB)"
            else:
                return "Error: pyttsx3 failed to create output file."

        # Use gTTS for .mp3 output
        if GTTS_AVAILABLE:
            if not filename.lower().endswith(".mp3"):
                filename += ".mp3"

            lang = _detect_gtts_lang(text)

            def _save_gtts():
                tts = gTTS(text=text, lang=lang, slow=False)
                tts.save(filename)

            await asyncio.to_thread(_save_gtts)

            if os.path.isfile(filename):
                size_kb = round(os.path.getsize(filename) / 1024, 1)
                return f"Speech saved (gTTS): {filename} ({size_kb} KB)"
            else:
                return "Error: gTTS failed to create output file."

        # Fallback: Windows SAPI via PowerShell (.wav)
        if not filename.lower().endswith(".wav"):
            filename = os.path.splitext(filename)[0] + ".wav"

        safe_text = text.replace("'", "''").replace('"', '`"')
        abs_path = os.path.abspath(filename)
        script = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.SetOutputToWaveFile('{abs_path}'); "
            f"$synth.Speak('{safe_text}'); "
            f"$synth.Dispose()"
        )
        await _run_powershell(script)

        if os.path.isfile(abs_path):
            size_kb = round(os.path.getsize(abs_path) / 1024, 1)
            return f"Speech saved (SAPI): {abs_path} ({size_kb} KB)"
        else:
            return "Error: No TTS engine available. Install pyttsx3 or gtts."

    except Exception as e:
        logger.error(f"speak_save_tool error: {e}")
        return f"Error saving speech: {e}"


@function_tool
async def set_voice_tool(rate: int = 175, volume: float = 1.0) -> str:
    """
    Set speech rate and volume for the TTS engine.
    Args:
        rate: Speech rate in words per minute (50-300, default 175).
        volume: Volume level (0.0 to 1.0, default 1.0).
    """
    try:
        # Validate
        rate = max(50, min(300, int(rate)))
        volume = max(0.0, min(1.0, float(volume)))

        _voice_settings["rate"] = rate
        _voice_settings["volume"] = volume

        return f"Voice settings updated: Rate={rate} wpm, Volume={volume:.1f}"

    except Exception as e:
        logger.error(f"set_voice_tool error: {e}")
        return f"Error setting voice: {e}"


@function_tool
async def list_voices_tool() -> str:
    """List all available TTS voices on the system."""
    try:
        voices_info = []

        if PYTTSX3_AVAILABLE:
            def _list():
                engine = pyttsx3.init()
                voices = engine.getProperty("voices")
                result = []
                for v in voices:
                    result.append({
                        "id": v.id,
                        "name": v.name,
                        "languages": getattr(v, "languages", []),
                        "gender": getattr(v, "gender", "unknown"),
                    })
                engine.stop()
                return result

            voices_info = await asyncio.to_thread(_list)

            if voices_info:
                lines = [f"Available TTS Voices ({len(voices_info)} found):", "=" * 50]
                for i, v in enumerate(voices_info, 1):
                    lines.append(f"  {i}. {v['name']}")
                    lines.append(f"     ID: {v['id']}")
                    if v["languages"]:
                        lines.append(f"     Languages: {v['languages']}")
                    if v["gender"] != "unknown":
                        lines.append(f"     Gender: {v['gender']}")

                lines.append(f"\nCurrent Settings: Rate={_voice_settings['rate']} wpm, Volume={_voice_settings['volume']}")
                return "\n".join(lines)

        # Fallback: query Windows SAPI voices
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo } | "
            "Select-Object Name, Culture, Gender, Age | Format-List"
        )
        result = await _run_powershell(script)

        if result.strip():
            return f"Available SAPI Voices:\n{result}\n\nCurrent Settings: Rate={_voice_settings['rate']} wpm, Volume={_voice_settings['volume']}"
        else:
            return "No TTS voices found. Install pyttsx3: pip install pyttsx3"

    except Exception as e:
        logger.error(f"list_voices_tool error: {e}")
        return f"Error listing voices: {e}"


# ═══════════════════════════════════════════════════════════════
# Gemini Realtime Voice Tools — the primary voice the user hears
# ═══════════════════════════════════════════════════════════════

@function_tool
async def switch_shell_voice_tool(voice_name: str) -> str:
    """Switch Shell's realtime Gemini voice (e.g. Aoede, Kore, Charon, Puck).

    Args:
        voice_name: Name of a Gemini 2.5 voice. Case-insensitive.
                    Unknown names fall back to the current voice.
    """
    try:
        from shell_voice import switch_voice_runtime, describe_voice
    except Exception as e:
        return f"Voice module unavailable: {e}"

    ok, msg = await switch_voice_runtime(voice_name)
    prefix = "✅" if ok else "⚠️"
    try:
        detail = describe_voice(voice_name)
    except Exception:
        detail = ""
    return f"{prefix} {msg}\n{detail}".strip()


@function_tool
async def list_shell_voices_tool(gender: str = "", style: str = "") -> str:
    """List available Gemini realtime voices.

    Args:
        gender: Optional filter, 'F' for female or 'M' for male. Empty = all.
        style:  Optional style keyword to filter on (e.g. 'firm', 'bright',
                'breezy', 'warm'). Matched as substring.
    """
    try:
        from shell_voice import list_voices, current_voice
    except Exception as e:
        return f"Voice module unavailable: {e}"

    voices = list_voices(gender=gender or None, style=style or None)
    if not voices:
        return "No voices match the given filters."

    active = current_voice()
    header = f"Gemini Realtime Voices ({len(voices)} shown, active={active})"
    lines = [header, "=" * len(header)]
    for v in voices:
        mark = "►" if v.name == active else " "
        lines.append(f" {mark} {v.name:<16} [{v.gender}, {v.style}]  — {v.description}")
    lines.append("\nSwitch with: switch_shell_voice_tool(voice_name='Aoede')")
    return "\n".join(lines)


@function_tool
async def set_voice_persona_tool(persona_name: str) -> str:
    """Set speaking style/persona (affects every subsequent utterance).

    Args:
        persona_name: One of: Hinglish, English, English-Indian, Hindi, Formal, Casual.
    """
    try:
        from shell_voice import set_persona_runtime, resolve_persona, PERSONA_NAMES
    except Exception as e:
        return f"Voice module unavailable: {e}"

    ok, msg = set_persona_runtime(persona_name)
    persona = resolve_persona(persona_name)
    hint = (
        f"\nPersona style: {persona.style_instructions[:140]}..."
        if persona.style_instructions else ""
    )
    available = f"\nAvailable: {', '.join(PERSONA_NAMES)}"
    return f"{'✅' if ok else '⚠️'} {msg}{hint}{available}"


@function_tool
async def voice_status_tool() -> str:
    """Show current voice, persona, and voice-subsystem diagnostics."""
    try:
        from shell_voice import diagnostics
    except Exception as e:
        return f"Voice module unavailable: {e}"

    d = diagnostics()
    lines = [
        "Shell Voice Status",
        "==================",
        f"  Active voice:     {d['current_voice']}  (session: {'live' if d['session_active'] else 'not started'})",
        f"  Active persona:   {d['current_persona']}",
        f"  Resolved voice:   {d['resolved_voice']}  (from env: {d.get('env_voice') or '—'})",
        f"  Resolved persona: {d['resolved_persona']}  (from env: {d.get('env_persona') or '—'})",
        f"  Defaults:         voice={d['default_voice']}, persona={d['default_persona']}",
        f"  Catalog size:     {d['catalog_size']} Gemini voices",
        f"  Personas:         {', '.join(d['personas'])}",
    ]
    return "\n".join(lines)
