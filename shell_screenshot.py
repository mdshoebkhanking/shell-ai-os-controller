#!/usr/bin/env python3
"""
Shell Screenshot Tools — Screen capture and recording utilities.
Uses mss (fast) with pyautogui fallback for screenshots.
"""

import os
import time
import logging
import asyncio
import platform
import shutil
import subprocess
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_screenshot")

# Default output directory
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
def _default_output_dir() -> str:
    if platform.system().lower() == "darwin":
        return os.path.join("/private", "tmp", "shell_screenshots")
    return os.path.join(_PROJECT_ROOT, "shell_downloads", "screenshots")


_OUTPUT_DIR = os.environ.get("SHELL_SCREENSHOT_DIR", _default_output_dir())


def _ensure_output_dir(path: str) -> str:
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except OSError:
        fallback = os.path.join(_PROJECT_ROOT, "shell_downloads", "screenshots")
        os.makedirs(fallback, exist_ok=True)
        return fallback


def _resolve_path(filename: str) -> str:
    """Resolve filename to full path, using default dir if no directory given."""
    if not os.path.dirname(filename):
        filename = os.path.join(_ensure_output_dir(_OUTPUT_DIR), filename)
    if not filename.lower().endswith(".png"):
        filename += ".png"
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    return filename


def _take_screenshot_mss(filepath: str, monitor=None):
    """Capture using mss library."""
    import mss
    with mss.mss() as sct:
        target = monitor if monitor else sct.monitors[0]
        img = sct.grab(target)
        mss.tools.to_png(img.rgb, img.size, output=filepath)
    return filepath


def _take_screenshot_pyautogui(filepath: str, region=None):
    """Fallback capture using pyautogui."""
    import pyautogui
    img = pyautogui.screenshot(region=region)
    img.save(filepath)
    return filepath


def _take_screenshot_macos(filepath: str, region=None):
    """Capture using macOS screencapture when Python capture libs are absent."""
    if platform.system().lower() != "darwin" or not shutil.which("screencapture"):
        raise RuntimeError("macOS screencapture is unavailable")
    cmd = ["screencapture", "-x"]
    if region:
        x, y, width, height = region
        cmd.extend(["-R", f"{int(x)},{int(y)},{int(width)},{int(height)}"])
    cmd.append(filepath)
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if proc.returncode != 0:
        output = (proc.stdout or "").strip()
        detail = output or "macOS returned no details"
        raise RuntimeError(
            "macOS screen capture failed. Grant Screen Recording permission to Terminal/Python/Codex "
            f"or run from a visible desktop session. Detail: {detail}"
        )
    return filepath


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: FULL SCREEN SCREENSHOT
# ═══════════════════════════════════════════════════════════════

@function_tool
async def take_screenshot_tool(filename: str) -> str:
    """
    Take a full screen screenshot and save to file.
    Args:
        filename: Output filename (saved to ~/Documents/Shell_Screenshots if no path given).
    """
    try:
        filepath = _resolve_path(filename)
        try:
            _take_screenshot_mss(filepath)
            method = "mss"
        except ImportError:
            if platform.system().lower() == "darwin":
                _take_screenshot_macos(filepath)
                method = "screencapture"
            else:
                _take_screenshot_pyautogui(filepath)
                method = "pyautogui"
        size_kb = os.path.getsize(filepath) / 1024
        return f"Screenshot saved: {filepath} ({size_kb:.1f} KB) [via {method}]"
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return f"Error taking screenshot: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: REGION SCREENSHOT
# ═══════════════════════════════════════════════════════════════

@function_tool
async def screenshot_region_tool(x: int, y: int, width: int, height: int, filename: str) -> str:
    """
    Take a screenshot of a specific screen region.
    Args:
        x: Left edge X coordinate.
        y: Top edge Y coordinate.
        width: Width of the region in pixels.
        height: Height of the region in pixels.
        filename: Output filename.
    """
    try:
        # Validate region dimensions up front — passing width<=0 silently
        # crashes mss (cryptic error) or captures the whole screen from
        # pyautogui depending on backend. Return a clean error instead.
        if not isinstance(width, int) or not isinstance(height, int):
            return f"Error: width and height must be integers (got {type(width).__name__}, {type(height).__name__})."
        if width <= 0 or height <= 0:
            return f"Error: width and height must be positive (got {width}x{height})."
        filepath = _resolve_path(filename)
        try:
            monitor = {"left": x, "top": y, "width": width, "height": height}
            _take_screenshot_mss(filepath, monitor=monitor)
            method = "mss"
        except ImportError:
            if platform.system().lower() == "darwin":
                _take_screenshot_macos(filepath, region=(x, y, width, height))
                method = "screencapture"
            else:
                _take_screenshot_pyautogui(filepath, region=(x, y, width, height))
                method = "pyautogui"
        size_kb = os.path.getsize(filepath) / 1024
        return (
            f"Region screenshot saved: {filepath} ({size_kb:.1f} KB)\n"
            f"Region: x={x}, y={y}, {width}x{height} [via {method}]"
        )
    except Exception as e:
        logger.error(f"Region screenshot failed: {e}")
        return f"Error taking region screenshot: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: WINDOW SCREENSHOT
