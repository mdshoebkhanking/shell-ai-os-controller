# Shell AI — Architecture

*An honest, reality-matching description of how Shell actually works. For
the pitch, see [README.md](README.md).*

---

## Big picture

Shell is three layers glued together:

```
┌──────────────────────────────────────────────────────────────────┐
│  LiveKit Agents  ·  streaming mic ↔ Gemini Realtime ↔ speaker    │
│  (livekit-agents, livekit-plugins-google, livekit-plugins-silero)│
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 │  AgentSession
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│  agent.py — the Assistant class                                  │
│    • imports ~80 shell_*.py modules lazily                       │
│    • registers ~300 @function_tool functions into `tools_list`   │
│    • passes `tools_list` + instructions + voice to Gemini        │
│    • handles session state, SocketIO events, shutdown            │
└──────────────────────────────────────────────────────────────────┘
                                 │
          ┌──────────────────────┼─────────────────────────────┐
          ▼                      ▼                             ▼
    Desktop I/O            Web I/O                      External APIs
    (pyautogui,            (selenium,                   (Groq, Perplexity,
     pygetwindow,          playwright,                   HF, Pollinations,
     pywin32)              aiohttp)                      OpenWeather, etc.)
```

The **only** AI running is hosted Gemini. Everything else is a Python
program deciding what to execute.

---

## Control flow — one utterance, end to end

1. User speaks into the mic.
2. LiveKit's VAD decides "speech is over" after `VAD_MIN_SILENCE_SEC`.
3. Audio is streamed to Gemini 2.5 Flash Native Audio.
4. Gemini transcribes internally, reasons, and emits either:
   - audio back (Aoede / Kore / whichever voice is set), and/or
   - one or more function calls into Shell's `tools_list`.
5. For each function call, the Python function runs in Shell's process.
6. Return value is sent back to Gemini as tool output; Gemini decides if
   it needs more tool calls or a final reply.
7. Final audio plays through the speaker; agent resumes listening.

Steps 3–7 are LiveKit's realtime agent loop, not anything custom to
Shell. Shell's job is only:

- Give Gemini a good `tools_list` with good docstrings.
- Execute function calls safely and quickly.
- Feed results back cleanly.

---

## Module map

### Core runtime

| File | Role |
|---|---|
| `agent.py` | Central orchestrator. 1946 lines; contains the `Assistant` class, session handlers, and the full `tools_list`. Slated for refactor. |
| `shell_voice.py` | Single source of truth for voice + persona. Exposes resolver, catalog of 30 Gemini voices, 6 personas, runtime switcher, session registration. |
| `shell_safety_gate.py` | Gates the dangerous "write LLM code to disk" operations. Refuses by default unless `SHELL_ALLOW_CODE_WRITE` / `SHELL_ALLOW_AGENT_PATCH` is set. Appends audit log. |
| `shell_config.py` | `.env` loader + typed getters. Grouped properties (`config.voice`, `config.email`, `config.vad`). |
| `shell_prompts.py` | `behavior_prompts` (full) and `realtime_prompts` (concise, default for voice sessions). |
| `shell_logger.py` | `get_logger(name)` helper — tagged console + file output to `shell_ai.log`. |

### Tool families

Each of these modules registers a set of `@function_tool`-decorated
functions into `agent.py`'s `tools_list`.

| File | Tools |
|---|---|
| `shell_browser_CTRL.py` | Selenium browser automation, YouTube, tabs, screenshots, bookmarks |
| `shell_window_CTRL.py` | Window management, notepad, terminal commands |
| `keyboard_mouse_CTRL.py` | Keyboard, mouse, hotkeys, clipboard gestures |
| `shell_image_ai.py` | Multi-provider image generation, upscale, filters, bg removal |
| `shell_system_pro.py` | Power, battery, brightness, process kill, specs |
| `shell_system_god.py` | Deeper Windows control: wifi, registry, port scan, services |
| `shell_email_tool.py` / `shell_email_web.py` | SMTP and Gmail Web fallback |
| `shell_whatsapp.py` | Unified facade over 5 legacy backends (desktop / auto-reply / monitor / Selenium / Node) |
| `shell_telegram.py` | Telegram bot polling + commands |
| `shell_instagram.py` / `shell_social_god.py` | Instagram + social aggregator |
| `shell_google_search.py` / `shell_news.py` / `shell_get_whether.py` / `shell_stock.py` | Information APIs |
| `shell_pdf.py` / `shell_file_converter.py` / `shell_zip.py` / `shell_json_tools.py` / `shell_regex.py` | Document and text utilities |
| `shell_calculator.py` / `shell_hash.py` / `shell_crypto.py` / `shell_qr.py` | Small utility tools |
| `shell_ocr.py` / `shell_screenshot.py` | Screen capture + OCR (uses `vision_engine.py` when Tesseract absent) |
| `shell_music.py` / `shell_video.py` | Audio / video file tools |
| `shell_ppt_god.py` | PowerPoint generation |
| `shell_speech.py` | Local TTS (pyttsx3 / gTTS / SAPI) + Gemini voice-switcher tools |
| `shell_translator.py` | Multi-provider translation |
| `shell_scheduler.py` | Timers, alarms, recurring schedules |
| `shell_terminal.py` | Shell commands, PowerShell, Python execution |

