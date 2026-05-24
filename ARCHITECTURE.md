# Shell AI — Architecture

*An honest, reality-matching description of how Shell actually works. For
the pitch, see [README.md](README.md).*

---

## Big picture

Shell is now five runtime surfaces behind one guarded backend:

```
┌──────────────────────────────────────────────────────────────────┐
│  React/Vite/WebGL renderer inside PyQt WebEngine                 │
│  Dashboard, chart chat, transcript, Settings, Gallery, Tools     │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 │  QWebChannel + hub events
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│  Shell Python host and runtime                                   │
│    • shell_web_ui/host.py exposes bridge APIs to JavaScript      │
│    • shell_hub.py streams runtime events when the hub is active  │
│    • shell_nl_router.py maps natural language to backend tools   │
│    • shell_tool_gateway.py executes catalogued tools safely      │
└──────────────────────────────────────────────────────────────────┘
                                 │
          ┌──────────────────────┼─────────────────────────────┐
          ▼                      ▼                             ▼
    Voice Pipeline         Agent/Tool Layer              External + OS I/O
    Gemini Live,           468 tool entries,             pywinauto, PyAutoGUI,
    local fallback,        37 agents, memory,            Windows-MCP, browser,
    wake/VAD flags         RAG, sandbox, checkpoints     Telegram, image APIs
```

The visible app defaults to the Web UI path. The preserved PyQt UI remains
available only as a rollback path with `SHELL_LEGACY_UI=1`. The classic voice
path can use Gemini/LiveKit or local fallbacks, while ShellAI Core can route
planning/summarization calls through OpenAI-compatible providers, OpenRouter,
or local Ollama depending on `~/.shellai/config.json` and environment
variables. Everything still resolves to Python code deciding what to execute
under policy, readiness, and safety gates.

---

## ShellAI Core and AI OS Fabric

ShellAI Core is the opt-in backend brain added for shell and desktop OS
automation. It is intentionally separate from the classic desktop behavior so
the PyQt app can keep working while the new agent loop matures.

```
CLI / Desktop bridge / future daemon
        │
        ▼
shellai.api.run_shellai_task()
        │
        ▼
AgentRuntime
        │
        ├─ CoordinatorAgent  ── planning JSON and request orchestration
        ├─ ShellAgent        ── shell/file/os tool execution boundary
        ├─ SafetyAgent       ── SAFE / ASK / BLOCK policy and audit decisions
        ├─ MemoryAgent       ── profile, conversation memory, relevant skills
        ├─ UIAgent           ── CLI/desktop summary shaping
        └─ OptimizerAgent    ── read-only suggestions from traces and skills
        │
        ▼
ModelRouter + MemoryStore + SkillManager + ToolRegistry
        │
        ▼
SQLite memory, JSON skills, trace snapshots, shell/file/os results
```

Important boundaries:

- `shellai/agent_loop.py` remains the stable single-request loop.
- `shellai/fabric/runtime.py` wires agents in-process only; there is no
  network bus or autonomous self-improvement loop.
- `core/shellai_bridge.py` is the desktop feature flag boundary. It returns
  `None` when `SHELLAI_BACKEND_MODE` is unset or `classic`, so the default Web
  UI and classic backend flows continue unchanged.
- `shellai/policy.py` and `shellai/safety.py` decide shell risk classes before
  `ShellTool` executes anything.
- `shellai/monitor.py` persists compact trace snapshots for CLI inspection.

Runtime storage defaults:

