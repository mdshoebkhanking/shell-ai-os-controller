#!/usr/bin/env python3
"""Build the premium public Shell AI launch demo video.

The builder stays local and reproducible:
- HTML/CSS slides are rendered with headless Chrome.
- FFmpeg adds motion, encoding, preview GIF, and audio mixing.
- macOS `say` creates the voiceover without storing third-party audio assets.
"""

from __future__ import annotations

import html
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / ".shell_runtime" / "demo_media_build"
SLIDE_DIR = BUILD_DIR / "slides"
PNG_DIR = BUILD_DIR / "png"
SEGMENT_DIR = BUILD_DIR / "segments"
OUTPUT = ROOT / "videos" / "shell-launch-demo.mp4"
POSTER = ROOT / "videos" / "shell-launch-demo-poster.png"
PREVIEW_GIF = ROOT / "gifs" / "shell-launch-preview.gif"
SCRIPT_PATH = ROOT / "videos" / "shell-launch-demo-voiceover.md"
WIDTH = 1280
HEIGHT = 720
FPS = 30
VOICE = "Daniel"
VOICE_RATE = "180"


VOICEOVER = """Meet Shell AI OS Controller, version one point zero, created by mdshoebking.

This is a desktop AI operating layer, not a normal chatbot.
It brings chat, voice, tools, automation, diagnostics, and safe execution into one focused workspace.

Chat is text first and fast.
Actions stay visible, tool results stay traceable, and voice remains under user control.

The voice workspace keeps transcript, audio state, and assistant controls clean.
The tool gateway organizes browser actions, files, apps, email, media, and system tasks with clearer boundaries.

The operations dashboard shows runtime health, dependencies, logs, release checks, and production readiness.

For beginners, Shell includes one click setup flows for Windows, macOS, and Linux.
For developers, it is open source, modular, and prepared for agents, plugins, workflows, and future AI runtimes.

Shell is built to be transparent, practical, and ready for real AI desktop automation.
"""


@dataclass(frozen=True)
class Scene:
    name: str
    duration: float
    html: str


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def asset_uri(relative_path: str) -> str:
    return (ROOT / relative_path).resolve().as_uri()


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def find_chrome() -> str:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise SystemExit("Headless Chrome is required to render the launch video slides.")