### Brain / memory

| File | Role |
|---|---|
| `brain/core.py` | `ShellBrain` — multi-provider chat wrapper (OpenAI / Groq / Gemini / Mistral / Perplexity / SambaNova / Blackbox / OpenRouter / DeepSeek) |
| `brain/memory_core.py` | Sentence-transformer-backed JSON memory store |
| `brain/predictive_engine.py` | scikit-learn classifier that guesses user's next action from logs |
| `shell_knowledge.py` | Plain-text knowledge facts + learn-from-file helpers |

### Advanced / honest-but-gated

| File | Status |
|---|---|
| `shell_evolution.py` | "Darwin Protocol" — can write new `shell_*.py` modules and hotpatch `agent.py`. **Gated by `SHELL_ALLOW_CODE_WRITE` / `SHELL_ALLOW_AGENT_PATCH`.** |
| `shell_sentinel.py` | Error-log watcher that asks Gemini for a fix and applies it. **Gated.** |
| `shell_self_heal.py` | Naming-aspirational. Realistic behavior is "retry + log + scan" rather than autonomous self-healing. |
| `shell_oracle.py` | Proactive background intelligence stub. |

### UI / transport

| File | Role |
|---|---|
| `shell_hub.py` | aiohttp + Socket.IO server. Bridges agent state to the UI. Issues LiveKit tokens on `/token`. |
| `shell_windows_mcp.py` | CursorTouch Windows-MCP stdio adapter. Exposes real MCP desktop tools (`Click`, `Type`, `Screenshot`, `Snapshot`, `App`, `Shell`, etc.) to UI/chat. |
| `mcp_server.py` / `shell_mcp_server.py` | Legacy HTTP JSON-action server kept for compatibility. It is no longer the UI's MCP surface. |
| `shell_ui/shell_cinematic_full.py` | PyQt6 "glass" UI — animated orb, states, captions. Connects to hub via Socket.IO. |
| `shell_ui/shell_orb_*.py` | Orb renderer variants (OpenGL, particle, pygame). |
| `launch.py` / `launch_ui.pyw` | UI entry points. |
| `start_shell.bat` | One-batch launcher (hub → MCP → agent → UI, each in its own terminal). |
| `ONE_CLICK_INSTALL.bat` | Windows venv + pip + registry setup. |

---

## Voice stack (post Phase 1)

```
.env                        shell_config.voice                 shell_voice
 │                           │                                  │
 └─ VOICE_NAME=Aoede ──────▶ resolve_voice() ────────────────▶ catalog of 30
    VOICE_PERSONA=Hinglish   resolve_persona() ──────────────▶ 6 personas
                                                               │
                                                               ▼
                                                 build_persona_instruction()
                                                 persona_system_suffix()
                                                               │
                              agent.py (entrypoint)             │
                                   │                            │
                                   │  append persona suffix ─◀──┘
                                   ▼
                           full_instructions = realtime_prompts + suffix
                                   │
                                   ▼
                 AgentSession(llm=Gemini Realtime, voice=Aoede, instructions=…)
                                   │
                                   ▼
                      register_session(session, voice=Aoede)
                                   │
                                   ▼
                   user speaks ↔ Aoede speaks ↔ tool calls
```

Runtime voice switching (`switch_shell_voice_tool`) tries
`llm.update_options(voice=…)`, `llm.update(voice=…)`,
`llm.set_voice(voice)`, then `session.update(voice=…)`. If the LiveKit
version does not expose any of those, the new voice is queued into
`os.environ["VOICE_NAME"]` so the next session starts with it.

