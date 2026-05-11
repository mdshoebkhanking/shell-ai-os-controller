# Shell AI OS Controller Current-System E2E Audit

Date: 2026-05-10  
Host: macOS Darwin 24.6.0, Python 3.9.6 via `.codex_ui_venv`  
Scope: stabilize and validate the current PyQt UI, hub backend, tool gateway, settings backend, Windows-MCP guard path, voice page behavior, and observability hooks before any future architecture expansion.

## Execution Summary

The current system can launch the hub and PyQt UI locally when GUI/network permissions are available. The UI renders all five primary pages, connects to the hub, executes safe local tools from chat, shows Windows-MCP unsupported-platform errors without crashing on macOS, persists settings/API changes through the backend, and handles missing voice dependencies as a visible error state.

High-impact fixes applied during this audit:

- Disabled dangerous code-writing execution in `.env` by setting `SHELL_ALLOW_CODE_WRITE=0`.
- Fixed `launch_ui.pyw` so it no longer forces `QT_QPA_PLATFORM=windows` on macOS/Linux.
- Added QtWebEngine preflight flags to `launch_ui.pyw` to match `launch.py`.
- Removed the stale “GODLEVEL” startup claim from `launch.py`.
- Added missing `websocket` transport visibility to startup health diagnostics.
- Added repeatable UI E2E probe: `tools/e2e_ui_probe.py`.

## What Was Launched

Backend:

```bash
.codex_ui_venv/bin/python shell_hub.py
```

Result:

- Started on `http://127.0.0.1:5000`.
- `/health`: HTTP 200, about `0.0046s`.
- `/capabilities`: HTTP 200, about `0.763s`, payload about `1.06 MB`.
- `/settings`: HTTP 200.
- `/api-keys`: HTTP 200.

UI:

```bash
.codex_ui_venv/bin/python launch.py
```

Result:

- Visible PyQt window opened.
- Hub status showed `ONLINE`.
- Chat page rendered correctly.
- Non-escalated sandbox launch aborted at `QApplication` because macOS pasteboard/window services were blocked; escalated GUI launch worked.

Automated UI probe:

```bash
.codex_ui_venv/bin/python tools/e2e_ui_probe.py --visible \
  --screens-dir /private/tmp/shell_ui_probe_visible3 \
  --json-out /private/tmp/shell_ui_probe_visible3_report.json
```

Result:

- `ok: true`.
- Chat, Voice, System, Tools, and Settings pages all rendered and screenshots were saved.
- Calculator tool via chat added visible UI output.
- Windows-MCP Screenshot command returned a visible “requires Windows” failure.
- Text chat returned text only; no auto-TTS trigger was observed.
- Voice visual toggle preserved geometry: `(124, 6, 260, 260)` before and after.
- Voice start entered `ERROR` with `Voice unavailable: sounddevice not installed`.

Regression tests:

```bash
.codex_ui_venv/bin/python -m pytest -q
```

Result:

- `138 passed, 1 warning in 3.04s`.
- Remaining warning: `urllib3` warns that Python is linked against LibreSSL 2.8.3 instead of OpenSSL 1.1.1+.

## Screenshots Captured

- Visible launch: `/private/tmp/shell_ui_start.png`
- UI probe pages: `/private/tmp/shell_ui_probe_visible3/`
- Final chat workflow: `/private/tmp/shell_ui_probe_visible3/final_chat_after_commands.png`
- Probe report: `/private/tmp/shell_ui_probe_visible3_report.json`

## Broken Systems

- Shell-v2 brain endpoint `http://127.0.0.1:8765/api/say` was not running. Chat falls back to local canned replies when this endpoint refuses connection.
- Full realtime voice runtime is not available in this environment because `sounddevice` and `livekit` are missing.
- Windows-MCP cannot run on macOS. This is handled correctly as an unsupported-platform state, but actual Windows automation needs validation on Windows with Python 3.13+ and `uvx`.
- Browser/OCR/media automation families are partly unavailable because dependencies are missing: `selenium`, `playwright`, `pytesseract`, `ffmpeg`, `tesseract`.

