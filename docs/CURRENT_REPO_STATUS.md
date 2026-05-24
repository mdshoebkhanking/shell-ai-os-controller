<!-- SPDX-License-Identifier: Apache-2.0 -->

# Current Repository Status

Date: 2026-05-24

This page is the short, current-state snapshot for the public repository.

## Release State

- Branch: `main`
- Latest GitHub Actions baseline before this documentation/media refresh: `1902d15`
- Public positioning: AI-native desktop control layer, not an OS replacement
- Primary interface: React/Vite/WebGL Shell Web UI embedded in PyQt WebEngine
- Rollback interface: legacy PyQt UI behind `SHELL_LEGACY_UI=1`
- License: Apache-2.0

## CI And Security

Latest GitHub Actions status:

| Workflow | Result |
| --- | --- |
| CI Release integrity | Passing |
| CI Python 3.10 tests | Passing |
| CI Python 3.11 tests | Passing |
| CI Python 3.12 tests | Passing |
| CI Python 3.13 tests | Passing |
| Security CodeQL | Passing |
| Security secret pattern guard | Passing |
| Security Python dependency audit | Passing |

Latest local validation:

```text
538 passed
```

## Current Product Surface

| Area | Current status |
| --- | --- |
| Dashboard | Chart + transcript chat, text-only typed replies, previous-task recall |
| Voice | Gemini Live route plus backend/local fallback controls |
| Telemetry | PyQtGraph-backed live charts with legacy rollback |
| Settings | General/API/Security scroll panels, API key manager, Telegram controls |
| Gallery | Generated image save, render, reveal, delete, and copy actions |
| Control Center | Direct backend tool execution path |
| Tools | 468 catalog entries scanned in probes |
| Agents | 37/37 agent readiness/execution smoke checks passed |
| Memory | Legacy JSON default, Memory v2 SQLite behind env flag |
| RAG | Project RAG v2 behind env flag |
| Sandbox | Secure Python workspace behind env flag |
| Checkpoints | Workflow checkpoint persistence behind env flag |
| Windows automation | pywinauto opt-in primary driver, PyAutoGUI/pywin32 fallback |
| Telegram | Token, allowlist, PC-control, terminal gate, status/start/stop/test send |

## Current Demo Assets

- Current 16:9 Web UI demo: `videos/shell-current-ui-landscape-demo.mp4`
- Current 16:9 Web UI poster: `videos/shell-current-ui-landscape-poster.png`
- Current SVG showcase: `screenshots/current/`
- Current vertical Web UI demo: `videos/shell-current-state-demo.mp4`
- Current vertical Web UI poster: `videos/shell-current-state-demo-poster.png`
- Classic launch demo: `videos/shell-launch-demo.mp4`
- Showcase screenshots: `screenshots/showcase/`
- Architecture diagram: `docs/assets/shell_architecture_map.svg`
- Status dashboard diagram: `docs/assets/shell_status_dashboard.svg`

## Known Limits

- Real Gemini voice requires a valid Gemini API key and working local/remote
  audio output.
- Real camera/screen capture can require OS privacy permissions.
- Windows-MCP and pywinauto are Windows-specific for real desktop control.
- Destructive tools are intentionally safety-gated and are not executed by the
  public probes.
- The Web UI bundle still needs code splitting for heavy optional views.
