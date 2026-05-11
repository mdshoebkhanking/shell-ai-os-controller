"""
Shell Music Tools - Audio playback, metadata, and TTS
------------------------------------------------------
Provides tools for playing audio, getting metadata,
text-to-speech conversion, and listing audio files.
"""

import os
import asyncio
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("SHELL_MUSIC")

# ── Soft imports ─────────────────────────────────────
try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except Exception:
    PYGAME_AVAILABLE = False

try:
    from mutagen import File as MutagenFile
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    from tinytag import TinyTag
    TINYTAG_AVAILABLE = True
except ImportError:
    TINYTAG_AVAILABLE = False

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

# Supported audio extensions
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma", ".m4a", ".opus"}

# ── Global playback state ────────────────────────────
_current_playing = {"file": None, "playing": False}


@function_tool
async def play_audio_tool(filepath: str) -> str:
    """
    Play an audio file.
    Args:
        filepath: Full path to the audio file to play.
    """
    try:
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"

        ext = os.path.splitext(filepath)[1].lower()
        if ext not in AUDIO_EXTENSIONS:
            return f"Unsupported audio format: {ext}. Supported: {', '.join(sorted(AUDIO_EXTENSIONS))}"

        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
                _current_playing["file"] = filepath
                _current_playing["playing"] = True
                filename = os.path.basename(filepath)
                return f"Now playing: {filename}"
            except Exception as e:
                return f"Pygame playback error: {e}"
        else:
            # Fallback: use Windows media player via subprocess
            proc = await asyncio.create_subprocess_shell(
                f'powershell -Command "Start-Process \'{filepath}\'"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            _current_playing["file"] = filepath
            _current_playing["playing"] = True
            filename = os.path.basename(filepath)
            return f"Opened with default player: {filename}"

    except Exception as e:
        logger.error(f"play_audio_tool error: {e}")
        return f"Error playing audio: {e}"


@function_tool
async def stop_audio_tool() -> str:
    """Stop currently playing audio."""
    try:
        if PYGAME_AVAILABLE:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                _current_playing["playing"] = False
                return f"Stopped playback: {os.path.basename(_current_playing['file'] or 'unknown')}"
            else:
                return "No audio is currently playing."
        else:
            # Fallback: try to kill common media players
            proc = await asyncio.create_subprocess_shell(
                'powershell -Command "Get-Process wmplayer,vlc -ErrorAction SilentlyContinue | Stop-Process -Force"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            _current_playing["playing"] = False
            return "Sent stop signal to media players."

    except Exception as e:
        logger.error(f"stop_audio_tool error: {e}")
        return f"Error stopping audio: {e}"


@function_tool
async def audio_info_tool(filepath: str) -> str:
    """
    Get audio file metadata (duration, bitrate, format, etc.).
    Args:
        filepath: Full path to the audio file.
    """
    try:
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"

        info_lines = []
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filepath)[1].lower()
        size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)

        info_lines.append(f"File: {filename}")
        info_lines.append(f"Format: {ext.upper().strip('.')}")
        info_lines.append(f"Size: {size_mb} MB")

        # Try mutagen first
        if MUTAGEN_AVAILABLE:
            try:
                audio = MutagenFile(filepath)
                if audio is not None:
                    if hasattr(audio.info, "length"):
                        duration = audio.info.length
                        mins = int(duration // 60)
                        secs = int(duration % 60)
                        info_lines.append(f"Duration: {mins}m {secs}s ({round(duration, 1)}s)")
                    if hasattr(audio.info, "bitrate"):
                        info_lines.append(f"Bitrate: {audio.info.bitrate // 1000} kbps")
                    if hasattr(audio.info, "sample_rate"):
                        info_lines.append(f"Sample Rate: {audio.info.sample_rate} Hz")
                    if hasattr(audio.info, "channels"):
                        info_lines.append(f"Channels: {audio.info.channels}")
                    # Tags
                    if audio.tags:
                        for key in ["title", "artist", "album", "genre", "date"]:
                            val = audio.tags.get(key) or audio.tags.get(key.upper())
                            if val:
                                info_lines.append(f"{key.capitalize()}: {val}")
                    return "\n".join(info_lines)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)

        # Try tinytag as fallback
        if TINYTAG_AVAILABLE:
            try:
                tag = TinyTag.get(filepath)
                if tag.duration:
                    mins = int(tag.duration // 60)
                    secs = int(tag.duration % 60)
                    info_lines.append(f"Duration: {mins}m {secs}s")
                if tag.bitrate:
                    info_lines.append(f"Bitrate: {int(tag.bitrate)} kbps")
                if tag.samplerate:
                    info_lines.append(f"Sample Rate: {tag.samplerate} Hz")
                if tag.channels:
                    info_lines.append(f"Channels: {tag.channels}")
                if tag.title:
                    info_lines.append(f"Title: {tag.title}")
                if tag.artist:
                    info_lines.append(f"Artist: {tag.artist}")
                if tag.album:
                    info_lines.append(f"Album: {tag.album}")
                return "\n".join(info_lines)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)

        # Fallback: just file info
        info_lines.append("(Install mutagen or tinytag for detailed metadata)")
        return "\n".join(info_lines)

    except Exception as e:
        logger.error(f"audio_info_tool error: {e}")
        return f"Error getting audio info: {e}"


@function_tool
async def text_to_speech_save_tool(text: str, filename: str, lang: str = "en") -> str:
    """
    Convert text to speech and save as audio file using gTTS.
    Args:
        text: Text to convert to speech.
        filename: Output filename (e.g. 'output.mp3').
        lang: Language code (default 'en'). Examples: 'en', 'hi', 'es', 'fr'.
    """
    try:
        if not text.strip():
            return "Error: Text cannot be empty."

        if not GTTS_AVAILABLE:
            return "Error: gtts is not installed. Run: pip install gtts"

        # Ensure .mp3 extension
        if not filename.lower().endswith(".mp3"):
            filename += ".mp3"

        # Run gTTS in thread to avoid blocking
        def _generate():
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(filename)

        await asyncio.to_thread(_generate)

        if os.path.isfile(filename):
            size_kb = round(os.path.getsize(filename) / 1024, 1)
            return f"TTS audio saved: {filename} ({size_kb} KB, lang={lang})"
        else:
            return "Error: File was not created."

    except Exception as e:
        logger.error(f"text_to_speech_save_tool error: {e}")
        return f"Error generating TTS: {e}"


@function_tool
async def list_audio_files_tool(directory: str) -> str:
    """
    List all audio files in a directory with basic metadata.
    Args:
        directory: Directory path to scan for audio files.
    """
    try:
        if not os.path.isdir(directory):
            return f"Directory not found: {directory}"

        audio_files = []
        for entry in os.scandir(directory):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in AUDIO_EXTENSIONS:
                    size_mb = round(entry.stat().st_size / (1024 * 1024), 2)
                    audio_files.append({
                        "name": entry.name,
                        "format": ext.strip(".").upper(),
                        "size_mb": size_mb,
                        "path": entry.path,
                    })

        if not audio_files:
            return f"No audio files found in: {directory}"

        # Sort by name
        audio_files.sort(key=lambda x: x["name"].lower())

        lines = [f"Audio files in {directory} ({len(audio_files)} found):"]
        lines.append("-" * 50)
        for i, af in enumerate(audio_files, 1):
            lines.append(f"  {i}. {af['name']}  [{af['format']}]  {af['size_mb']} MB")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"list_audio_files_tool error: {e}")
        return f"Error listing audio files: {e}"
