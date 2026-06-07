# Shell vs IRIS Tools/Agents Gap Report

Generated: 2026-06-07 16:40 CEST

## Scope

Compared Shell's current Electron/Python backend architecture against the IRISX reference repo at `/private/tmp/IRISX-AI`, then validated Shell's tools, agents, Control Center, offline brain, Kokoro TTS, and Electron UI path.

## IRIS Findings

- IRIS uses an Electron renderer with `electron-vite` and `electron-builder`.
- IRIS exposes OS/application features as direct `ipcMain.handle(...)` handlers in `src/main/index.ts`.
- IRIS has a thinner native IPC path for desktop actions, so its EXE feels closer to Chrome/Electron by default.
- IRIS does not appear to have Shell's larger readiness/safety classified catalog; Shell's advantage is broader tool/agent inventory plus offline brain and Kokoro routing.

## Shell Root Causes Found

- `tools/all_tools_ui_probe.py` still used the retired PyQt worker path. That meant the probe was not validating the Windows Electron EXE path.
- `tools/agents_ui_probe.py` still drove the old PyQt chat UI and only covered 37 of the 40 catalog agents.
- Control Center showed tools as clickable even when backend readiness was `NEEDS_API_KEY`, `WINDOWS_ONLY`, `MISSING_DEPENDENCY`, `EXPERIMENTAL`, or `BLOCKED_BY_SAFETY`, which made expected not-ready tools look broken.

## Fixes Applied

- Rewired all-tools probe to call `ShellBackendBridge.call("execute-tool", ...)`, the same backend channel used by Electron Control Center.
- Rewired agents probe to call the Electron backend bridge directly and cover all 40 catalog agents, including orchestration and safe swarm smoke.
- Added Control Center readiness badges, readiness/reason detail output, and disabled execution for tools the backend marks not ready.

## Current Inventory

- Full Control Center catalog: 490 capabilities.
- Decorated Shell tools/agents: 473 total.
- Tools: 433.
- Agents: 40.
- Windows MCP actions: 17.

Readiness for the 473 decorated tools/agents:

- `READY`: 255.
- `WINDOWS_ONLY`: 43.
- `MISSING_DEPENDENCY`: 67.
- `NEEDS_API_KEY`: 77.
- `EXPERIMENTAL`: 26.
- `BLOCKED_BY_SAFETY`: 5.

## Validation Results

- `tools/all_tools_ui_probe.py`: PASS.
  - Runtime: `electron-backend-bridge`.
  - Total scanned: 473.
  - Safe ready workers executed: 64.
  - Tool errors: 0.
  - Worker errors: 0.
  - Timeouts: 0.
- `tools/agents_ui_probe.py`: PASS.
  - Runtime: `electron-backend-bridge`.
  - Agents tested: 40/40.
  - Passed: 40.
  - Failed: 0.
- Targeted pytest: PASS.
  - 122 passed.
- `npm run build --prefix shell_web_ui`: PASS.
- Electron offline E2E: PASS.
  - Offline brain replied correctly.
  - Kokoro speech event used `engine: kokoro`.
  - `presetHit: true`.
  - `totalMs`: about 15-17 ms.
- Electron full UI E2E: PASS.
  - Tabs/buttons/settings/update fixture passed.
  - Responsiveness: about 60 fps.
  - Update download responsiveness: about 60 fps.

## Remaining Windows-Only Verification

These are not locally verifiable on macOS and must be run on the Windows target before release:

- Frozen `ShellAI.exe` runtime probe.
- Installed EXE icon resource check.
- Windows app-open smoke for typo-tolerant `calculator` / `notepad`.
- RAM smoke for bundled Electron EXE.
- Windows-MCP executable readiness.
- Frozen Kokoro and offline LLM path resolution from the installed app layout.

## Known Non-Blocking Warnings

- Vite reports large chunks after minification; build still passes.
- Electron dev mode reports the usual insecure CSP warning; it says the warning will not show once packaged.
- Electron renderer logs a `THREE.Clock` deprecation warning. It is not currently breaking E2E, but should be cleaned in a later performance pass.
- Local acceptance is `BLOCKED` overall on macOS because frozen Windows EXE probes require Windows.