## Unstable Systems

- Socket.IO falls back to HTTP polling because `websocket-client` is missing. UI still connects, but realtime latency and resilience are weaker.
- macOS global hotkey registration logs an Accessibility warning through `pynput`; quick launcher hotkeys will not work until the app is trusted in Accessibility settings.
- Rapid widget screenshots in the visible probe produced repeated `QPainter` warnings around graphics effects. The UI stayed usable, but this should be cleaned up before heavy automated visual testing.
- The Tools catalog is large: 433 capabilities and about 1.06 MB JSON per `/capabilities` response.

## UI Problems

- UI page rendering is stable for Chat, Voice, System, Tools, and Settings under the probe.
- Voice orb visual off/on no longer shifts position in the tested path.
- Voice page initially says `READY` even when `sounddevice` is missing; the accurate error appears only after pressing Start Voice.
- Sidebar active state in the probe does not update when pages are changed programmatically through `_on_page_change`; real sidebar clicks should still drive the normal active state.
- Some font aliases are missing, causing a small startup cost: Qt reports about 50 ms to populate aliases.
- The UI still depends heavily on `shell_ui/shell_cinematic_full.py`, which remains a large monolithic file.

## Backend Problems

- Hub starts and endpoints work after real loopback permissions are available.
- In-memory observability events/traces are process-local. Tool executions run in UI/CLI processes do not automatically appear in the hub process `/health` trace list.
- Health reports optional dependencies but still returns top-level state `READY`. This is acceptable for degraded operation, but the UI should show degraded capability readiness more prominently.
- API key management correctly avoids returning secret values.

## Orchestration Issues

- Chat primary path expects Shell-v2 at port `8765`; if it is down, the UI silently falls to local replies after logging an error.
- The catalog reports 38 agent-like capabilities, while `shell_agents:list_agents_tool` reports 21 agents. The agent inventory needs one source of truth.
- Tool routing blocks unsafe terminal execution as expected when `SHELL_ALLOW_TERMINAL_EXEC=0`.
- Tool readiness metadata is present, but the Tools page still lists unavailable Windows-MCP items first on macOS.

## Dependency Problems

Final health missing dependencies:

- `websocket`
- `selenium`
- `playwright`
- `pytesseract`
- `sounddevice`
- `livekit`
- `ffmpeg`
- `tesseract`
- `uvx`

Impact:

- No true websocket transport.
- No local mic capture.
- No LiveKit voice runtime in this venv.
- No OCR executable path.
- No full browser automation stack.
- No Windows-MCP launcher on this host.

## Performance Bottlenecks

- `/health`: about `0.0046s`.
- `/capabilities`: about `0.763s`, about `1.06 MB`.
- Full UI probe: about `12.4s` wall time in offscreen performance run.
- Full test suite: about `3.04s`.
- Capability catalog should be cached or paginated for production UI responsiveness.

## Memory Leaks

No deterministic leak was proven in this audit. The probe starts/stops backend workers and voice listener cleanup without hanging. Remaining risk areas:

- Multiple QTimers in the monolithic UI.
- Background socket/polling client threads.
- QuickLauncher global hotkey listener.
- Graphics effects during repeated screenshots.

## Dead Code

Observed dead/legacy weight:

- `_backups_/` contains large historical copies.
- Nested `shell.v1.0-main-main/...` copy exists inside the project tree.
- `launch_ui.pyw` was stale relative to `launch.py` before this audit.
- Compatibility modules under `shell_ui/chat`, `voice`, `settings`, etc. are import seams, but most implementation still lives in the monolith.

## Duplicate Logic

Capability duplicate detection reported:

- `shell_brain.__init__:activate_god_mode_tool` and `shell_brain.god_mode:activate_god_mode_tool`
- `shell_whatsapp_CTRL:send_whatsapp_message` and `shell_whatsapp_ULTRA:send_whatsapp_message`
- `shell_crypto:hash_file_tool` and `shell_hash:hash_file_tool`

