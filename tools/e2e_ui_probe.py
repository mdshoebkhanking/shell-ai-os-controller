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

    from shell_ui.app_bootstrap import configure_qt_application

    app = QApplication.instance() or QApplication(sys.argv)
    configure_qt_application(app)

    original_settings = None
    original_shell_language = os.environ.get("SHELL_LANGUAGE")
    try:
        from shell_settings_manager import get_settings

        original_settings = get_settings()
    except Exception:
        original_settings = None

    from shell_ui.shell_cinematic_full import ShellHoloUI

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
    page_names = ["chat", "voice", "system", "agents", "tools", "settings"]

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

        window._on_page_change(2)
        _process_events(app, 1.0)
        system_text = "\n".join(lbl.text() for lbl in window.system_page.findChildren(QLabel))
        report["commands"]["system_platform_status"] = {
            "panel_visible": "AI OS Status" in system_text,
            "score_visible": "READY" in system_text or "ATTENTION" in system_text or "OPTIMAL" in system_text,
            "capabilities_visible": "capabilities" in system_text.lower(),
            "voice_identity_visible": "Aoede" in system_text,
        }
        if not all(report["commands"]["system_platform_status"].values()):
            report["ok"] = False
            report["errors"].append("system platform status panel did not render expected backend state")

        window._on_page_change(3)
        _process_events(app, 1.0)
        agents_text = "\n".join(lbl.text() for lbl in window.agents_page.findChildren(QLabel))
        report["commands"]["agents_page"] = {
            "panel_visible": "Agents" in agents_text,
            "orchestration_visible": "orchestration agents" in agents_text.lower(),
            "agent_tools_visible": "agent tools" in agents_text.lower(),
            "routing_visible": "terminal echo hello" in agents_text or "Routing Checks" in agents_text,
            "approval_visible": "approval" in agents_text.lower(),
        }
        if not all(report["commands"]["agents_page"].values()):
            report["ok"] = False
            report["errors"].append("agents page did not render expected orchestration state")

        window._on_page_change(4)
        _process_events(app, 1.0)
        tools_text = "\n".join(lbl.text() for lbl in window.tools_page.findChildren(QLabel))
        catalog = list(getattr(window.tools_page, "_catalog", []) or [])
        non_ready = next(
            (
                item for item in catalog
                if not bool((item.get("readiness") or {}).get("ok", True))
            ),
            None,
        )
        ready_safe = next(
            (
                item for item in catalog
                if bool((item.get("readiness") or {}).get("ok", True))
                and str((item.get("metadata") or {}).get("safety_level") or "safe").lower() == "safe"
            ),
            None,
        )
        non_ready_run_disabled = True
        ready_safe_run_enabled = True
        if non_ready:
            window.tools_page._select_item(non_ready)
            non_ready_run_disabled = not window.tools_page._run_btn.isEnabled()
        if ready_safe:
            window.tools_page._select_item(ready_safe)
            ready_safe_run_enabled = window.tools_page._run_btn.isEnabled()
        report["commands"]["tools_readiness"] = {
            "summary_visible": "Ready" in tools_text and "Needs API" in tools_text,
            "state_filter_visible": window.tools_page._state_filter.count() > 1,
            "non_ready_direct_run_disabled": non_ready_run_disabled,
            "ready_safe_direct_run_enabled": ready_safe_run_enabled,
        }
        if not all(report["commands"]["tools_readiness"].values()):
            report["ok"] = False
            report["errors"].append("tools page readiness controls did not render or gate execution correctly")

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