def base_css() -> str:
    return f"""
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      width: {WIDTH}px;
      height: {HEIGHT}px;
      overflow: hidden;
      background: #020407;
      color: #f7fbff;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", Inter, Segoe UI, Arial, sans-serif;
    }}
    .stage {{
      position: relative;
      width: {WIDTH}px;
      height: {HEIGHT}px;
      overflow: hidden;
      background:
        radial-gradient(circle at 76% 18%, rgba(31, 221, 255, 0.24), transparent 27%),
        radial-gradient(circle at 19% 78%, rgba(112, 122, 255, 0.20), transparent 29%),
        linear-gradient(135deg, #05080d 0%, #07111b 46%, #030508 100%);
    }}
    .stage:before {{
      content: "";
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(255,255,255,0.055) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px);
      background-size: 64px 64px;
      mask-image: radial-gradient(circle at center, black 0%, transparent 78%);
      opacity: 0.22;
    }}
    .stage:after {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(255,255,255,0.045), transparent 12%, transparent 82%, rgba(0,0,0,0.58));
      pointer-events: none;
    }}
    .noise {{
      position: absolute;
      inset: 0;
      opacity: 0.09;
      background:
        repeating-linear-gradient(0deg, rgba(255,255,255,0.04) 0px, rgba(255,255,255,0.04) 1px, transparent 1px, transparent 4px);
      mix-blend-mode: overlay;
    }}
    .topbar {{
      position: absolute;
      top: 26px;
      left: 44px;
      right: 44px;
      height: 54px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      z-index: 4;
      color: rgba(236, 248, 255, 0.76);
      font-size: 14px;
      letter-spacing: 0;
    }}
    .brand-mini {{
      display: flex;
      gap: 12px;
      align-items: center;
      font-weight: 700;
      color: #f7fbff;
    }}
    .brand-mini img {{
      width: 34px;
      height: 34px;
      border-radius: 10px;
      box-shadow: 0 0 28px rgba(46, 232, 255, 0.35);
    }}
    .pill-row {{ display: flex; gap: 10px; align-items: center; }}
    .pill {{
      border: 1px solid rgba(128, 234, 255, 0.24);
      background: rgba(8, 18, 30, 0.72);
      box-shadow: inset 0 1px rgba(255,255,255,0.12), 0 12px 40px rgba(0,0,0,0.28);
      border-radius: 999px;
      padding: 8px 13px;
      color: rgba(230, 246, 255, 0.82);
      backdrop-filter: blur(14px);
      font-size: 13px;
      font-weight: 700;
    }}
    .content {{
      position: absolute;
      inset: 96px 58px 58px;
      z-index: 3;
    }}
    .kicker {{
      color: #69eaff;
      font-size: 15px;
      font-weight: 800;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0;
      font-size: 66px;
      line-height: 0.92;
      letter-spacing: 0;
      max-width: 780px;
      text-shadow: 0 26px 70px rgba(0,0,0,0.55);
    }}
    h2 {{
      margin: 0;
      font-size: 48px;
      line-height: 1;
      letter-spacing: 0;
      max-width: 520px;
      text-shadow: 0 24px 60px rgba(0,0,0,0.50);
    }}
    .lead {{
      margin-top: 22px;
      max-width: 530px;
      color: rgba(233, 246, 255, 0.78);
      font-size: 20px;
      line-height: 1.42;
      font-weight: 500;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: 450px 1fr;
      gap: 70px;
      align-items: center;
      height: 100%;
    }}
    .logo-wrap {{
      position: relative;
      width: 430px;
      height: 430px;
      display: grid;
      place-items: center;
    }}
    .logo-wrap:before {{
      content: "";
      position: absolute;
      inset: 12px;
      border-radius: 50%;
      border: 1px solid rgba(118, 236, 255, 0.18);
      box-shadow: 0 0 90px rgba(35, 224, 255, 0.28), inset 0 0 90px rgba(68, 92, 255, 0.12);
    }}
    .logo-wrap:after {{
      content: "";
      position: absolute;
      width: 520px;
      height: 150px;
      border: 1px solid rgba(140, 236, 255, 0.18);
      border-radius: 50%;
      transform: rotate(-18deg);
      filter: blur(0.2px);
    }}
    .hero-logo {{
      width: 348px;
      height: 348px;
      border-radius: 48px;
      box-shadow: 0 50px 120px rgba(0,0,0,0.70), 0 0 72px rgba(105, 234, 255, 0.24);
      z-index: 2;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 418px 1fr;
      gap: 44px;
      align-items: center;
      height: 100%;
    }}
    .layout.reverse {{
      grid-template-columns: 1fr 418px;
    }}
    .copy-card {{
      padding: 28px;
      border-radius: 28px;
      background: linear-gradient(145deg, rgba(10, 22, 36, 0.78), rgba(4, 9, 15, 0.56));
      border: 1px solid rgba(127, 232, 255, 0.17);
      box-shadow: 0 28px 80px rgba(0,0,0,0.40), inset 0 1px rgba(255,255,255,0.08);
      backdrop-filter: blur(18px);
    }}
    .mockup {{
      position: relative;
      border-radius: 32px;
      padding: 14px;
      background:
        linear-gradient(135deg, rgba(255,255,255,0.26), rgba(255,255,255,0.03) 36%, rgba(94, 231, 255, 0.20));
      box-shadow: 0 40px 120px rgba(0,0,0,0.58), 0 0 70px rgba(24, 209, 255, 0.14);
      transform: perspective(1100px) rotateY(-4deg) rotateX(1.5deg);
    }}
    .reverse .mockup {{
      transform: perspective(1100px) rotateY(4deg) rotateX(1.5deg);
    }}
    .mockup img {{
      width: 100%;
      height: 452px;
      object-fit: cover;
      display: block;
      border-radius: 22px;
      background: #05080d;
    }}
    .mockup:after {{
      content: "";
      position: absolute;
      left: 44px;
      right: 44px;
      bottom: -22px;
      height: 32px;
      border-radius: 50%;
      background: rgba(64, 225, 255, 0.28);
      filter: blur(22px);
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 24px;
    }}
    .chip {{
      padding: 10px 13px;
      border-radius: 999px;
      background: rgba(103, 235, 255, 0.10);
      border: 1px solid rgba(103, 235, 255, 0.20);
      color: rgba(237, 251, 255, 0.92);
      font-size: 13px;
      font-weight: 800;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 18px;
      margin-top: 42px;
    }}
    .card {{
      min-height: 176px;
      border-radius: 26px;
      padding: 22px;
      background: linear-gradient(145deg, rgba(9, 21, 34, 0.82), rgba(4, 8, 14, 0.64));
      border: 1px solid rgba(129, 235, 255, 0.18);
      box-shadow: 0 28px 80px rgba(0,0,0,0.34), inset 0 1px rgba(255,255,255,0.08);
    }}
    .card b {{
      display: block;
      font-size: 20px;
      margin-bottom: 10px;
      color: #ffffff;
    }}
    .card span {{
      color: rgba(230, 246, 255, 0.70);
      font-size: 15px;
      line-height: 1.38;
      font-weight: 550;
    }}
    .metric-row {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-top: 26px;
    }}
    .metric {{
      border-radius: 20px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.11);
      padding: 18px;
    }}
    .metric strong {{
      display: block;
      font-size: 34px;
      color: #ffffff;
      margin-bottom: 3px;
    }}
    .metric small {{
      color: rgba(221, 242, 255, 0.68);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .timeline {{
      position: absolute;
      left: 58px;
      right: 58px;
      bottom: 30px;
      height: 3px;
      border-radius: 99px;
      background: rgba(255,255,255,0.08);
      z-index: 4;
    }}
    .timeline span {{
      display: block;
      height: 100%;
      border-radius: 99px;
      background: linear-gradient(90deg, #69eaff, #ffffff, #7d88ff);
      box-shadow: 0 0 18px rgba(105, 234, 255, 0.72);
    }}
    """