Agent inventory is also duplicated between catalog discovery and `list_agents_tool`.

## Unsafe Execution Paths

Fixed:

- `SHELL_ALLOW_CODE_WRITE` was enabled and is now disabled.

Verified blocked:

- `shell_terminal:run_python_tool` returns `BLOCKED_BY_SAFETY` when `SHELL_ALLOW_TERMINAL_EXEC=0`.
- Windows-MCP Shell tool is blocked by platform and terminal safety state on macOS.

Still requiring production policy:

- UI should make enabled dangerous flags visually obvious.
- Code-writing and patching tools should require explicit per-action approval, not only env flags.

## Race Conditions

No crash-level race was reproduced. Risks remain around:

- Socket.IO reconnect while page transitions are happening.
- QThread worker cleanup during app close.
- Voice listener error emission racing with stop.
- Settings commit while hub is restarting.

## Event Synchronization Issues

- UI can show `ONLINE` when Socket.IO polling connects.
- Hub `/health` event and trace arrays remain empty unless events originate in that same hub process.
- UI backend command results render correctly in chat, but system-wide trace persistence is not centralized.

## Startup Issues

- Running GUI startup inside the restricted sandbox aborts at `QApplication`; real macOS GUI permissions are required.
- `.codex_ui_venv` Python is linked against LibreSSL, causing `urllib3` warnings.
- Missing `websocket-client` forces polling mode.
- Missing font families cause minor startup overhead.
- `launch_ui.pyw` cross-platform startup bug was fixed.

## Missing Observability

Present:

- `/health` structured diagnostics.
- Tool gateway trace IDs for blocked/failed tool runs.
- Readiness counts in `/capabilities`.
- UI probe JSON and screenshots.

Missing:

- Persistent central trace store across hub/UI/tool processes.
- UI-visible trace timeline for each chat/tool run.
- Long-run CPU/RAM sampling in the audit report.
- Structured UI exception log panel.
- Dependency remediation actions from the UI.

## Architecture Weaknesses

- `shell_ui/shell_cinematic_full.py` remains the largest coupling point.
- Chat depends on a separate Shell-v2 service on port `8765`, but startup orchestration does not guarantee that service exists.
- Capability discovery is AST-based and broad; it exposes unavailable tools unless filtered by readiness in the UI.
- UI and backend are only partially event-driven; many state changes are still direct method calls.

## Maintainability Risks

- Hundreds of tools remain discoverable, with duplicate capability families.
- Agent definitions are partly catalog-driven and partly hardcoded.
- Settings/API key concepts are mixed in one UI/backend surface, which makes boolean safety flags look like API-key status rows.
- Historical backups and nested project copies increase search noise and accidental import risk.

## Rollback / Recovery

Changes can be reverted by restoring:

- `launch.py`
- `launch_ui.pyw`
- `core/health/startup.py`
- `tools/e2e_ui_probe.py`
- `.env` value `SHELL_ALLOW_CODE_WRITE=1` only if unsafe code-writing is intentionally needed for a controlled session.

Recommended recovery order if the app fails to start:

1. Start hub: `.codex_ui_venv/bin/python shell_hub.py`
2. Check health: `curl http://127.0.0.1:5000/health`
3. Start UI: `.codex_ui_venv/bin/python launch.py`
4. Run probe: `.codex_ui_venv/bin/python tools/e2e_ui_probe.py --visible`
5. Run tests: `.codex_ui_venv/bin/python -m pytest -q`

## Next Stabilization Work

1. Install or document the missing runtime dependencies per feature profile.
2. Add a single startup supervisor that launches hub, Shell-v2, agent, and UI in the correct order.
3. Move observability from process memory to a small local event/trace store.
4. Paginate/filter the Tools page by readiness so unavailable Windows-only tools do not dominate macOS.
5. Split `shell_cinematic_full.py` incrementally by page while preserving imports.
6. Unify agent registry counts and execution paths.
7. Add a UI health dashboard that shows dependency failures, safety flags, and current route decisions.
