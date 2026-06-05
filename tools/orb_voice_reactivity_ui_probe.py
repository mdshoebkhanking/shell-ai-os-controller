from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QEventLoop, QRect, QTimer
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def wait_ms(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def run_js(page: Any, source: str, timeout_ms: int = 5000) -> Any:
    result: dict[str, Any] = {"done": False, "value": None}
    loop = QEventLoop()

    def callback(value: Any) -> None:
        result["done"] = True
        result["value"] = value
        loop.quit()

    page.runJavaScript(source, callback)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    return result["value"] if result["done"] else None


def wait_until_js(page: Any, source: str, timeout_ms: int = 20000) -> Any:
    deadline = time.monotonic() + timeout_ms / 1000
    last_value: Any = None
    while time.monotonic() < deadline:
        last_value = run_js(page, source, timeout_ms=1500)
        if last_value:
            return last_value
        wait_ms(250)
    return last_value


def image_stats(image: QImage) -> dict[str, Any]:
    width = image.width()
    height = image.height()
    center_x = width / 2
    center_y = height / 2
    max_radius = max(1.0, (center_x * center_x + center_y * center_y) ** 0.5)
    bright_radii: list[float] = []
    bright_pixels = 0
    outer_bright_pixels = 0
    white_pixels = 0
    luma_sum = 0.0
    green_sum = 0.0
    sample_count = 0

    step = 2
    for y in range(0, height, step):
        for x in range(0, width, step):
            color = image.pixelColor(x, y)
            red = color.red()
            green = color.green()
            blue = color.blue()
            luma = red * 0.299 + green * 0.587 + blue * 0.114
            sample_count += 1
            luma_sum += luma
            green_sum += green
            if luma > 20:
                bright_pixels += 1
                radius = (((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5) / max_radius
                bright_radii.append(radius)
                if radius > 0.42:
                    outer_bright_pixels += 1
                if red > 180 and green > 180 and blue > 180:
                    white_pixels += 1

    bright_radii.sort()
    p90 = bright_radii[int(len(bright_radii) * 0.9)] if bright_radii else 0.0
    p98 = bright_radii[int(len(bright_radii) * 0.98)] if bright_radii else 0.0
    return {
        "width": width,
        "height": height,
        "sample_count": sample_count,
        "bright_pixels": bright_pixels,
        "outer_bright_pixels": outer_bright_pixels,
        "white_pixels": white_pixels,
        "avg_luma": round(luma_sum / max(1, sample_count), 4),
        "avg_green": round(green_sum / max(1, sample_count), 4),
        "bright_radius_p90": round(p90, 5),
        "bright_radius_p98": round(p98, 5),
    }


def diff_stats(before: QImage, after: QImage) -> dict[str, Any]:
    width = min(before.width(), after.width())
    height = min(before.height(), after.height())
    changed = 0
    total_delta = 0
    samples = 0
    step = 2
    for y in range(0, height, step):
        for x in range(0, width, step):
            a = before.pixelColor(x, y)
            b = after.pixelColor(x, y)
            delta = abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue())
            samples += 1
            total_delta += delta
            if delta > 18:
                changed += 1
    return {
        "changed_pixels": changed,
        "sample_count": samples,
        "changed_ratio": round(changed / max(1, samples), 5),
        "avg_rgb_delta": round(total_delta / max(1, samples), 4),
    }


def capture_canvas(window: Any, rect_payload: dict[str, Any], output_path: Path) -> QImage:
    pixmap = window.view.grab()
    scale_x = pixmap.width() / max(1, window.view.width())
    scale_y = pixmap.height() / max(1, window.view.height())
    rect = QRect(
        int(float(rect_payload["x"]) * scale_x),
        int(float(rect_payload["y"]) * scale_y),
        max(1, int(float(rect_payload["width"]) * scale_x)),
        max(1, int(float(rect_payload["height"]) * scale_y)),
    )
    cropped = pixmap.copy(rect)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(str(output_path))
    return cropped.toImage().convertToFormat(QImage.Format.Format_RGB32)


def main() -> int:
    os.environ.setdefault("SHELL_LEGACY_UI", "0")
    os.environ.setdefault("SHELL_IMAGE_LOCAL_FALLBACK", "1")
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--enable-gpu-rasterization --ignore-gpu-blocklist")

    from shell_web_ui.host import ShellWebUI

    app = QApplication.instance() or QApplication([str(Path(__file__).name)])
    window = ShellWebUI()
    window.show()
    window.raise_()

    load_state: dict[str, Any] = {"finished": False, "ok": False}
    load_loop = QEventLoop()

    def on_load_finished(ok: bool) -> None:
        load_state["finished"] = True
        load_state["ok"] = bool(ok)
        load_loop.quit()

    window.view.loadFinished.connect(on_load_finished)
    QTimer.singleShot(25000, load_loop.quit)
    load_loop.exec()

    report_dir = ROOT / ".shell_runtime" / "orb_voice_reactivity_probe"
    report_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "ok": False,
        "load": load_state,
        "screenshots": {},
        "metrics": {},
        "errors": [],
    }

    ready = wait_until_js(
        window.view.page(),
        """
        (() => {
          const canvas = document.querySelector('canvas');
          const rect = canvas ? canvas.getBoundingClientRect() : null;
          return Boolean(window.shellAPI && canvas && rect && rect.width > 120 && rect.height > 120);
        })()
        """,
        timeout_ms=20000,
    )
    if not ready:
        report["errors"].append("Dashboard canvas or shellAPI did not become ready.")
        print(json.dumps(report, indent=2, sort_keys=True))
        window.close()
        return 2

    rect_payload = run_js(
        window.view.page(),
        """
        (() => {
          const rect = document.querySelector('canvas').getBoundingClientRect();
          return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
        })()
        """,
    )
    report["canvas_rect"] = rect_payload
    wait_ms(1200)
    idle_path = report_dir / "orb_idle.png"
    idle_image = capture_canvas(window, rect_payload, idle_path)

    window.bridge.emit_event("voice-status", {"state": "listening", "actualRuntime": True})
    window.bridge.emit_event("speech-status", {"state": "speaking", "engine": "probe"})
    for _ in range(20):
        window.bridge.emit_event("voice-amplitude", {"value": 0.95})
        wait_ms(90)
    reactive_path = report_dir / "orb_voice_reactive.png"
    reactive_image = capture_canvas(window, rect_payload, reactive_path)
    window.bridge.emit_event("speech-status", {"state": "stopped", "engine": "probe"})
    wait_ms(300)

    idle_stats = image_stats(idle_image)
    reactive_stats = image_stats(reactive_image)
    delta_stats = diff_stats(idle_image, reactive_image)
    report["screenshots"] = {
        "idle": str(idle_path),
        "voice_reactive": str(reactive_path),
    }
    report["metrics"] = {
        "idle": idle_stats,
        "voice_reactive": reactive_stats,
        "diff": delta_stats,
        "radius_p98_delta": round(reactive_stats["bright_radius_p98"] - idle_stats["bright_radius_p98"], 5),
        "white_pixel_delta": reactive_stats["white_pixels"] - idle_stats["white_pixels"],
        "outer_bright_delta": reactive_stats["outer_bright_pixels"] - idle_stats["outer_bright_pixels"],
    }

    canvas_nonblank = idle_stats["bright_pixels"] > 100 and reactive_stats["bright_pixels"] > 100
    visible_reaction = (
        delta_stats["changed_ratio"] > 0.035
        or report["metrics"]["radius_p98_delta"] > 0.01
        or report["metrics"]["white_pixel_delta"] > 50
        or report["metrics"]["outer_bright_delta"] > 50
    )
    report["ok"] = bool(load_state["ok"] and canvas_nonblank and visible_reaction)
    if not canvas_nonblank:
        report["errors"].append("Orb canvas looked blank in one or more captures.")
    if not visible_reaction:
        report["errors"].append("Injected voice amplitude did not create a measurable canvas change.")

    report_path = report_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    window.close()
    app.processEvents()
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