---

## Safety gates (post Phase 2)

Any code-writing tool **must** call `shell_safety_gate.check_code_write`
(or the stricter `check_agent_patch`) before touching disk:

```
create_capability_tool  ──┐
hotpatch_agent_tool     ──┼─▶ check_agent_patch() or check_code_write()
rollback_evolution_tool ──┤           │
sentinel.heal_file      ──┘           │
                                      ▼
                               env flag set?
                              /            \
                            yes             no
                             │              │
                             ▼              ▼
                    audit_write()      return BLOCKED
                    perform write       with explainer
```

Audit log lives at `.shell_safety_audit.log`.

Default environment: **both flags off**. This was a deliberate break
from the original behaviour, where these tools would happily execute
arbitrary Gemini output. If you want the old behaviour back, set both
flags to `1` in `.env`.

---

## WhatsApp stack (post Phase 3)

Historically five files (`shell_whatsapp_CTRL.py`, `_ULTRA.py`,
`_auto_reply.py`, `_monitor.py`, `_web_real.py`) with overlapping
launch / focus / send helpers. Phase 3 introduced a facade:

```
             ┌───────────────────────────────────────────┐
             │              shell_whatsapp.py            │
             │  (single import point for agent.py)       │
             └─────┬─────────┬─────────┬─────────┬───────┘
                   │         │         │         │
                   ▼         ▼         ▼         ▼
             CTRL       ULTRA     auto_reply   monitor     web_real
             (send)     (bulk,    (AI reply,   (loop +     (Selenium,
                         media)    log,         state)      QR link)
                                   contact
                                   memory)
```

All 17 tool names agent.py used to import from 5 separate files are
now re-exported from a single `shell_whatsapp` module. The legacy
backend files continue to exist so any third-party code that imports
them directly keeps working.

Phase 3 also replaced a silently broken `verify_message_sent()` that
had been calling a non-existent `vision_engine.analyze_screen` method
and hiding the `AttributeError` behind a `return True`.

---

## Dependencies (post Phase 4)

`requirements.txt` is organised into sections:

- **Core runtime** — LiveKit + Gemini SDKs, dotenv, requests/httpx/aiohttp.
- **AI provider SDKs** — openai, mistralai, groq. Anthropic is intentionally
  not installed or registered by default.
- **Browser & web** — selenium, playwright.
- **Vision & media** — pillow, opencv, pytesseract, numpy, rembg, mss.
- **Desktop automation** — pyautogui, pyperclip, pynput, keyboard, psutil.
- **Windows-only** — pygetwindow, pywin32, comtypes, wmi.
- **Audio I/O** — sounddevice, pyttsx3, gtts.
- **Documents** — pypdf, python-pptx, pdf2image, reportlab, qrcode, pyzbar.
- **NLP / ML** — fuzzywuzzy, sentence-transformers, scikit-learn,
  youtube-transcript-api, yt-dlp, deep-translator.
- **Communication** — instagrapi, speechrecognition.
- **UI** — PyQt6, PyQt6-WebEngine, PyOpenGL, GPUtil, pygame-ce, ursina.
- **Utilities** — pyfiglet, cryptography, yfinance.
- **Testing** — pytest, pytest-asyncio, pytest-timeout.

Removed in the April 2026 cleanup: beautifulsoup4, colorama.

---

## Test suite

| File | Focus | Count |
|---|---|---|
| `tests/test_security_regressions.py` | Downloader SSRF/path safety, workflow gates, env redaction | 4 |

All tests run offline. Run: `pytest` (uses `pytest.ini`).

---

## Known architectural debts

1. **agent.py is monolithic** — 2000+ lines in one file, one class, one
   `__init__`. Planned split into decorator-driven auto-discovery where
   each tool module self-registers.
2. **Legacy HTTP MCP naming remains.** The active UI/chat MCP surface is
   CursorTouch Windows-MCP, but old compatibility files still need a future
   rename to `shell_http_api.py`.
3. **Hub auth is optional.** It binds to loopback by default and supports
   `SHELL_HUB_TOKEN`, but Socket.IO/event scoping is still broad.
4. **Dual Google SDKs.** `google-generativeai` (deprecated) and
   `google-genai` (modern) both installed; migration ongoing.
5. **Hardcoded screen coordinates** in WhatsApp desktop backend.
   Resilient only at 1920×1080.

These are tracked in the README roadmap section and will be addressed
in subsequent phases.
