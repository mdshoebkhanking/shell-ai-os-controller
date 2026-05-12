#!/usr/bin/env python3
"""Build the public Shell AI launch demo video with voiceover.

The script uses only local assets, macOS `say`, and FFmpeg. It creates a small
GitHub-friendly MP4 from the official logo and real UI screenshots.

The Homebrew FFmpeg build on some Macs does not include `drawtext`, so the
video deliberately avoids text overlays. The narration and README provide the
context while the visuals stay authentic to the real app.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / ".shell_runtime" / "demo_media_build"
OUTPUT = ROOT / "videos" / "shell-launch-demo.mp4"
SCRIPT_PATH = ROOT / "videos" / "shell-launch-demo-voiceover.md"


VOICEOVER = """Shell AI OS Controller.
Version one point zero, built by mdshoebking.

Shell is a desktop AI operating layer for chat, voice, tools, automation, and runtime diagnostics.

The interface is designed for fast interaction.
Text appears first, voice stays under user control, and every action can be traced.

The voice page brings transcript, audio state, and assistant controls into one clean workspace.

The tool catalog gives Shell a safe way to route automation, browser actions, files, email, media, and system tasks.

The system dashboard exposes health, readiness, dependencies, logs, and production release checks.

Beginners can use the one click install flow.
Developers can inspect the architecture, tests, release gates, and plugin roadmap.

Shell AI OS Controller is open source, transparent, and built for real AI desktop automation.
"""

SLIDES = [
    {
        "name": "hero",
        "duration": 7,
        "image": "assets/brand/shell-official-logo.png",
    },
    {
        "name": "chat",
        "duration": 7,
        "image": "screenshots/showcase/chat-interface.png",
    },
    {
        "name": "voice",
        "duration": 7,
        "image": "screenshots/showcase/voice-interface.png",
    },
    {
        "name": "tools",
        "duration": 7,
        "image": "screenshots/showcase/tools-catalog.png",
    },
    {
        "name": "system",
        "duration": 7,
        "image": "screenshots/showcase/system-dashboard.png",
    },
    {
        "name": "install",
        "duration": 7,
        "image": "screenshots/showcase/settings-panel.png",
    },
    {
        "name": "final",
        "duration": 15,
        "image": "assets/brand/shell-official-logo.png",
    },
]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def render_segment(image: Path, duration: int, output: Path) -> None:
    frames = duration * 30
    fade_out = max(0, duration - 0.35)
    run([
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image),
        "-vf",
        (
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x05070b,"
            f"zoompan=z='min(zoom+0.00045,1.026)':d={frames}:s=1280x720:fps=30,"
            "fade=t=in:st=0:d=0.35,"
            f"fade=t=out:st={fade_out}:d=0.35,"
            "format=yuv420p"
        ),
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        str(output),
    ])


def build_voiceover(output: Path) -> None:
    SCRIPT_PATH.write_text(
        "# Shell Launch Demo Voiceover\n\n"
        "This is the voiceover script used by `tools/build_launch_video.py`.\n\n"
        "```text\n"
        f"{VOICEOVER.strip()}\n"
        "```\n",
        encoding="utf-8",
    )
    run(["say", "-v", "Rishi", "-r", "178", "-o", str(output), VOICEOVER])


def main() -> int:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required to build the launch video.")
    if not shutil.which("say"):
        raise SystemExit("macOS say is required for the local voiceover build.")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    segments: list[Path] = []
    for index, slide in enumerate(SLIDES, start=1):
        segment = BUILD_DIR / f"{index:02d}_{slide['name']}.mp4"
        render_segment(ROOT / str(slide["image"]), int(slide["duration"]), segment)
        segments.append(segment)

    concat_file = BUILD_DIR / "segments.txt"
    concat_file.write_text(
        "".join(f"file '{segment.as_posix()}'\n" for segment in segments),
        encoding="utf-8",
    )
    silent_video = BUILD_DIR / "silent.mp4"
    run([
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(silent_video),
    ])

    voiceover = BUILD_DIR / "voiceover.aiff"
    build_voiceover(voiceover)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg",
        "-y",
        "-i",
        str(silent_video),
        "-i",
        str(voiceover),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "24",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(OUTPUT),
    ])
    print(f"Created {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
