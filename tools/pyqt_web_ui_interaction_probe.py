from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QEventLoop, QTimer
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


def wait_until_js(page: Any, source: str, timeout_ms: int = 15000) -> Any:
    deadline = time.monotonic() + timeout_ms / 1000
    last_value: Any = None
    while time.monotonic() < deadline:
        last_value = run_js(page, source, timeout_ms=1500)
        if last_value:
            return last_value
        wait_ms(120)
    return last_value


def click_tab(page: Any, label: str) -> dict[str, Any]:
    started = time.perf_counter()
    clicked = run_js(
        page,
        f"""
        (() => {{
          const label = {json.dumps(label)};
          const buttons = Array.from(document.querySelectorAll('button'));
          const button = buttons.find((item) => (item.textContent || '').trim().toLowerCase().includes(label.toLowerCase()));
          if (!button) return {{ clicked: false, label }};
          button.click();
          return {{ clicked: true, label }};
        }})()
        """,
    )
    ready = wait_until_js(
        page,
        f"""
        (() => {{
          const text = (document.body && document.body.innerText || '').toLowerCase();
          return text.includes({json.dumps(label.lower())});
        }})()
        """,
        timeout_ms=8000,
    )
    return {
        "label": label,
        "clicked": bool(isinstance(clicked, dict) and clicked.get("clicked")),
        "ready": bool(ready),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def click_settings_subtab(page: Any, label: str) -> dict[str, Any]:
    started = time.perf_counter()
    clicked = run_js(
        page,
        f"""
        (() => {{
          const label = {json.dumps(label)};
          const wanted = label.toLowerCase();
          const buttons = Array.from(document.querySelectorAll('button'));
          const button = buttons.find((item) => {{
            const text = (item.textContent || '').trim().toLowerCase();
            const aria = (item.getAttribute('aria-label') || '').trim().toLowerCase();
            return text === wanted || aria.includes(`settings ${{wanted.toLowerCase()}} tab`);
          }});
          if (!button) return {{ clicked: false, label }};
          button.click();
          return {{ clicked: true, label }};
        }})()
        """,
    )
    ready = wait_until_js(
        page,
        f"""
        (() => {{
          const wanted = {json.dumps(label.lower())};
          const text = (document.body && document.body.innerText || '').toLowerCase();
          if (wanted === 'general') {{
            return text.includes('ai personality matrix') || text.includes('user designation');
          }}
          if (wanted === 'api keys') {{
            return text.includes('external api endpoints') || text.includes('gemini pro core');
          }}
          return text.includes(wanted);
        }})()
        """,
        timeout_ms=8000,
    )
    return {
        "label": label,
        "clicked": bool(isinstance(clicked, dict) and clicked.get("clicked")),
        "ready": bool(ready),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def main() -> int:
    os.environ.setdefault("SHELL_LEGACY_UI", "0")
    os.environ.setdefault("SHELL_IMAGE_LOCAL_FALLBACK", "1")

    from shell_web_ui.host import ShellWebUI

    app = QApplication.instance() or QApplication([str(Path(__file__).name)])
    window = ShellWebUI()
    window.resize(1280, 760)
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

    report_dir = ROOT / ".shell_runtime" / "pyqt_web_ui_interaction_probe"
    report_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "ok": False,
        "load": load_state,
        "tabs": [],
        "settingsSubtabs": [],
        "settingsInput": {},
        "offlineBrain": {},
        "screenshots": {},
        "errors": [],
    }

    ready = wait_until_js(
        window.view.page(),
        """
        (() => {
          const text = document.body && document.body.innerText || '';
          return Boolean(text.includes('DASHBOARD') && document.querySelector('.shell-orb-stage'));
        })()
        """,
        timeout_ms=20000,
    )
    if not ready:
        report["errors"].append("Shell dashboard did not become ready in PyQt WebEngine.")
        print(json.dumps(report, indent=2, sort_keys=True))
        window.close()
        return 2

    for label in ("SETTINGS", "Apps", "NOTES", "GALLERY", "CONTROL", "DASHBOARD"):
        result = click_tab(window.view.page(), label)
        report["tabs"].append(result)
        if not result["clicked"] or not result["ready"]:
            report["errors"].append(f"Tab did not become ready: {label}")
        wait_ms(180)

    click_tab(window.view.page(), "SETTINGS")
    general_tab = click_settings_subtab(window.view.page(), "GENERAL")
    report["settingsSubtabs"].append(general_tab)
    input_ready = wait_until_js(
        window.view.page(),
        """
        (() => Array.from(document.querySelectorAll('input, textarea'))
          .some((item) => !item.disabled && item.getClientRects().length > 0))()
        """,
        timeout_ms=5000,
    )
    if not input_ready:
        keys_tab = click_settings_subtab(window.view.page(), "API KEYS")
        report["settingsSubtabs"].append(keys_tab)
        input_ready = wait_until_js(
            window.view.page(),
            """
            (() => Array.from(document.querySelectorAll('input, textarea'))
              .some((item) => !item.disabled && item.getClientRects().length > 0))()
            """,
            timeout_ms=5000,
        )
    input_metrics = run_js(
        window.view.page(),
        """
        (() => {
          const input = Array.from(document.querySelectorAll('input, textarea'))
            .find((item) => !item.disabled && item.getClientRects().length > 0);
          if (!input) return { available: false };
          const value = 'shell-local-ui-performance-check-1234567890';
          const started = performance.now();
          input.focus();
          input.value = '';
          for (const char of value) {
            input.value += char;
            input.dispatchEvent(new InputEvent('input', { inputType: 'insertText', data: char, bubbles: true }));
          }
          const elapsed = performance.now() - started;
          return { available: true, chars: value.length, elapsedMs: Math.round(elapsed * 100) / 100, valueLength: input.value.length };
        })()
        """,
    )
    report["settingsInput"] = input_metrics if isinstance(input_metrics, dict) else {"available": False}
    if not report["settingsInput"].get("available"):
        report["settingsInputDiagnostics"] = run_js(
            window.view.page(),
            """
            (() => ({
              inputCount: document.querySelectorAll('input, textarea').length,
              visibleInputCount: Array.from(document.querySelectorAll('input, textarea'))
                .filter((item) => !item.disabled && item.getClientRects().length > 0).length,
              bodyTextPreview: (document.body && document.body.innerText || '').slice(0, 1200)
            }))()
            """,
        )
        report["errors"].append("No visible Settings input was available for typing probe.")
    elif float(report["settingsInput"].get("elapsedMs") or 9999) > 120:
        report["errors"].append("Settings input event probe exceeded 120 ms.")

    run_js(
        window.view.page(),
        """
        (() => {
          window.__shellProbeOfflineBrain = { pending: true };
          window.electron.ipcRenderer.invoke('offline-llm-status')
            .then((value) => { window.__shellProbeOfflineBrain = { pending: false, value }; })
            .catch((error) => { window.__shellProbeOfflineBrain = { pending: false, error: String(error && error.message || error) }; });
          return true;
        })()
        """,
    )
    offline = wait_until_js(
        window.view.page(),
        """
        (() => {
          const value = window.__shellProbeOfflineBrain;
          return value && value.pending === false ? value : false;
        })()
        """,
        timeout_ms=8000,
    )
    report["offlineBrain"] = offline if isinstance(offline, dict) else {"pending": True}
    if report["offlineBrain"].get("pending") is True:
        report["errors"].append("Offline brain status bridge did not return.")

    screenshot_path = report_dir / "shell_pyqt_interaction.png"
    window.view.grab().save(str(screenshot_path))
    report["screenshots"]["interaction"] = str(screenshot_path)
    report["ok"] = not report["errors"] and bool(load_state["ok"])

    report_path = report_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    window.close()
    app.processEvents()
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