# ═══════════════════════════════════════════════════════════════

@function_tool
async def screenshot_window_tool(window_title: str, filename: str) -> str:
    """
    Screenshot a specific window by its title.
    Uses pygetwindow to find window bounds, then mss to capture.
    Args:
        window_title: Title (or partial title) of the window to capture.
        filename: Output filename.
    """
    try:
        import pygetwindow as gw

        windows = gw.getWindowsWithTitle(window_title)
        if not windows:
            available = [w.title for w in gw.getAllWindows() if w.title.strip()]
            avail_str = "\n  ".join(available[:15]) if available else "(none)"
            return f"No window found matching '{window_title}'.\nAvailable windows:\n  {avail_str}"

        win = windows[0]
        if win.isMinimized:
            win.restore()
            await asyncio.sleep(0.5)

        filepath = _resolve_path(filename)
        monitor = {
            "left": win.left,
            "top": win.top,
            "width": win.width,
            "height": win.height,
        }
        try:
            _take_screenshot_mss(filepath, monitor=monitor)
        except ImportError:
            _take_screenshot_pyautogui(filepath, region=(win.left, win.top, win.width, win.height))

        size_kb = os.path.getsize(filepath) / 1024
        return (
            f"Window screenshot saved: {filepath} ({size_kb:.1f} KB)\n"
            f"Window: '{win.title}' at ({win.left},{win.top}) {win.width}x{win.height}"
        )
    except ImportError:
        return "Error: pygetwindow is required. Install with: pip install pygetwindow"
    except Exception as e:
        logger.error(f"Window screenshot failed: {e}")
        return f"Error capturing window: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: SCREEN RECORDING
# ═══════════════════════════════════════════════════════════════

@function_tool
async def screen_record_start_tool(filename: str, duration: int) -> str:
    """
    Record the screen for N seconds and save as an AVI video.
    Uses mss for fast frame capture and cv2 for video encoding.
    Args:
        filename: Output filename (will use .avi extension).
        duration: Recording duration in seconds (max 120).
    """
    try:
        import mss
        import cv2
        import numpy as np

        if duration < 1 or duration > 120:
            return "Error: Duration must be between 1 and 120 seconds."

        # Resolve path
        if not os.path.dirname(filename):
            filename = os.path.join(_OUTPUT_DIR, filename)
        if not filename.lower().endswith(".avi"):
            filename = os.path.splitext(filename)[0] + ".avi"
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        fps = 10.0

        def _record():
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                width = monitor["width"]
                height = monitor["height"]
                fourcc = cv2.VideoWriter_fourcc(*"XVID")
                out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
                frame_interval = 1.0 / fps
                start = time.time()
                frame_count = 0
                try:
                    while time.time() - start < duration:
                        frame_start = time.time()
                        img = sct.grab(monitor)
                        frame = np.array(img)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        out.write(frame)
                        frame_count += 1
                        elapsed = time.time() - frame_start
                        if elapsed < frame_interval:
                            time.sleep(frame_interval - elapsed)
                finally:
                    out.release()
                return frame_count

        frame_count = await asyncio.get_event_loop().run_in_executor(None, _record)
        size_mb = os.path.getsize(filename) / (1024 * 1024)
        return (
            f"Screen recording saved: {filename}\n"
            f"Duration: {duration}s | Frames: {frame_count} | "
            f"Size: {size_mb:.2f} MB | FPS: {fps}"
        )
    except ImportError as ie:
        missing = str(ie).split("'")[-2] if "'" in str(ie) else str(ie)
        return f"Error: Required library missing ({missing}). Install with: pip install mss opencv-python numpy"
    except Exception as e:
        logger.error(f"Screen recording failed: {e}")
        return f"Error recording screen: {e}"
