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


MODEL_ID = os.environ.get("SHELL_PROBE_OFFLINE_MODEL_ID", "qwen2.5-3b-q4")
MODEL_NAME = os.environ.get("SHELL_PROBE_OFFLINE_MODEL_NAME", "Qwen2.5 3B Q4")


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


def click_button_by_text(page: Any, label: str) -> dict[str, Any]:
    started = time.perf_counter()
    clicked = run_js(
        page,
        f"""
        (() => {{
          const label = {json.dumps(label)};
          const wanted = label.toLowerCase();
          const button = Array.from(document.querySelectorAll('button')).find((item) => {{
            const text = (item.textContent || '').trim().toLowerCase();
            const aria = (item.getAttribute('aria-label') || '').trim().toLowerCase();
            return text === wanted || text.includes(wanted) || aria.includes(wanted);
          }});
          if (!button) return {{ clicked: false, label }};
          button.click();
          return {{ clicked: true, label, text: (button.textContent || '').trim() }};
        }})()
        """,
    )
    return {
        "label": label,
        "clicked": bool(isinstance(clicked, dict) and clicked.get("clicked")),
        "elapsedMs": round((time.perf_counter() - started) * 1000, 2),
        "details": clicked if isinstance(clicked, dict) else {},
    }


def main() -> int:
    os.environ.setdefault("SHELL_LEGACY_UI", "0")
    os.environ.setdefault("SHELL_IMAGE_LOCAL_FALLBACK", "1")
    os.environ.setdefault("SHELL_CHAT_PROVIDER_MODE", "offline")
    os.environ.setdefault("SHELL_OFFLINE_LLM_ASYNC_UI", "1")
    os.environ.setdefault("SHELL_WINDOWS_PERFORMANCE_MODE", "balanced")
    os.environ.setdefault("SHELL_OFFLINE_LLM_CONTEXT", "768")
    os.environ.setdefault("SHELL_OFFLINE_LLM_BATCH", "32")
    os.environ.setdefault("SHELL_OFFLINE_LLM_MAX_TOKENS", "96")

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

    report_dir = ROOT / ".shell_runtime" / "pyqt_offline_brain_e2e_probe"
    report_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "ok": False,
        "load": load_state,
        "model": {"id": MODEL_ID, "name": MODEL_NAME},
        "ui": {},
        "download": {},
        "chat": {},
        "voiceChat": {},
        "tts": {},
        "screenshots": {},
        "errors": [],
    }

    page = window.view.page()
    ready = wait_until_js(
        page,
        """
        (() => {
          const text = document.body && document.body.innerText || '';
          return Boolean(text.includes('DASHBOARD') && window.shellAPI && window.electron?.ipcRenderer);
        })()
        """,
        timeout_ms=20000,
    )
    if not ready:
        report["errors"].append("Shell UI bridge did not become ready in PyQt WebEngine.")
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
        window.close()
        return 2

    run_js(
        page,
        """
        (() => {
          window.__offlineBrainProbe = { events: [], invokes: [] };
          const record = (channel, payload) => window.__offlineBrainProbe.events.push({
            channel,
            payload,
            at: Math.round(performance.now() * 100) / 100
          });
          for (const channel of ['offline-llm-download-event', 'chat-updated', 'speech-status', 'voice-status']) {
            window.shellAPI.on(channel, (_event, payload) => record(channel, payload));
          }
          const ipc = window.electron?.ipcRenderer;
          if (ipc && !ipc.__offlineBrainProbeWrapped) {
            const originalInvoke = ipc.invoke.bind(ipc);
            ipc.invoke = async (channel, ...args) => {
              const started = performance.now();
              try {
                const value = await originalInvoke(channel, ...args);
                if (String(channel).startsWith('offline-llm')) {
                  window.__offlineBrainProbe.invokes.push({
                    channel,
                    args,
                    success: true,
                    value,
                    elapsedMs: Math.round((performance.now() - started) * 100) / 100
                  });
                }
                return value;
              } catch (error) {
                window.__offlineBrainProbe.invokes.push({
                  channel,
                  args,
                  success: false,
                  error: String(error && error.message || error),
                  elapsedMs: Math.round((performance.now() - started) * 100) / 100
                });
                throw error;
              }
            };
            ipc.__offlineBrainProbeWrapped = true;
          }
          return true;
        })()
        """,
    )

    click_button_by_text(page, "SETTINGS")
    wait_until_js(
        page,
        """
        (() => (document.body && document.body.innerText || '').includes('Command Center'))()
        """,
        timeout_ms=8000,
    )
    click_button_by_text(page, "GENERAL")
    wait_until_js(
        page,
        """
        (() => (document.body && document.body.innerText || '').includes('OFFLINE BRAIN'))()
        """,
        timeout_ms=8000,
    )

    card_selector_js = f"""
      const modelName = {json.dumps(MODEL_NAME)};
      const candidates = Array.from(document.querySelectorAll('div'))
        .filter((item) => {{
          const text = item.innerText || '';
          const button = Array.from(item.querySelectorAll('button')).find((button) => {{
            const label = (button.textContent || '').trim().toUpperCase();
            return label === 'USE' || label === 'DOWNLOAD' || /%$/.test(label);
          }});
          return text.includes(modelName) && text.includes('RECOMMENDED') && Boolean(button);
        }})
        .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
      const card = candidates[0];
    """
    model_card = run_js(
        page,
        f"""
        (() => {{
          {card_selector_js}
          if (!card) return {{ found: false, modelName }};
          card.scrollIntoView({{ block: 'center', inline: 'nearest' }});
          const button = Array.from(card.querySelectorAll('button')).find((item) => {{
            const text = (item.textContent || '').trim().toUpperCase();
            return text === 'USE' || text === 'DOWNLOAD' || /%$/.test(text);
          }});
          return {{
            found: true,
            text: (card.innerText || '').slice(0, 900),
            textLength: (card.innerText || '').length,
            buttonText: button ? (button.textContent || '').trim() : '',
            buttonDisabled: button ? Boolean(button.disabled) : null
          }};
        }})()
        """,
    )
    report["ui"]["recommendedCardBefore"] = model_card if isinstance(model_card, dict) else {"found": False}
    if not report["ui"]["recommendedCardBefore"].get("found"):
        report["errors"].append("Recommended model card was not visible in Settings > General.")
    else:
        clicked = run_js(
            page,
            f"""
            (() => {{
              {card_selector_js}
              if (!card) return {{ clicked: false, reason: 'card-missing' }};
              const button = Array.from(card.querySelectorAll('button')).find((item) => {{
                const text = (item.textContent || '').trim().toUpperCase();
                return text === 'USE' || text === 'DOWNLOAD' || /%$/.test(text);
              }});
              if (!button) return {{ clicked: false, reason: 'button-missing' }};
              if (button.disabled) return {{ clicked: false, reason: 'button-disabled', text: (button.textContent || '').trim() }};
              button.click();
              return {{ clicked: true, text: (button.textContent || '').trim() }};
            }})()
            """,
        )
        report["ui"]["recommendedButtonClick"] = clicked if isinstance(clicked, dict) else {"clicked": False}
        wait_until_js(
            page,
            f"""
            (() => {{
              const probe = window.__offlineBrainProbe || {{}};
              const call = (probe.invokes || []).find((item) => item.channel === 'offline-llm-download' && JSON.stringify(item.args || []).includes({json.dumps(MODEL_ID)}));
              return call || false;
            }})()
            """,
            timeout_ms=10000,
        )

    run_js(
        page,
        """
        (() => {
          window.__offlineBrainProbe.statusAfterUse = { pending: true };
          Promise.all([
            window.electron.ipcRenderer.invoke('offline-llm-status'),
            window.electron.ipcRenderer.invoke('offline-llm-catalog')
          ]).then(([status, catalog]) => {
            window.__offlineBrainProbe.statusAfterUse = {
              pending: false,
              status: status?.status,
              available: status?.available,
              modelFile: status?.modelFile,
              modelPath: status?.modelPath,
              selectedModelId: status?.selectedModelId || catalog?.selectedModelId || '',
              installedModels: (catalog?.installedModels || []).map((item) => item.id)
            };
          }).catch((error) => {
            window.__offlineBrainProbe.statusAfterUse = {
              pending: false,
              error: String(error && error.message || error)
            };
          });
          return true;
        })()
        """,
        timeout_ms=10000,
    )
    status_after = wait_until_js(
        page,
        """
        (() => {
          const value = window.__offlineBrainProbe?.statusAfterUse;
          return value && value.pending === false ? value : false;
        })()
        """,
        timeout_ms=10000,
    )
    report["download"]["statusAfterUse"] = status_after if isinstance(status_after, dict) else {}
    probe_state = run_js(page, "(() => window.__offlineBrainProbe || {})()")
    report["download"]["probeStateAfterUse"] = probe_state if isinstance(probe_state, dict) else {}
    if report["download"]["statusAfterUse"].get("selectedModelId") != MODEL_ID:
        report["errors"].append("Recommended model was not selected after USE/DOWNLOAD flow.")
    if report["download"]["statusAfterUse"].get("available") is not True:
        report["errors"].append("Offline brain was not ready after recommended model flow.")

    click_button_by_text(page, "DASHBOARD")
    wait_until_js(
        page,
        """
        (() => (document.body && document.body.innerText || '').includes('DASHBOARD'))()
        """,
        timeout_ms=8000,
    )

    run_js(
        page,
        """
        (() => {
          window.__offlineBrainProbe.textChat = { pending: true };
          const started = performance.now();
          const beforeEvents = (window.__offlineBrainProbe?.events || []).length;
          window.shellAPI.call('chat-message', 'Reply in one short line: what is 7 plus 5?', { source: 'text' })
            .then((result) => {
              const deadline = performance.now() + 30000;
              const tick = () => {
                const events = (window.__offlineBrainProbe?.events || []).slice(beforeEvents);
                const chatEvents = events.filter((item) => item.channel === 'chat-updated');
                const finalEvent = chatEvents.find((item) => item.payload && item.payload.pending === false && item.payload.source === 'text')
                  || chatEvents.find((item) => item.payload && item.payload.source === 'text' && !item.payload.pending && item.payload.reply !== result?.reply);
                if (!finalEvent && performance.now() <= deadline) {
                  setTimeout(tick, 150);
                  return;
                }
                const finalEvents = (window.__offlineBrainProbe?.events || []).slice(beforeEvents);
                window.__offlineBrainProbe.textChat = {
                  pending: false,
                  result,
                  finalEvent: finalEvent || null,
                  elapsedMs: Math.round((performance.now() - started) * 100) / 100,
                  events: finalEvents
                };
              };
              tick();
            })
            .catch((error) => {
              window.__offlineBrainProbe.textChat = {
                pending: false,
                error: String(error && error.message || error),
                elapsedMs: Math.round((performance.now() - started) * 100) / 100
              };
            });
          return true;
        })()
        """,
        timeout_ms=5000,
    )
    text_chat = wait_until_js(
        page,
        """
        (() => {
          const value = window.__offlineBrainProbe?.textChat;
          return value && value.pending === false ? value : false;
        })()
        """,
        timeout_ms=30000,
    )
    report["chat"] = text_chat if isinstance(text_chat, dict) else {"success": False}
    chat_final_payload = ((report["chat"].get("finalEvent") or {}).get("payload") or {})
    chat_reply = str(chat_final_payload.get("reply") or (report["chat"].get("result") or {}).get("reply") or "")
    if not chat_reply:
        report["errors"].append("Text chat did not return a local model reply.")
    if "provider" in chat_reply.lower() or "api key" in chat_reply.lower():
        report["errors"].append("Text chat returned provider/API fallback instead of local model reply.")

    run_js(
        page,
        """
        (() => {
          window.__offlineBrainProbe.voiceChat = { pending: true };
          const started = performance.now();
          const beforeEvents = (window.__offlineBrainProbe?.events || []).length;
          window.shellAPI.call('chat-message', 'Reply in Hinglish, one short line: local voice test successful hai kya?', { source: 'voice' })
            .then((result) => {
              const deadline = performance.now() + 30000;
              const tick = () => {
                const events = (window.__offlineBrainProbe?.events || []).slice(beforeEvents);
                const chatEvents = events.filter((item) => item.channel === 'chat-updated');
                const finalEvent = chatEvents.find((item) => item.payload && item.payload.pending === false && item.payload.voice === true)
                  || chatEvents.find((item) => item.payload && item.payload.voice === true && !item.payload.pending);
                if (!finalEvent && performance.now() <= deadline) {
                  setTimeout(tick, 150);
                  return;
                }
                setTimeout(() => {
                  const finalEvents = (window.__offlineBrainProbe?.events || []).slice(beforeEvents);
                  window.__offlineBrainProbe.voiceChat = {
                    pending: false,
                    result,
                    finalEvent: finalEvent || null,
                    elapsedMs: Math.round((performance.now() - started) * 100) / 100,
                    events: finalEvents
                  };
                }, 2500);
              };
              tick();
            })
            .catch((error) => {
              window.__offlineBrainProbe.voiceChat = {
                pending: false,
                error: String(error && error.message || error),
                elapsedMs: Math.round((performance.now() - started) * 100) / 100
              };
            });
          return true;
        })()
        """,
        timeout_ms=5000,
    )
    voice_chat = wait_until_js(
        page,
        """
        (() => {
          const value = window.__offlineBrainProbe?.voiceChat;
          return value && value.pending === false ? value : false;
        })()
        """,
        timeout_ms=42000,
    )
    report["voiceChat"] = voice_chat if isinstance(voice_chat, dict) else {"success": False}
    final_payload = ((report["voiceChat"].get("finalEvent") or {}).get("payload") or {})
    voice_reply = str(final_payload.get("reply") or (report["voiceChat"].get("result") or {}).get("reply") or "")
    if not voice_reply:
        report["errors"].append("Voice-source chat did not return a final local model reply.")
    if "provider" in voice_reply.lower() or "api key" in voice_reply.lower():
        report["errors"].append("Voice-source chat returned provider/API fallback instead of local model reply.")

    run_js(
        page,
        """
        (() => {
          window.__offlineBrainProbe.explicitTts = { pending: true };
          const started = performance.now();
          const beforeEvents = (window.__offlineBrainProbe?.events || []).length;
          window.shellAPI.speakText('Shell local Kokoro voice test. Haan bhai, offline voice ready hai.')
            .then((result) => {
              const deadline = performance.now() + 20000;
              const tick = () => {
                const events = (window.__offlineBrainProbe?.events || []).slice(beforeEvents);
                const terminalSpeech = events.find((item) => {
                  if (item.channel !== 'speech-status' || !item.payload) return false;
                  const state = String(item.payload.state || '').toLowerCase();
                  return state === 'speaking' || state === 'error';
                });
                if (!terminalSpeech && performance.now() <= deadline) {
                  setTimeout(tick, 200);
                  return;
                }
                window.__offlineBrainProbe.explicitTts = {
                  pending: false,
                  result,
                  terminalSpeech: terminalSpeech || null,
                  elapsedMs: Math.round((performance.now() - started) * 100) / 100,
                  events
                };
              };
              tick();
            })
            .catch((error) => {
              window.__offlineBrainProbe.explicitTts = {
                pending: false,
                error: String(error && error.message || error),
                elapsedMs: Math.round((performance.now() - started) * 100) / 100
              };
            });
          return true;
        })()
        """,
        timeout_ms=5000,
    )
    explicit_tts = wait_until_js(
        page,
        """
        (() => {
          const value = window.__offlineBrainProbe?.explicitTts;
          return value && value.pending === false ? value : false;
        })()
        """,
        timeout_ms=30000,
    )
    report["tts"] = explicit_tts if isinstance(explicit_tts, dict) else {"success": False}
    tts_result = report["tts"].get("result") if isinstance(report["tts"].get("result"), dict) else {}
    if not tts_result.get("success"):
        report["errors"].append(f"Explicit local voice playback failed: {tts_result.get('message') or tts_result.get('error') or 'unknown'}")

    screenshot_path = report_dir / "offline_brain_e2e.png"
    window.view.grab().save(str(screenshot_path))
    report["screenshots"]["e2e"] = str(screenshot_path)
    report["ok"] = not report["errors"] and bool(load_state["ok"])

    report_path = report_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    window.close()
    app.processEvents()
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
