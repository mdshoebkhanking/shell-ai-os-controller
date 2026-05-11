from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


MAC_APP_NAMES = {
    "calculator": "Calculator",
    "dictionary": "Dictionary",
    "calendar": "Calendar",
    "textedit": "TextEdit",
    "system settings": "System Settings",
}


def _process_events(app, duration_s: float = 0.15) -> None:
    deadline = time.time() + duration_s
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _wait_for_workers(window, app, timeout_s: float = 75.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        app.processEvents()
        workers = list(getattr(window, "_backend_command_workers", []) or [])
        if not any(worker is not None and worker.isRunning() for worker in workers):
            return True
        time.sleep(0.03)
    return False


def _message_text(window) -> str:
    from PyQt6.QtWidgets import QLabel

    return "\n".join(label.text() for label in window.chat_page.findChildren(QLabel))


def _send_chat(window, app, text: str, timeout_s: float = 75.0) -> dict[str, object]:
    before = _message_text(window)
    window.chat_page._input.setPlainText(text)
    _process_events(app, 0.06)
    window.chat_page._send()
    _process_events(app, 0.08)
    workers_done = _wait_for_workers(window, app, timeout_s=timeout_s)
    _process_events(app, 0.25)
    after = _message_text(window)
    delta = after[len(before):].strip() if after.startswith(before) else after
    return {
        "command": text,
        "workers_done": workers_done,
        "response_tail": delta[-1800:],
        "message_count_chars": len(after),
    }


def _is_macos_app_running(name: str) -> bool | None:
    if sys.platform != "darwin":
        return None
    app_name = MAC_APP_NAMES.get(name.lower(), name)
    script = f'application "{app_name}" is running'
    proc = subprocess.run(
        ["osascript", "-e", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip().lower() == "true"


def _screenshot(window, path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    return bool(window.grab().save(str(path)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Drive Shell chat UI commands and report results.")
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--screens-dir", default="/private/tmp/shell_chat_probe")
    parser.add_argument("--json-out", default="/private/tmp/shell_chat_probe_report.json")
    args = parser.parse_args()

    if not args.visible:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SHELL_V2_TIMEOUT_S", "3")
    os.environ.setdefault("SHELL_ALLOW_AGENT_BROWSER_EXEC", "1")
    os.environ.setdefault("SHELL_AGENT_BROWSER_SOCKET_DIR", "/tmp/shell-agent-browser")

    from PyQt6.QtWidgets import QApplication
    from shell_ui.shell_cinematic_full import ShellHoloUI

    app = QApplication.instance() or QApplication(sys.argv)
    window = ShellHoloUI()
    window.resize(1260, 720)
    window.show()
    _process_events(app, 1.0)

    screens_dir = Path(args.screens_dir)
    report: dict[str, object] = {
        "ok": True,
        "errors": [],
        "app_commands": [],
        "close_commands": [],
        "tool_commands": [],
        "agent_commands": [],
        "screenshots": {},
    }

    app_names = ["calculator", "dictionary", "calendar", "textedit", "system settings"]

    try:
        window._on_page_change(0)
        _process_events(app, 0.2)
        report["screenshots"]["initial"] = str(screens_dir / "initial.png")
        _screenshot(window, screens_dir / "initial.png")

        for app_name in app_names:
            result = _send_chat(window, app, f"open {app_name}", timeout_s=40)
            result["running_after"] = _is_macos_app_running(app_name)
            report["app_commands"].append(result)

        tool_commands = [
            "what is 2 + 3 * 4",
            "count words in hello shell world",
            '/tool shell_external_integrations:external_integration_status_tool {}',
            '/tool shell_external_integrations:openclaw_skill_search_tool {"query":"github","limit":2}',
            '/tool shell_external_integrations:agent_browser_command_tool {"command":"skills list","timeout_s":10}',
            '/tool shell_external_integrations:agent_browser_command_tool {"command":"open https://example.com","timeout_s":25}',
            '/tool shell_external_integrations:agent_browser_command_tool {"command":"snapshot -i","timeout_s":25}',
            '/tool shell_external_integrations:agent_browser_command_tool {"command":"close --all","timeout_s":10}',
        ]
        for command in tool_commands:
            report["tool_commands"].append(_send_chat(window, app, command, timeout_s=80))

        agent_commands = [
            "/agent shell_agents:list_agents_tool {}",
            "testing agent return one short UI test idea",
        ]
        for command in agent_commands:
            report["agent_commands"].append(_send_chat(window, app, command, timeout_s=90))

        for app_name in reversed(app_names):
            result = _send_chat(window, app, f"close {app_name}", timeout_s=40)
            result["running_after"] = _is_macos_app_running(app_name)
            report["close_commands"].append(result)

        report["screenshots"]["final"] = str(screens_dir / "final.png")
        _screenshot(window, screens_dir / "final.png")

        open_failures = [
            row for row in report["app_commands"]
            if row.get("workers_done") is not True or row.get("running_after") is False
        ]
        close_failures = [
            row for row in report["close_commands"]
            if row.get("workers_done") is not True or row.get("running_after") is True
        ]
        command_timeouts = [
            row for group in ("tool_commands", "agent_commands")
            for row in report[group]
            if row.get("workers_done") is not True
        ]
        report["summary"] = {
            "apps_opened": len(report["app_commands"]) - len(open_failures),
            "apps_closed": len(report["close_commands"]) - len(close_failures),
            "tool_commands": len(report["tool_commands"]),
            "agent_commands": len(report["agent_commands"]),
            "open_failures": len(open_failures),
            "close_failures": len(close_failures),
            "command_timeouts": len(command_timeouts),
        }
        report["ok"] = not open_failures and not close_failures and not command_timeouts
    except Exception as exc:
        report["ok"] = False
        report["errors"].append(str(exc))
    finally:
        for app_name in reversed(app_names):
            if _is_macos_app_running(app_name):
                try:
                    from shell_window_CTRL import close_app
                    import asyncio

                    asyncio.run(close_app(app_name))
                except Exception:
                    pass
        try:
            window._stop_backend_command_workers()
        except Exception:
            pass
        window.close()
        _process_events(app, 0.2)

    Path(args.json_out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
