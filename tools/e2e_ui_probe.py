from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _process_events(app, duration_s: float = 0.15) -> None:
    deadline = time.time() + duration_s
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _grab(widget, path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = widget.grab()
    return bool(pixmap.save(str(path)))


def _wait_for_workers(window, app, timeout_s: float = 12.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        app.processEvents()
        workers = list(getattr(window, "_backend_command_workers", []) or [])
        if not any(worker is not None and worker.isRunning() for worker in workers):
            return
        time.sleep(0.03)
    raise TimeoutError("backend command worker did not finish")


def _send_via_chat(window, app, text: str) -> None:
    window.chat_page._input.setPlainText(text)
    _process_events(app, 0.05)
    window.chat_page._send()
    _process_events(app, 0.05)


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise Shell PyQt UI end-to-end.")
    parser.add_argument("--screens-dir", default="/private/tmp/shell_ui_probe")
    parser.add_argument("--json-out", default="/private/tmp/shell_ui_probe_report.json")
    parser.add_argument("--visible", action="store_true", help="Render using the real display instead of offscreen Qt.")
    args = parser.parse_args()

    if not args.visible:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SHELL_V2_TIMEOUT_S", "2")

    from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

    original_settings = None
    original_shell_language = os.environ.get("SHELL_LANGUAGE")
    try:
        from shell_settings_manager import get_settings

        original_settings = get_settings()
    except Exception:
        original_settings = None

    from shell_ui.shell_cinematic_full import ShellHoloUI

    app = QApplication.instance() or QApplication(sys.argv)
    window = ShellHoloUI()
    window.resize(1260, 720)
    window.show()
    _process_events(app, 1.2)

    report: dict[str, object] = {
        "ok": True,
        "pages": {},
        "commands": {},
        "settings": {},
        "screenshots": {},
        "errors": [],
    }
    screens_dir = Path(args.screens_dir)
    page_names = ["chat", "voice", "system", "tools", "settings"]

    try:
        for idx, name in enumerate(page_names):
            window._on_page_change(idx)
            _process_events(app, 0.35)
            shot = screens_dir / f"{idx}_{name}.png"
            report["screenshots"][name] = str(shot)
            report["pages"][name] = {
                "index": window.pages.currentIndex(),
                "screenshot_saved": _grab(window, shot),
                "visible": window.pages.currentWidget() is window.pages.widget(idx),
            }

        window._on_page_change(1)
        _process_events(app, 0.2)
        vp = window.voice_page
        geom_before = tuple(vp.visualizer.geometry().getRect())
        vp.visuals_btn.click()
        _process_events(app, 0.2)
        visual_hidden = not vp.visualizer.isVisible()
        vp.visuals_btn.click()
        _process_events(app, 0.2)
        geom_after = tuple(vp.visualizer.geometry().getRect())
        vp.term_btn.click()
        _process_events(app, 1.2)
        report["commands"]["voice_page"] = {
            "visual_toggle_hides": visual_hidden,
            "visualizer_visible_after_toggle": vp.visualizer.isVisible(),
            "visualizer_geometry_before": geom_before,
            "visualizer_geometry_after": geom_after,
            "test_voice_button_removed": not hasattr(vp, "test_voice_btn"),
            "status_after_start": vp.status_badge.text(),
            "description_after_start": vp._desc.text(),
        }
        try:
            window._stop_voice_listener()
        except Exception:
            pass

        window._on_page_change(0)
        _process_events(app, 0.2)

        before_labels = len(window.chat_page.findChildren(QLabel))
        _send_via_chat(window, app, '/tool shell_calculator:calculate_tool {"expression":"2 + 3 * 4"}')
        _wait_for_workers(window, app)
        _process_events(app, 0.3)
        after_labels = len(window.chat_page.findChildren(QLabel))
        report["commands"]["calculator_tool"] = {
            "labels_before": before_labels,
            "labels_after": after_labels,
            "added_labels": after_labels - before_labels,
        }

        _send_via_chat(window, app, '/mcp Screenshot {}')
        _wait_for_workers(window, app)
        _process_events(app, 0.3)
        mcp_text = "\n".join(lbl.text() for lbl in window.chat_page.findChildren(QLabel))
        report["commands"]["windows_mcp_screenshot"] = {
            "unsupported_message_visible": "requires Windows" in mcp_text,
            "error_visible": "failed" in mcp_text.lower() or "requires Windows" in mcp_text,
        }

        _send_via_chat(window, app, "hello")
        _process_events(app, 2.8)
        chat_text = "\n".join(lbl.text() for lbl in window.chat_page.findChildren(QLabel))
        report["commands"]["text_chat"] = {
            "user_echo_visible": "hello" in chat_text.lower(),
            "fallback_or_reply_visible": ("Shell" in chat_text or "AI Error" in chat_text or "Hello" in chat_text),
            "tts_not_auto_triggered": not bool(getattr(getattr(window, "_tts", None), "_force_next", False)),
        }

        settings = window.settings_page
        if hasattr(settings, "_on_language_changed"):
            settings._on_language_changed(1)
            _process_events(app, 0.2)
            report["settings"]["language_env"] = os.environ.get("SHELL_LANGUAGE")
        commit_buttons = [
            btn for btn in settings.findChildren(QPushButton)
            if "commit" in btn.text().lower()
        ]
        if commit_buttons:
            commit_buttons[0].click()
            _process_events(app, 0.5)
        report["settings"]["commit_button_found"] = bool(commit_buttons)

        report["screenshots"]["final"] = str(screens_dir / "final_chat_after_commands.png")
        _grab(window, screens_dir / "final_chat_after_commands.png")
    except Exception as exc:
        report["ok"] = False
        report["errors"].append(str(exc))
    finally:
        try:
            window._stop_backend_command_workers()
        except Exception:
            pass
        if original_settings is not None:
            try:
                from shell_settings_manager import set_settings

                set_settings(dict(original_settings))
            except Exception:
                pass
        if original_shell_language is not None:
            os.environ["SHELL_LANGUAGE"] = original_shell_language
        window.close()
        _process_events(app, 0.2)

    Path(args.json_out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
