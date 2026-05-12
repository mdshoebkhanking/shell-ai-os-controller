#!/usr/bin/env python3
"""Build the public Shell AI cinematic launch demo video.

The video is generated locally from versioned assets:
- HTML/CSS shots rendered with headless Chrome.
- FFmpeg turns still frames into fast cinematic motion cuts.
- macOS `say` creates a local voiceover.
- FFmpeg creates a synthetic cinematic bed, transition hits, and preview GIF.

The result is intentionally short-shot and high-energy so it does not feel
like a static slide deck.
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
VOICE_RATE = "176"


VOICEOVER = """Shell AI OS Controller.
The future of AI automation, built by mdshoebking.

This is not a normal chatbot.
It is a desktop AI operating layer for chat, voice, tools, diagnostics, and controlled automation.

Ask. Execute. Inspect. Continue.

Text stays fast.
Voice stays optional.
Actions stay visible.

Shell connects workflows across apps, files, browser tasks, media, email, and system tools with safer boundaries.

For beginners, setup is simple.
For developers, the platform is open, modular, and ready to extend.

Agents, plugins, workflows, health checks, release gates, and runtime diagnostics work together in one AI workspace.

Shell is not pretending to be AGI.
It is practical AI infrastructure for real desktop productivity.

Shell AI OS Controller.
Build. Automate. Evolve.
"""


@dataclass(frozen=True)
class Scene:
    name: str
    duration: float
    html: str
    motion: str = "push"


def run(cmd: list[str], *, timeout: float | None = None) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True, timeout=timeout)


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
        radial-gradient(circle at 76% 18%, rgba(255,255,255,0.12), transparent 24%),
        radial-gradient(circle at 18% 76%, rgba(88,232,255,0.20), transparent 30%),
        linear-gradient(135deg, #020407 0%, #071018 46%, #111820 100%);
    }}
    .stage:before {{
      content: "";
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px);
      background-size: 58px 58px;
      mask-image: radial-gradient(circle at center, black 0%, transparent 78%);
      opacity: 0.24;
    }}
    .stage:after {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.055), transparent 15%, transparent 82%, rgba(0,0,0,0.72)),
        radial-gradient(circle at center, transparent 50%, rgba(0,0,0,0.35));
      pointer-events: none;
    }}
    .noise {{
      position: absolute;
      inset: 0;
      opacity: 0.08;
      background: repeating-linear-gradient(0deg, rgba(255,255,255,0.06) 0px, rgba(255,255,255,0.06) 1px, transparent 1px, transparent 4px);
      mix-blend-mode: overlay;
    }}
    .topbar {{
      position: absolute;
      left: 42px;
      right: 42px;
      top: 24px;
      height: 46px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      z-index: 8;
      color: rgba(242,248,255,0.78);
      font-size: 13px;
      font-weight: 700;
    }}
    .brand-mini {{
      display: flex;
      align-items: center;
      gap: 10px;
      color: #f7fbff;
    }}
    .brand-mini img {{
      width: 32px;
      height: 32px;
      border-radius: 9px;
      box-shadow: 0 0 28px rgba(255,255,255,0.16);
    }}
    .pill-row {{ display: flex; gap: 8px; }}
    .pill {{
      border: 1px solid rgba(255,255,255,0.16);
      background: rgba(8, 14, 22, 0.70);
      border-radius: 999px;
      padding: 8px 12px;
      backdrop-filter: blur(14px);
    }}
    .content {{
      position: absolute;
      inset: 88px 56px 52px;
      z-index: 5;
    }}
    .shine {{
      position: absolute;
      width: 720px;
      height: 90px;
      left: -120px;
      top: 76px;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.36), transparent);
      transform: rotate(-18deg);
      filter: blur(10px);
      opacity: 0.55;
    }}
    .logo-core {{
      position: relative;
      display: grid;
      place-items: center;
      width: 392px;
      height: 392px;
      margin: 0 auto;
    }}
    .logo-core:before {{
      content: "";
      position: absolute;
      inset: -22px;
      border-radius: 50%;
      border: 1px solid rgba(255,255,255,0.15);
      box-shadow: 0 0 110px rgba(129,240,255,0.20), inset 0 0 70px rgba(255,255,255,0.08);
    }}
    .logo-core:after {{
      content: "";
      position: absolute;
      width: 550px;
      height: 132px;
      border: 1px solid rgba(130,236,255,0.20);
      border-radius: 50%;
      transform: rotate(-17deg);
    }}
    .logo-core img {{
      width: 330px;
      height: 330px;
      border-radius: 66px;
      z-index: 2;
      box-shadow: 0 50px 120px rgba(0,0,0,0.72), 0 0 60px rgba(255,255,255,0.15);
    }}
    .hero {{
      display: grid;
      grid-template-columns: 460px 1fr;
      gap: 68px;
      align-items: center;
      height: 100%;
    }}
    .kicker {{
      color: #83ecff;
      font-size: 14px;
      font-weight: 850;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      margin-bottom: 16px;
    }}
    h1 {{
      margin: 0;
      max-width: 820px;
      font-size: 70px;
      line-height: 0.9;
      letter-spacing: 0;
      text-shadow: 0 28px 80px rgba(0,0,0,0.65);
    }}
    h2 {{
      margin: 0;
      max-width: 600px;
      font-size: 48px;
      line-height: 0.98;
      letter-spacing: 0;
    }}
    .lead {{
      margin-top: 20px;
      max-width: 620px;
      color: rgba(232,244,251,0.78);
      font-size: 20px;
      line-height: 1.38;
      font-weight: 560;
    }}
    .impact {{
      display: grid;
      place-items: center;
      height: 100%;
      text-align: center;
    }}
    .impact h1 {{
      max-width: 1000px;
      font-size: 88px;
      line-height: 0.84;
      text-transform: uppercase;
    }}
    .impact .lead {{
      margin-left: auto;
      margin-right: auto;
      max-width: 760px;
    }}
    .ui-shot {{
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 42px;
      align-items: center;
      height: 100%;
    }}
    .ui-shot.reverse {{
      grid-template-columns: 0.95fr 1.05fr;
    }}
    .copy {{
      border-radius: 28px;
      padding: 28px;
      background: linear-gradient(145deg, rgba(11,20,30,0.82), rgba(4,7,12,0.62));
      border: 1px solid rgba(255,255,255,0.13);
      box-shadow: 0 28px 90px rgba(0,0,0,0.44), inset 0 1px rgba(255,255,255,0.10);
      backdrop-filter: blur(18px);
    }}
    .mock {{
      position: relative;
      border-radius: 30px;
      padding: 13px;
      background: linear-gradient(135deg, rgba(255,255,255,0.30), rgba(255,255,255,0.04) 38%, rgba(108,235,255,0.22));
      box-shadow: 0 42px 120px rgba(0,0,0,0.62), 0 0 70px rgba(130,236,255,0.12);
      transform: perspective(1000px) rotateY(-5deg) rotateX(1.5deg);
    }}
    .reverse .mock {{
      transform: perspective(1000px) rotateY(5deg) rotateX(1.5deg);
    }}
    .mock img {{
      width: 100%;
      height: 448px;
      display: block;
      object-fit: cover;
      border-radius: 21px;
      background: #05080d;
    }}
    .mock:after {{
      content: "";
      position: absolute;
      left: 56px;
      right: 56px;
      bottom: -24px;
      height: 34px;
      border-radius: 50%;
      background: rgba(116,235,255,0.26);
      filter: blur(22px);
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 9px;
      margin-top: 24px;
    }}
    .chip {{
      padding: 10px 13px;
      border-radius: 999px;
      color: rgba(246,251,255,0.95);
      background: rgba(114,232,255,0.10);
      border: 1px solid rgba(114,232,255,0.22);
      font-size: 13px;
      font-weight: 850;
    }}
    .node-map {{
      position: relative;
      height: 470px;
      border-radius: 34px;
      border: 1px solid rgba(255,255,255,0.12);
      background:
        radial-gradient(circle at center, rgba(118,236,255,0.14), transparent 42%),
        linear-gradient(145deg, rgba(9,17,27,0.82), rgba(3,5,9,0.64));
      box-shadow: 0 42px 120px rgba(0,0,0,0.55);
      overflow: hidden;
    }}
    .node-map svg {{
      position: absolute;
      inset: 0;
    }}
    .node {{
      position: absolute;
      width: 164px;
      padding: 15px 16px;
      border-radius: 22px;
      background: rgba(9,18,28,0.86);
      border: 1px solid rgba(255,255,255,0.14);
      color: #f7fbff;
      font-size: 15px;
      font-weight: 850;
      box-shadow: 0 18px 54px rgba(0,0,0,0.38);
    }}
    .node small {{
      display: block;
      margin-top: 4px;
      color: rgba(228,243,251,0.62);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-top: 26px;
    }}
    .metric {{
      border-radius: 18px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      padding: 16px;
    }}
    .metric strong {{
      display: block;
      font-size: 34px;
      color: #ffffff;
    }}
    .metric small {{
      color: rgba(224,240,249,0.70);
      font-size: 12px;
      font-weight: 850;
      text-transform: uppercase;
    }}
    .timeline {{
      position: absolute;
      left: 58px;
      right: 58px;
      bottom: 28px;
      height: 3px;
      border-radius: 99px;
      background: rgba(255,255,255,0.08);
      z-index: 8;
    }}
    .timeline span {{
      display: block;
      height: 100%;
      border-radius: 99px;
      background: linear-gradient(90deg, #f7fbff, #83ecff, #a0a8ff);
      box-shadow: 0 0 20px rgba(131,236,255,0.62);
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
  <div class="shine"></div>
  <div class="topbar">
    <div class="brand-mini"><img src="{asset_uri('assets/brand/shell-official-logo.png')}" alt=""> Shell AI OS Controller</div>
    <div class="pill-row">
      <div class="pill">v1.0.0</div>
      <div class="pill">mdshoebking</div>
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


def logo_markup(size_class: str = "logo-core") -> str:
    return f'<div class="{size_class}"><img src="{asset_uri("assets/brand/shell-official-logo.png")}" alt=""></div>'


def impact(kicker: str, title: str, lead: str, tags: list[str], progress: int) -> str:
    return page(
        f"""
        <div class="content">
          <section class="impact">
            <div>
              <div class="kicker">{esc(kicker)}</div>
              <h1>{esc(title)}</h1>
              <div class="lead">{esc(lead)}</div>
              {chips(tags)}
            </div>
          </section>
        </div>
        """,
        progress,
    )


def hero(title: str, lead: str, progress: int) -> str:
    return page(
        f"""
        <div class="content">
          <section class="hero">
            {logo_markup()}
            <div>
              <div class="kicker">Official public launch</div>
              <h1>{esc(title)}</h1>
              <div class="lead">{esc(lead)}</div>
              {chips(["AI workspace", "Automation", "Voice", "Tools", "Open source"])}
            </div>
          </section>
        </div>
        """,
        progress,
    )


def ui_scene(kicker: str, title: str, lead: str, image: str, tags: list[str], progress: int, reverse: bool = False) -> str:
    copy = f"""
    <section class="copy">
      <div class="kicker">{esc(kicker)}</div>
      <h2>{esc(title)}</h2>
      <div class="lead">{esc(lead)}</div>
      {chips(tags)}
    </section>
    """
    mock = f'<section class="mock"><img src="{asset_uri(image)}" alt=""></section>'
    pieces = mock + copy if reverse else copy + mock
    cls = "ui-shot reverse" if reverse else "ui-shot"
    return page(f'<div class="content"><div class="{cls}">{pieces}</div></div>', progress)


def node_scene(kicker: str, title: str, lead: str, progress: int) -> str:
    return page(
        f"""
        <div class="content">
          <div class="ui-shot reverse">
            <section class="node-map">
              <svg viewBox="0 0 620 470" preserveAspectRatio="none">
                <path d="M310 235 L130 112 M310 235 L492 104 M310 235 L116 346 M310 235 L512 352" stroke="#83ecff" stroke-opacity="0.36" stroke-width="2"/>
                <circle cx="310" cy="235" r="72" fill="none" stroke="#ffffff" stroke-opacity="0.18" stroke-width="2"/>
                <circle cx="310" cy="235" r="34" fill="#f7fbff" fill-opacity="0.90"/>
              </svg>
              <div class="node" style="left:226px; top:186px;">Shell Core<small>orchestration</small></div>
              <div class="node" style="left:48px; top:68px;">Agents<small>planned tasks</small></div>
              <div class="node" style="right:44px; top:62px;">Tools<small>safe routes</small></div>
              <div class="node" style="left:46px; bottom:60px;">Memory<small>context</small></div>
              <div class="node" style="right:42px; bottom:56px;">Plugins<small>future sdk</small></div>
            </section>
            <section class="copy">
              <div class="kicker">{esc(kicker)}</div>
              <h2>{esc(title)}</h2>
              <div class="lead">{esc(lead)}</div>
              {chips(["Agents", "Plugins", "Workflows", "Health", "Diagnostics"])}
            </section>
          </div>
        </div>
        """,
        progress,
    )


def install_scene(progress: int) -> str:
    return page(
        f"""
        <div class="content">
          <div class="ui-shot">
            <section class="copy">
              <div class="kicker">Beginner friendly</div>
              <h2>Download. Install. Launch.</h2>
              <div class="lead">One-click setup and repair flows reduce terminal setup, dependency confusion, and first-run friction.</div>
              {chips(["Windows", "macOS", "Linux", "Repair tools"])}
              <div class="metrics">
                <div class="metric"><strong>1</strong><small>starter file</small></div>
                <div class="metric"><strong>3</strong><small>platforms</small></div>
                <div class="metric"><strong>100</strong><small>readiness gate</small></div>
              </div>
            </section>
            <section class="mock"><img src="{asset_uri('screenshots/showcase/settings-panel.png')}" alt=""></section>
          </div>
        </div>
        """,
        progress,
    )


def build_scenes() -> list[Scene]:
    raw: list[tuple[str, float, str, str]] = [
        ("01_intro_logo", 3.0, hero("SHELL AI OS", "A premium AI desktop control layer for real workflows.", 4), "push"),
        ("02_future", 2.0, impact("Launch trailer", "The future of AI automation", "Built for visible, human-controlled desktop productivity.", ["Official logo", "v1.0.0"], 7), "pull"),
        ("03_ai_workflows", 1.35, impact("System reveal", "AI Workflows", "Plan, route, execute, inspect.", ["Fast", "Traceable"], 9), "left"),
        ("04_chat_cut", 1.75, ui_scene("Realtime interface", "Chat that shows the work", "Text-first interaction with visible tool state.", "screenshots/showcase/chat-interface.png", ["Text", "Tools", "Results"], 12), "right"),
        ("05_automation", 1.25, impact("Capability", "Automation", "Local tools with clearer boundaries.", ["Apps", "Files", "Browser"], 14), "push"),
        ("06_tools_cut", 1.75, ui_scene("Tool gateway", "Routes stay visible", "Actions can be tested, explained, and improved.", "screenshots/showcase/tools-catalog.png", ["Registry", "Safety", "Fallbacks"], 17, True), "left"),
        ("07_future_ready", 1.3, impact("Platform", "Future Ready", "Open source architecture for long-term growth.", ["Plugins", "Agents"], 19), "pull"),
        ("08_voice", 2.0, ui_scene("Voice workspace", "Voice only when you want it", "Transcript, audio state, and assistant controls stay clean.", "screenshots/showcase/voice-interface.png", ["Transcript", "Audio", "Control"], 22), "right"),
        ("09_dashboard", 2.0, ui_scene("Operations", "Health you can inspect", "Runtime checks, logs, release gates, and diagnostics.", "screenshots/showcase/system-dashboard.png", ["Health", "Logs", "Gates"], 25, True), "left"),
        ("10_settings", 2.0, ui_scene("Configuration", "Setup with confidence", "API setup, themes, voice, Telegram, and repair paths.", "screenshots/showcase/settings-panel.png", ["Beginner mode", "Repair"], 28), "push"),
        ("11_windows", 2.0, ui_scene("Real acceptance", "Tested on desktop flows", "Windows acceptance captures keep the product honest.", "screenshots/showcase/windows-chat-acceptance.png", ["Windows", "UI", "Runtime"], 31, True), "right"),
        ("12_built_everyone", 2.5, impact("Beginner experience", "Built for everyone", "Powerful enough for developers. Simple enough for beginners.", ["No terminal maze", "Clear fixes"], 35), "pull"),
        ("13_install", 2.5, install_scene(39), "push"),
        ("14_platforms", 2.35, impact("Cross platform", "Windows. macOS. Linux.", "One project structure. Clean launch paths.", ["Install", "Launch", "Repair"], 43), "left"),
        ("15_errors", 2.1, impact("Better failures", "Human-readable errors", "No raw dependency panic when the system can explain what to fix.", ["Diagnostics", "Recovery"], 46), "right"),
        ("16_nodes", 3.0, node_scene("AI operating ecosystem", "Agents, tools, memory, plugins", "A modular foundation for future AI workflows without unsafe autonomy.", 51), "push"),
        ("17_plugins", 3.0, impact("Extensible", "Build. Automate. Extend.", "Designed for workflows, plugins, agents, and future AI runtimes.", ["SDK ready", "Open source"], 56), "pull"),
        ("18_observable", 3.0, ui_scene("Observable", "The system explains itself", "Health panels and release gates make behavior easier to debug.", "screenshots/showcase/system-dashboard.png", ["Trace", "Inspect", "Recover"], 61), "left"),
        ("19_human", 3.0, impact("Trust boundary", "Human controlled", "Shell assists, routes, and automates approved workflows. It does not pretend to be AGI.", ["Visible actions", "Approvals"], 66), "right"),
        ("20_build", 1.3, impact("Hype", "Build", "Create workflows faster.", ["Workspace"], 69), "push"),
        ("21_chat_zoom", 1.5, ui_scene("Live", "Ask. Execute.", "Chat, route, inspect.", "screenshots/showcase/chat-interface.png", ["Fast"], 72, True), "left"),
        ("22_automate", 1.3, impact("Hype", "Automate", "Connect local desktop work.", ["Tools"], 75), "pull"),
        ("23_tools_zoom", 1.5, ui_scene("Control", "Tools in one place", "Browser, files, apps, media, email, system.", "screenshots/showcase/tools-catalog.png", ["300+ tools"], 78), "right"),
        ("24_evolve", 1.3, impact("Hype", "Evolve", "Open architecture. Real roadmap.", ["Community"], 81), "push"),
        ("25_runtime_zoom", 1.5, ui_scene("Runtime", "Production gates", "Release checks before public shipping.", "screenshots/showcase/system-dashboard.png", ["100/100"], 84, True), "left"),
        ("26_logo_flash", 1.5, hero("Shell AI OS Controller", "A futuristic AI workspace with practical boundaries.", 87), "pull"),
        ("27_repo", 1.9, impact("Open source", "GitHub repository", "github.com/mdshoebkhanking/shell-ai-os-controller", ["Apache-2.0", "v1.0.0"], 90), "right"),
        ("28_final_logo", 5.0, hero("Shell AI OS Controller", "The future of AI productivity, built by mdshoebking.", 96), "push"),
        ("29_final_words", 4.2, impact("Final", "Build. Automate. Evolve.", "Clone the repository and start testing Shell.", ["github.com/mdshoebkhanking/shell-ai-os-controller"], 100), "pull"),
    ]
    return [Scene(name, duration, html_text, motion) for name, duration, html_text, motion in raw]


def render_slide(chrome: str, scene: Scene) -> Path:
    html_path = SLIDE_DIR / f"{scene.name}.html"
    png_path = PNG_DIR / f"{scene.name}.png"
    html_path.write_text(scene.html, encoding="utf-8")
    cmd = [
        chrome,
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-extensions",
        "--log-level=3",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        f"--screenshot={png_path}",
        f"--window-size={WIDTH},{HEIGHT}",
        html_path.resolve().as_uri(),
    ]
    last_error: Exception | None = None
    for attempt in range(2):
        proc = subprocess.Popen(cmd, cwd=ROOT)
        try:
            return_code = proc.wait(timeout=24)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.wait()
            if png_path.exists() and png_path.stat().st_size > 4096:
                return png_path
            last_error = exc
            continue
        if return_code == 0:
            return png_path
        last_error = subprocess.CalledProcessError(return_code, cmd)
    if last_error:
        raise last_error
    return png_path


def zoompan_filter(scene: Scene) -> str:
    frames = int(scene.duration * FPS)
    fade_in = min(0.22, scene.duration * 0.18)
    fade_out_start = max(0.0, scene.duration - min(0.28, scene.duration * 0.20))
    x_expr = "iw/2-(iw/zoom/2)"
    y_expr = "ih/2-(ih/zoom/2)"
    if scene.motion == "left":
        x_expr = "iw/2-(iw/zoom/2)-18+on*0.38"
    elif scene.motion == "right":
        x_expr = "iw/2-(iw/zoom/2)+18-on*0.38"
    elif scene.motion == "pull":
        y_expr = "ih/2-(ih/zoom/2)-10+on*0.18"
    else:
        y_expr = "ih/2-(ih/zoom/2)+sin(on/9)*5"
    return (
        "scale=1360:765,"
        f"zoompan=z='min(zoom+0.00072,1.055)':x='{x_expr}':y='{y_expr}':d={frames}:s=1280x720:fps={FPS},"
        f"fade=t=in:st=0:d={fade_in:.2f},"
        f"fade=t=out:st={fade_out_start:.2f}:d=0.24,"
        "format=yuv420p"
    )


def render_segment(scene: Scene, image: Path) -> Path:
    segment = SEGMENT_DIR / f"{scene.name}.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-vf",
            zoompan_filter(scene),
            "-t",
            f"{scene.duration:.2f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "21",
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
    impact_ms = [0, 5000, 6400, 8200, 9400, 11200, 12500, 20500, 30000, 42000, 55800]
    filter_parts = [
        "[1:a]volume=0.020[a1]",
        "[2:a]volume=0.012[a2]",
        "[3:a]volume=0.030,highpass=f=700,lowpass=f=6000[air]",
    ]
    impact_labels: list[str] = []
    for idx, ms in enumerate(impact_ms):
        label = f"hit{idx}"
        impact_labels.append(f"[{label}]")
        filter_parts.append(
            f"[4:a]volume=0.20,afade=t=out:st=0.04:d=0.34,adelay={ms}|{ms}[{label}]"
        )
    bed_inputs = "[a1][a2][air]" + "".join(impact_labels)
    bed_count = 3 + len(impact_labels)
    filter_parts.append(
        f"{bed_inputs}amix=inputs={bed_count}:duration=longest:dropout_transition=0,"
        f"afade=t=in:st=0:d=1.2,afade=t=out:st={max(0, duration - 2.0):.2f}:d=2.0[bed]"
    )
    filter_parts.append(
        "[0:a]highpass=f=75,lowpass=f=10000,"
        "acompressor=threshold=-20dB:ratio=2.1:attack=14:release=170,"
        "loudnorm=I=-15:TP=-1.5:LRA=10[voice]"
    )
    filter_parts.append(
        "[voice][bed]amix=inputs=2:duration=longest:dropout_transition=0,alimiter=limit=0.95[a]"
    )

    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(voiceover),
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=64:duration={duration:.2f}:sample_rate=44100",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=128:duration={duration:.2f}:sample_rate=44100",
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=pink:duration={duration:.2f}:sample_rate=44100",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=48:duration=0.45:sample_rate=44100",
            "-filter_complex",
            ";".join(filter_parts),
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
            "22",
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
            "00:00:03.0",
            "-i",
            str(OUTPUT),
            "-vf",
            (
                "fps=8,scale=720:-1:flags=lanczos,"
                "split[s0][s1];[s0]palettegen=max_colors=96[p];"
                "[s1][p]paletteuse=dither=bayer:bayer_scale=4"
            ),
            "-t",
            "12",
            str(PREVIEW_GIF),
        ]
    )


def main() -> int:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required to build the launch video.")
    if not shutil.which("say"):
        raise SystemExit("macOS say is required for the local voiceover build.")

    chrome = find_chrome()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    for directory in (SLIDE_DIR, PNG_DIR, SEGMENT_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    scenes = build_scenes()
    rendered = [render_slide(chrome, scene) for scene in scenes]
    shutil.copyfile(rendered[0], POSTER)

    segments = [render_segment(scene, image) for scene, image in zip(scenes, rendered)]
    silent_video = BUILD_DIR / "silent_cinematic.mp4"
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
