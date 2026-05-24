<!-- SPDX-License-Identifier: Apache-2.0 -->

# Shell AI OS Controller Current-System E2E Audit

Date: 2026-05-24

Scope: current React Web UI, PyQt WebEngine host, Shell bridge, chart/chat
routing, Gallery, Telegram controls, tool gateway, agent/tool probes, installer
health, CI, and public release gates.

## Executive Summary

Shell currently launches through the React/Vite/WebGL renderer embedded inside
PyQt WebEngine. The old PyQt UI remains as a rollback path, but the checked
README, docs, screenshots, and videos now point at the Web UI path.

The repository is in a green CI state:

- GitHub Actions CI passes Release integrity and Python 3.10/3.11/3.12/3.13.
- GitHub Actions Security passes CodeQL, secret-pattern guard, and Python
  dependency audit.
- Local CI-style pytest run passes with `538 passed`.

## User-Facing Flows Verified

| Flow | Result |
| --- | --- |
| Dashboard tabs and nested panels | Pass |
| Chart/transcript text chat | Pass |
| Text-originated chat stays text-only | Pass |
| Previous task recall in transcript/chart | Pass |
| Chart telemetry prompts | Pass |
| Normal text prompts from chart box | Pass |
| Control Center calculator/tool execution | Pass |
| Settings General/API/Security scroll behavior | Pass |
| API key panel placement | Pass |
| Telegram status/start/stop/test controls | Pass |
| Gallery image save/render/delete/copy bridge | Pass |
| Fake camera and fake screen-share streams | Pass |
| CSS enter/fade/zoom animation utilities | Pass |
| Voice button click paths | Pass |

Latest real UI probe coverage is documented in `.shell_runtime/` locally and
summarized in `SESSION_LOG.md`.

## Backend And Tool Validation

| Probe | Result |
| --- | --- |
| Tool catalog scan | 468 entries, 0 probe errors |
| Agent probe | 37/37 agents passed |
| Chart/tools/Gallery/animation probe | Passed |
| Chart/transcript focused probe | Passed |
| Installer focused tests | Passed |
| Release integrity workflow | Passed |

Important tool policies verified:

- Destructive tools stay safety-gated.
- Text chart/chat commands do not trigger voice playback.
- Missing optional providers produce clear readiness or setup messages.
- Windows-only automation remains unsupported on macOS/Linux and active on
  Windows when the required driver path is available.

## Current Architecture Under Test

```text
React Web UI
  -> PyQt WebEngine host
  -> QWebChannel shell bridge
  -> Shell natural-language router
  -> Tool gateway / agent orchestrator
  -> local tools, OS automation, APIs, memory, RAG, sandbox, checkpoints
  -> structured result events back to the UI
```

Voice and remote access paths are intentionally opt-in:

- Gemini Live voice requires a valid Gemini API key and working audio output.
- Wake word and VAD are behind `SHELL_WAKE_WORD_ENABLED` and
  `SHELL_VAD_ENABLED`.
- Telegram PC control requires a token, allowlisted chat ID, and explicit
  remote-control gates.

## Known Limitations

- Real camera/screen capture may require OS privacy permissions and app restart.
- Real Windows-MCP and pywinauto control must be validated on Windows/RDP.
- macOS remote sessions still depend on the RDP/Parsec audio forwarding path for
  audible voice.
- The main Web UI bundle is still large and should be split by heavy optional
  routes.
- Public GA still needs signed Windows installer and macOS notarization.

## Recommended Next Validation

1. Run one-click install on a clean Windows machine.
2. Start Shell through `Start_ShellAI.bat`.
3. Test chat, voice output, app open/close, Gallery image generation, Telegram
   status, and Control Center execution from the visible UI.
4. Run the Windows acceptance script and attach the generated report to the
   release notes.