| Data | Default path |
|---|---|
| Config | `~/.shellai/config.json` or `SHELLAI_CONFIG` |
| SQLite memory | `~/.shellai/data/memory.sqlite3` |
| Skills | `~/.shellai/skills/manual` and `~/.shellai/skills/auto` |
| Traces | `~/.shellai/traces` |
| Logs | `~/.shellai/logs` |

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
| `agent.py` | Central classic orchestrator. Contains the `Assistant` class, session handlers, and the full legacy LiveKit tool list. Slated for continued extraction behind stable interfaces. |
| `shellai/` | New opt-in ShellAI Core package: CLI, agent loop, fabric runtime, models, memory, skills, tools, monitor, cron, daemon. |
| `core/shellai_bridge.py` | Feature-flagged desktop bridge from UI/agent callers into ShellAI Core. Defaults to classic behavior. |
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
| `shellai/memory/store.py` | SQLite-backed ShellAI Core memory facade for conversation, user profile, skill metadata, and audit records. |
| `shellai/skills/manager.py` | JSON skill loader/manager plus deterministic auto-skill drafts for reusable workflows. |
| `shellai/models/router.py` | Provider/model-role resolver for planning, command generation, and summarization. |

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
| `shell_hub.py` | aiohttp + Socket.IO server. Bridges agent/runtime state to the UI. Issues LiveKit tokens on `/token`. |
| `shell_windows_mcp.py` | CursorTouch Windows-MCP stdio adapter. Exposes real MCP desktop tools (`Click`, `Type`, `Screenshot`, `Snapshot`, `App`, `Shell`, etc.) to UI/chat. |
| `mcp_server.py` / `shell_mcp_server.py` | Legacy HTTP JSON-action server kept for compatibility. It is no longer the UI's MCP surface. |
| `shell_web_ui/host.py` | PyQt WebEngine host for the React renderer. Exposes Shell bridge APIs, system metrics, tool execution, Gallery, media permissions, voice state, and settings. |
| `shell_web_ui/src/` | React/Vite/WebGL Shell UI: Dashboard chart/chat, Settings, Gallery, Phone, Control Center, Notes, orb, animation system, and Shell bridge client. |
| `shell_ui/shell_cinematic_full.py` | Preserved PyQt6 legacy UI and rollback implementation behind `SHELL_LEGACY_UI=1`. |
| `ShellAICoreWorker` in `shell_ui/shell_cinematic_full.py` | Optional legacy worker that routes chat text through ShellAI Core when `SHELLAI_BACKEND_MODE=shellai_core`. Web UI routes through the bridge/host path. |
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
- **UI** — React, Vite, TypeScript, PyQt6, PyQt6-WebEngine, QWebChannel,
  PyOpenGL, GPUtil, pygame-ce, ursina.
- **Utilities** — pyfiglet, cryptography, yfinance.
- **Testing** — pytest, pytest-asyncio, pytest-timeout.

Removed in the April 2026 cleanup: beautifulsoup4, colorama.

---

## Test suite

| File | Focus | Count |
|---|---|---|
| `tests/test_security_regressions.py` | Downloader SSRF/path safety, workflow gates, env redaction | 4 |
| `tests/test_shellai_stage*.py` | ShellAI Core stages: config, models, memory, skills, tools, agent loop, desktop API bridge | 45+ |
| `tests/test_shellai_phase2_*.py` | AI OS Fabric wrappers, policy/monitor/optimizer, cron, daemon | 20+ |

All tests run offline. Run: `pytest` (uses `pytest.ini`). The latest full local
CI-style run in this workspace passed with `538 passed`. GitHub Actions is
green on Python 3.10, 3.11, 3.12, and 3.13.

---

## Known architectural debts

1. **agent.py is still monolithic** — one large classic entry point still
   owns LiveKit session wiring and legacy tool registration. ShellAI Core and
   `shell_tool_gateway.py` are the newer extraction boundaries, but the classic
   path still needs gradual split-out into stable modules.
2. **Legacy HTTP MCP naming remains.** The active UI/chat MCP surface is
   CursorTouch Windows-MCP, but old compatibility files still need a future
   rename to `shell_http_api.py`.
3. **Hub auth is optional.** It binds to loopback by default and supports
   `SHELL_HUB_TOKEN`, but Socket.IO/event scoping is still broad.
4. **Dual Google SDKs.** `google-generativeai` (deprecated) and
   `google-genai` (modern) both installed; migration ongoing.
5. **Large Web UI bundle.** The current Vite build passes, but the main chunk is
   still large and should be code-split around Gallery, Notes, vision, and
   workflow editor modules.

These are tracked in the README roadmap section and will be addressed
in subsequent phases.