def page(body: str, progress: int) -> str:
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>{base_css()}</style>
</head>
<body>
<main class="stage">
  <div class="noise"></div>
  <div class="topbar">
    <div class="brand-mini"><img src="{asset_uri('assets/brand/shell-official-logo.png')}" alt=""> Shell AI OS Controller</div>
    <div class="pill-row">
      <div class="pill">v1.0.0</div>
      <div class="pill">by mdshoebking</div>
    </div>
  </div>
  {body}
  <div class="timeline"><span style="width:{progress}%"></span></div>
</main>
</body>
</html>
"""


def chips(items: list[str]) -> str:
    return '<div class="chips">' + "".join(f'<span class="chip">{esc(item)}</span>' for item in items) + "</div>"


def screenshot_scene(
    *,
    kicker: str,
    title: str,
    lead: str,
    image: str,
    chip_items: list[str],
    progress: int,
    reverse: bool = False,
) -> str:
    copy = f"""
    <section class="copy-card">
      <div class="kicker">{esc(kicker)}</div>
      <h2>{esc(title)}</h2>
      <div class="lead">{esc(lead)}</div>
      {chips(chip_items)}
    </section>
    """
    mockup = f"""
    <section class="mockup">
      <img src="{asset_uri(image)}" alt="">
    </section>
    """
    pieces = mockup + copy if reverse else copy + mockup
    cls = "layout reverse" if reverse else "layout"
    return page(f'<div class="content"><div class="{cls}">{pieces}</div></div>', progress)


def build_scenes() -> list[Scene]:
    logo = asset_uri("assets/brand/shell-official-logo.png")
    return [
        Scene(
            "01_hero",
            7.5,
            page(
                f"""
                <div class="content">
                  <div class="hero-grid">
                    <div class="logo-wrap"><img class="hero-logo" src="{logo}" alt=""></div>
                    <div>
                      <div class="kicker">Official public launch</div>
                      <h1>Shell AI OS Controller</h1>
                      <div class="lead">A cinematic desktop AI operating layer for chat, voice, tools, automation, and runtime diagnostics.</div>
                      {chips(["AI workspace", "Automation", "Voice", "Tools", "Open source"])}
                    </div>
                  </div>
                </div>
                """,
                12,
            ),
        ),
        Scene(
            "02_chat",
            8.5,
            screenshot_scene(
                kicker="Realtime workspace",
                title="Chat that shows the work",
                lead="Fast text-first interaction with visible execution state, tool results, and assistant responses in one focused control surface.",
                image="screenshots/showcase/chat-interface.png",
                chip_items=["Text first", "Traceable actions", "No hidden execution"],
                progress=25,
            ),
        ),
        Scene(
            "03_voice",
            8.5,
            screenshot_scene(
                kicker="Voice control",
                title="Voice only when you want it",
                lead="A dedicated voice workspace for transcripts, audio state, and assistant controls without forcing speech into every chat reply.",
                image="screenshots/showcase/voice-interface.png",
                chip_items=["Transcript", "Audio state", "Voice on demand"],
                progress=38,
                reverse=True,
            ),
        ),
        Scene(
            "04_tools",
            8.5,
            screenshot_scene(
                kicker="Tool gateway",
                title="Automation with boundaries",
                lead="Shell organizes tools, agents, and integrations so actions can be routed, tested, explained, and improved over time.",
                image="screenshots/showcase/tools-catalog.png",
                chip_items=["Browser", "Files", "Apps", "Email", "Media", "System"],
                progress=51,
            ),
        ),
        Scene(
            "05_ops",
            8.5,
            screenshot_scene(
                kicker="Operations center",
                title="Health you can inspect",
                lead="Runtime readiness, dependency checks, logs, and release gates make the project easier to debug and safer to ship.",
                image="screenshots/showcase/system-dashboard.png",
                chip_items=["Diagnostics", "Release gates", "Runtime logs"],
                progress=64,
                reverse=True,
            ),
        ),
        Scene(
            "06_install",
            8.5,
            page(
                f"""
                <div class="content">
                  <div class="layout">
                    <section class="copy-card">
                      <div class="kicker">Beginner setup</div>
                      <h2>Download. Install. Launch.</h2>
                      <div class="lead">One-click launchers and repair flows reduce terminal setup, dependency confusion, and first-run friction.</div>
                      {chips(["Windows", "macOS", "Linux", "Repair flow"])}
                      <div class="metric-row">
                        <div class="metric"><strong>1</strong><small>starter file</small></div>
                        <div class="metric"><strong>3</strong><small>platforms</small></div>
                        <div class="metric"><strong>100</strong><small>readiness</small></div>
                      </div>
                    </section>
                    <section class="mockup"><img src="{asset_uri('screenshots/showcase/settings-panel.png')}" alt=""></section>
                  </div>
                </div>
                """,
                77,
            ),
        ),
        Scene(
            "07_ecosystem",
            8.5,
            page(
                f"""
                <div class="content">
                  <div class="kicker">Open source ecosystem</div>
                  <h1 style="font-size:58px; max-width:940px;">Built to grow without pretending to be AGI.</h1>
                  <div class="lead" style="max-width:760px;">Transparent architecture for agents, plugins, workflows, memory, observability, and safe automation.</div>
                  <div class="cards">
                    <div class="card"><b>Agents</b><span>Role-based execution with boundaries, fallbacks, and clear ownership.</span></div>
                    <div class="card"><b>Plugins</b><span>Future extension points for tools, workflows, providers, and UI panels.</span></div>
                    <div class="card"><b>Memory</b><span>Context and workflow memory planned around user control and privacy.</span></div>
                    <div class="card"><b>Safety</b><span>Risk scoring, approvals, audit logs, and reversible automation.</span></div>
                  </div>
                </div>
                """,
                90,
            ),
        ),
        Scene(
            "08_final",
            10.0,
            page(
                f"""
                <div class="content">
                  <div class="hero-grid">
                    <div class="logo-wrap"><img class="hero-logo" src="{logo}" alt=""></div>
                    <div>
                      <div class="kicker">Shell AI OS Controller</div>
                      <h1>Clone. Install. Launch. Build.</h1>
                      <div class="lead">A transparent AI desktop automation ecosystem, open source and ready for real testing.</div>
                      {chips(["github.com/mdshoebkhanking/shell-ai-os-controller", "v1.0.0", "MIT licensed"])}
                    </div>
                  </div>
                </div>
                """,
                100,
            ),
        ),
    ]


def render_slide(chrome: str, scene: Scene) -> Path:
    html_path = SLIDE_DIR / f"{scene.name}.html"
    png_path = PNG_DIR / f"{scene.name}.png"
    html_path.write_text(scene.html, encoding="utf-8")
    run(
        [
            chrome,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--log-level=3",
            "--hide-scrollbars",
            "--allow-file-access-from-files",
            f"--screenshot={png_path}",
            f"--window-size={WIDTH},{HEIGHT}",
            html_path.resolve().as_uri(),
        ]
    )
    return png_path


def render_segment(scene: Scene, image: Path) -> Path:
    segment = SEGMENT_DIR / f"{scene.name}.mp4"
    frames = int(scene.duration * FPS)
    fade_out = max(0.0, scene.duration - 0.45)
    run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-vf",
            (
                "scale=1280:720,"
                f"zoompan=z='min(zoom+0.00042,1.035)':d={frames}:s=1280x720:fps={FPS},"
                "fade=t=in:st=0:d=0.28,"
                f"fade=t=out:st={fade_out}:d=0.35,"
                "format=yuv420p"
            ),
            "-t",
            f"{scene.duration:.2f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            str(segment),
        ]
    )
    return segment


def build_voiceover(output: Path) -> None:
    SCRIPT_PATH.write_text(
        "# Shell Launch Demo Voiceover\n\n"
        "This is the voiceover script used by `tools/build_launch_video.py`.\n\n"
        f"- Voice: macOS `{VOICE}`\n"
        f"- Rate: {VOICE_RATE} words per minute\n\n"
        "```text\n"
        f"{VOICEOVER.strip()}\n"
        "\n```\n",
        encoding="utf-8",
    )
    run(["say", "-v", VOICE, "-r", VOICE_RATE, "-o", str(output), VOICEOVER])


def build_audio(voiceover: Path, duration: float, output: Path) -> None:
    bed = BUILD_DIR / "ambient_bed.m4a"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=74:duration={duration:.2f}:sample_rate=44100",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=148:duration={duration:.2f}:sample_rate=44100",
            "-filter_complex",
            (
                "[0:a]volume=0.014[a0];"
                "[1:a]volume=0.008[a1];"
                f"[a0][a1]amix=inputs=2,afade=t=in:st=0:d=1.6,afade=t=out:st={max(0, duration - 2.0):.2f}:d=2.0[bed]"
            ),
            "-map",
            "[bed]",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            str(bed),
        ]
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(voiceover),
            "-i",
            str(bed),
            "-filter_complex",
            (
                "[0:a]highpass=f=75,lowpass=f=10000,acompressor=threshold=-20dB:ratio=2.2:attack=18:release=180,"
                "loudnorm=I=-16:TP=-1.5:LRA=11[voice];"
                "[1:a]volume=0.75[bed];"
                "[voice][bed]amix=inputs=2:duration=longest:dropout_transition=0,alimiter=limit=0.95[a]"
            ),
            "-map",
            "[a]",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output),
        ]
    )


def concat_segments(segments: list[Path], output: Path) -> None:
    concat_file = BUILD_DIR / "segments.txt"
    concat_file.write_text(
        "".join(f"file '{segment.as_posix()}'\n" for segment in segments),
        encoding="utf-8",
    )
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(output)])


def combine(video: Path, audio: Path, duration: float) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-t",
            f"{duration:.2f}",
            "-movflags",
            "+faststart",
            str(OUTPUT),
        ]
    )


def build_preview_gif() -> None:
    PREVIEW_GIF.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "00:00:06.2",
            "-i",
            str(OUTPUT),
            "-vf",
            (
                "fps=8,scale=760:-1:flags=lanczos,"
                "split[s0][s1];[s0]palettegen=max_colors=128[p];"
                "[s1][p]paletteuse=dither=bayer:bayer_scale=4"
            ),
            "-t",
            "16",
            str(PREVIEW_GIF),
        ]
    )


def main() -> int:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required to build the launch video.")
    if not shutil.which("say"):
        raise SystemExit("macOS say is required for the local voiceover build.")

    chrome = find_chrome()
    for directory in (SLIDE_DIR, PNG_DIR, SEGMENT_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    scenes = build_scenes()
    rendered = [render_slide(chrome, scene) for scene in scenes]
    shutil.copyfile(rendered[1], POSTER)

    segments = [render_segment(scene, image) for scene, image in zip(scenes, rendered)]
    silent_video = BUILD_DIR / "silent_premium.mp4"
    concat_segments(segments, silent_video)

    duration = sum(scene.duration for scene in scenes)
    voiceover = BUILD_DIR / "voiceover.aiff"
    final_audio = BUILD_DIR / "launch_audio.m4a"
    build_voiceover(voiceover)
    build_audio(voiceover, duration, final_audio)
    combine(silent_video, final_audio, duration)
    build_preview_gif()

    print(f"Created {OUTPUT.relative_to(ROOT)}")
    print(f"Created {POSTER.relative_to(ROOT)}")
    print(f"Created {PREVIEW_GIF.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
