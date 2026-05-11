"""
Shell Video Tools - Video processing via ffmpeg/ffprobe
--------------------------------------------------------
Provides tools for video metadata, audio extraction,
thumbnails, trimming, and format conversion.
All operations use ffmpeg/ffprobe via subprocess.
"""

import os
import asyncio
import json
import shutil
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("SHELL_VIDEO")


async def _check_ffmpeg() -> bool:
    """Check if ffmpeg is available on the system."""
    return shutil.which("ffmpeg") is not None


async def _check_ffprobe() -> bool:
    """Check if ffprobe is available on the system."""
    return shutil.which("ffprobe") is not None


async def _run_cmd(cmd: list, timeout: int = 120) -> tuple:
    """Run a subprocess command and return (stdout, stderr, returncode)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"), proc.returncode
    except asyncio.TimeoutError:
        proc.kill()
        return "", "Command timed out", -1


@function_tool
async def video_info_tool(filepath: str) -> str:
    """
    Get video file metadata (duration, resolution, fps, codec, bitrate).
    Args:
        filepath: Full path to the video file.
    """
    try:
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"

        if not await _check_ffprobe():
            return "Error: ffprobe not found. Install ffmpeg (includes ffprobe) and add to PATH."

        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            filepath,
        ]

        stdout, stderr, rc = await _run_cmd(cmd)

        if rc != 0:
            return f"ffprobe error: {stderr}"

        data = json.loads(stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        lines = [f"Video Info: {os.path.basename(filepath)}", "=" * 50]

        # Format info
        duration = float(fmt.get("duration", 0))
        mins = int(duration // 60)
        secs = int(duration % 60)
        size_mb = round(int(fmt.get("size", 0)) / (1024 * 1024), 2)
        bitrate_kbps = int(fmt.get("bit_rate", 0)) // 1000

        lines.append(f"Duration: {mins}m {secs}s ({duration:.1f}s)")
        lines.append(f"Size: {size_mb} MB")
        lines.append(f"Bitrate: {bitrate_kbps} kbps")
        lines.append(f"Format: {fmt.get('format_long_name', fmt.get('format_name', 'unknown'))}")

        # Stream details
        for stream in streams:
            codec_type = stream.get("codec_type", "unknown")
            codec_name = stream.get("codec_name", "unknown")

            if codec_type == "video":
                width = stream.get("width", "?")
                height = stream.get("height", "?")
                fps_parts = stream.get("r_frame_rate", "0/1").split("/")
                fps = round(int(fps_parts[0]) / max(int(fps_parts[1]), 1), 2) if len(fps_parts) == 2 else "?"
                lines.append(f"\nVideo Stream:")
                lines.append(f"  Codec: {codec_name}")
                lines.append(f"  Resolution: {width}x{height}")
                lines.append(f"  FPS: {fps}")
                pix_fmt = stream.get("pix_fmt")
                if pix_fmt:
                    lines.append(f"  Pixel Format: {pix_fmt}")

            elif codec_type == "audio":
                sample_rate = stream.get("sample_rate", "?")
                channels = stream.get("channels", "?")
                lines.append(f"\nAudio Stream:")
                lines.append(f"  Codec: {codec_name}")
                lines.append(f"  Sample Rate: {sample_rate} Hz")
                lines.append(f"  Channels: {channels}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"video_info_tool error: {e}")
        return f"Error getting video info: {e}"


@function_tool
async def video_extract_audio_tool(filepath: str, output: str) -> str:
    """
    Extract audio track from a video file.
    Args:
        filepath: Full path to the input video file.
        output: Output audio file path (e.g. 'audio.mp3', 'audio.wav').
    """
    try:
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"

        if not await _check_ffmpeg():
            return "Error: ffmpeg not found. Install ffmpeg and add to PATH."

        cmd = [
            "ffmpeg", "-y", "-i", filepath,
            "-vn",  # no video
            "-acodec", "libmp3lame" if output.endswith(".mp3") else "copy",
            "-q:a", "2",
            output,
        ]

        stdout, stderr, rc = await _run_cmd(cmd, timeout=300)

        if rc != 0:
            return f"ffmpeg error: {stderr[-500:]}"

        if os.path.isfile(output):
            size_mb = round(os.path.getsize(output) / (1024 * 1024), 2)
            return f"Audio extracted: {output} ({size_mb} MB)"
        else:
            return "Error: Output file was not created."

    except Exception as e:
        logger.error(f"video_extract_audio_tool error: {e}")
        return f"Error extracting audio: {e}"


@function_tool
async def video_thumbnail_tool(filepath: str, timestamp: str = "00:00:01", output: str = "thumbnail.jpg") -> str:
    """
    Extract a single frame from a video at a given timestamp.
    Args:
        filepath: Full path to the input video file.
        timestamp: Time position (e.g. '00:00:05', '00:01:30'). Default '00:00:01'.
        output: Output image path (e.g. 'thumbnail.jpg', 'frame.png').
    """
    try:
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"

        if not await _check_ffmpeg():
            return "Error: ffmpeg not found. Install ffmpeg and add to PATH."

        cmd = [
            "ffmpeg", "-y",
            "-ss", timestamp,
            "-i", filepath,
            "-vframes", "1",
            "-q:v", "2",
            output,
        ]

        stdout, stderr, rc = await _run_cmd(cmd, timeout=60)

        if rc != 0:
            return f"ffmpeg error: {stderr[-500:]}"

        if os.path.isfile(output):
            size_kb = round(os.path.getsize(output) / 1024, 1)
            return f"Thumbnail saved: {output} ({size_kb} KB) at {timestamp}"
        else:
            return "Error: Thumbnail was not created."

    except Exception as e:
        logger.error(f"video_thumbnail_tool error: {e}")
        return f"Error extracting thumbnail: {e}"


@function_tool
async def video_trim_tool(filepath: str, start: str, end: str, output: str) -> str:
    """
    Trim a video between two timestamps.
    Args:
        filepath: Full path to the input video file.
        start: Start timestamp (e.g. '00:00:10').
        end: End timestamp (e.g. '00:01:30').
        output: Output video file path.
    """
    try:
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"

        if not await _check_ffmpeg():
            return "Error: ffmpeg not found. Install ffmpeg and add to PATH."

        cmd = [
            "ffmpeg", "-y",
            "-i", filepath,
            "-ss", start,
            "-to", end,
            "-c", "copy",  # stream copy (fast, no re-encoding)
            output,
        ]

        stdout, stderr, rc = await _run_cmd(cmd, timeout=300)

        if rc != 0:
            return f"ffmpeg error: {stderr[-500:]}"

        if os.path.isfile(output):
            size_mb = round(os.path.getsize(output) / (1024 * 1024), 2)
            return f"Video trimmed: {output} ({size_mb} MB) [{start} -> {end}]"
        else:
            return "Error: Output file was not created."

    except Exception as e:
        logger.error(f"video_trim_tool error: {e}")
        return f"Error trimming video: {e}"


@function_tool
async def video_convert_tool(filepath: str, output: str) -> str:
    """
    Convert video to a different format (output format detected from extension).
    Args:
        filepath: Full path to the input video file.
        output: Output file path with desired extension (e.g. 'video.mp4', 'video.avi', 'video.mkv').
    """
    try:
        if not os.path.isfile(filepath):
            return f"File not found: {filepath}"

        if not await _check_ffmpeg():
            return "Error: ffmpeg not found. Install ffmpeg and add to PATH."

        out_ext = os.path.splitext(output)[1].lower()
        in_ext = os.path.splitext(filepath)[1].lower()

        if out_ext == in_ext:
            return f"Input and output are the same format ({out_ext}). No conversion needed."

        # Choose codec based on output format
        codec_args = []
        if out_ext == ".mp4":
            codec_args = ["-c:v", "libx264", "-c:a", "aac", "-preset", "medium"]
        elif out_ext == ".webm":
            codec_args = ["-c:v", "libvpx-vp9", "-c:a", "libopus"]
        elif out_ext == ".avi":
            codec_args = ["-c:v", "mpeg4", "-c:a", "mp3"]
        elif out_ext == ".mkv":
            codec_args = ["-c:v", "copy", "-c:a", "copy"]
        elif out_ext == ".mov":
            codec_args = ["-c:v", "libx264", "-c:a", "aac"]
        elif out_ext == ".gif":
            codec_args = ["-vf", "fps=10,scale=480:-1", "-an"]
        else:
            codec_args = ["-c:v", "copy", "-c:a", "copy"]

        cmd = ["ffmpeg", "-y", "-i", filepath] + codec_args + [output]

        stdout, stderr, rc = await _run_cmd(cmd, timeout=600)

        if rc != 0:
            return f"ffmpeg conversion error: {stderr[-500:]}"

        if os.path.isfile(output):
            in_size = round(os.path.getsize(filepath) / (1024 * 1024), 2)
            out_size = round(os.path.getsize(output) / (1024 * 1024), 2)
            return f"Video converted: {output} ({out_size} MB, from {in_size} MB {in_ext} -> {out_ext})"
        else:
            return "Error: Output file was not created."

    except Exception as e:
        logger.error(f"video_convert_tool error: {e}")
        return f"Error converting video: {e}"
