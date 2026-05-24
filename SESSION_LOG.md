## Session: 2026-05-24

### Completed
- Created six project-specific Codex skills in `/Users/m1/.codex/skills` to make future Shell AI work more consistent and project-aware:
  - `shell-ai-workflow`
  - `shell-ai-web-ui-qa`
  - `shell-ai-installer-release`
  - `shell-ai-voice-os`
  - `shell-ai-agent-tools`
  - `shell-ai-performance`
- Added focused reference maps for Shell architecture, Web UI QA, installer/release behavior, voice/OS automation, agent/tool routing, and performance.
- Added a reusable `project_snapshot.py` helper inside `shell-ai-workflow`.
- Validated skill frontmatter, naming, metadata presence, and TODO cleanup with a local structural check.
- Verified `project_snapshot.py` runs against the current Shell repo and reports root/build state.
- Updated the one-click installer and repair path for the current Shell Web UI.
- Added `shell_web_ui` npm dependency install plus production build into `installer/bootstrap.py`.
- Added a Web UI build readiness check so health reports fail clearly when `shell_web_ui/dist/index.html` is missing.
- Updated Windows/macOS/Linux launchers to default to the current Web UI with `SHELL_LEGACY_UI=0`.
- Aligned macOS docs/tests with the tracked `start_shellai.command` launcher name.
- Updated installer docs and README beginner install instructions for the React Shell Web UI build step.
- Deep-tested the live Shell Web UI through the Qt remote debugging port, including Dashboard, chart transcript, voice controls, Settings tabs, Telegram panel, Control Center, Phone, Notes, camera, and screen-share UI paths.
- Fixed chart/transcript memory recall so Shell remembers the immediately previous text or voice task when the user asks "tumhe yaad hai" / recall-style prompts.
- Kept chart text interaction text-only: chart/transcript commands now answer in chat without triggering voice playback unless the input source is voice or the user explicitly presses the speaker control.
- Added local backend handling for telemetry chart prompts such as CPU/RAM chart requests so they do not fall through to provider-unavailable replies.
- Fixed a PyQtGraph availability check regression so importing the legacy UI no longer eagerly imports `pyqtgraph` / `numpy`.
- Fixed Web UI Gallery integration: the Python bridge now scans `~/Pictures/Shell_Generated`, supports `save-image-to-gallery`, delete, reveal, and save-copy actions, and returns file URLs that the Gallery view can render.
- Fixed image-generation chat formatting so successful backend image paths are surfaced as Gallery-saved results, and failed provider attempts remain honest instead of pretending success.
- Added Hinglish/natural photo routing such as `neon shell city ki photo banao` to `shell_image_ai:generate_image_tool` with excellent/photorealistic defaults.
- Added chart-chat routing for `show all tools` and `tool health status`.
- Fixed common unit aliases so chart text such as `convert 2 meter to centimeter` routes as `m -> cm` and returns `200 cm`.
- Fixed Dashboard text/chart input robustness for RDP/automation/IME paths by reading the live input ref when React state is stale.
- Restored missing CSS enter animation utility classes (`animate-in`, `fade-in`, `zoom-in`, slide-in variants, animation duration/delay handling) so modal/widget UI animations actually run.
- Ran deep tool and agent probes: `468` tool catalog entries scanned with `0` probe errors, and `37/37` agents passed readiness/execution smoke checks.
- Ran focused chart/transcript UI probe and backend bridge regressions to verify calculator commands, chart prompts, clear button behavior, and previous-task recall.
- Added and ran a real UI chart/tools/Gallery/animation probe covering calculator, unit conversion, hash, base64, tools-list routing, Gallery save/render, and CSS animation runtime.
- Pushed Shell Web UI and OS-control integration to GitHub on `main`.
- Investigated the pushed commit checks, fixed GitHub Actions Web UI build setup plus CI Python health-check wiring for CI/security jobs, corrected GitHub author identity for future commits, and raised the CYBER_NEON subtle text contrast above the audit threshold.

### Changes Made
- Added `/Users/m1/.codex/skills/shell-ai-workflow/SKILL.md`, `references/project-map.md`, `scripts/project_snapshot.py`, and `agents/openai.yaml`.
- Added `/Users/m1/.codex/skills/shell-ai-web-ui-qa/SKILL.md`, `references/web-ui-map.md`, and `agents/openai.yaml`.
- Added `/Users/m1/.codex/skills/shell-ai-installer-release/SKILL.md`, `references/installer-contract.md`, and `agents/openai.yaml`.
- Added `/Users/m1/.codex/skills/shell-ai-voice-os/SKILL.md`, `references/voice-os-map.md`, and `agents/openai.yaml`.
- Added `/Users/m1/.codex/skills/shell-ai-agent-tools/SKILL.md`, `references/agent-tool-map.md`, and `agents/openai.yaml`.
- Added `/Users/m1/.codex/skills/shell-ai-performance/SKILL.md`, `references/performance-map.md`, and `agents/openai.yaml`.
- Updated `installer/bootstrap.py`.
- Updated `ONE_CLICK_INSTALL.bat`, `ONE_CLICK_INSTALL.command`, `Repair_ShellAI.bat`, `Start_ShellAI.bat`, `start_shellai.command`, `start_shellai.sh`, and `installer/install_mac.command`.
- Updated `installer/README.md`, `README.md`, and `tests/test_installer_bootstrap.py`.
- Updated `shell_ui/shell_cinematic_full.py`.
- Updated `shell_web_ui/host.py`.
- Updated `shell_web_ui/src/views/Dashboard.tsx`.
- Updated `shell_web_ui/src/views/Gallery.tsx`.
- Updated `shell_web_ui/src/shellBridge.ts`.
- Updated `shell_web_ui/src/assets/main.css`.
- Updated `shell_nl_router.py`.
- Updated `.github/workflows/ci.yml` and `.github/workflows/security.yml`.
- Updated `shell_ui/design_tokens.py`.
- Updated `tools/chart_transcript_ui_probe.mjs`.
- Added `tools/chart_tools_gallery_animation_probe.mjs`.
- Added `tests/test_shell_web_ui_bridge.py`.
- Updated `tests/test_nl_router.py`.
- Updated `SESSION_LOG.md`.

### Current State
- Project-specific skills are discoverable under `/Users/m1/.codex/skills`.
- Manual structural validation passed for all six new skills.
- Official `quick_validate.py` is blocked in the current Python environments because `PyYAML` / `yaml` is missing.
- Installer tests pass: `18 passed`.
- Python compile passes for `installer/bootstrap.py`, `launch.py`, and `shell_web_ui/host.py`.
- `shell_web_ui` production build passes and writes `shell_web_ui/dist/index.html`.
- Bootstrap health now confirms `[OK] Shell Web UI build: shell_web_ui/dist/index.html`.
- Local `.codex_ui_venv` still reports Python `3.9.6` as too old; the managed one-click `.shellai_venv` path requires Python `3.10+`.
- Live Shell Web UI is running with remote debugging on port `9235` and rendered successfully without console errors in the deep UI probe.
- Full UI probe passed `30/30` checks, including scrollable Settings sections, logo/titlebar cleanup, Telegram status, Control Center command execution, fake camera/screen streams, transcript prompt, chart route, and voice button clicks.
- Chart/transcript probe passed all checks: clear transcript, normal text Q&A, chart prompt, calculator command, previous-task recall, text-only voice counter, and clear-after-messages.
- Chart/tools/Gallery/animation probe passed all checks from the real UI:
  - `calculate 11*11` -> `Result: 121`
  - `convert 2 meter to centimeter` -> `2.0 m = 200 cm`
  - `hash shell with sha256` -> SHA-256 digest
  - `encode hello as base64` -> `aGVsbG8=`
  - `show all tools` routes through the backend tool gateway
  - Gallery bridge saved and rendered a generated image item
  - `animate-in fade-in zoom-in duration-300` resolves to the `shell-enter` animation at runtime
- Regression tests passed: `66` base backend/router/voice tests, `43` performance/runtime tests, and `40` focused bridge/chart/router/import tests.
- Latest commit health check found GitHub author metadata on the previous push was not linked to the `mdshoebkhanking` account; local git config now uses `mdshoebkhanking <255382462+mdshoebkhanking@users.noreply.github.com>`.
- GitHub Security secret-pattern job exposed that CI runners do not have `.shellai_venv`; workflows now export `SHELLAI_VENV_DIR` to the active setup-python environment after installing CI requirements.
- Full pytest isolated the remaining CI matrix failure to `ecosystem_master_audit` open-source scoring; passing repo audits now use a minimum public-quality component score so low/info local workspace noise cannot fail the final launch gate.
- Local verification after the CI fix: `npm run build` passed, `tools/production_release_check.py --strict` passed, `tests/test_phase6_ui_ux.py` passed, and focused bridge/router/image tests passed (`38 passed`).
- GitHub Actions fix is staged as a follow-up commit candidate; local worktree still has three unrelated unstaged deletions that were intentionally not pushed.
- Latest targeted regression passed: `45 passed, 1 warning`.
- Latest all-tools probe passed across `468` catalog entries: `62` safe tools executed, `40` agent readiness-only, `10` expected-not-ready, `312` safety-skipped, `44` environment-skipped, `0` errors.
- Latest agents probe passed: `37/37`.
- `npm run build` passes for `shell_web_ui`; Vite still reports only non-blocking `face-api.js` browser externalization and large chunk warnings.
- `installer/bootstrap.py health` currently reports `NEEDS_REPAIR` because `.codex_ui_venv` is Python `3.9.6`; Web UI build, PyQt6, WebEngine, telemetry, sounddevice, speech recognition, LiveKit, wake word, and VAD are OK.
- macOS audio health reports `AudioQueueStart failed (-66680)`, so audible Shell voice still depends on a working output device or RDP/Parsec audio forwarding path.

### Next Steps
1. Run `ONE_CLICK_INSTALL` on the target machine to create/repair `.shellai_venv` with Python 3.10+.
2. Start Shell through `Start_ShellAI.bat` on Windows or `start_shellai.command` on macOS.
3. Re-run `installer/bootstrap.py health` inside the managed `.shellai_venv` after install.
4. Add/configure the Gemini API key and verify real Gemini Live voice over the final RDP/Parsec audio output path.
5. Grant macOS Accessibility, Microphone, Camera, and Screen Recording permissions to the Python/Terminal runner for real OS input automation and real media capture.

### Open Issues
- Vite still emits non-blocking warnings for `face-api.js` browser-externalized `fs` and a large main chunk.
- macOS audio health still reports `AudioQueueStart failed (-66680)` until an output device/remote audio path is available.
- Several optional dependencies remain warnings until the repair/install path installs them or their feature flags are enabled.
- Real dangerous/destructive tools were intentionally not executed by the all-tools probe; they remain safety-gated by design.

## Session: 2026-05-23

### Completed
- Used four parallel agents for UI audit, code review, UI testing recommendations, and assistant UI/media research.
- Removed the redundant centered `Shell OS // MAC/SYSTEM` titlebar label and the custom macOS-style three-dot chrome from the Web UI.
- Fixed typed transcript/chart policy: text input now stays text-only, and voice output only auto-runs for voice-source backend replies or the explicit speaker button.
- Reworked dashboard chart mode so chart prompts keep the selected metric family instead of being overwritten by live core metric refresh.
- Made Dashboard transcript/chart input responsive on narrower screens instead of hiding it below large desktop widths.
- Fixed Settings layout scrolling by removing hardcoded absolute tab panels; General/API/Security now scroll inside the tab content while the Settings tab strip stays visible.
- Added the Shell logo to the Web UI header and verified it loads from the local renderer asset.
- Improved camera/screen-share behavior: vision can start independently of voice connection, uses `getDisplayMedia()` first, enables Qt WebEngine media/screen permissions, updates active state before video playback, and adds an explicit `STOP CAPTURE` control.
- Added Telegram Remote Control management inside Settings > API Keys: token field, allowed chat IDs, PC-control toggle, terminal safety toggle, status/start/stop controls, and test-message send.
- Fixed Control Center selected-tool layout so the Execute button no longer overlaps the result panel at desktop/RDP heights, and verified backend calculator execution from the UI.
- Fixed backend voice mute bridge and source metadata propagation from voice recognition into chat events.
- Cleaned two voice runtime bugs found by review: duplicate `ai-force-speak` listeners and mismatched `index_Folder` / `index_directory` tool names.

### Changes Made
- Updated `shell_web_ui/src/views/Dashboard.tsx`.
- Updated `shell_web_ui/src/IndexRoot.tsx`.
- Updated `shell_web_ui/src/UI/ShellAI.tsx`.
- Updated `shell_web_ui/src/components/Titlebar.tsx`.
- Updated `shell_web_ui/src/views/Settings.tsx`.
- Updated `shell_web_ui/src/views/ControlCenter.tsx`.
- Added `shell_web_ui/src/public/shell-logo.png`.
- Updated `shell_web_ui/host.py`.
- Updated `shell_web_ui/src/shellBridge.ts`.
- Updated `shell_web_ui/src/services/shell-voice-ai.ts`.
- Updated `tools/real_web_ui_cdp_probe.mjs` with scroll, text-only speech, titlebar, Telegram status, Control Center execution, Phone error-state, vision modal, and fake camera/screen stream checks.
- Updated `README.md`.
- Updated `SESSION_LOG.md`.

### Current State
- `npm run build` passes for `shell_web_ui`.
- Python compile passes for `shell_web_ui/host.py` and `launch.py`.
- Real visible Shell Web UI probe passed with `30/30` checks:
  - all main tabs opened,
  - Settings System/General/API/Security opened,
  - General scroll container verified,
  - API Keys scroll container verified,
  - Telegram status panel executed through the backend tool gateway,
  - Control Center selected `shell_calculator:calculate_tool` and returned `Result: 4`,
  - Phone manual connection error state rendered cleanly,
  - Notes create/save worked,
  - chart prompt updated chart/transcript without voice calls,
  - chart text command route returned calculator output without voice calls,
  - vision modal opened,
  - fake camera and fake screen streams activated,
  - transcript prompt worked,
  - voice test/start/stop buttons were clickable,
  - console error count was `0`.
- Latest probe report: `.shell_runtime/real_web_ui_cdp_probe_latest/report.json`.

### Next Steps
1. User should visually test the currently opened Shell window over RDP/Parsec.
2. For real screen sharing on macOS, grant the Python/Terminal runner Screen Recording permission if macOS prompts.
3. For real Gemini voice, add the Gemini API key in Settings > API Keys > Gemini Pro Core.
4. For Telegram remote control, add the BotFather token and allowed chat ID in Settings > API Keys > Telegram Remote Control, then enable only the safety gates you need.

### Open Issues
- macOS screen share may still require OS-level Privacy & Security permission and sometimes an app restart after permission is granted.
- Vite still emits the non-blocking `face-api.js` browser `fs` externalization warning and large chunk warning.
- Existing unrelated dirty worktree changes remain untouched.

## Session: 2026-05-20

### Completed
- Updated the public repository documentation to match the current ShellAI Core / AI OS Fabric state on `main`.
- Added a dedicated ShellAI Core and AI OS Fabric guide covering CLI usage, runtime layout, desktop feature flag, model routing, safety policy, and current limitations.
- Updated README, architecture docs, developer docs, roadmap, and `.env.example` with current ShellAI CLI, provider, memory, skills, monitor, cron, daemon, and desktop bridge details.

### Changes Made
- Updated `README.md`.
- Updated `ARCHITECTURE.md`.
- Added `docs/SHELLAI_FABRIC.md`.
- Updated `docs/README.md`.
- Updated `docs/ARCHITECTURE_GUIDE.md`.
- Updated `docs/DEVELOPER_GUIDE.md`.
- Updated `docs/ROADMAP.md`.
- Updated `.env.example`.
- Updated `SESSION_LOG.md`.

### Current State
- The repo now documents both the classic desktop Shell path and the opt-in ShellAI Core backend path.
- ShellAI Core remains feature-flagged through `SHELLAI_BACKEND_MODE=shellai_core`; classic behavior remains the default.

### Next Steps
1. Run documentation diff checks and regression tests.
2. Commit the documentation refresh.
3. Push the updated `main` branch to GitHub.

### Open Issues
- The local Python runtime still emits the known LibreSSL/urllib3 warning during tests.
- ASK-level ShellAI Core commands still need a real desktop approval UI.

## Session: 2026-05-20

### Completed
- Prepared the ShellAI Phase 2 + desktop bridge changes for GitHub publishing.
- Verified the correct nested Git repository and remote: `origin` -> `https://github.com/mdshoebkhanking/shell-ai-os-controller.git`.
- Reviewed the worktree before staging to avoid publishing unrelated temporary files.
- Ran a targeted secret-pattern scan across the new `shellai` package, desktop bridge, tests, and touched UI files.

### Changes Made
- Updated `SESSION_LOG.md` with this GitHub publish-prep checkpoint.

### Current State
- Pending GitHub publish from feature branch to avoid pushing directly to `main`.
- Latest full regression result remains: `.codex_ui_venv/bin/python -m pytest -q` returned `466 passed, 1 warning`.
- Visible UI validation remains complete for E2E pages, all-tools audit, agents route, ShellAI Core mode, classic mode, and safety blocking.

### Next Steps
1. Create a publish branch.
2. Stage intended ShellAI Phase 2, desktop bridge, UI, test, and session-log files.
3. Run final diff checks.
4. Commit and push to GitHub.

### Open Issues
- macOS Accessibility permission is still not granted in this environment, so global input monitoring/mouse automation remains OS-gated.
- Some tool catalog entries remain readiness-only by design due missing dependency, missing API key, Windows-only behavior, experimental status, or safety policy.

## Session: 2026-05-20

### Completed
- Performed broad visible PyQt UI validation at the user's request.
- Ran visible end-to-end UI probe across Chat, Voice, System, Agents, Tools, and Settings pages.
- Ran full visible tool catalog audit: 442 catalog entries inspected, 53 safe READY tools executed, unsafe/stateful tools skipped by safety, 0 errors.
- Ran visible agents chat route probe: 37/37 agent commands passed through the UI.
- Ran mixed ShellAI Core mode UI probe: `!pwd` routed through ShellAI Core, `/tool shell_calculator...` stayed on the legacy backend-command path, and `!rm -rf /` was blocked.
- Fixed a discovered ShellAI Core opt-in regression so slash commands (`/tool`, `/agent`, `/mcp`) continue using the existing backend-command UI path even when `SHELLAI_BACKEND_MODE=shellai_core`.
- Improved blocked-command desktop copy from generic “ShellAI Core error” to “Blocked for safety”.
- Captured visible UI screenshots under `/private/tmp`.

### Changes Made
- Updated `shell_ui/shell_cinematic_full.py`.
- Updated `core/shellai_bridge.py`.
- Updated `SESSION_LOG.md`.

### Current State
- Visible E2E UI report passed: `/private/tmp/shellai-full-ui-e2e/report.json`.
- Visible tool audit report passed: `/private/tmp/shellai-full-tools-ui/report.json`.
- Visible agents probe report passed: `/private/tmp/shellai-agents-ui/report.json`.
- Mixed ShellAI Core/legacy command screenshot captured: `/private/tmp/shellai-core-mixed-ui/mixed_shellai_core.png`.
- Full regression suite passed after the UI routing fix: `.codex_ui_venv/bin/python -m pytest -q` returned `466 passed, 1 warning`.

### Next Steps
1. Add a dedicated checked-in `tools/shellai_core_ui_probe.py` so this ShellAI Core bridge UI test is reusable.
2. Add a real ASK approval UI flow instead of ending at `needs_confirmation`.
3. Add a manual checklist for tests that require user-granted macOS Accessibility permissions.

### Open Issues
- macOS Accessibility permission is still not granted in this environment, so global input monitoring/mouse automation is unavailable.
- Some catalog entries remain readiness-only by design: missing dependency, missing API key, Windows-only, experimental, or blocked-by-safety.

## Session: 2026-05-20

### Completed
- Performed real UI-style validation of the ShellAI Core desktop bridge.
- Tested the PyQt chat pipeline with `SHELLAI_BACKEND_MODE=shellai_core` using actual widgets: `!pwd`, `!rm missing-ui-probe.txt`, and `!rm -rf /`.
- Verified `ShellAICoreWorker` completes without leaving `_waiting_reply` stuck or the worker running.
- Verified ShellAI Core system log entries appear for `ok`, `needs_confirmation`, and `blocked` results.
- Launched a visible PyQt window, sent `!pwd`, captured `/private/tmp/shellai-ui-visible/shellai_core_visible.png`, and verified the chat bubble showed `shell=ok`.
- Tested `SHELLAI_BACKEND_MODE=classic` via the PyQt chat flow and verified the local classic reply path still works without ShellAI Core log entries.

### Changes Made
- Updated `SESSION_LOG.md` with UI validation results.

### Current State
- Offscreen widget-level ShellAI Core UI probe passed with `ok: true`.
- Visible ShellAI Core UI launch/screenshot probe passed with `ok: true`.
- Classic-mode UI smoke passed with `ok: true`.
- Observed environment warnings are expected in this sandbox/macOS setup: Accessibility trust missing for global input monitoring, chat history home path not writable, and Shell-v2 bridge permission warning. These did not break chat UI or ShellAI Core routing.

### Next Steps
1. Add an approval UI for ASK-level commands so `needs_confirmation` can become an explicit user decision instead of a final status.
2. Improve blocked-command desktop copy so BLOCK reads as a safety block rather than a generic “ShellAI Core error”.
3. Add a reusable checked-in UI probe for ShellAI Core bridge regression testing.

### Open Issues
- Visible UI testing was automated through PyQt widgets and window screenshots, not manual mouse/keyboard interaction.
- macOS Accessibility permission is still required for real global input/mouse automation.

## Session: 2026-05-20

### Completed
- Implemented Phase 2.1 through Phase 2.8 for the `shellai` AI OS Fabric path.
- Added `MemoryAgent` as the high-level wrapper over `MemoryStore` and `SkillManager`.
- Added `AgentRuntime` for in-process fabric wiring across Coordinator, Shell, Safety, Memory, UI, and Optimizer agents.
- Added `UIAgent` response shaping with CLI and desktop summary fields while preserving the existing `summary` field.
- Added central policy loading/evaluation and JSONL audit logging for shell safety decisions.
- Updated `ShellTool` and `SafetyAgent` to route shell risk decisions through policy + audit.
- Added persisted trace snapshots and `shellai monitor`.
- Added read-only `OptimizerAgent` suggestions and `shellai optimize`.
- Added manual cron jobs and `shellai cron list/run`.
- Added opt-in file-backed daemon queue and `shellai daemon start/stop/status/enqueue/process`.
- Added Phase-2 tests covering memory context, runtime boundaries, UI summaries, policy/audit behavior, monitor redaction, optimizer suggestions, cron jobs, daemon queue behavior, and CLI surfaces.

### Changes Made
- Created `shellai/agents_memory.py`.
- Created `shellai/agents_ui.py`.
- Created `shellai/agents_optimizer.py`.
- Created `shellai/fabric/__init__.py`.
- Created `shellai/fabric/runtime.py`.
- Created `shellai/policy.py`.
- Created `shellai/monitor.py`.
- Created `shellai/cron/__init__.py`.
- Created `shellai/cron/runtime.py`.
- Created `shellai/daemon.py`.
- Updated `shellai/agent_loop.py`.
- Updated `shellai/agents.py`.
- Updated `shellai/tools/shell_tool.py`.
- Updated `shellai/cli.py`.
- Updated `tests/test_shellai_stage1.py` for the richer policy/audit trace.
- Created `tests/test_shellai_phase2_memory_runtime_ui.py`.
- Created `tests/test_shellai_phase2_policy_monitor_optimizer.py`.
- Created `tests/test_shellai_phase2_cron_daemon.py`.
- Updated `SESSION_LOG.md`.

### Current State
- ShellAI Stage 1-8 + Phase 2 focused validation passed: `.codex_ui_venv/bin/python -m pytest tests/test_shellai_stage1.py tests/test_shellai_stage2_config.py tests/test_shellai_stage3_models.py tests/test_shellai_stage4_memory.py tests/test_shellai_stage5_skills.py tests/test_shellai_stage6_tools.py tests/test_shellai_stage7_agent_loop.py tests/test_shellai_stage8_api_bridge.py tests/test_shellai_phase2_memory_runtime_ui.py tests/test_shellai_phase2_policy_monitor_optimizer.py tests/test_shellai_phase2_cron_daemon.py -q` returned `45 passed`.
- Full repository validation passed: `.codex_ui_venv/bin/python -m pytest -q` returned `466 passed, 1 warning`.
- Syntax validation passed with `PYTHONPYCACHEPREFIX=/private/tmp/shell_pycache .codex_ui_venv/bin/python -m py_compile ...` for the updated Phase-2 modules and desktop bridge files.
- CLI smoke checks passed for `doctor`, `run "!pwd" --json`, `skills list`, `monitor`, `optimize`, `cron list`, `cron run skill_usage_report --dry-run`, and opt-in daemon start/status/stop.
- Safety smoke checks confirmed ASK commands return `needs_confirmation` without execution and BLOCK commands return `blocked`.
- Desktop bridge smoke checks confirmed `SHELLAI_BACKEND_MODE=classic` returns the classic no-op bridge path and `SHELLAI_BACKEND_MODE=shellai_core` routes through ShellAI Core.

### Next Steps
1. Add a real desktop approval UI for ASK-level commands before enabling richer desktop automation.
2. Add streaming/progress callbacks from AgentRuntime to the PyQt worker.
3. Add richer context sources: active window, selected file/project, VS Code workspace, and ADB device state.
4. Convert persisted traces/audit logs into a lightweight desktop diagnostics page once UX is ready.

### Open Issues
- Natural-language planning still requires a configured provider; explicit `!command` requests remain deterministic and provider-free.
- Daemon mode is file-backed and manual; it does not run as a true background service yet.
- Cron jobs are manual and conservative; memory maintenance currently marks/checks old rows rather than performing aggressive compression.
- UIAgent formatting is deterministic by default; model-shaped summaries require `SHELLAI_UI_MODEL_SUMMARY=1`.

## Session: 2026-05-20

### Completed
- Implemented Stage 8 desktop bridge for the new `shellai` core.
- Added `shellai.api.run_shellai_task(...)` as a stable Python API for desktop, daemon, and future app callers.
- Added structured API error responses for config/runtime/agent-loop failures instead of raw tracebacks.
- Added `core.shellai_bridge` with `SHELLAI_BACKEND_MODE` feature flag support; default remains `classic`, opt-in is `shellai_core`.
- Added a minimal `agent.py` bridge helper for callers that want to route a single request through the new core.
- Added a PyQt worker path in `shell_ui/shell_cinematic_full.py` that runs ShellAI Core only when the feature flag is enabled and logs returned steps to the system log.
- Added Stage 8 API and desktop bridge smoke tests.

### Changes Made
- Created `shellai/api.py`.
- Created `core/shellai_bridge.py`.
- Updated `agent.py`.
- Updated `shell_ui/shell_cinematic_full.py`.
- Created `tests/test_shellai_stage8_api_bridge.py`.
- Updated `SESSION_LOG.md`.

### Current State
- Classic desktop behavior remains the default because `SHELLAI_BACKEND_MODE` defaults to `classic`.
- Opt-in path: set `SHELLAI_BACKEND_MODE=shellai_core` and desktop chat requests route through `shellai.api.run_shellai_task(...)`.
- Focused validation passed: `.codex_ui_venv/bin/python -m pytest tests/test_shellai_stage8_api_bridge.py -q` returned `4 passed`.
- Full ShellAI validation passed: `.codex_ui_venv/bin/python -m pytest tests/test_shellai_stage1.py tests/test_shellai_stage2_config.py tests/test_shellai_stage3_models.py tests/test_shellai_stage4_memory.py tests/test_shellai_stage5_skills.py tests/test_shellai_stage6_tools.py tests/test_shellai_stage7_agent_loop.py tests/test_shellai_stage8_api_bridge.py -q` returned `34 passed`.
- Syntax validation passed with `PYTHONPYCACHEPREFIX=/private/tmp/shell_pycache .codex_ui_venv/bin/python -m py_compile shellai/api.py core/shellai_bridge.py agent.py shell_ui/shell_cinematic_full.py`.

### Next Steps
1. Add interactive approval UI for `ASK` shell commands before enabling broader desktop automation.
2. Add streaming/progress callbacks from `run_shellai_task(...)` to the PyQt worker.
3. Pass richer desktop context such as active window, selected files, and project metadata when those sources are stable.

### Open Issues
- Natural-language requests still require a configured planning provider; explicit `!command` requests can use the deterministic path without an LLM key.
- ShellAI Core is non-streaming in Stage 8; the UI receives one final structured result.
- `auto_approve_ask` is hard-coded to `False` for the desktop bridge until an approvals UI exists.

## Session: 2026-05-20

### Completed
- Implemented Stage 7 core `shellai` agent loop.
- Added `shellai/agent_loop.py` with context assembly, JSON plan validation, model planning, safety-aware tool execution, summarization fallback, memory save, and auto-skill draft creation.
- Added `MessageKind.USER_REQUEST` and `create_user_request(...)` for future chat/UI/daemon callers.
- Wired `shellai run` to the new agent loop while preserving the existing CLI command shape.
- Added deterministic explicit-shell planning for prefixed requests like `!pwd` so safe local commands can run without an API key.
- Added graceful fallback when the default `~/.shellai` runtime path is not writable in the sandbox.
- Added focused tests covering safe shell execution, ASK-level command blocking, FileTool usage, auto-skill draft creation, and invalid planning JSON.

### Changes Made
- Created `shellai/agent_loop.py`.
- Updated `shellai/protocol.py`.
- Updated `shellai/cli.py`.
- Updated `tests/test_shellai_stage1.py` for the Stage 7 execution response shape.
- Created `tests/test_shellai_stage7_agent_loop.py`.
- Updated `SESSION_LOG.md`.

### Current State
- Focused validation passed: `.codex_ui_venv/bin/python -m pytest tests/test_shellai_stage1.py tests/test_shellai_stage2_config.py tests/test_shellai_stage3_models.py tests/test_shellai_stage4_memory.py tests/test_shellai_stage5_skills.py tests/test_shellai_stage6_tools.py tests/test_shellai_stage7_agent_loop.py -q` returned `30 passed`.
- `SHELLAI_CONFIG=/private/tmp/shellai-stage7-smoke/config.json .codex_ui_venv/bin/python -m shellai run '!pwd' --json` executes safely and writes conversation memory.
- Default `.codex_ui_venv/bin/python -m shellai run '!pwd' --json` executes safely and returns a warning when `/Users/m1/.shellai` is not writable instead of failing.

### Next Steps
1. Stage 8: extend CLI surfaces around the new loop without adding daemon behavior yet.
2. Add interactive approval wiring for `ASK` steps when implementing richer chat/TUI flows.
3. Connect desktop Shell/PyQt callers to `run_agent_task(...)` once the CLI path is stable.

### Open Issues
- Natural-language planning still requires a configured provider; missing keys produce structured planning errors.
- Summarization falls back to deterministic summaries when no provider key is available.
- Logs currently appear on stderr during CLI runs; JSON payload remains the structured response.

## Session: 2026-05-20

### Completed
- Implemented Stage 5 skills framework with JSON v1 schema, validation, discovery, creation, deletion, auto-draft creation, and SkillMemory registration.
- Wired `shellai skills list` and `shellai skills show <id>` to the file-backed skill manager.
- Implemented Stage 6 tool system with typed `ToolRequest` / `ToolResult`, `ShellTool`, `FileTool`, `OSTool`, and `ToolRegistry`.
- Connected `ShellTool` to the existing `SAFE` / `ASK` / `BLOCK` risk policy with dry-run and approval behavior.
- Added trace hooks for skill and tool operations.
- Added tests for skill validation, skill discovery/fetching, auto-skill drafts, SkillMemory usage tracking, shell risk behavior, file operations, OS helpers, and registry lookup.
- Made `shellai skills list` degrade cleanly when the default home runtime path is not writable under the current sandbox.

### Changes Made
- Created `shellai/skills/__init__.py`.
- Created `shellai/skills/schema.py`.
- Created `shellai/skills/manager.py`.
- Created `shellai/tools/__init__.py`.
- Created `shellai/tools/base.py`.
- Created `shellai/tools/shell_tool.py`.
- Created `shellai/tools/file_tool.py`.
- Created `shellai/tools/os_tool.py`.
- Created `shellai/tools/registry.py`.
- Updated `shellai/cli.py`.
- Created `tests/test_shellai_stage5_skills.py`.
- Created `tests/test_shellai_stage6_tools.py`.
- Updated `SESSION_LOG.md`.

### Current State
- Focused validation passed: `.codex_ui_venv/bin/python -m pytest tests/test_shellai_stage1.py tests/test_shellai_stage2_config.py tests/test_shellai_stage3_models.py tests/test_shellai_stage4_memory.py tests/test_shellai_stage5_skills.py tests/test_shellai_stage6_tools.py -q` returned `25 passed`.
- `SHELLAI_CONFIG=/private/tmp/shellai-smoke/config.json .codex_ui_venv/bin/python -m shellai skills list` returns an empty skill list successfully.
- Default `shellai skills list` cannot write `/Users/m1/.shellai` in this sandbox, but now returns a structured JSON error instead of a traceback.

### Next Steps
1. Stage 7: implement the agent loop that composes memory retrieval, model routing, skills, safety, and tools.
2. Connect `ShellAgent` to `ToolRegistry` through `SafetyAgent` approval decisions.
3. Add examples under the runtime/manual skills path or repo examples when packaging docs are updated.

### Open Issues
- Full CLI skill storage under `~/.shellai` needs a writable user home or `SHELLAI_CONFIG` override in this sandbox.
- Auto-skill creation is deterministic but not yet connected to successful agent task completion; that belongs in Stage 7+.
- `OSTool.open_path` remains a platform-specific stub by design.

## Session: 2026-05-20

### Completed
- Implemented Stage 3 model provider abstraction for the new `shellai` package.
- Added a `ModelProvider` interface, `ModelRouter`, OpenAI-compatible HTTP provider, and Ollama provider.
- Added model diagnostics for missing API keys and surfaced them through `shellai doctor`.
- Implemented Stage 4 SQLite memory system with conversation, user profile, and skill memory tables.
- Added a `MemoryStore` facade with save/search/profile/skill APIs and request-trace hooks.
- Added focused tests for model routing, missing-key diagnostics, fake provider injection, SQLite initialization, memory save/search, user profile upsert, and skill usage tracking.
- Fixed a Python 3.9 compatibility issue in the model type alias after validation exposed it.

### Changes Made
- Created `shellai/models/__init__.py`.
- Created `shellai/models/base.py`.
- Created `shellai/models/router.py`.
- Created `shellai/models/openai_compatible.py`.
- Created `shellai/models/ollama.py`.
- Created `shellai/memory/__init__.py`.
- Created `shellai/memory/store.py`.
- Updated `shellai/cli.py`.
- Created `tests/test_shellai_stage3_models.py`.
- Created `tests/test_shellai_stage4_memory.py`.
- Updated `SESSION_LOG.md`.

### Current State
- `shellai doctor` reports model-router diagnostics for OpenAI, OpenRouter, and Ollama.
- Missing API keys are reported as diagnostics instead of hard crashes.
- Memory DB schema initializes safely with `CREATE TABLE IF NOT EXISTS`.
- Focused validation passed: `.codex_ui_venv/bin/python -m pytest tests/test_shellai_stage1.py tests/test_shellai_stage2_config.py tests/test_shellai_stage3_models.py tests/test_shellai_stage4_memory.py -q` returned `15 passed`.

### Next Steps
1. Stage 5: implement the skills framework on top of `SkillMemory`.
2. Stage 6: connect tool interfaces to the risk policy and trace system.
3. Later Phase 2: introduce `MemoryAgent` as a thin caller of `MemoryStore`, then add summarization/embedding.

### Open Issues
- No real provider calls were made during validation; tests use diagnostics and a fake provider.
- Embeddings are intentionally left as an interface hook for future memory search.
- Command execution remains disabled in the new `shellai` path by design.

## Session: 2026-05-20

### Completed
- Reviewed the Stage 1 `shellai` package and preserved its public behavior.
- Added a lightweight future-aware agent protocol for later AI OS Fabric work.
- Upgraded Stage 2 config with typed runtime paths, provider backend settings, env fallback, and per-role model lookup.
- Added future-agent model role mapping for `CoordinatorAgent`, `ShellAgent`, `SafetyAgent`, `MemoryAgent`, `OptimizerAgent`, and `UIAgent`.
- Expanded default tool priorities for Git, Python, Node, browser, Android/ADB, and VS Code while keeping Linux/Windows first.
- Updated CLI doctor output to include paths, provider diagnostics, agent model roles, and active provider readiness.
- Added focused tests for config env fallback, config persistence, future agent role mapping, and trace-ready agent messages.

### Changes Made
- Created `shellai/protocol.py`.
- Updated `shellai/agents.py`.
- Updated `shellai/config.py`.
- Updated `shellai/cli.py`.
- Created `tests/test_shellai_stage2_config.py`.
- Updated `SESSION_LOG.md`.

### Current State
- Stage 1 CLI behavior remains compatible.
- `shellai doctor` now reports active provider diagnostics, config/data/log/skill paths, model roles, and future agent model mappings.
- Focused validation passed: `.codex_ui_venv/bin/python -m pytest tests/test_shellai_stage1.py tests/test_shellai_stage2_config.py -q` returned `8 passed`.
- CLI smoke checks passed for `shellai doctor` and `shellai run '!git status' --json`.

### Next Steps
1. Stage 3: add model provider abstraction using the Stage 2 provider backend config.
2. Keep provider implementations thin: OpenAI-compatible first, then Ollama.
3. Keep future Phase-2 agents dormant until memory, skills, tools, and daemon stages exist.

### Open Issues
- The shell environment still lacks a `python` binary; validation used `.codex_ui_venv/bin/python`.
- No command execution or full multi-agent routing was added in Stage 2 by design.

## Session: 2026-05-20

### Completed
- Refined the 10-stage ShellAI next-generation controller plan with in-process `CoordinatorAgent`, `ShellAgent`, and `SafetyAgent` roles.
- Added Stage 1 architecture foundations for a new additive `shellai` package.
- Added central logging and a process-local in-memory request trace store.
- Added a configurable shell command risk policy with `SAFE`, `ASK`, and `BLOCK` levels.
- Added default user profile context for an India-based power-user developer using mixed Hindi/English, with Marathi/Urdu support.
- Added focused Stage 1 tests and smoke-checked the CLI.

### Changes Made
- Created `shellai/__init__.py`.
- Created `shellai/__main__.py`.
- Created `shellai/observability.py`.
- Created `shellai/config.py`.
- Created `shellai/safety.py`.
- Created `shellai/agents.py`.
- Created `shellai/cli.py`.
- Created `tests/test_shellai_stage1.py`.

### Current State
- `shellai doctor` works and reports provider/model defaults, tool switches, risk policy default, and the India/Hinglish dev profile.
- `shellai run '!git status' --json` produces a `SAFE` risk decision and a four-step trace: coordinator receive, shell proposal, safety classification, coordinator completion.
- Focused validation passed: `.codex_ui_venv/bin/python -m pytest tests/test_shellai_stage1.py -q` returned `4 passed`.

### Next Steps
1. Stage 2: persist config with setup wizard behavior and richer tool/model defaults for Linux + Windows first.
2. Stage 3: add model provider interfaces for OpenAI-compatible endpoints and Ollama.
3. Stage 4: add SQLite memory layers for conversation, user profile, and skills.

### Open Issues
- The shell environment does not expose a `python` binary; validation used `.codex_ui_venv/bin/python`.
- Stage 1 does not execute commands yet. It only classifies and traces requests.

## Session: 2026-05-17

### Completed
- Built a 20-second Instagram-ready 9:16 Remotion reel for Shell AI OS Controller.
- Added an isolated Remotion project under `videos/instagram-reel/`.
- Rendered the final MP4 at 1080x1920, 30 fps, 600 frames.
- Verified a still frame and a contact sheet for layout/readability.

### Changes Made
- Created `videos/instagram-reel/package.json`.
- Created `videos/instagram-reel/tsconfig.json`.
- Created `videos/instagram-reel/remotion.config.ts`.
- Created `videos/instagram-reel/src/index.ts`.
- Created `videos/instagram-reel/src/Root.tsx`.
- Created `videos/instagram-reel/src/ShellInstagramReel.tsx`.
- Copied reel assets into `videos/instagram-reel/public/`.
- Generated `videos/instagram-reel/package-lock.json`.
- Generated `videos/instagram-reel/out/frame-300.png`.
- Generated `videos/instagram-reel/out/contact-sheet.jpg`.
- Rendered `videos/shell-ai-os-controller-instagram-reel.mp4`.

### Current State
- Final video exists at `videos/shell-ai-os-controller-instagram-reel.mp4`.
- Video metadata verified with ffprobe: H.264, 1080x1920, 30 fps, 20.000 seconds, 600 frames.
- TypeScript check passed with `npx tsc --noEmit`.
- Remotion still render passed at frame 300.

### Next Steps
1. Preview the MP4 locally before posting.
2. Add music or voiceover in Instagram/Reels editor if desired.
3. Re-render with edited copy if a shorter or more Hindi/Hinglish-heavy version is needed.

### Open Issues
- No voiceover was added because no voice provider or script approval was requested.

## Session: 2026-05-17

### Completed
- Rebuilt the Instagram reel as a 60-second 9:16 video.
- Added the provided ElevenLabs voiceover MP3 to the Remotion public audio assets.
- Generated local OS-style sound effects: ambient bed, boot chime, data whoosh, scan, UI click, UI ping, and confirmation pulse.
- Rendered the final 60-second MP4 with layered voiceover and SFX.
- Verified TypeScript, a still frame, full render metadata, and a 12-frame contact sheet.

### Changes Made
- Updated `videos/instagram-reel/src/Root.tsx` from 20 seconds to 60 seconds.
- Updated `videos/instagram-reel/package.json` render/still scripts and pinned `@remotion/media`.
- Rebuilt `videos/instagram-reel/src/ShellInstagramReel.tsx` with a new proof-led OS-controller storyboard.
- Added audio assets under `videos/instagram-reel/public/audio/`.
- Generated `videos/instagram-reel/out/frame-900.png`.
- Generated `videos/instagram-reel/out/contact-sheet-60s.jpg`.
- Rendered `videos/shell-ai-os-controller-instagram-reel-60s.mp4`.

### Current State
- Final 60-second video exists at `videos/shell-ai-os-controller-instagram-reel-60s.mp4`.
- Video metadata verified with ffprobe: H.264, 1080x1920, 30 fps, 60.000 seconds, 1800 frames.
- Audio metadata verified with ffprobe: AAC stereo, 48 kHz, voiceover plus SFX mix present.
- TypeScript check passed with `npx tsc --noEmit`.

### Next Steps
1. Preview the MP4 with sound before posting.
2. Replace the ElevenLabs MP3 if an exact Hinglish script-synced voiceover is desired.
3. Keep the 20-second version only if a shorter teaser is still useful.

### Open Issues
- Voiceover timing uses the provided 57.73-second MP3 with a final visual outro tail; no new TTS script was generated in this session.

## Session: 2026-05-17

### Completed
- Reworked the 60-second Instagram reel around the actual provided voiceover beats.
- Changed the concept from a generic promo into a realistic Shell workflow demo: prompt, mouse control, typing, browser preview, code generation, terminal checks, plugin tools, safety approval, and final website result.
- Kept action shots short, with each visual segment around 3 seconds.
- Rendered and verified the final MP4 as a vertical 9:16 reel.

### Changes Made
- Updated `videos/instagram-reel/src/ShellInstagramReel.tsx` with a voice-synced 20-shot real-workflow storyboard.
- Generated transcript files in `videos/instagram-reel/out/voiceover-transcript.*`.
- Generated validation stills and contact sheets under `videos/instagram-reel/out/`.
- Rendered `videos/shell-ai-real-workflow-reel-60s.mp4`.

### Current State
- Final voice-synced real-workflow video exists at `videos/shell-ai-real-workflow-reel-60s.mp4`.
- Video metadata verified with ffprobe: H.264, 1080x1920, 30 fps, 60.000 seconds, 1800 frames.
- Audio metadata verified with ffprobe: AAC stereo, 48 kHz, 60.053333 seconds.
- TypeScript check passed with `npx tsc --noEmit`.
- Contact sheets confirm all 20 shots render and match the intended workflow rhythm.

### Next Steps
1. Preview the final MP4 with sound before posting.
2. Use `videos/shell-ai-real-workflow-reel-60s.mp4` as the main Instagram reel version.

### Open Issues
- No open issues from the final render.

## Session: 2026-05-19

### Completed
- Ran a full visible Shell UI QA cycle covering chat, premium voice, backend tools, core/extra agents, app open/close control, page navigation, settings, and safe catalog execution.
- Researched current UI/voice QA patterns for desktop apps, realtime voice assistants, and smoke probes before implementing fixes.
- Found and fixed a backend-tool provider transport cleanup leak where `execute_tool_sync()` closed its temporary event loop before closing `aiohttp` provider sessions created by agent/model calls.
- Found and fixed agent UX issues where simple TestingAgent/advisory smoke prompts could expose internal missing-tool errors or over-answer concise requests.
- Added local UI-smoke fast paths for core, master, and extra agents so QA/readiness probes stay fast, concise, and quota-free.
- Re-ran visible probes and release/test gates after the fixes.

### Changes Made
- Updated `shell_tool_gateway.py` to close loop-local reusable provider transports before shutting down temporary backend-tool event loops.
- Updated `shell_agents.py` with missing-tool reasoning fallback, stricter planning instructions against invented tools, honest partial/failure status detection, concise TestingAgent short-idea handling, and local UI smoke replies.
- Updated `shell_extra_agents.py` with local UI smoke replies for extra-agent readiness prompts.
- Added regression coverage in `tests/test_provider_transport_reuse.py` and `tests/test_agent_safety.py`.

### Current State
- Visible chat/tools/agents probe passed: 5 apps opened, 5 apps closed, 8 backend tool commands passed, 2 agent commands passed, zero timeouts/failures.
- The original `aiohttp` unclosed client-session/connector warning no longer appears after the chat/tools/agents probe.
- Visible premium voice validation passed: `backend=gemini_live_pcm`, `voice=Aoede`, `model=gemini-3.1-flash-live-preview`, `queue_to_first_audible_ms=842.976`, `queue_to_playback_ms=843.389`, fallback blocked.
- Visible all-agents probe passed: 37/37 agents, with smoke prompts now local and usually around 220-240 ms instead of provider-dependent multi-second replies.
- Visible all-tools catalog sweep passed: 436 entries checked, 53 safe workers executed, 10 expected not-ready states, 291 safety-skipped, 38 agent readiness-only, zero tool/worker/schema/timeouts.
- Visible full-page e2e probe passed across chat, voice, system, tools, settings, backend command output, Windows-only MCP fallback, and screenshots.
- Full test suite passed: `394 passed, 1 warning`.
- Strict production release check passed with no blockers; warning remains that local `.env` must not be included in public release packages.

### Next Steps
1. Upgrade the local Python runtime away from Python 3.9/LibreSSL to remove Google auth EOL and urllib3 OpenSSL warnings.
2. Continue reducing first-audible premium voice latency below the current ~0.84 s visible UI measurement through persistent Gemini Live session reuse.
3. Add a recorded interruption/noisy-room voice fixture suite so voice validation covers more real-world acoustic edge cases automatically.
4. Broaden agent fast paths only where they are explicit QA/readiness checks; keep real agent work on the full reasoning pipeline.

### Open Issues
- macOS Accessibility permission is not granted for this process, so input event monitoring remains unavailable until the app is added to Accessibility clients.
- Python 3.9 is past EOL and the bundled SSL module uses LibreSSL; tests pass, but dependency warnings remain.
- Some catalog entries are intentionally readiness-only, Windows-only, API-key-gated, guarded, or safety-skipped; they were not executed by design in the safe all-tools sweep.

## Session: 2026-05-19

### Completed
- Researched current realtime voice assistant patterns across OpenAI Realtime, Gemini Live, LiveKit, streaming TTS projects, and recent streaming TTS papers.
- Benchmarked Shell's current low-latency paths before and after a focused realtime UX pass.
- Reduced voice listener end-of-turn delay from 2.0 seconds to a configurable 750 ms default.
- Added faster 50 ms mic chunks and shorter minimum speech duration for more immediate voice turn handling.
- Added interruption/barge-in handling that stops active TTS when the listener detects new user speech.
- Added earlier streaming TTS segmentation so first voice chunks can start before a full sentence is available.
- Added cached macOS audio-output probing and timestamped TTS latency events.
- Added queue-to-playback timing to `tools/latency_probe.py`.
- Verified a real live Groq streaming prompt.

### Changes Made
- Modified `shell_voice_listener_runtime.py`.
- Modified `shell_voice_runtime.py`.
- Modified `shell_ui/shell_cinematic_full.py`.
- Modified `tools/latency_probe.py`.
- Updated `tests/test_voice_latency_runtime.py`.
- Updated `tests/test_chat_tts_policy.py`.

### Current State
- Targeted latency/policy tests passed: `29 passed`.
- Full test suite passed: `355 passed, 1 warning`.
- UI probe passed with screenshots written under `/private/tmp/shell_ui_realtime_post`.
- Audible TTS post-change probe measured `queue_to_playback_ms` at about 4.8 ms on the fast system TTS path.
- Live Groq provider probe measured first chunk at about 204 ms for a tiny prompt.

### Next Steps
1. Add true streaming PCM TTS output behind `TTSSpeaker` instead of subprocess-based whole-utterance playback.
2. Add a native realtime speech-to-speech provider path for OpenAI Realtime or Gemini Live.
3. Add real mic conversation test automation with recorded utterance injection and barge-in stress cases.
4. Start or bundle Shell-v2 automatically so localhost streaming is measurable in the default launcher.
5. Add a compact always-visible latency dashboard for first UI, first token, first audio, and interruption timing.

### Open Issues
- Shell-v2 was not running on `127.0.0.1:8765`, so the localhost Shell-v2 live path still reports connection refused.
- The current fast path uses system TTS for instant startup; premium cloud voice still needs true streaming audio to avoid multi-second Gemini file-generation delays.
- Manual real microphone conversation testing was not completed in this automated session.

## Session: 2026-05-19

### Completed
- Ran a second realtime UX redesign cycle focused on interruption-first voice orchestration.
- Added voice listener latency events for speech start, speech end, speech-end-to-processing, recognition duration, and speech-end-to-text timing.
- Added voice turn IDs so stale AI chunks, stale replies, stale errors, and delayed fast replies are ignored after a user barge-in or newer turn.
- Added voice barge-in cancellation that stops TTS, clears queued/partial voice stream state, disconnects stale worker signals, requests worker interruption, and advances the turn ID immediately.
- Added voice AI latency recording for first voice text chunk and stream completion.
- Added a `voice.turn_cancel` probe to `tools/latency_probe.py`.
- Re-ran audible TTS, live Groq streaming, UI, targeted, and full-suite validation.

### Changes Made
- Updated `shell_voice_listener_runtime.py` with latency telemetry signals.
- Updated `shell_ui/shell_cinematic_full.py` with voice turn ownership, stale-signal guards, barge-in cancellation, and voice latency logging.
- Updated `tools/latency_probe.py` with the voice turn cancellation probe.
- Updated `tests/test_chat_tts_policy.py`.
- Updated `tests/test_voice_latency_runtime.py`.

### Current State
- Pre-cycle audible TTS baseline: `queue_to_playback_ms` 4.343 ms, `playback_started` 2.44 ms.
- Post-cycle audible TTS: `queue_to_playback_ms` 7.589 ms, `playback_started` 6.26 ms. This remains effectively instant and the patch did not target the TTS process path.
- Pre-cycle live Groq first chunk: 170.005 ms.
- Post-cycle live Groq first chunks: 372.738 ms then 182.829 ms on repeat; cadence stayed smooth at about 5.2-5.4 ms average chunk interval.
- Synthetic first token stayed stable: 11.106 ms pre, 11.096 ms post.
- New interruption cleanup probe: `voice.turn_cancel` completed in 4.366-6.146 ms, stopped TTS, disconnected 5 stale signals, requested worker interruption, cleared partial stream state, and advanced the turn ID.
- UI probe passed.
- Full test suite passed: `358 passed, 1 warning`.

### Next Steps
1. Add real recorded-audio voice test automation so speech-end-to-first-audio can be measured without manual mic use.
2. Add true streaming PCM TTS instead of subprocess utterance playback.
3. Evaluate an OpenAI Realtime or Gemini Live speech-to-speech session path for full-duplex audio and native provider interruption events.
4. Track voice backend-command turns separately so interrupted voice tool calls cannot later speak stale tool output.
5. Start or bundle Shell-v2 automatically so localhost streaming is measurable by default.

### Open Issues
- Shell-v2 still was not running on `127.0.0.1:8765`; local connection probes report connection refused.
- Manual noisy-room microphone testing was not completed in this automated cycle.
- The backend-command voice path is not yet turn-ID guarded; normal AI voice replies are guarded now.

## Session: 2026-05-19

### Completed
- Ran a third realtime conversational UX cycle focused on streaming TTS readiness, Shell-v2 startup reliability, and remaining stale voice output paths.
- Researched current OpenAI Realtime/Speech API, Gemini Live, LiveKit, Pipecat, and streaming TTS guidance.
- Added an explicit `SHELL_TTS_ENGINE=openai-stream` / `openai-pcm` path that streams OpenAI Speech API PCM chunks through `sounddevice` via `LocalAudioPlayer.play_stream`.
- Added cancellation support for the streaming PCM path through the existing `stop_speaking()` lifecycle.
- Added UI warmup autostart for the default local Shell-v2 bridge when `http://127.0.0.1:8765` is down.
- Added turn guards for voice-origin backend commands so stale tool results cannot speak after a newer voice turn or barge-in.
- Extended the latency probe UI sample to report whether Shell-v2 bridge autostart happened and whether `/health` responded.

### Changes Made
- Updated `shell_voice_runtime.py` with optional OpenAI streaming PCM TTS.
- Updated `shell_ui/shell_cinematic_full.py` with Shell-v2 autostart and turn-guarded voice backend-command routing.
- Updated `tools/latency_probe.py` with Shell-v2 autostart visibility in UI probe output.
- Updated `tests/test_voice_latency_runtime.py`.
- Updated `tests/test_chat_tts_policy.py`.
- Updated `tests/test_shell_v2_runtime.py`.

### Current State
- Pre-cycle UI warmup did not start Shell-v2; `shell_v2.connect_1s` reported connection refused.
- Post-cycle UI warmup autostarted Shell-v2; `ui.init_first_paint` reported `shell_v2_bridge_started: true` and `shell_v2_health_ok: true`.
- Pre-cycle UI init sample: 2126.854 ms. Post-cycle UI init sample: 1796.735 ms in the clean post run.
- Default audible TTS stayed effectively instant: post-cycle `queue_to_playback_ms` 7.285 ms and `playback_started` 6.08 ms on macOS `say`.
- Synthetic first token stayed stable: 11.096 ms pre-cycle and 12.115 ms post-cycle.
- Shell-v2 fake bridge probe: first visible chunk 18.18 ms, provider-to-SSE overhead 2.115 ms, transport-to-worker overhead 6.065 ms, no residual thread leak after shutdown.
- Shell-v2 live Groq bridge probe: first visible chunk 547.04 ms; provider first token was 539.093 ms, provider-to-SSE overhead 1.535 ms, transport-to-worker overhead 6.412 ms.
- Live direct Groq probe: first chunk 292.008 ms with smooth 5.245 ms average chunk cadence.
- Targeted realtime tests passed: `36 passed`.
- UI probe passed.
- Full test suite passed: `362 passed, 1 warning`.

### Next Steps
1. Enable and benchmark `SHELL_TTS_ENGINE=openai-stream` with a real OpenAI key to measure PCM first-audio latency against macOS `say` and Gemini file TTS.
2. Add recorded-audio injection tests for speech-end-to-first-audio and noisy-room regression coverage.
3. Add native OpenAI Realtime or Gemini Live speech-to-speech sessions for full-duplex audio and provider-native interruption events.
4. Add cancellation propagation into Shell-v2 HTTP/SSE requests so abandoned streams can stop provider work, not only ignore stale UI signals.
5. Add adaptive buffering for streaming PCM TTS so first playback begins on the first safe audio frame but backpressure avoids underruns.

### Open Issues
- Real OpenAI streaming PCM TTS was implemented behind a feature flag but could not be live-benchmarked because no OpenAI API key is configured in this workspace.
- Live Groq first-token latency varied substantially; the Shell-v2 transport overhead was low, so provider/network latency is now the visible bottleneck in that path.
- Manual noisy-room and overlapping-speech tests are still not automated.

## Session: 2026-05-19

### Completed
- Ran a fourth realtime conversational UX cycle focused on overlapping-pipeline cancellation and provider variance.
- Researched current OpenAI Realtime, Gemini Live, LiveKit, Pipecat, and full-duplex turn-taking guidance around interruption-first voice systems.
- Added explicit cancellation state to `ShellV2Worker` so UI interruption stops consuming the SSE stream after the first stale chunk instead of only ignoring late completion.
- Added explicit cancellation state to `AIChatWorker` so in-process streaming generation exits before emitting stale final replies.
- Updated the Shell-v2 bridge to treat client disconnects as expected cancellation and to preserve `asyncio.CancelledError` semantics.
- Added worker-level cancellation tests and a `shell_v2.worker_cancel` latency probe.
- Re-ran real TTS playback, live Groq direct streaming, live Shell-v2 bridge streaming, UI, targeted, and full-suite validation.

### Changes Made
- Updated `shell_ui/shell_cinematic_full.py` with cancellation-aware Shell-v2 and in-process chat workers.
- Updated `shell_v2_runtime.py` with client-disconnect-safe SSE writes and explicit async cancellation propagation.
- Updated `tools/latency_probe.py` with Shell-v2 worker-cancel measurement.
- Updated `tests/test_shell_v2_live_streaming.py`.
- Updated `tests/test_streaming_first_token.py`.

### Current State
- Shell-v2 worker cancellation probe: stream cancelled after one chunk in 0.24-0.70 ms, emitted no final reply, and did not emit stream-done.
- Voice turn cancellation probe: stopped TTS, cleared partial stream state, disconnected stale signals, advanced the turn ID, and completed in 0.138-3.815 ms across post runs.
- Real TTS playback with macOS `say`: `playback_started` 4.42 ms and `queue_to_playback_ms` 6.101 ms when run with system audio access.
- Synthetic chat first-token remained stable at 11.112-11.145 ms.
- Shell-v2 fake bridge probe: first visible chunk 17.75 ms, provider-to-SSE overhead 1.059 ms, transport-to-worker overhead 6.691 ms, no thread leak.
- Live direct Groq samples: first chunks 205.109 ms, 145.970 ms, and 162.086 ms; cadence stayed smooth at about 5.18-5.24 ms average interval.
- Live Shell-v2 Groq bridge samples: first visible chunks 703.849 ms and 221.439 ms; provider-to-SSE overhead stayed low at 1.582-1.671 ms and transport-to-worker overhead stayed about 6.34-6.40 ms.
- UI warmup probe with local networking allowed: `shell_v2_bridge_started: true` and `shell_v2_health_ok: true`.
- UI probe passed.
- Targeted realtime tests passed: `22 passed`.
- Full test suite passed: `364 passed, 1 warning`.

### Next Steps
1. Move cancellation deeper into provider calls where supported so disconnecting Shell-v2 streams cancels provider inference immediately, not only server/client consumption.
2. Add a persistent realtime speech session prototype using OpenAI Realtime or Gemini Live WebSocket/WebRTC semantics for true duplex audio.
3. Add recorded/noisy audio fixtures and barge-in playback tests for speech-end-to-first-audio and overlapping speech regression coverage.
4. Add provider variance controls: short prompt budgets, session reuse where safe, fallback racing, and visible immediate acknowledgement states.
5. Live-benchmark `SHELL_TTS_ENGINE=openai-stream` once an OpenAI key is configured.

### Open Issues
- True native speech-to-speech is still not implemented; Shell is still primarily a cascaded STT -> LLM -> TTS system with improving overlap.
- OpenAI streaming PCM TTS could not be live-benchmarked because no OpenAI API key is configured in this workspace.
- Manual noisy-room microphone testing and overlapping-speech real-world testing remain incomplete in this automated environment.
- Provider first-token variance remains the dominant visible latency bottleneck now that Shell-v2 transport overhead is low.

## Session: 2026-05-19

### Completed
- Ran a fifth realtime conversational UX cycle focused on persistent duplex voice-session groundwork.
- Researched OpenAI Realtime sessions, Gemini Live stateful WebSocket audio, LiveKit turn handling, Pipecat interruption frames, and 2026 full-duplex voice-agent benchmarks.
- Added a transport-agnostic `RealtimeVoiceSession` controller for continuous voice state: listening, user speaking, thinking, assistant speaking, interrupted, prewarmed, and stopped.
- Added speech-start AI path prewarming so voice sessions can hydrate Shell-v2/brain state while the user is still speaking.
- Routed normal voice AI turns through the persistent Shell-v2 SSE bridge when available, while preserving the existing in-process fallback.
- Changed Shell-v2 default brain creation to use the brain singleton so bridge sessions keep provider/cache/runtime state warm instead of constructing a fresh brain per request.
- Added a Shell-v2 runtime reuse probe proving two turns reuse one provider transport inside the same runtime loop.
- Added regression tests for voice-session state, Shell-v2 voice preference, Shell-v2 stream duplicate suppression, fallback behavior, and provider transport reuse.

### Changes Made
- Added `shell_realtime_voice_session.py`.
- Updated `shell_ui/shell_cinematic_full.py` with persistent voice-session tracking, speech-start prewarm, and Shell-v2 voice routing.
- Updated `shell_v2_runtime.py` to use `MultiAIBrain.get_instance()` by default.
- Updated `tools/latency_probe.py` with `voice.realtime_session` and `shell_v2.runtime_reuse` probes.
- Added `tests/test_realtime_voice_session.py`.
- Updated `tests/test_shell_v2_runtime.py`.
- Updated `tests/test_chat_tts_policy.py`.

### Current State
- Realtime session controller overhead: 0.051-0.093 ms in post probes.
- Shell-v2 runtime reuse probe: two turns reused one provider transport (`uses: 2`), created one session, and closed one session on runtime shutdown.
- Voice turn cancellation remained fast: 0.099 ms in the clean post latency probe, 2.483 ms in the audible TTS probe.
- Shell-v2 worker cancellation stayed sub-millisecond: stream cancelled after one chunk in 0.61-0.64 ms.
- UI warmup still autostarts Shell-v2: `shell_v2_bridge_started: true`, `shell_v2_health_ok: true`.
- Real TTS playback with macOS `say`: `playback_started` 4.38 ms and `queue_to_playback_ms` 5.851 ms.
- Synthetic chat first-token stayed stable: 11.095-11.100 ms.
- Shell-v2 fake bridge probe: first visible chunk 17.04 ms, provider-to-SSE overhead 1.103 ms, transport-to-worker overhead 5.937 ms.
- Live direct Groq probe: first chunk 173.340 ms, average cadence 5.127 ms.
- Live Shell-v2 Groq bridge probe: first visible chunk 174.306 ms; provider first token 166.697 ms, provider-to-SSE overhead 1.559 ms, transport-to-worker overhead 6.004 ms.
- UI probe passed.
- Targeted realtime tests passed: `44 passed`.
- Full test suite passed: `370 passed, 1 warning`.

### Next Steps
1. Add a true realtime audio session transport behind a feature flag using OpenAI Realtime or Gemini Live WebSocket/WebRTC semantics.
2. Add provider-native audio interruption events and truncate/cancel handling for unplayed assistant audio.
3. Add recorded noisy-room and overlapping-speech fixtures to measure speech-start, endpointing, interruption, and false-interruption behavior.
4. Add adaptive endpointing controls based on live session pace and false-interruption history.
5. Live-benchmark OpenAI streaming PCM TTS and compare it with the current macOS `say` fast path.

### Open Issues
- This is persistent-session groundwork, not yet native speech-to-speech; Shell still uses cascaded recognition, text generation, and TTS for local voice.
- The voice route now prefers persistent Shell-v2 when available, but true duplex audio transport is still future work.
- Manual noisy-room microphone testing and overlapping-speech real-world testing remain incomplete in this automated environment.
- Provider first-token variance remains visible, though the bridge/session overhead is now consistently low.

## Session: 2026-05-19

### Completed
- Ran a sixth realtime conversational UX cycle focused on duplex-readiness through adaptive endpointing and conversational pacing.
- Researched current OpenAI Realtime VAD/interruption guidance, Gemini Live activity detection, LiveKit adaptive interruption handling, Pipecat smart-turn/end-of-turn strategies, and 2026 full-duplex voice-agent benchmark direction.
- Added adaptive voice endpoint timing to the local microphone listener: faster for short clean turns, more patient when the measured ambient floor approaches the speech threshold.
- Added endpointing telemetry to `speech_ended` latency payloads so real voice sessions report the effective timeout, adaptive state, and noise floor.
- Added an adaptive endpointing latency probe and regression tests for short clean turns, noisy turns, and feature-flag disable behavior.

### Changes Made
- Updated `shell_voice_listener_runtime.py` with adaptive endpoint timeout calculation, pre-speech noise-floor tracking, and endpointing telemetry.
- Updated `tools/latency_probe.py` with `voice.adaptive_endpointing`.
- Updated `tests/test_voice_latency_runtime.py` with adaptive endpointing coverage.

### Current State
- Adaptive endpointing probe: fixed 750 ms baseline now maps to 570 ms for short clean turns, 650 ms for medium clean turns, 850 ms for long clean turns, and 720 ms for short noisy turns.
- Realtime session controller overhead remained low: 0.022-0.064 ms in the TTS probe and 0.061-0.064 ms in the escalated UI/provider probe.
- Voice turn cancellation remained fast: 0.049 ms in the escalated UI/provider probe and 1.299 ms in the audible TTS probe.
- Shell-v2 worker cancellation remained sub-millisecond: 0.23-0.26 ms in post probes.
- UI warmup with local networking allowed still autostarts Shell-v2: `shell_v2_bridge_started: true`, `shell_v2_health_ok: true`.
- Real TTS playback with macOS `say`: `playback_started` 4.73 ms and `queue_to_playback_ms` 6.404 ms.
- Synthetic chat first-token stayed stable: 11.100-12.154 ms across post probes.
- Shell-v2 fake bridge probe: first visible chunk 17.14 ms, provider-to-SSE overhead 1.108 ms, transport-to-worker overhead 6.032 ms.
- Live direct Groq probe: first chunk 237.146 ms with 5.255 ms average chunk cadence.
- Live Shell-v2 Groq bridge probe: first visible chunk 298.950 ms; provider first token 290.920 ms, provider-to-SSE overhead 1.563 ms, transport-to-worker overhead 6.467 ms.
- UI probe passed.
- Targeted realtime tests passed: `41 passed`.
- Full test suite passed: `373 passed, 1 warning`.

### Next Steps
1. Replace amplitude-only local endpointing with semantic or model-assisted turn completion when using provider-native realtime sessions.
2. Add a true persistent duplex audio transport behind a feature flag using OpenAI Realtime or Gemini Live WebSocket/WebRTC audio.
3. Add interruption-aware audio truncation for unplayed assistant speech, including provider-native cancellation where supported.
4. Add recorded noisy-room and overlapping-speech fixtures to validate endpointing, barge-in, false interruptions, and speech-end-to-first-audio under realistic conditions.
5. Add provider variance hiding with predictive acknowledgements, provider session hydration, and optional provider racing for voice-critical turns.

### Open Issues
- This cycle improves local turn pacing, but it is not true duplex speech-to-speech yet.
- Adaptive endpointing currently uses a conservative amplitude/noise heuristic; it does not yet infer semantic turn completion or conversational intent.
- Manual noisy-room microphone testing and overlapping-speech real-world testing remain incomplete in this automated environment.
- Provider first-token variance remains the dominant live-path latency bottleneck; Shell-v2 transport overhead is still low.

## Session: 2026-05-19

### Completed
- Ran a seventh realtime conversational UX cycle focused on semantic conversational pacing.
- Researched OpenAI semantic VAD, LiveKit dynamic endpointing/adaptive interruption options, Pipecat Smart Turn, and recent turn-taking papers on disfluency, pause intent, and context-aware speak-vs-wait decisions.
- Added local semantic pacing memory to the microphone listener so recognized turn text can gently bias the next endpoint timeout.
- Added classifications for empty recognition, hesitation/thinking phrases, trailing continuation words, short commands, and default complete turns.
- Added `semantic_turn_analyzed` latency events and `speech_ended` semantic-bias telemetry.
- Extended the adaptive endpointing probe and tests to cover semantic hesitation, continuation, short-command, and disabled states.

### Changes Made
- Updated `shell_voice_listener_runtime.py` with semantic turn classification, smoothed semantic endpoint bias, and semantic pacing telemetry.
- Updated `tools/latency_probe.py` so `voice.adaptive_endpointing` reports semantic pacing outcomes.
- Updated `tests/test_voice_latency_runtime.py` with semantic pacing regression coverage.

### Current State
- Semantic pacing probe: fixed 750 ms baseline still maps to 570 ms for a short clean turn, but the next timeout becomes 669 ms after a hesitation, 651 ms after a trailing continuation, and 614 ms after a short command on a medium turn.
- Semantic classifications are exposed in probe output: `hesitation`, `continuation`, and `short_command`, with smoothed bias values of +99 ms, +81 ms, and -36 ms respectively in the post-run sample.
- Realtime session controller overhead remained low: 0.043-0.047 ms in the UI/provider probe and 0.046-0.047 ms in the audible TTS probe.
- Voice turn cancellation remained fast: 0.046 ms in the UI/provider probe and 2.672 ms in the audible TTS probe.
- Shell-v2 worker cancellation remained sub-millisecond: 0.21 ms in the UI/provider probe and 0.50 ms in the audible TTS probe.
- Real TTS playback with macOS `say`: `playback_started` 4.44 ms and `queue_to_playback_ms` 6.084 ms.
- Synthetic chat first-token stayed stable: 11.093-11.105 ms across post probes.
- Shell-v2 fake bridge probe: first visible chunk 17.11 ms, provider-to-SSE overhead 1.104 ms, transport-to-worker overhead 6.006 ms.
- Live direct Groq probe: first chunk 915.887 ms in one high-variance sample.
- Live Shell-v2 Groq bridge probe: first visible chunk 294.090 ms; provider first token 286.323 ms, provider-to-SSE overhead 1.522 ms, transport-to-worker overhead 6.245 ms.
- UI probe passed.
- Targeted realtime tests passed: `45 passed`.
- Full test suite passed: `377 passed, 1 warning`.

### Next Steps
1. Add real partial-transcript or provider-native semantic turn detection so semantic completion can affect the current turn, not only the next one.
2. Add recorded hesitation and continuation fixtures to test pause-intent behavior deterministically.
3. Integrate OpenAI Realtime `semantic_vad` or Gemini Live activity detection behind a feature flag for provider-native turn completion.
4. Add adaptive false-interruption recovery using short/empty recognition and backchannel detection.
5. Add provider variance hiding through voice-specific acknowledgement states, session hydration, and optional provider racing.

### Open Issues
- Semantic pacing currently uses recognized text after endpointing, so it improves future pacing and telemetry but cannot yet prevent a current-turn premature endpoint.
- The classifier is deliberately conservative and heuristic-based; it is not a trained semantic endpointing model.
- Manual noisy-room, emotional pacing, and overlapping-speech testing remain incomplete in this automated environment.
- Provider first-token variance remains the dominant visible live-path latency bottleneck.

## Session: 2026-05-19

### Completed
- Ran an eighth realtime conversational UX cycle focused on semantic turn intelligence and user rhythm adaptation.
- Researched OpenAI semantic VAD, Realtime interruption/truncation, LiveKit turn-handling options, Pipecat Smart Turn, and recent conversational turn-taking work on context-aware speak/wait timing.
- Added a smoothed semantic rhythm profile to the local voice listener so Shell can distinguish immediate turn meaning from the user's broader conversational style.
- Added rhythm styles for `patient`, `fast`, `reflective`, and `balanced`, with tightly clamped rhythm bias feeding into adaptive endpoint timing.
- Added rhythm telemetry to `speech_ended` and `semantic_turn_analyzed` latency events.
- Extended latency probes and tests to validate patient-style and fast-style rhythm adaptation.

### Changes Made
- Updated `shell_voice_listener_runtime.py` with semantic rhythm EMA tracking, rhythm-style classification, and rhythm bias integration.
- Updated `tools/latency_probe.py` so `voice.adaptive_endpointing` reports patient/fast rhythm profiles and resulting endpoint timing.
- Updated `tests/test_voice_latency_runtime.py` with semantic rhythm regression tests.

### Current State
- Semantic timing probe: base endpoint remains 750 ms; short clean turn remains 570 ms; short noisy turn remains 720 ms.
- Immediate semantic pacing: hesitation maps to 680.25 ms, continuation maps to 666.75 ms, and short command maps to 591.50 ms.
- Learned rhythm pacing: two patient-style turns map the next short clean endpoint to 728.85 ms; two fast short-command turns map a medium endpoint to 559.33 ms.
- Rhythm profile telemetry is exposed: patient profile had hesitation score 0.65, continuation score 0.35, rhythm bias +23.40 ms; fast profile had short-command score 1.0, rhythm bias -34.88 ms.
- Realtime session controller overhead remained low: 0.064-0.079 ms in the UI/provider probe and 0.020-0.024 ms in the audible TTS probe.
- Voice turn cancellation remained fast: 0.052 ms in the UI/provider probe and 2.207 ms in the audible TTS probe.
- Shell-v2 worker cancellation remained sub-millisecond: 0.51 ms in the UI/provider probe and 0.31 ms in the audible TTS probe.
- Real TTS playback with macOS `say`: `playback_started` 5.82 ms and `queue_to_playback_ms` 8.621 ms.
- Synthetic chat first-token stayed stable: 11.073-11.101 ms across post probes.
- Shell-v2 fake bridge probe: first visible chunk 17.87 ms, provider-to-SSE overhead 1.111 ms, transport-to-worker overhead 6.759 ms.
- Live direct Groq probe: first chunk 336.722 ms.
- Live Shell-v2 Groq bridge probe: first visible chunk 190.290 ms; provider first token 182.563 ms, provider-to-SSE overhead 1.605 ms, transport-to-worker overhead 6.122 ms.
- UI probe passed.
- Targeted realtime tests passed: `47 passed`.
- Full test suite passed: `379 passed, 1 warning`.

### Next Steps
1. Move semantic turn intelligence into the current turn with partial transcript or provider-native semantic VAD.
2. Add recorded fixtures for hesitation, continuation, short commands, backchannels, noisy rooms, and overlapping speech.
3. Add false-interruption recovery and backchannel detection so short acknowledgements do not always cancel assistant speech.
4. Add provider-native realtime session support for OpenAI `semantic_vad` or Gemini Live activity detection behind a feature flag.
5. Add voice-specific provider variance hiding with immediate acknowledgement states and optional provider/session racing.

### Open Issues
- Rhythm adaptation still learns from completed turns; it cannot yet infer semantic completion before local STT returns text.
- The rhythm model is intentionally heuristic and conservative, not a trained prosody-aware or transformer endpointing model.
- Manual noisy-room, emotional pacing, backchannel, and overlapping-speech tests remain incomplete in this automated environment.
- Provider first-token variance remains the dominant visible live-path bottleneck.

## Session: 2026-05-19

### Completed
- Ran a realtime voice identity cycle focused on preserving the intended Shell voice instead of silently taking faster fallback paths.
- Researched current OpenAI Realtime/TTS and Gemini Live/TTS voice configuration behavior, including session voice locking, prebuilt voice configuration, streaming PCM, and voice activity/interruption handling.
- Traced Shell's audible speech routing through the UI, Shell-v2 streaming text path, `TTSSpeaker`, Gemini TTS, OpenAI PCM TTS, edge/system fallbacks, and interruption cleanup.
- Fixed the main identity regression where default `fast` + `cloud` + `instant` mode could speak through system `say` before Gemini Aoede.
- Added explicit TTS telemetry for configured engine, voice mode, Gemini voice, OpenAI voice, persona, active backend, active voice, premium-first policy, and fallback permission.
- Added UI System Dashboard logs for backend selection, playback start, fallback activation, and fallback blocking.
- Made cancellation/interruption cleanup identity-safe so a stopped Gemini playback is not reported as a fallback failure and does not trigger system TTS.
- Updated the Voice settings UI to treat the dropdown as the Shell signature voice and prefer `tts_voice` over the legacy `voice_persona` key.

### Changes Made
- Updated `shell_voice_runtime.py` with premium-first cloud routing, voice identity snapshots, backend selection events, fallback telemetry, and cancellation-safe playback handling.
- Updated `shell_ui/shell_cinematic_full.py` to display voice identity/fallback events in the System Dashboard and to persist the voice dropdown via `tts_voice`.
- Updated `tools/latency_probe.py` with `tts.voice_identity` reporting and configurable audible TTS probe timeout.
- Updated `tests/test_voice_latency_runtime.py` with regressions for cloud premium-first routing, explicit fallback logging, blocked fallback logging, OpenAI backend selection telemetry, and cancellation without fallback failure.

### Current State
- Active voice identity probe: `configured_engine=fast`, `voice_mode=cloud`, `gemini_voice=Aoede`, `openai_voice=coral`, `persona=Hinglish`, `premium_voice_first=true`, `cloud_fallback_allowed=false`.
- Clean audible TTS probe selected `backend=gemini`, `voice=Aoede`, `model=gemini-2.5-flash-preview-tts`, with no system fallback.
- Clean audible TTS first premium playback: `queue_to_playback_ms=2932.134 ms`; local `afplay` start after file handoff was `2.89 ms`; Gemini audio ready at `2927.15 ms`.
- Sandbox audible probe correctly blocked system fallback when CoreAudio was unavailable; escalated desktop-audio probe confirmed Gemini Aoede playback path.
- Interruption cleanup probe remained stable: `voice.turn_cancel` 3.270 ms and `shell_v2.worker_cancel` 0.59 ms in the clean audible run.
- UI launch verification passed: `launch.py` opened the visible Shell desktop window successfully, then the launched process was terminated after verification.
- Targeted voice tests passed: `32 passed`.
- Full test suite passed: `382 passed, 1 warning`.

### Next Steps
1. Add provider-native streaming audio for the default Shell voice so Aoede can start before full Gemini TTS generation completes.
2. Add a visible Voice Identity panel/status line showing active backend, voice, fallback state, and last playback path without relying only on logs.
3. Add a voice identity watchdog that warns if `voice_mode=cloud` cannot reach Gemini before the user hears anything.
4. Evaluate a persistent Gemini Live or OpenAI Realtime voice session for lower first-audio latency while preserving one locked signature voice.
5. Add real recorded interruption/noisy-room playback fixtures to validate that cancellation never causes fallback/system voice bleed-through.

### Open Issues
- Gemini generateContent TTS is still full-response TTS, so premium first-audio latency is provider-bound at about 2.9 seconds in the clean local probe.
- OpenAI streaming PCM support exists but is not the configured primary identity because the current Shell signature voice is Gemini Aoede and no OpenAI key is configured in this environment.
- Human timbre judgment cannot be performed by the agent directly; audible playback was exercised on the desktop audio path, and telemetry confirms the active backend/voice.
- System voice fallback is now blocked by default in cloud mode, which preserves identity but means audio will fail visibly if Gemini or audio output is unavailable unless `SHELL_CLOUD_TTS_LOCAL_FALLBACK=1` is explicitly set.

## Session: 2026-05-19

### Completed
- Ran a premium streaming voice cycle focused on reducing first-audio latency without sacrificing Shell's Aoede identity.
- Researched Gemini Live audio output, OpenAI Realtime/TTS streaming patterns, low-buffer PCM playback, and provider-native voice-session behavior.
- Verified the existing Google SDK exposes Live sessions through `client.aio.live.connect` and that the current working Live model for this environment is `gemini-3.1-flash-live-preview`.
- Added a Gemini Live PCM streaming backend that locks `Aoede` through `speech_config.voice_config.prebuilt_voice_config.voice_name`.
- Changed cloud TTS routing so Shell tries `gemini_live_pcm` first, falls back to premium batch Gemini only if needed, and still blocks system fallback unless explicitly allowed.
- Added voice identity telemetry for `premium_streaming_voice` and `gemini_live_model`.
- Added UI System Dashboard visibility for Gemini Live first chunk and completion events.
- Fixed Gemini Live prompt behavior so the provider reads Shell's response text aloud instead of treating it as a new conversational prompt.
- Fixed Gemini Live async cleanup by holding the SDK client until after the playback loop closes, preventing pending `aclose()` warnings in the final probe.

### Changes Made
- Updated `shell_voice_runtime.py` with `_speak_gemini_live_tts`, streamed PCM playback through `LocalAudioPlayer`, Live audio extraction, Live-first routing, and cleanup safeguards.
- Updated `shell_ui/shell_cinematic_full.py` so Live first chunk / completion events appear in voice identity logs.
- Updated `tools/latency_probe.py` to report `SHELL_GEMINI_LIVE_TTS` and `GEMINI_LIVE_TTS_MODEL`.
- Updated `tests/test_voice_latency_runtime.py` with Live-first routing and fake Gemini Live PCM playback coverage.

### Current State
- Active voice identity probe: `configured_engine=fast`, `voice_mode=cloud`, `gemini_voice=Aoede`, `premium_voice_first=true`, `premium_streaming_voice=true`, `gemini_live_model=gemini-3.1-flash-live-preview`, `cloud_fallback_allowed=false`.
- Baseline premium batch Gemini from the prior cycle: `queue_to_playback_ms=2932.134 ms`, Gemini audio ready at `2927.15 ms`.
- Final audible Gemini Live probe: `backend=gemini_live_pcm`, `voice=Aoede`, first Live PCM chunk at `758.19 ms`, `playback_started=758.97 ms`, `queue_to_playback_ms=1355.331 ms`.
- Full UI in-app voice validation: visible Shell UI launched, `_tts.speak(...)` used the same `gemini_live_pcm` backend, first chunk at `807.50 ms`, playback start at `808.20 ms`, no system fallback.
- Streaming generated 30 chunks / 190,088 bytes in the final runtime probe and 42 chunks / 287,048 bytes in the full UI validation.
- Interruption/realtime probes remained stable: `voice.turn_cancel=3.765 ms`, `shell_v2.worker_cancel=0.67 ms`, `voice.realtime_session` control overhead `0.053 ms`.
- Targeted voice tests passed: `34 passed, 1 warning`.
- Full test suite passed: `384 passed, 1 warning`.

### Next Steps
1. Reuse a persistent Gemini Live session across turns to remove the ~200 ms connection setup and reduce queue-to-playback overhead.
2. Add adaptive first-audio measurement that ignores the initial 2-byte Live primer chunk and records first substantial PCM chunk / first audible energy.
3. Build true duplex interruption propagation into the Gemini Live audio session so barge-in can interrupt provider generation, not just local playback.
4. Add an optional short acknowledgement/backchannel system that preserves Aoede identity while hiding provider variance.
5. Compare Gemini Live Aoede against OpenAI Realtime voices only as an optional alternate identity, not as a silent replacement.

### Open Issues
- First Live audio is now sub-second from backend selection, but queue-to-playback still includes about 600 ms of local TTS-thread / probe scheduling overhead.
- Gemini Live sometimes emits a tiny 2-byte first PCM primer chunk; the current metric records it as first chunk, so future reporting should distinguish primer vs substantial audible audio.
- The Live backend is still turn-scoped, not a persistent duplex session, so the next breakthrough is session reuse plus provider-native interruption.
- Human timbre judgment remains limited to audible playback execution plus telemetry confirmation; the agent cannot personally perceive voice tone.

## Session: 2026-05-19

### Completed
- Ran an autonomous realtime voice QA cycle focused on premium first-audio truthfulness, startup warmup behavior, cleanup stability, and full UI audible validation.
- Researched current realtime voice patterns around Gemini Live VAD/interruption, OpenAI Realtime semantic/server VAD, LiveKit interruption handling, Pipecat smart turn detection, and 2026 voice-agent pipelining papers.
- Found that Gemini Live can emit a tiny 2-byte PCM primer before meaningful audio, so the previous first-chunk metric overstated perceived first-audio responsiveness.
- Added first-audible PCM telemetry so Shell now distinguishes `gemini_live_first_chunk` from `gemini_live_first_audible_chunk`.
- Found that no-audio environments could trigger `LocalAudioPlayer` failures plus pending asyncio generator/task noise; added PCM audio preflight before opening provider streams.
- Found duplicate TTS warmup requests in the full UI path could delay the first real utterance; deduped warmup while preserving idle startup laziness.
- Added a reusable full UI voice validation probe for future audible-route QA.

### Changes Made
- Updated `shell_voice_runtime.py` with PCM playback preflight, first-audible Gemini Live telemetry, warmup deduplication, and local streaming-runtime prewarm that keeps heavy provider modules opt-in via `SHELL_TTS_PROVIDER_PREWARM=1`.
- Updated `tools/latency_probe.py` to report `first_audible_ms`, `queue_to_first_audible_ms`, warmup completion, and warmup wait time.
- Updated `shell_ui/shell_cinematic_full.py` so first-audible and streaming runtime readiness events appear in voice identity logs.
- Added `tools/voice_ui_validation_probe.py` for real Shell UI TTS validation with backend, voice, model, first-audible, queue-to-audio, and identity reporting.
- Updated `tests/test_voice_latency_runtime.py` for warmup dedupe, PCM preflight, and primer-vs-audible chunk behavior.

### Current State
- No-audio sandbox probe now exits cleanly through `pcm_audio_unavailable` and blocked fallback; it no longer opens a Gemini stream or leaks asyncio cleanup warnings.
- Accurate audible metric discovered the previous `gemini_live_first_chunk` was a 2-byte primer packet; real first audible audio is now tracked at `gemini_live_first_audible_chunk`.
- Pre-provider-warmup audible probe: first substantial PCM was `1505.13 ms`, queue-to-first-audible `1506.334 ms`.
- Provider-module prewarm experiment: backend selection dropped from `614.57 ms` to `0.08 ms`, Gemini Live connect from `825.42 ms` to `193.50 ms`, and first substantial PCM from `1505.13 ms` to `799.29 ms`; heavy provider-module prewarm remains opt-in to avoid idle startup network-stack imports.
- Default full UI validation after warmup dedupe: `backend=gemini_live_pcm`, `voice=Aoede`, `model=gemini-3.1-flash-live-preview`, `queue_to_first_audible_ms=1192.254`, `queue_to_playback_ms=1193.121`, no system fallback.
- Full UI validation with duplicate warmup before the dedupe showed `queue_to_first_audible_ms=1656.085`; after dedupe the default full UI path measured `1192.254 ms`.
- Targeted voice tests passed: `33 passed, 1 warning`.
- Idle startup regression test passed: `1 passed`.
- Full test suite passed: `387 passed, 1 warning`.

### Next Steps
1. Move provider-module prewarm from opt-in env to an explicit user-intent trigger, such as voice-session start or microphone activation, so Shell can get the ~800 ms first-audible path without violating idle startup laziness.
2. Reuse a persistent Gemini Live session across turns to remove the ~200 ms connection setup.
3. Add provider-native interruption/truncation for Gemini Live so barge-in cancels provider generation, not only local playback.
4. Add first-audible energy detection instead of byte thresholding, so silence and primer packets are distinguished more precisely.
5. Build recorded noisy-room/interruption fixtures and run them through the new full UI voice validation tooling.

### Open Issues
- Default first audible Aoede in full UI is now honest and stable but still around 1.2 seconds; the opt-in provider prewarm path shows a route toward ~0.8 seconds without changing voice identity.
- Provider-first-audio variance remains visible between runs, even with local warmup fixed.
- Gemini Live remains turn-scoped rather than a persistent duplex session.
- Human timbre judgment still requires the user’s ear; telemetry confirms `gemini_live_pcm` and `Aoede`, but the agent cannot directly perceive audio quality.

## Session: 2026-05-19

### Completed
- Ran an intent-based predictive prewarm cycle focused on moving provider/runtime hydration from passive startup to explicit voice intent.
- Researched current realtime voice-agent patterns: LiveKit preemptive generation and turn handling, Gemini Live low-latency stateful audio sessions, OpenAI Realtime turn detection, and Pipecat speech-start / smart-turn behavior.
- Added a public TTS intent-prewarm path that can import provider modules only after user voice intent, without changing idle startup behavior.
- Wired explicit voice-session start and speech-start prewarm into the premium voice runtime.
- Extended the full UI voice validation probe with `--intent-prewarm` to measure the real user-intent path.
- Fixed a background-thread UI mutation discovered during visible validation; prewarm threads now log instead of directly touching Qt widgets.

### Changes Made
- Updated `shell_voice_runtime.py` with provider-module-aware `prewarm_for_voice_intent(...)`, separate local/provider readiness flags, and deduped prewarm locking.
- Updated `shell_ui/shell_cinematic_full.py` so voice-session start triggers predictive TTS prewarm, and the existing speech-start realtime prewarm also warms the premium voice runtime.
- Updated `tools/voice_ui_validation_probe.py` with `--intent-prewarm` and intent prewarm wait reporting.
- Updated realtime/voice tests to cover provider-module intent prewarm and speech-start TTS hydration.

### Current State
- Idle startup remains lightweight: `test_ui_idle_startup_does_not_autostart_socketio` passed, so `socketio`, `engineio`, `aiohttp`, and `brain.core` are still not loaded by passive UI startup.
- Default full UI baseline from prior cycle: `queue_to_first_audible_ms=1192.254`, `queue_to_playback_ms=1193.121`.
- Intent-prewarm visible UI validation: `backend=gemini_live_pcm`, `voice=Aoede`, `model=gemini-3.1-flash-live-preview`, `intent_prewarm_wait_ms=375.927`, `queue_to_first_audible_ms=866.993`, `queue_to_playback_ms=867.398`, no system fallback.
- Intent-prewarm removed the provider import/backend-selection penalty: `tts_backend_selected` occurred at `0.09 ms`, Gemini Live connected at `193.79 ms`, and first substantial audible PCM arrived at `866.8 ms`.
- No-audio cleanup probe still exits through `pcm_audio_unavailable` and blocked fallback, with no provider stream opened and no async cleanup noise.
- Targeted predictive/voice tests passed: `40 passed, 1 warning`.
- Full test suite passed: `389 passed, 1 warning`.

### Next Steps
1. Promote intent prewarm from the validation probe into more real UX triggers: microphone button hover/focus, active voice session start, and high-confidence VAD onset.
2. Add persistent Gemini Live session reuse after voice-session start to remove the remaining ~190-220 ms connection setup.
3. Add a small prewarm state indicator in System/Voice telemetry without direct background-thread UI writes.
4. Add interruption tests while provider modules are prewarming to ensure barge-in cannot race with hydration.
5. Measure multi-turn voice sessions to confirm the second and third turns stay warm without leaking provider/session state.

### Open Issues
- Intent prewarm improves first-audible latency to the ~0.87 s range in visible UI validation, but provider first-audio variance remains.
- Gemini Live is still turn-scoped; provider modules are warm, but the actual Live WebSocket is not yet persistent across voice turns.
- Intent prewarm currently imports provider modules but does not open a provider audio session, which is the safer first step but not the final realtime-duplex architecture.
- Human timbre judgment still requires user verification; telemetry confirms the Aoede premium route.

## Session: 2026-05-19

### Completed
- Ran a hybrid multi-language runtime architecture cycle focused on Shell's future Tauri/Rust-or-Go realtime core without starting a risky rewrite.
- Researched current Tauri v2 process/IPC/sidecar patterns, Rust Tokio async networking, Go pipeline/concurrency patterns, LiveKit turn orchestration, Pipecat smart-turn endpointing, and OpenAI Realtime VAD/turn detection.
- Mapped current hot runtime boundaries: Python Shell-v2 SSE bridge, async runtime thread, PyQt SSE worker, premium voice runtime, optional LiveKit realtime audio runtime, provider transport reuse, and tool catalog execution.
- Confirmed this local environment does not currently include `rustc`, `cargo`, or `go`, so native extraction should be planned and benchmark-gated before adding toolchain/build complexity.
- Added best-effort `TCP_NODELAY` configuration to the Shell-v2 bridge listener and accepted client sockets so realtime SSE frames prefer immediate local delivery.
- Added focused unit coverage for the low-latency socket helper.

### Changes Made
- Updated `shell_v2_runtime.py` with `_set_tcp_nodelay(...)`, listener-level low-latency socket setup, and accepted-connection low-latency setup.
- Updated `tests/test_shell_v2_runtime.py` with success/failure tests for the best-effort TCP no-delay helper.

### Current State
- Shell-v2 local bridge before samples: first visible text median `18.45 ms`; transport-to-worker median `7.342 ms`; stream completion median `40.68 ms`.
- Shell-v2 local bridge after samples: first visible text median `17.27 ms`; transport-to-worker median `6.215 ms`; stream completion median `39.52 ms`.
- Measured improvement: first visible text improved by `1.18 ms` (`6.4%`); transport-to-worker improved by `1.127 ms` (`15.4%`).
- Baseline memory probe remains stable: provider transport closes cleanly, `after_close.session_count=0`, peak RSS `27.859 MB`.
- Latency probe remained healthy; `shell_v2.worker_cancel` stayed sub-millisecond at `0.406 ms` total in the after run.
- Production release check passed with no blockers; warning only that local `.env` exists and must not be packaged.
- Full test suite passed: `396 passed, 1 warning`.

### Next Steps
1. Add a dedicated hybrid-runtime benchmark that isolates SSE frame encode, local TCP flush, queue handoff, provider transport reuse, and voice PCM scheduling as separate migration gates.
2. Prototype a Rust sidecar only for a narrow Shell-v2 transport shim once Rust tooling is intentionally added; keep Python as the AI/provider/tool orchestration layer.
3. Compare a Go sidecar for websocket/SSE supervision only if operational simplicity beats Rust/Tauri integration for that boundary.
4. Treat realtime PCM audio scheduling and persistent duplex websocket sessions as the highest-value future Rust candidates.
5. Keep provider SDKs, workflow orchestration, tool execution, and rapid AI experimentation in Python until profiling proves otherwise.

### Open Issues
- No native Rust/Go prototype was built in this cycle because the toolchains are not installed locally and the safe first step was architecture mapping plus a measurable Python transport improvement.
- Provider first-token and premium voice first-audio variance are still much larger than local Shell-v2 transport overhead.
- Shell is still PyQt-based today; Tauri migration should be a phased frontend/runtime program, not a direct replacement commit.
- Future native sidecars need explicit IPC ownership, lifecycle supervision, crash recovery, telemetry, and cleanup tests before they can become production runtime paths.

## Session: 2026-05-19

### Completed
- Ran an agent-first architecture cycle focused on moving Shell from a static tool registry toward bounded multi-agent orchestration.
- Researched current agent architecture patterns across OpenAI Agents SDK, Anthropic effective/managed agents, LangGraph-style supervisor routing, AutoGen, CrewAI, and OpenHands/OpenDevin.
- Added a deterministic `AgentFirstOrchestrator` that wraps existing backend tools as internal capabilities owned by specialist agents.
- Added 19 bounded orchestration agents, including realtime conversation, planner, voice, workflow, reasoning, research, browser, desktop automation, memory, vision, system monitoring, context, retrieval, coding, task execution, provider routing, multimodal, communication, and validator agents.
- Added a user-facing orchestrator tool so complex tasks can enter through the agent supervisor before any low-level capability executes.
- Updated Shell prompts so complex/cross-domain tasks prefer the agent orchestrator while simple one-step actions can still use direct tools.
- Updated catalog classification and cache versioning so the orchestrator appears as an agent boundary, not another ordinary tool.
- Extended latency and agent ecosystem probes to measure active agent-first orchestration.

### Changes Made
- Added `core/agent_orchestrator/` with the active agent-first routing layer and structured `AgentRoutePlan`.
- Added `shell_agent_orchestrator.py` with `orchestrate_shell_goal_tool` and `list_orchestration_agents_tool`.
- Updated `agent.py` to load the agent orchestrator ahead of the legacy static tool list.
- Updated `shell_prompts.py` with agent-first guidance.
- Updated `shell_tool_catalog.py` to classify the orchestrator as an agent boundary and invalidate old catalog cache.
- Updated `tools/latency_probe.py` and `tools/agent_ecosystem_audit.py` for active orchestrator validation.
- Added `tests/test_agent_first_orchestrator.py`.

### Current State
- Direct deterministic route baseline before this cycle: median `0.0335-0.0423 ms` for common commands.
- Agent-first orchestration after this cycle: median `0.1338-0.2073 ms`, p95 max `0.2433 ms` across math, desktop, browser/search, and coding-agent prompts.
- Measured overhead is roughly `0.10-0.17 ms`, which is low enough for realtime UI/voice routing while adding agent ownership, memory scopes, approval state, and traces.
- Catalog now reports `455` total capabilities with `40` agents.
- Active agent audit passes: `19` orchestration agents registered; reasoning routes through `reasoning_agent`; risky terminal capability requires approval and is not execution-allowed.
- Realtime checks stayed stable: `shell_v2.worker_cancel=0.376 ms`, `voice.turn_cancel=1.197 ms`, realtime session control overhead `0.017 ms`.
- Voice identity remains premium: Gemini `Aoede`, premium streaming voice enabled, cloud fallback disabled.
- UI probes passed: agents `37/37`; all-tools probe `ok=true`, `438` UI-visible items, `53` executed successfully, `291` safety-skipped, `0` errors.
- Full test suite passed: `402 passed, 1 warning`.
- Production release check passed with no blockers; warning only that local `.env` exists and must not be packaged.

### Next Steps
1. Route more existing `/agent` UI flows through `AgentFirstOrchestrator` so users increasingly see agent plans instead of raw tool names.
2. Add an agent trace panel showing selected agent, capability, approval state, memory scopes, and validation result.
3. Add a durable task queue for long-running workflow/coding/research agents before enabling background autonomy.
4. Add evaluator/validator passes for risky agent plans before execution, especially terminal, file-write, messaging, and desktop automation capabilities.
5. Start converting high-level tool categories into capability packs owned by agents while keeping the low-level functions available internally.

### Open Issues
- Existing LiveKit still receives the legacy large tool list for compatibility; the agent orchestrator is now first-class but not yet the only execution gateway.
- Background agents remain intentionally disabled until durable queues, cancellation, watchdogs, and UI-visible state are implemented.
- Memory binding is structured but not yet connected to encrypted/vector long-term memory adapters.
- Multi-agent collaboration is deterministic and bounded today; deeper LLM-based planning should be added only behind latency, safety, and observability gates.

## Session: 2026-05-19

### Completed
- Ran a full platform-evolution cycle focused on turning Shell AI OS readiness into a first-class, UI/chat-visible control plane.
- Researched current realtime and agent platform patterns across OpenAI Realtime, Gemini Live, LiveKit turn handling, Pipecat smart turn/interruption systems, OpenAI Agents SDK, Tauri, Tokio, and Go concurrency.
- Added a lightweight Shell platform supervisor that reports realtime, premium voice, agent orchestration, memory, multimodal, packaging, hybrid-runtime, and capability readiness in one redacted snapshot.
- Exposed the supervisor as a Shell tool and natural-language route for prompts like "show shell platform health".
- Added the platform supervisor to latency probes so AI OS readiness has a measurable runtime budget.
- Ran visible UI, chat, agent, all-tools, voice, live-provider, memory, release, and full-test validation.

### Changes Made
- Added `core/platform_supervisor/` with structured `PlatformDomainStatus`, `PlatformSnapshot`, and `ShellPlatformSupervisor`.
- Added `shell_platform_supervisor.py` with `shell_platform_status_tool`.
- Updated `agent.py` to load the platform status tool in the main assistant tool list.
- Updated `shell_nl_router.py` to route platform/runtime/Shell health requests to the supervisor.
- Updated `shell_tool_catalog.py` so platform/supervisor/runtime tools classify under system capabilities.
- Updated `tools/latency_probe.py` with `platform.supervisor_snapshot`.
- Added `tests/test_platform_supervisor.py`.

### Current State
- Platform supervisor snapshot reports `status=ready`, `score=88`, and domains: realtime, voice, agents, memory, multimodal, packaging, hybrid runtime.
- Supervisor latency is fast enough for UI diagnostics: `platform.supervisor_snapshot=8.215 ms`, internal `snapshot_ms=4.465 ms` after import warmup.
- Premium voice remains preserved: `backend=gemini_live_pcm`, `voice=Aoede`, `premium_voice_first=true`, `cloud_fallback_allowed=false`.
- Real visible voice validation passed: first audible premium Gemini Live PCM chunk `760.21 ms`, playback start `760.74 ms`, queue-to-first-audible `760.511 ms`, no fallback voice.
- Live Groq provider streaming passed: first chunk `168.395 ms`, completion `176.502 ms`, 3 chunks.
- Live Shell-v2 + Groq SSE passed: provider first token `136.614 ms`, first visible `144.55 ms`, provider-to-SSE `1.641 ms`, transport-to-worker `6.295 ms`.
- Gemini text live probe surfaced a quota/rate-limit response cleanly; Gemini Live voice still succeeded.
- Memory probe passed with provider transport cleanup: `after_close.session_count=0`, peak RSS `30.891 MB`.
- Visible UI e2e probe passed across chat, voice, system, tools, settings, calculator tool, screenshot unsupported state, and voice page controls.
- Chat UI probe passed: 5 app open commands, 5 close commands, 8 tool commands, 2 agent commands, 0 failures.
- Agents UI probe passed: `37/37` agents.
- All-tools UI probe passed: `439` UI-visible items, `53` executed successfully, `292` safety-skipped, `10` expected not-ready, `0` errors.
- Production release check passed with no blockers; warning only that local `.env` exists and must not be packaged.
- Agent ecosystem audit passed; remaining findings are planned architecture gaps, not regressions.
- Full test suite passed: `406 passed, 1 warning`.

### Next Steps
1. Add an in-app AI OS status panel that renders the platform supervisor domains with current score, risks, and next actions.
2. Hydrate the memory store through validated agent executions so the memory domain moves from attention to ready.
3. Unify screen/OCR/image observations into the agent context fabric so the multimodal domain becomes operational, not only available.
4. Add a provider-variance dashboard that separates quota/rate-limit failures from transport failures and recommends fallback routing.
5. Prototype persistent provider-native voice sessions only after adding explicit lifecycle, cleanup, and interruption tests.

### Open Issues
- Gemini text provider currently hits quota/rate-limit in live probes; Shell handles it cleanly, but provider availability is not guaranteed.
- OpenAI provider is not registered in this local environment, so OpenAI live text streaming was skipped.
- macOS reports this process is not trusted for Accessibility input monitoring; UI tests still passed, but real desktop-control polish needs Accessibility permission.
- Python 3.9 / LibreSSL warnings remain from local runtime dependencies and should be addressed in a packaging/runtime upgrade.
- The platform supervisor is read-only; it reports architecture readiness but does not yet drive an in-app status dashboard.

## Session: 2026-05-19

### Completed
- Reviewed the gap between backend reality and the visible UI: backend reports `456` capabilities, `399` tools, `40` agents, realtime/voice telemetry, readiness states, and platform-supervisor domains, while the UI mostly showed generic system charts and logs.
- Added a real AI OS Status panel to the System page so users can see the backend platform state directly.
- Wired the panel to `core.platform_supervisor.build_platform_snapshot(include_catalog=True)` through a dedicated Qt worker.
- Made the panel lazy-load on actual page visibility or manual Refresh to avoid background thread lifecycle issues in tests and offscreen page construction.
- Extended e2e UI validation so the probe fails if AI OS Status, score, capabilities, or Aoede identity are not rendered.

### Changes Made
- Updated `shell_ui/shell_cinematic_full.py` with `PlatformStatusWorker`, a System page AI OS Status card, platform domain chips, summary rendering, risk rendering, and lazy refresh lifecycle handling.
- Updated `tools/e2e_ui_probe.py` to verify the new backend-backed System page panel.
- Updated `tests/test_ui_working_smoke.py` with direct UI coverage for platform status rendering.

### Current State
- Visible UI e2e probe passed and confirmed the System page renders AI OS Status, score, backend capabilities, and Aoede voice identity.
- Platform supervisor remains fast in the latency probe: `platform.supervisor_snapshot=4.776 ms`, internal `snapshot_ms=2.525 ms`.
- Realtime probes remained stable: `shell_v2.worker_cancel=0.173 ms`, `voice.turn_cancel=1.692 ms`, realtime session control overhead `0.017 ms`.
- Premium voice identity remains stable: Gemini `Aoede`, premium streaming enabled, local/cloud fallback disabled.
- Production release check passed with no blockers; warnings remain for local `.env` and mac audio.
- Full test suite passed: `407 passed, 1 warning`.

### Next Steps
1. Add a dedicated Agents page that shows the 19 orchestration agents, the 40 agent tools, selected capability, approval state, and memory scopes.
2. Replace the generic Tools/MCP page with capability-group views: Ready, Needs API Key, Missing Dependency, Windows Only, Safety Blocked, Experimental.
3. Add a Voice Diagnostics page showing active TTS engine, Aoede identity, first-audible latency, interruption timing, and fallback state.
4. Add a Provider Routing page showing Gemini/Groq/OpenAI availability, quotas/rate limits, first-token latency, and fallback decisions.
5. Add a Memory/Context page showing local memory namespaces, record counts, recent validated memories, and reset/export controls.

### Open Issues
- The new panel is read-only; it surfaces backend state but does not yet provide drill-down actions for each domain.
- Agent orchestration, provider routing, voice diagnostics, and memory state still need dedicated UI panels to fully match backend reality.
- macOS Accessibility permission is still not granted, so some real desktop automation capabilities are constrained by OS trust settings.
- Python 3.9 / LibreSSL warnings remain and should be handled in a packaging/runtime modernization cycle.

## Session: 2026-05-19

### Completed
- Added a dedicated first-class Agents page so the UI now exposes Shell's real agent-first orchestration layer instead of hiding it inside generic Tools commands.
- Wired Agents into the sidebar, top-bar context labels, start-page environment hook, command palette, shortcut help, and end-to-end UI probe.
- Connected the Agents page to the real `AgentFirstOrchestrator` and capability catalog through a lazy Qt worker.
- Rendered orchestration agents, agent-tool counts, readiness totals, approval-gate state, and deterministic routing checks.
- Validated that Tools and Settings still route correctly after inserting Agents at page index `3`.

### Changes Made
- Updated `shell_ui/shell_cinematic_full.py` with `AgentStatusWorker`, `AgentsPage`, live stack wiring, context labels, start-map support, and updated keyboard-help labels.
- Updated `shell_ui/command_palette.py` with a `Go to Agents` action and shifted Tools/Settings shortcuts.
- Updated `shell_ui/shortcut_help.py` with Agents, Tools, and Settings navigation entries.
- Updated `tools/e2e_ui_probe.py` to validate the Agents page and shifted page indexes.
- Updated `tests/test_ui_working_smoke.py` with direct Agents page rendering coverage and `SHELL_START_PAGE=agents` coverage.

### Current State
- Agents page renders the real backend agent layer: `19` orchestration agents, agent-tool totals, approval state, and route checks.
- Offscreen e2e UI probe passed across chat, voice, system, agents, tools, settings, calculator tool, Windows-MCP unsupported state, and text chat.
- Visible e2e UI probe passed across chat, voice, system, agents, tools, settings, calculator tool, Windows-MCP unsupported state, and text chat.
- Dedicated agents UI probe passed: `37/37` agent commands.
- All-tools UI probe passed: `439` UI-visible items, `53` executed successfully, `40` agent-readiness-only, `292` safety-skipped, `10` expected not-ready, `0` errors.
- Production release check passed with no blockers; warnings remain for local `.env` and mac audio.
- Full test suite passed: `408 passed, 1 warning`.

### Next Steps
1. Upgrade the Tools/MCP page into capability-group views: Ready, Needs API Key, Missing Dependency, Windows Only, Safety Blocked, Experimental.
2. Add a Voice Diagnostics page for active TTS engine, Aoede identity, first-audible latency, interruption timing, and fallback state.
3. Add a Provider Routing page showing Gemini/Groq/OpenAI availability, first-token latency, quota/rate-limit state, and fallback decisions.
4. Add a Memory/Context page for local memory namespaces, record counts, recent memories, and reset/export controls.
5. Add drill-down actions from System and Agents cards into the relevant diagnostic pages.

### Open Issues
- Agents page is currently read-only; it exposes orchestration state but does not yet allow controlled agent execution from the dashboard.
- macOS Accessibility permission is still not granted, so real desktop-control polish remains constrained by OS trust settings.
- Python 3.9 / LibreSSL warnings remain from local runtime dependencies.

## Session: 2026-05-19

### Completed
- Ran the next autonomous product-evolution cycle against the Tools/MCP surface after the Agents page exposed the backend orchestration layer.
- Researched current realtime/agent UX patterns around explicit turn/interruption state, session readiness, and observable agent orchestration.
- Found and fixed a real UI lifecycle issue where the new readiness filter emitted before the Tools list layout existed.
- Added first-class capability readiness visibility to the Tools page so users can see backend state before executing a capability.
- Added direct-run gating so not-ready or unsafe capabilities are routed through chat/agent orchestration instead of being treated like ordinary safe buttons.

### Changes Made
- Updated `shell_ui/shell_cinematic_full.py` with Tools readiness chips, readiness-state filter, readiness/safety metadata in list rows, a selected-capability readiness detail panel, and direct-run gating.
- Updated `tools/e2e_ui_probe.py` so UI validation fails if Tools readiness controls are missing or direct-run gating regresses.
- Updated `tests/test_ui_working_smoke.py` with focused coverage for readiness chips, state filtering, not-ready run disabling, chat routing availability, and safe direct-run availability.

### Current State
- Tools page now surfaces real backend readiness counts: Ready, Needs API, Missing dep, Windows, Safety, Experimental.
- Offscreen e2e UI probe passed and confirmed Tools readiness summary, state filter, not-ready direct-run disablement, and ready-safe direct-run enablement.
- Visible e2e UI probe passed with the same Tools readiness checks.
- All-tools UI probe passed: `439` items, `53` executed successfully, `40` agent-readiness-only, `292` safety-skipped, `10` expected not-ready, `0` errors.
- Latency probe passed; premium voice identity remains Gemini Live PCM/Aoede with premium voice first and cloud fallback disabled.
- Memory probe passed with provider transport cleanup: session count returned to `0` after close, peak RSS `30.969 MB`.
- Production release check passed with no blockers; warnings remain for local `.env` and mac audio.
- Full test suite passed: `409 passed, 1 warning`.

### Next Steps
1. Add a Voice Diagnostics page for active TTS engine, Aoede identity, first-audible latency, interruption timing, fallback state, and streaming voice health.
2. Add a Provider Routing page showing Gemini/Groq/OpenAI availability, first-token latency, quota/rate-limit state, fallback decisions, and provider variance.
3. Add a Memory/Context page for local memory namespaces, record counts, recent validated memories, reset/export controls, and agent memory bindings.
4. Add controlled execution actions to the Agents page with approval-gated run flows.
5. Modernize the local runtime away from Python 3.9/LibreSSL warnings in the packaging cycle.

### Open Issues
- Tools page is still a single two-pane surface; it now exposes readiness, but it does not yet provide dedicated drill-down pages per capability state.
- Direct-run gating is intentionally conservative: unsafe/not-ready tools must go through chat orchestration or readiness repair.
- macOS Accessibility permission is still not granted, so some desktop-control capabilities remain constrained by OS trust settings.
- Python 3.9 / LibreSSL warnings remain from local runtime dependencies.

## Session: 2026-05-19

### Completed
- Ran a safe first full-computer-control platform cycle focused on observability, readiness, and policy gates before adding any broader autonomous OS execution.
- Researched current computer-use architecture and safety patterns from OpenAI, Anthropic, Microsoft UI Automation, Apple Accessibility, and recent desktop-vision research.
- Added a unified computer-control readiness layer that reports OS-specific app control, input control, screen understanding, clipboard, Windows-MCP, macOS, Linux, and safety states.
- Added a user-visible Computer Control Status backend tool and deterministic natural-language route.
- Surfaced Computer Control in the AI OS Status panel so the UI now shows real desktop-control readiness alongside realtime, voice, agents, memory, packaging, hybrid runtime, and capabilities.
- Updated e2e UI validation so the System page fails if Computer Control readiness disappears.

### Changes Made
- Added `core/computer_control/readiness.py` and `core/computer_control/__init__.py`.
- Added `shell_computer_control.py` with `computer_control_status_tool`.
- Updated `core/platform_supervisor/supervisor.py` with a `computer_control` platform domain.
- Updated `shell_nl_router.py` with desktop/computer/screen control readiness routing while preserving AI OS status routing.
- Updated `shell_ui/shell_cinematic_full.py` System page summary and domain chips.
- Updated `tests/test_computer_control_readiness.py`, `tests/test_platform_supervisor.py`, and `tools/e2e_ui_probe.py`.

### Current State
- Computer-control snapshot on this machine reports `attention`, score `84`, platform `macos`.
- macOS app control and screen understanding are visible; input control remains intentionally attention-gated because Accessibility/Screen Recording trust must be granted by the user.
- Safety policy is explicit: observe first, no silent fallback, direct control requires confirmation, high-impact actions stay gated.
- Offscreen e2e UI probe passed and confirmed Computer Control appears in the System page.
- All-tools UI probe passed: `440` items, `53` executed successfully, `40` agent-readiness-only, `293` safety-skipped, `10` expected not-ready, `0` errors.
- Latency probe passed; platform supervisor now includes `computer_control` score `84` and status `attention`.
- Memory probe passed with peak RSS `30.891 MB`.
- Production release check passed with no blockers; warning remains for local `.env`.
- Full test suite passed: `413 passed, 1 warning`.

### Next Steps
1. Build a dedicated Desktop Agent plan loop: observe screen, propose actions, require confirmation, execute one step, capture screenshot, verify outcome.
2. Replace the placeholder macOS desktop adapter with a permission-aware `MacDesktopController` that reports Accessibility and Screen Recording state accurately.
3. Add an Automation Audit timeline in the UI for every screenshot, click, type, clipboard, app launch, and terminal-sensitive proposal.
4. Validate Windows-MCP end to end on a real Windows machine before claiming full Windows desktop control.
5. Prototype Linux X11 and Wayland adapters separately instead of assuming a single Linux desktop automation path.

### Open Issues
- This cycle intentionally added readiness and safety visibility, not new autonomous desktop execution.
- macOS Accessibility permission is still not trusted in the current UI probe run, so real input-event monitoring remains constrained by OS settings.
- OCR quality may be limited when optional OCR dependencies are missing.
- Python 3.9 / LibreSSL warnings remain from the local runtime environment.

## Session: 2026-05-19

### Completed
- Built the dedicated Desktop Agent loop foundation requested after the computer-control readiness cycle.
- Added observe-preview-confirm-execute-verify architecture for desktop control without enabling free-running automation.
- Added one-step-at-a-time Desktop Agent planning for screenshot, open app, close app, coordinate click, observed-element click, type text, and keyboard shortcut actions.
- Added explicit approval enforcement: execution is blocked unless `approved=True`, and `dry_run=True` remains the default.
- Added post-step verification requirements so each action asks for a fresh screenshot/OCR observation before continuing.
- Exposed Desktop Agent planning and single-step execution as user-visible system tools.
- Added deterministic natural-language routing for `desktop agent plan ...` commands.
- Added readiness reporting for the `desktop_agent_loop` group.

### Changes Made
- Added `core/computer_control/agent_loop.py`.
- Updated `core/computer_control/__init__.py` to export `DesktopAgentLoop`.
- Updated `core/computer_control/readiness.py` with `desktop_agent_loop` readiness.
- Updated `shell_computer_control.py` with `desktop_agent_plan_tool` and `desktop_agent_execute_step_tool`.
- Updated `shell_nl_router.py` with Desktop Agent plan routing.
- Updated `tests/test_computer_control_readiness.py` and `tests/test_platform_supervisor.py`.

### Current State
- Desktop Agent can plan `click Start Voice` from observed bounds into one guarded coordinate click with a fresh-screenshot verification requirement.
- Desktop Agent can plan `open calculator`, but execution is blocked without explicit approval and dry-runs by default.
- Computer-control platform score improved from `84` to `87`; status remains `attention` because real macOS Accessibility/Screen Recording permissions are still not trusted.
- Offscreen e2e UI probe passed.
- Visible e2e UI probe passed.
- All-tools UI probe passed: `442` items, `53` executed successfully, `40` agent-readiness-only, `295` safety-skipped, `10` expected not-ready, `0` errors.
- Latency probe passed; platform supervisor includes `computer_control` score `87`.
- Memory probe passed with peak RSS `31.25 MB`.
- Production release check passed with no blockers; warning remains for local `.env`.
- Full test suite passed: `416 passed, 1 warning`.

### Next Steps
1. Add a visible Automation Audit timeline showing every Desktop Agent plan, approval gate, dry-run, execution, and verification requirement.
2. Add an approval UI for Desktop Agent plans instead of requiring JSON/tool invocation.
3. Implement a permission-aware `MacDesktopController` that reports Accessibility and Screen Recording trust state precisely.
4. Add real post-step screenshot comparison for approved Desktop Agent execution.
5. Validate Windows-MCP Desktop Agent execution on a real Windows machine.

### Open Issues
- The Desktop Agent loop is intentionally conservative and does not yet run multi-step autonomous workflows.
- There is no dedicated UI approval timeline yet; plans are available through system tools and the readiness surface.
- macOS Accessibility permission remains untrusted in probes, so real input monitoring/control is constrained by OS permissions.
- Python 3.9 / LibreSSL warnings remain from the local runtime environment.

## Session: 2026-05-19

### Completed
- Ran a real-tester QA cycle across full pytest, visible/offscreen UI, chat workflows, voice, agents, tools, Shell-v2 streaming, latency, memory, release, repo, platform, and live provider probes.
- Validated visible Shell UI pages: Chat, Voice, System, Agents, Tools, and Settings.
- Validated chat-driven macOS app open/close flows, calculator/text tools, external integration status, OpenClaw search, agent-browser open/snapshot/close, and agent routing.
- Validated premium voice path: `gemini_live_pcm`, Aoede voice, premium voice first, cloud fallback disabled, first audible chunk around `780 ms`.
- Found a real streaming QA/runtime issue: provider error strings from fallback text providers could be treated as successful streaming chunks.
- Fixed streaming provider error normalization so Gemini/OpenAI/etc. error strings trigger fallback/failure instead of appearing as valid assistant output.
- Tightened live provider probe so provider error chunks no longer false-pass.

### Changes Made
- Updated `brain/core.py` with shared provider-error detection for normal chat, streaming providers, and non-streaming streaming fallback.
- Updated `tools/live_provider_stream_probe.py` with `provider_error` detection and stricter `ok` semantics.
- Updated `tests/test_streaming_first_token.py` with coverage for non-streaming fallback error strings and true-streaming first error chunks.

### Current State
- Full test suite passed: `418 passed, 1 warning`.
- Targeted streaming tests passed: `6 passed`.
- Offscreen e2e UI probe passed after the fix.
- Visible e2e UI probe passed before the fix.
- Visible chat workflow probe passed: `5` apps opened, `5` apps closed, `8` tool commands, `2` agent commands, `0` failures.
- Agents UI probe passed: `37/37`.
- All-tools UI probe passed after the fix: `442` total, `53` executed successfully, `295` safety-skipped, `10` expected not-ready, `0` errors.
- Shell-v2 elevated bridge probe passed after the fix: first visible `17.27 ms`, provider-to-SSE `1.052 ms`, completion `39.49 ms`.
- Latency probe passed; sandbox-only `shell_v2.connect_1s` network sample remains blocked unless elevated.
- Memory probe passed after the fix: peak RSS `31.484 MB`.
- Production release check passed with no blockers; warning remains for local `.env`.
- Production readiness passed: `100/100`.
- Repo audit passed: `100/100`.
- Live Gemini text provider probe now correctly fails on quota/rate-limit response instead of false-passing.
- Live Groq provider probe passed: first chunk `169.384 ms`, `17` chunks, completion `219.868 ms`.

### Next Steps
1. Add provider-health UI so quota/rate-limit states are visible to users before a provider is selected.
2. Prefer a healthy streaming text provider automatically when Gemini text is quota-limited while preserving Gemini Live/Aoede for voice.
3. Add signed-release setup documentation/actions for Apple Developer ID notarization and Windows Authenticode.
4. Run Windows acceptance on a real Windows desktop/RDP host.
5. Upgrade local runtime packaging away from Python 3.9/LibreSSL warnings.

### Open Issues
- Gemini text generation key is currently quota/rate-limited; Groq live text streaming is healthy.
- Signing/notarization remains blocked without Apple Developer ID/notary credentials and Windows signing tooling/credentials.
- Windows acceptance is blocked on this macOS host by design; elevated non-Windows probe validates hub/UI/voice/agents but cannot replace real Windows UAT.
- macOS Accessibility permission remains untrusted in probes, so some desktop-control capabilities remain OS-gated.
- Python 3.9 / LibreSSL warnings remain from the local runtime environment.

## Session: 2026-05-19

### Completed
- Investigated the reported issue where Shell's real premium voice could be heard twice.
- Traced the duplicate path to voice streaming orchestration: incremental TTS chunks could play while Shell-v2 also emitted the final full reply for the same turn.
- Added turn-level guards so a voice turn that has already streamed audio cannot route the final Shell-v2 reply through full-reply TTS again.
- Added protection against late chunk signals after a streamed turn has already finalized.
- Added regression coverage for the problematic signal ordering.

### Changes Made
- Updated `shell_ui/shell_cinematic_full.py` so streamed Shell-v2 voice turns finalize through the streaming path and do not double-speak the full reply.
- Updated `tests/test_realtime_voice_session.py` with a fake TTS recorder test proving the final full reply is not spoken after streamed audio.

### Current State
- Targeted voice tests passed: `51 passed, 1 warning`.
- Visible voice validation passed: backend `gemini_live_pcm`, voice `Aoede`, first audible `842.24 ms`, first playback `842.88 ms`.
- Full test suite passed: `419 passed, 1 warning`.
- E2E UI probe passed.
- Latency probe passed; sandbox-only `shell_v2.connect_1s` remains blocked unless elevated.
- Production release check passed with no blockers; warning remains for local `.env`.

### Next Steps
1. Add a live voice-session probe that simulates Shell-v2 chunk/end/reply signal reordering directly through the UI worker.
2. Add user-visible voice playback telemetry showing queued segments versus final full reply suppression.
3. Add optional audio-device diagnostics for macOS `AudioQueueStart failed (-66680)` cases.

### Open Issues
- macOS Accessibility permission remains untrusted in probes, so some desktop-control capabilities remain OS-gated.
- Python 3.9 / LibreSSL warnings remain from the local runtime environment.
- Local `.env` exists and must not be included in public release packages.

## Session: 2026-05-19

### Completed
- Added a provider/voice observability cycle so the System page now shows whether provider credentials are configured, whether the AI brain provider graph is loaded, and whether lazy startup is preserved.
- Added a dedicated `providers` domain to the AI OS platform supervisor snapshot.
- Added redacted provider runtime diagnostics that expose key names/counts and loaded provider names without exposing secret values.
- Verified the System UI visually; the status card now shows `Providers 4 keys · 0 loaded · lazy · Voice Aoede` on this machine.

### Changes Made
- Updated `shell_ai_runtime.py` with redacted provider key/runtime snapshot helpers.
- Updated `core/platform_supervisor/supervisor.py` with a provider readiness domain.
- Updated `shell_ui/shell_cinematic_full.py` to render provider status in the AI OS Status summary and domain chip grid.
- Updated `tools/e2e_ui_probe.py` to require provider status visibility.
- Added `tests/test_provider_runtime_snapshot.py`.
- Updated platform/UI smoke tests for provider-domain coverage.

### Current State
- Targeted provider/platform/UI tests passed: `16 passed`.
- Offscreen e2e UI probe passed and verified provider status, Aoede voice identity, agents, tools, chat, and voice page behavior.
- Latency probe passed with UI/provider runtime enabled; provider runtime init `2.829 ms`, provider transport reuse `0.595 ms`, platform snapshot score `88`.
- Memory probe passed with provider runtime/transport enabled; peak RSS `219.094 MB`, provider transport cleanup verified.
- Full test suite passed: `421 passed, 1 warning`.
- Production release check passed with no blockers; warning remains for local `.env`.

### Next Steps
1. Add live provider-health classification in the UI for quota-limited, auth-failed, and transient provider states.
2. Prefer healthy streaming text providers automatically while preserving Gemini Live/Aoede for premium voice identity.
3. Add a voice playback telemetry panel showing active backend, voice, queued segments, suppressed final replies, and first-audible timing.
4. Add a dedicated diagnostics page for macOS Accessibility/Screen Recording permissions and audio-device readiness.

### Open Issues
- Gemini text provider can still be quota-limited even when premium Gemini Live/Aoede voice works.
- macOS Accessibility permission remains untrusted in probes, so some desktop-control capabilities remain OS-gated.
- Python 3.9 / LibreSSL warnings remain from the local runtime environment.
- Local `.env` exists and must not be included in public release packages.

## Session: 2026-05-23

### Completed
- Updated Shell Web UI per user correction: API key management stays inside `SETTINGS > API KEYS`; no separate API tab was added.
- Added a new top-level `CONTROL` tab for backend-accessible tools, agents, and actions.
- Added Dashboard Transcript chat input so typed messages can call lightweight natural-command backend routing from the UI.
- Added a Dashboard chart prompt/card inside the Transcript panel.
- Reworked Dashboard/Settings/Control overflow behavior to use scrollable panels instead of shrinking the visual design.

### Changes Made
- Updated `shell_web_ui/src/views/Dashboard.tsx` with transcript chat, chart prompt, scrollable left stack, and restored lower control dock placement.
- Added `shell_web_ui/src/views/ControlCenter.tsx` and wired it into `shell_web_ui/src/UI/ShellAI.tsx`.
- Expanded `shell_web_ui/src/views/Settings.tsx` API Keys section for Shell-required provider keys: Gemini, Groq, Hugging Face, Tavily, LiveKit, OpenAI, OpenRouter, Mistral, Google Search, CSE, and OpenWeather.
- Expanded `shell_web_ui/host.py` bridge channels for `chat-message`, `get-capabilities`, `execute-tool`, `list-api-keys`, and fuller `secure-save-keys`.
- Added `TAVILY_API_KEY` to `.env.example` and the API manager allowlist.
- Updated `tools/real_web_ui_cdp_probe.mjs` to test the new Control tab, chart prompt, and transcript prompt from the actual rendered UI.

### Current State
- Python syntax validation passed for `shell_web_ui/host.py`, `shell_api_manager.py`, and `launch.py`.
- `npm run build` passed after the new UI changes.
- Real visible QWebEngine UI validation passed via CDP: `18/18` steps, `0` console errors.
- Final report: `.shell_runtime/real_web_ui_cdp_probe_final_scroll_control/report.json`.
- Final screenshots: `.shell_runtime/real_web_ui_cdp_probe_final_scroll_control/`.

### Next Steps
1. Decide whether the `CONTROL` tab should execute guarded tools directly or require an extra confirmation modal.
2. Wire free-form transcript chat to the full production AI brain after the user confirms preferred behavior; current implementation routes known natural commands and avoids heavy agent imports for stability.
3. Optimize the large web bundle and lazy-load heavier visual/vision dependencies.

### Open Issues
- The Vite build still warns about a large main chunk and browser-externalized `fs` from `face-api.js`; non-blocking.
- Full voice runtime start/stop is still scaffolded at the bridge layer.
- Existing unrelated deleted files are still present in the worktree and were not reverted.

## Session: 2026-05-22

### Completed
- Analyzed an external assistant UI reference and extracted transferable dashboard, voice, memory, codebase, remote-access, and automation patterns.
- Mapped the reference architecture into Shell-owned PyQt modules, preserving the existing Shell backend and safety boundaries.
- Replaced Shell's primary chat surface with a native PyQt Shell-style Neural OS dashboard while preserving Shell's backend APIs.
- Added Shell neural feature modules for streaming voice state, core memory, deep focus, remote access records, project scanning/coding assist, and background process inspection.
- Added docs and targeted tests for the migration.
- Implemented Phase 1 PyQtGraph telemetry charts for the System page with legacy QPainter rollback.
- Implemented Phase 1 wake-word/VAD pipeline scaffolding with openWakeWord and Silero VAD adapters behind default-off flags.
- Implemented Phase 2 Feature 3 pywinauto Windows automation layer behind `SHELL_PYWINAUTO_ENABLED=0`.
- Implemented Phase 2 Feature 4 Memory v2 behind `SHELL_MEMORY_V2_ENABLED=0`.
- Implemented Phase 2 Feature 5 offline sherpa-onnx STT fallback behind `SHELL_LOCAL_STT_ENABLED=0`.
- Implemented Phase 3 Feature 6 Project RAG v2 behind `SHELL_PROJECT_RAG_ENABLED=0`.
- Implemented Phase 3 Feature 7 Secure Coding Sandbox behind `SHELL_SECURE_SANDBOX_ENABLED=0`.
- Implemented Phase 3 Feature 8 Agent Workflow Checkpoints behind `SHELL_WORKFLOW_CHECKPOINTS_ENABLED=0`.

### Changes Made
- Added `shell_ui/neural_dashboard.py`.
- Updated `shell_ui/design_tokens.py` to use the Shell near-black + emerald CYBER_NEON palette.
- Updated `shell_ui/shell_cinematic_full.py` for Shell branding, dashboard routing, and Shell feature phrase detection.
- Updated `shell_ui/shell_cinematic_full.py` so System telemetry charts select `PyQtGraphLineChart` by default and preserve `_LegacyLiveLineChart` behind `SHELL_PYQTGRAPH_ENABLED=0`.
- Added `shell_voice_pipeline.py` with `VoicePipelineManager`, openWakeWord adapter, Silero VAD adapter, fake-detector hooks, false-positive measurement, and state snapshots.
- Updated `shell_voice_listener_runtime.py` to route mic input through optional wake-word and VAD stages while preserving the existing timing endpoint fallback.
- Updated `shell_ui/shell_cinematic_full.py` with wake-word sensitivity settings and voice pipeline interrupt handoff.
- Updated `shell_settings_manager.py`, `requirements.txt`, `shell_ui/requirements_ui.txt`, and `installer/bootstrap.py` for wake-word/VAD settings and optional dependencies.
- Added `core/automation/windows_pywinauto.py` with a Windows-only pywinauto driver for app launch/focus/close/minimize/maximize/resize/window listing and a common Notepad/Calculator/File Explorer test plan.
- Updated `shell_window_CTRL.py` to try pywinauto first on Windows when enabled, while preserving pywin32/pygetwindow/PyAutoGUI fallbacks.
- Updated `core/computer_control/readiness.py` and `installer/bootstrap.py` with pywinauto readiness/dependency metadata.
- Added `core/memory/v2.py` with local SQLite storage, redaction-before-write, tags, importance scoring, time decay, recall audit logs, soft deletes, and legacy JSON migration.
- Added `shell_memory_v2.py` with `save_memory()`, `recall_memory()`, `forget_memory()`, migration/status helpers, and discoverable Memory v2 tools.
- Updated `shell_memory.py` so existing memory tools route to Memory v2 when `SHELL_MEMORY_V2_ENABLED=1`, while legacy JSON remains the default path.
- Updated `agent.py` to expose Memory v2 tools in the main agent tool list.
- Added `shell_local_stt.py` with a lazy sherpa-onnx streaming recognizer, auto model path detection, local-primary mode, fallback status tool, and fake-testable streaming API.
- Updated `shell_voice_listener_runtime.py` so SpeechRecognition API errors can fall back to local STT when enabled; `SHELL_LOCAL_STT_PRIMARY=1` tries sherpa-onnx first and falls back to the API path on local load failure.
- Updated `requirements.txt`, `shell_ui/requirements_ui.txt`, `installer/bootstrap.py`, and `core/health/startup.py` with `sherpa-onnx>=1.12.38` / `sherpa_onnx` readiness metadata.
- Added `core/project_rag/` with incremental SQLite indexing, `.gitignore`-style ignore rules, supported code/doc extension scanning, chunking, optional embeddings, and lexical BM25 fallback.
- Added `shell_project_rag.py` with index/query/status tools and wired Project RAG v2 into Shell coding assistance when enabled.
- Updated `agent.py`, `requirements.txt`, `installer/bootstrap.py`, and `core/health/startup.py` with Project RAG tools and optional `rank-bm25` / `sentence_transformers` metadata.
- Added `core/secure_sandbox.py` with isolated per-run workspaces, timeout enforcement, environment secret scrubbing, rollback cleanup, redacted audit logging, and a Python network import guard.
- Added `shell_secure_sandbox.py` with sandbox run/status tools and wired the sandbox into `shell_terminal.py`, `shell_code_engine.py`, and `agent.py` when `SHELL_SECURE_SANDBOX_ENABLED=1`.
- Updated `requirements.txt`, `installer/bootstrap.py`, and `core/health/startup.py` with optional `docker` metadata for a future container-backed sandbox path.
- Added `core/workflow_checkpoints.py` with SQLite/JSON checkpoint storage, last-action workflow state, resume loading, rollback checkpoint creation, pruning, and event publication.
- Added `shell_workflow_checkpoints.py` with public `save_checkpoint()`, `load_checkpoint()`, and `rollback()` APIs plus discoverable workflow checkpoint tools.
- Updated `agent.py` to expose workflow checkpoint save/load/rollback/status tools in the main tool list.
- Added `tests/test_workflow_checkpoints.py`.
- Added `shell_neural_voice.py`, `shell_core_memory.py`, `shell_focus_mode.py`, `shell_remote_access.py`, `shell_coding_assist.py`, and `shell_process_inspector.py`.
- Added `docs/SHELL_NEURAL_INTEGRATION_REPORT.md` and `docs/SHELL_PERFORMANCE_BENCHMARK.md`.
- Updated `README.md` with Shell UI migration documentation links and the PyQtGraph rollback flag.
- Updated `requirements.txt`, `requirements-ci.txt`, and `shell_ui/requirements_ui.txt` with `pyqtgraph>=0.13.7`.
- Added `openwakeword>=0.6.0` and `silero-vad>=5.1.2` to full/UI requirements.
- Added `pywinauto>=0.6.8; sys_platform == "win32"` to full requirements.
- Added `tests/test_neural_shell_integration.py`, `tests/test_pyqtgraph_telemetry_charts.py`, and `tests/test_voice_pipeline_manager.py`.
- Added `tests/test_pywinauto_windows_driver.py`.

### Current State
- Targeted validation passed: `18 passed in 1.01s` for `tests/test_neural_shell_integration.py`, `tests/test_low_latency_interaction.py`, and `tests/test_ui_working_smoke.py`.
- PyQtGraph chart validation passed: `3 passed in 0.46s` after installing `pyqtgraph==0.13.7` in `.codex_ui_venv`.
- Targeted Neural UI/latency regression passed with PyQtGraph backend: `21 passed in 2.56s`.
- PyQtGraph telemetry micro-benchmark: `0.138 ms` average and `2.785 ms` max over 200 offscreen updates, below the `<50 ms` target.
- Voice pipeline manager/listener tests passed: `10 passed in 0.65s` initially, then `62 passed, 1 warning` across pipeline, listener, latency, page layout, realtime session, and TTS policy regression tests.
- Final targeted Phase 1 regression passed: `84 passed, 1 warning` across voice pipeline, listener extraction, voice latency, voice UI, realtime session, chat TTS policy, UI smoke, Shell neural integration, PyQtGraph charts, and low-latency interaction tests.
- Silero VAD real dependency smoke passed after installing `silero-vad==5.1.2`: `0.127 ms` average and `0.502 ms` max over 40 silent 512-sample frames.
- openWakeWord real package installed and adapter smoke tested. Default "Hey Shell" correctly falls back to button mode because openWakeWord does not ship a built-in "Hey Shell" model; deployment requires `SHELL_WAKE_WORD_MODEL_PATHS`.
- pywinauto driver targeted tests passed on fake Windows wrappers: `41 passed in 1.34s`; compile validation clean.
- pywinauto/computer-control/security/UI regression passed: `65 passed, 1 warning`.
- Real pywinauto app-control success rate is not measured on this macOS host; Notepad/Calculator/File Explorer plan is ready for Windows validation.
- Memory v2 tests passed: `8 passed`.
- Memory v2/SHELL/pywinauto/readiness/NL/security/UI regression passed: `74 passed, 1 warning`.
- Memory v2 micro-benchmark: save `1.403 ms` average over 200 inserts; recall `4.103 ms` average and `4.603 ms` max over 100 recalls against 200 memories.
- Local STT focused regression passed: `50 passed, 1 warning` across local STT, voice listener extraction, voice pipeline, and voice latency tests.
- Local STT/installer/platform/security/UI regression passed with unrelated launcher assertion deselected: `93 passed, 1 deselected, 1 warning`.
- Local STT fake-recognizer micro-benchmark: `0.011 ms` average and `0.030 ms` max adapter overhead over 100 transcribes. Real model latency still requires a downloaded sherpa-onnx model.
- Project RAG focused regression passed: `15 passed`.
- Memory/voice/local STT/Project RAG/SHELL/pywinauto/readiness/NL/security/UI regression passed with unrelated launcher assertion deselected: `111 passed, 1 deselected, 1 warning`.
- Project RAG micro-benchmark: index `10.298 ms` for 120 files / 120 chunks; query `1.304 ms` average and `1.478 ms` max over 100 lexical queries.
- Secure Sandbox compile validation passed for `core/secure_sandbox.py`, `shell_secure_sandbox.py`, `shell_terminal.py`, `shell_code_engine.py`, `agent.py`, `installer/bootstrap.py`, and `core/health/startup.py`.
- Secure Sandbox focused regression passed: `25 passed, 1 warning` across sandbox, tool catalog, and security regression tests.
- Secure Sandbox broad regression passed with unrelated launcher assertion deselected: `120 passed, 1 deselected, 1 warning`.
- Secure Sandbox micro-benchmark: isolated Python run `21.771 ms` average and `23.449 ms` max over 20 runs with 0 failures.
- Workflow Checkpoints compile validation passed for `core/workflow_checkpoints.py`, `shell_workflow_checkpoints.py`, and `agent.py`.
- Workflow Checkpoints focused regression passed: `8 passed`.
- Workflow Checkpoints broad regression passed with unrelated launcher assertion deselected: `128 passed, 1 deselected, 1 warning`.
- Workflow Checkpoints micro-benchmark: SQLite save `1.931 ms` average, load `0.335 ms` average, rollback `1.878 ms` average.
- Python compile validation passed for all new Shell neural modules using `PYTHONPYCACHEPREFIX=/private/tmp/shell_pycache`.
- Latency probe passed overall. Latest local observations include fast local chat candidate `0.312 ms`, local reply `0.002 ms`, streaming first-token provider metric `11.111 ms`, and voice realtime control overhead `0.016 ms`.
- Sandbox blocked the direct local Shell-v2 socket sample with `Operation not permitted`; mocked SSE and provider streaming probes passed.

### Next Steps
1. Capture fresh visible screenshots for the new Shell dashboard and replace the old public showcase screenshots.
2. Wire real remote tunneling only after choosing an approved tunnel provider and safety policy.
3. Add optional OS-level focus automation for notification muting/app blocking behind explicit user approval.
4. Add a real microphone partial-transcript bridge into `shell_neural_voice.VOICE_COORDINATOR`.
5. Add or train a real openWakeWord "Hey Shell" model and set `SHELL_WAKE_WORD_MODEL_PATHS` before enabling wake-word mode by default.
6. Validate pywinauto against Notepad, Calculator, and File Explorer on a real Windows desktop/RDP session.
7. Capture fresh visible screenshots for the new Shell dashboard and replace the old public showcase screenshots.
8. Run full test suite on a machine with the complete dependency set before release packaging.

### Open Issues
- True `0 ms` latency is physically impossible; current implementation uses streaming-first updates and records first partial/response timings.
- Browser-only optimizations such as Service Workers, IndexedDB, Web Workers, and WebAssembly are not directly applicable to the PyQt desktop surface.
- Remote access is currently safe session tracking plus localhost port checks, not public tunneling.
- Existing unrelated deleted files are present in the worktree and were not reverted.
- `tests/test_installer_bootstrap.py::test_mac_launchers_use_bootstrap_directly` fails if run because `Start_ShellAI.command` is missing in the current worktree; this predates the Offline STT work and was not recreated.
- Wake-word mode remains default-off and requires a custom "Hey Shell" model path for real activation.
- pywinauto mode remains default-off and still needs real Windows UAT for the 90% app-control success target.
- Memory v2 remains default-off pending user migration validation from legacy JSON memory.
- Offline STT remains default-off and needs a real sherpa-onnx model directory for end-to-end microphone latency and accuracy validation.
- Project RAG v2 remains default-off; semantic embedding quality requires installing `sentence-transformers` and selecting an available embedding model.
- Secure Sandbox remains default-off. Timeout, rollback, env scrubbing, and audit logs are validated locally; network isolation is a Python import guard until a Docker/bubblewrap backend is explicitly added and enabled.
- Workflow Checkpoints remain default-off. SQLite/JSON persistence and rollback APIs are validated locally; post-crash resume still needs a user-facing UI prompt after app restart.

## Session: 2026-05-22

### Completed
- Removed all project-visible legacy external UI branding strings and filenames from code, tests, docs, README, and session notes.
- Renamed the dashboard and feature modules to Shell-owned neutral names.
- Updated tool function names, imports, env vars, docs, and tests to use Shell Neural/Core naming.
- Verified no remaining case-insensitive legacy branding references with repository-wide `rg` scans.

### Changes Made
- Renamed `shell_ui/neural_dashboard.py` as the primary Shell Neural dashboard module.
- Renamed feature modules to `shell_neural_voice.py`, `shell_core_memory.py`, `shell_focus_mode.py`, `shell_remote_access.py`, `shell_coding_assist.py`, and `shell_process_inspector.py`.
- Renamed docs to `docs/SHELL_NEURAL_INTEGRATION_REPORT.md` and `docs/SHELL_PERFORMANCE_BENCHMARK.md`.
- Renamed integration tests to `tests/test_neural_shell_integration.py`.
- Updated `shell_ui/shell_cinematic_full.py`, `README.md`, docs, and tests to remove old branding and use Shell Neural labels.

### Current State
- Repository-wide text scan for the removed brand returns no matches.
- Repository filename scan for the removed brand returns no matches.
- Syntax validation passed for renamed Shell Neural modules and UI files.
- Focused regression passed: `25 passed`.
- Broad Phase regression passed with unrelated launcher assertion deselected: `128 passed, 1 deselected, 1 warning`.

### Next Steps
1. Relaunch Shell UI and visually confirm the top bar/window title use Shell branding.
2. Replace old public screenshots with fresh Shell Neural UI screenshots.

### Open Issues
- Existing unrelated deleted files are still present in the worktree and were not reverted.
- `tests/test_installer_bootstrap.py::test_mac_launchers_use_bootstrap_directly` remains deselected because `Start_ShellAI.command` is missing in the current worktree.

## Session: 2026-05-23

### Completed
- Ran a full safe tool/agent QA sweep after the user requested deep testing of all tools and agents.
- Fixed `tools/agents_ui_probe.py` so nested report paths create their parent directory before writing.
- Added a safe local UI-smoke response path for `shell_agent_tools:deploy_swarm_tool` so swarm readiness tests do not falsely fail when cloud AI providers or network access are unavailable.
- Fixed the Web UI bridge startup race that could make the first Dashboard `CLEAR` click clear only local fallback history instead of backend history.
- Rebuilt and relaunched the Shell Web UI with the bridge timing fix.
- Updated the chart/transcript focused probe to accept the current concise `Memory in Python...` answer wording.

### Changes Made
- Updated `shell_agent_tools.py`.
- Updated `tests/test_agent_safety.py`.
- Updated `tools/agents_ui_probe.py`.
- Updated `shell_web_ui/src/shellBridge.ts`.
- Updated `tools/chart_transcript_ui_probe.mjs`.
- Rebuilt `shell_web_ui/dist/`.

### Current State
- Tool catalog QA passed: `468` catalog entries audited, `62` safe tools executed, `40` agents readiness-only, `10` expected-not-ready, `312` safety-skipped, `44` environment-skipped, `0` unexpected errors.
- Agents UI QA passed: `38/38` agents passed, including `DeploySwarm`.
- Real Web UI deep probe passed: `30/30` click/type/screenshot checks, `0` console events.
- Chart/transcript focused probe passed: `7/7`, including initial clear, normal questions, explicit chart prompt, calculator route, and text-mode no-voice policy.
- Targeted tests passed: `tests/test_agent_safety.py` `11 passed`; `tests/test_nl_router.py` `23 passed`.
- Python compile validation passed for updated Python probe/backend files.
- Shell Web UI is running visibly on debug port `9235`.

### Next Steps
1. For real external actions such as YouTube playback, email/Telegram sending, downloads, or terminal execution, run manual tests only after the relevant API keys/safety flags are intentionally enabled.
2. For website/code generation, explicitly enable `SHELL_ALLOW_CODE_WRITE=1` in `.env` before expecting Shell to write generated files.
3. Optimize remaining large Vite bundle warnings in a later performance pass.

### Open Issues
- Several catalog entries are correctly marked `NEEDS_API_KEY`, `MISSING_DEPENDENCY`, `WINDOWS_ONLY`, `BLOCKED_BY_SAFETY`, or `EXPERIMENTAL`; these were not force-executed.
- macOS Accessibility permission remains required for some real desktop-control input actions.
- Vite still reports non-blocking large-chunk and `face-api.js` browser `fs` externalization warnings.

## Session: 2026-05-23

### Completed
- Investigated why normal user commands like `song play karo` and `website banao ...` were falling through instead of controlling Shell tools.
- Added deterministic NL routes for generic music/video playback commands without requiring the word `YouTube`.
- Added deterministic NL routes for direct website/webpage/site creation prompts so they reach the code-engine scaffold tool.
- Improved web UI chat formatting for safety-blocked website/code creation so the user sees a clear reason instead of a confusing generic tool response.
- Restarted the visible Shell Web UI so the updated router/backend is loaded.

### Changes Made
- Updated `shell_nl_router.py` with generic media playback routing and direct website scaffold routing.
- Updated `tests/test_nl_router.py` with regression coverage for `song play karo` and `website banao landing page for bakery`.
- Updated `shell_web_ui/host.py` to present code-write safety blocks clearly in chat/chart replies.

### Current State
- `tests/test_nl_router.py`: `23 passed`.
- Python compile validation passed for `shell_web_ui/host.py` and `shell_nl_router.py`.
- Route probe confirms:
  - `song play karo` -> `shell_browser_CTRL:play_youtube_video`.
  - `website banao landing page for bakery` -> `shell_code_engine:create_fullstack_app_tool`.
  - `make a website for calculator` -> `shell_code_engine:create_fullstack_app_tool`.
  - `open calculator` remains routed to `shell_window_CTRL:open_app`.
- Chat backend smoke confirms website creation returns a clear blocked message while `SHELL_ALLOW_CODE_WRITE` is off.
- Shell UI is running on Qt WebEngine remote debugging port `9235`.

### Next Steps
1. If trusted website/code generation is desired, explicitly enable `SHELL_ALLOW_CODE_WRITE=1` in `.env`, restart Shell, and test scaffold output in an isolated workspace.
2. UI-test the real `song play karo` flow from the Shell window, accepting that it will open YouTube or a browser search.
3. Continue expanding direct NL routes for other common Hinglish commands as they are found.

### Open Issues
- Website/code file writing remains intentionally disabled until the safety flag is explicitly enabled.
- Real YouTube playback was not triggered in the automated test to avoid unexpectedly opening/playing media.

## Session: 2026-05-23

### Completed
- Performed a real visible Shell Web UI QA pass through the launched PyQt WebEngine app using the CDP probe.
- Tested the primary UI tabs one by one: Dashboard, Macros, Apps, Notes, Gallery, Phone, Control, and Settings.
- Tested the Settings subtabs: System, General, API Keys, and Security.
- Verified Notes create/save from the UI path.
- Verified Dashboard transcript prompt from the UI path with `calculate 2+2`, which returned `4`.
- Verified Dashboard chart prompt from the UI path.
- Verified voice start/stop from the UI path; the Dashboard entered the real `LISTENING` voice state.
- Removed the duplicate chart prompt surface by keeping one dashboard chart panel and one shared transcript input with separate chart/send actions.
- Fixed dashboard chart/transcript placement so the chart stays inside the transcript area instead of creating another competing input.
- Fixed Macros sidebar toggle placement so it anchors at the sidebar edge.
- Fixed Phone tab spacing so the new-device card is visible and not cut off.
- Wired the web UI voice controls into the production `VoiceListenerThread` runtime instead of only emitting bridge scaffold events.

### Changes Made
- Updated `shell_web_ui/host.py` with real voice runtime start/stop, coordinator usage, voice status events, transcript forwarding, amplitude events, latency events, and graceful error handling.
- Updated `shell_web_ui/src/IndexRoot.tsx` to track backend voice state and reflect real LISTENING/STOPPED/ERROR statuses in the UI.
- Updated `shell_web_ui/src/UI/ShellAI.tsx` to pass backend voice state into the Dashboard.
- Updated `shell_web_ui/src/views/Dashboard.tsx` to consolidate chart and transcript input behavior and improve chart visibility/status text.
- Updated `shell_web_ui/src/views/WorkFlowEditor.tsx` to correct the sidebar toggle position.
- Updated `shell_web_ui/src/views/Phone.tsx` to reduce oversized vertical spacing and keep device cards visible.
- Updated `SESSION_LOG.md` with the latest visible UI QA state.

### Current State
- `npm run build` passes for `shell_web_ui/`.
- Python syntax validation passes for `shell_web_ui/host.py`, `shell_api_manager.py`, and `launch.py`.
- Final real UI deep probe passed: `18/18` steps, `0` failed, `0` console events.
- Probe report: `.shell_runtime/real_web_ui_deep_probe_final_alltabs/report.json`.
- Probe screenshots: `.shell_runtime/real_web_ui_deep_probe_final_alltabs/`.
- Main voice listener dependencies are available and the UI reached `TRANSCRIPT LISTENING`.

### Next Steps
1. Install/configure the offline STT dependency if offline speech fallback is required in this environment.
2. Optimize remaining Vite large-chunk warnings with code splitting.
3. Re-run a longer manual microphone dictation pass with an available input device and real spoken commands.

### Open Issues
- `sherpa_onnx` is not installed, so the offline STT fallback is not active.
- Vite still reports non-blocking warnings for `face-api.js` browser-externalized `fs` and a large generated chunk.
- Existing unrelated deleted files remain in the worktree and were not reverted.

## Session: 2026-05-23

### Completed
- Added audible Shell voice output from the Web UI through a backend `speak-text` bridge.
- Added a Dashboard speaker button so the user can hear "Shell AI voice ready hai" directly from the UI.
- Made backend chat replies speak through local TTS after `chat-updated` events.
- Reworked Dashboard chart prompts so chart questions stay local, concise, and metric-focused instead of routing into long backend chat answers.
- Added short chart replies such as network/RAM/CPU/temp summaries and stored them in the transcript history.
- Reduced Dashboard clutter by removing the fake battery indicator, making top status meaningful, compacting the left rail, and fixing the blank optics/network/core metric sizing.
- Kept one chart panel and one shared transcript input with separate chart/send buttons.
- Extended the real UI CDP probe to verify the new Shell voice speaker button and concise chart response.

### Changes Made
- Updated `shell_web_ui/host.py` with `speak-text` and `stop-speech` channels using local OS TTS (`say` on macOS, PowerShell speech on Windows, `spd-say`/`espeak` on Linux).
- Updated `shell_web_ui/src/shellBridge.ts` and `shell_web_ui/src/env.d.ts` with speech bridge support and browser fallback speech synthesis.
- Updated `shell_web_ui/src/views/Dashboard.tsx` with concise chart replies, speech output, speaker control, compact left dashboard panels, and cleaner transcript controls.
- Updated `shell_web_ui/src/UI/ShellAI.tsx` to remove the fake battery readout and show a meaningful READY/LISTENING state.
- Updated `shell_web_ui/src/views/Settings.tsx` so Settings fills the available app viewport instead of forcing a nested screen height.
- Updated `tools/real_web_ui_cdp_probe.mjs` to test the speaker button and assert concise chart transcript output.
- Updated `SESSION_LOG.md` with the latest UI/voice/chart QA state.

### Current State
- Backend TTS smoke test returned success and started local speech output.
- `npm run build` passes for `shell_web_ui/`.
- Python syntax validation passes for `shell_web_ui/host.py`, `shell_api_manager.py`, and `launch.py`.
- Final real visible UI probe passed: `19/19` steps, `0` failed, `0` console events.
- Final probe report: `.shell_runtime/real_web_ui_deep_probe_voice_chart_cleanup_final2/report.json`.
- Final probe screenshots: `.shell_runtime/real_web_ui_deep_probe_voice_chart_cleanup_final2/`.

### Next Steps
1. Run a longer manual microphone dictation test with the user's actual mic selected and macOS microphone permissions confirmed.
2. Add code splitting for heavy renderer chunks to reduce the remaining Vite large-chunk warning.
3. Decide whether the optics panel should stay on Dashboard or move behind a vision-specific mode if the user wants an even cleaner voice/chart-only dashboard.

### Open Issues
- `sherpa_onnx` is still not installed, so offline STT fallback is not active.
- Vite still reports non-blocking warnings for `face-api.js` browser-externalized `fs` and a large generated chunk.
- Existing unrelated deleted files remain in the worktree and were not reverted.

## Session: 2026-05-23

### Completed
- Investigated why Shell voice was not audible to the user.
- Verified macOS volume was `100` and output mute was `false`.
- Verified `/usr/bin/say` and `/usr/bin/afplay` are present.
- Confirmed macOS `say` can render a valid AIFF file at `/private/tmp/shell_voice_test.aiff`.
- Found CLI playback failure: `afplay` returned `AudioQueueStart failed (-66680)`, so backend command-line playback cannot be trusted in this environment.
- Switched Shell Web UI speech to use browser/QWebEngine `speechSynthesis` first, with backend OS TTS kept as fallback.
- Rebuilt the web UI and relaunched Shell visibly.
- Clicked the Dashboard speaker button through the real UI; browser speech support was present and `speechSynthesis.speaking` became `true`.

### Changes Made
- Updated `shell_web_ui/src/views/Dashboard.tsx` so `speakShell()` uses browser speech first and falls back to the backend `speak-text` bridge only if needed.
- Updated `shell_web_ui/src/shellBridge.ts` so `window.shellAPI.speakText()` also prefers browser speech before Python backend speech.
- Updated `SESSION_LOG.md` with the audio diagnosis and browser speech fix.

### Current State
- `npm run build` passes for `shell_web_ui/`.
- Python syntax validation passes for `shell_web_ui/host.py` and `launch.py`.
- Visible Shell UI is launched for user testing on debug port `9233`.
- Speaker button click test succeeded at the UI level: `speechSynthesis.speaking: true`.

### Next Steps
1. User should click the Dashboard speaker button once in the visible Shell UI.
2. If no sound is heard while `speechSynthesis.speaking` is true, check macOS Sound Output and select real speakers/headphones instead of virtual devices such as BlackHole.

### Open Issues
- CLI playback via `afplay` fails with `AudioQueueStart failed (-66680)` in this environment.
- `sherpa_onnx` is still not installed, so offline STT fallback is not active.
- Vite still reports non-blocking warnings for `face-api.js` browser-externalized `fs` and a large generated chunk.

## Session: 2026-05-23

### Completed
- Ran the requested multi-agent UI review loop and converted the findings into a 5-loop fix/test cycle.
- Fixed Dashboard chart chat so normal questions are answered as text instead of being hijacked by telemetry keywords.
- Added a compact `CLEAR` button to the Dashboard transcript and made it clear persisted web UI history.
- Added visible `CHART` and `SEND` labels to the transcript controls.
- Fixed bridge startup races by waiting briefly for QWebChannel before falling back to browser-only handlers.
- Added backend `clear-history` and ADB fallback handlers so hidden PhoneView cannot crash the app during startup.
- Made TerminalOverlay lazy-render only when terminal output is visible, removing hidden terminal banner/PID text from the UI DOM.
- Added a dedicated chart/transcript UI probe for normal QA, telemetry charting, calculator command routing, text-only voice policy, and transcript clearing.
- Re-ran full real WebEngine UI QA after fixes.

### Changes Made
- Updated `shell_web_ui/src/views/Dashboard.tsx`.
- Updated `shell_web_ui/src/UI/ShellAI.tsx`.
- Updated `shell_web_ui/src/shellBridge.ts`.
- Updated `shell_web_ui/host.py`.
- Updated `shell_web_ui/src/views/Phone.tsx`.
- Rebuilt `shell_web_ui/src/components/TerminalOverlay.tsx` as a lazy overlay.
- Added `tools/chart_transcript_ui_probe.mjs`.
- Updated `tools/real_web_ui_cdp_probe.mjs`.
- Updated `README.md` with the web UI QA behavior and probe commands.

### Current State
- `npm run build` passes for `shell_web_ui/`.
- Python syntax validation passes for `shell_web_ui/host.py`.
- Dedicated chart/transcript probe passes: `7/7` functional steps, text mode voice counters remain `0`, hidden terminal text absent.
- Full real UI probe passes: `30/30` steps, `consoleEvents: 0`.
- Shell is running visibly on debug port `9235` for user testing.

### Next Steps
1. User can test Dashboard chart chat directly with normal questions, telemetry prompts, and OS/tool commands.
2. Continue security hardening for API-key redaction and guarded command confirmation in a later pass.
3. Consider code-splitting the large web UI bundle before release.

### Open Issues
- Vite still reports non-blocking warnings for `face-api.js` browser-externalized `fs` and a large generated chunk.
- Three.js emits an upstream deprecation warning for `THREE.Clock`; functional probes ignore warnings and fail only on errors/exceptions.
- Existing unrelated worktree changes remain untouched.

## Session: 2026-05-23

### Completed
- Corrected the voice route after the user clarified they want the real Shell/Gemini Live voice, not local/browser TTS.
- Verified the existing Gemini Live service already supports native audio output with Gemini voice names `Puck` and `Aoede`.
- Added runtime support so the PyQt Web UI can use Gemini Live voice by default instead of forcing the Python backend voice listener path.
- Added `GeminiLiveService.waitUntilReady()` and `GeminiLiveService.forceSpeak()` so the Dashboard speaker button can send a real Gemini Live prompt after the socket is open.
- Added a Settings > General voice runtime selector: `GEMINI LIVE` and `LOCAL FALLBACK`.
- Verified the current environment has no Gemini API key available, so real Gemini voice cannot connect until the user adds one.
- Rebuilt and relaunched Shell with the Gemini Live voice route enabled.

### Changes Made
- Updated `shell_web_ui/src/services/shell-voice-ai.ts` with Gemini socket readiness and force-speak helpers.
- Updated `shell_web_ui/src/IndexRoot.tsx` to default to `gemini` voice runtime and route start/stop/speaker actions through Gemini Live unless the user selects backend fallback.
- Updated `shell_web_ui/src/UI/ShellAI.tsx` to carry the new voice runtime props.
- Updated `shell_web_ui/src/views/Dashboard.tsx` so the speaker button asks Gemini Live to speak first when `GEMINI LIVE` is selected.
- Updated `shell_web_ui/src/views/Settings.tsx` with the voice runtime selector.
- Updated `SESSION_LOG.md` with the real voice routing state.

### Current State
- `npm run build` passes for `shell_web_ui/`.
- Python syntax validation passes for `shell_web_ui/host.py` and `launch.py`.
- Shell is relaunched with the new build on debug port `9235`.
- Gemini Live is now the default intended voice runtime.

### Next Steps
1. Add a Gemini API key in `Settings > API Keys > Gemini Pro Core`, then save all keys.
2. Return to Dashboard and press the speaker button or phone button to hear the real Gemini voice.
3. Keep remote audio forwarding enabled in Parsec/RDP, otherwise even real Gemini audio will not reach the local computer.

### Open Issues
- Gemini API key is currently missing, so real Gemini Live voice cannot connect yet.
- Remote audio forwarding is still a separate RDP/Parsec client-side requirement.
- Vite still reports non-blocking warnings for `face-api.js` browser-externalized `fs` and a large generated chunk.

## Session: 2026-05-23

### Completed
- Backed up the existing `shell_ui/` directory into `shell_ui_LEGACY/` without deleting the working legacy UI.
- Added `shell_web_ui/` as the new React/Vite/WebGL renderer and applied Shell AI branding throughout the imported renderer source.
- Removed remaining external assistant and personal branding strings from the new web renderer source.
- Added a PyQt WebEngine host with QWebChannel communication between the React UI and Shell's Python backend.
- Made `launch.py` default to the new Shell Web UI, with `SHELL_LEGACY_UI=1` rollback to the preserved PyQt UI.
- Documented the web renderer launch, dev server, build flow, bridge API, and rollback flags in `README.md`.

### Changes Made
- Added `shell_web_ui/host.py`, `shell_web_ui/src/shellBridge.ts`, `shell_web_ui/src/main.tsx`, renderer config files, package files, assets, and branded UI source.
- Updated `launch.py` to choose `ShellWebUI` by default and retain legacy PyQt launch behind an environment flag.
- Updated `README.md` with the Shell Web UI architecture, commands, and new environment flags.
- Updated this session log with the web renderer migration state.

### Current State
- `npm install --no-audit --no-fund --loglevel=info` completed for `shell_web_ui/`.
- `npm run build` passed in `1.49s`.
- Python syntax validation passed for `shell_web_ui/host.py` and `launch.py`.
- Bridge smoke test passed for system stats, installed apps, and voice-start request handling.
- Repository scan across `shell_web_ui`, docs, README, session log, and launcher returns no remaining old external UI brand strings.
- Local Vite server starts successfully with elevated localhost permission and reports ready in `116 ms`.
- Follow-up validation after launching Shell:
  - Targeted agent/tool/feature regression passed: `148 passed, 1 warning`.
  - Agents UI probe passed: `37/37` agents executed through the chat UI path.
  - All-tools UI probe passed across `468` catalog entries: `62` safe tools executed, `40` agents readiness-only, `10` expected-not-ready, `312` safety-skipped, `44` environment-skipped, `0` errors.
  - Shell Web UI build passed again in `1.41s`.
  - Shell Web UI bridge smoke passed for system stats, installed apps, running apps, history, secure keys, start voice, stop voice, and memory search.
  - Actual `launch.py` GUI smoke opened the default Shell AI Web UI successfully.
  - First GUI smoke exposed a CSP block for `qrc:///qtwebchannel/qwebchannel.js`; fixed by adding `qrc:` to the renderer CSP and replacing null IPC fallbacks with safe default values.
  - Second GUI smoke opened Shell AI Web UI without CSP/runtime bridge errors. Remaining console output was a non-blocking Three.js deprecation warning.
  - Latency probe passed overall; key observations included catalog discovery `79.642 ms`, local chat candidate `0.117 ms`, local reply `0.002 ms`, UI first paint `1607.407 ms`, provider runtime init `3.445 ms`, streaming first token `11.115 ms`, voice control overhead `0.017 ms`, and platform supervisor score `88`.

### Next Steps
1. Capture fresh screenshots/video for the Shell Web UI now that visible launch is working.
2. Wire `start-voice` and `stop-voice` bridge handlers into the full production voice runtime instead of the current request/emit scaffold.
3. Add code splitting for large renderer chunks, especially heavy widgets and face/vision dependencies.
4. Expand the bridge handlers for notes, gallery, terminal overlay, live coding, and widget-specific actions.
5. Run full regression after resolving the pre-existing missing launcher file in the worktree.

### Open Issues
- Visual screenshot automation could not complete through the in-app browser backend; visible `launch.py` GUI smoke did run successfully.
- The Vite build still warns about a large main chunk and browser-externalized `fs` from `face-api.js`; both are non-blocking but should be optimized before release.
- `start-voice` / `stop-voice` currently confirm bridge flow and emit UI events; full microphone pipeline start/stop wiring remains the next integration step.
- `tools/latency_probe.py` reports `shell_v2.connect_1s` as blocked by the sandbox's local socket permission, while mocked SSE/runtime/provider streaming checks pass.
- Existing unrelated deleted files are still present in the worktree and were not reverted.

## Session: 2026-05-22

### Completed
- Re-cloned and deeply analyzed the approved external assistant UI repository in `/private/tmp`.
- Mapped the source UI layout: compact top identity strip, tab rail, left optics/network/metrics column, center particle sphere with control dock, right live transcript, and modal-style research/RAG/remote widgets.
- Upgraded Shell's PyQt Neural dashboard to more closely match that structure while keeping Shell branding and Shell backend wiring.
- Added dashboard-local live charts, a richer 3D-style particle sphere, Shell Neural widget cards for Deep Research, Project RAG, Remote Link, and Live Coding, plus responsive side rails.

### Changes Made
- Updated `shell_ui/neural_dashboard.py` with the richer dashboard layout and visual behavior.
- Kept `shell_ui/shell_cinematic_full.py` Shell-branded and routed dashboard feature cards through existing Shell command handling.

### Current State
- Syntax validation passed for the updated dashboard.
- Focused UI/RAG regression passed: `23 passed`.
- Broad Phase regression passed with unrelated launcher assertion deselected: `128 passed, 1 deselected, 1 warning`.
- Repository-wide removed-brand text and filename scans still return no matches.

### Next Steps
1. Visually test the relaunched Shell UI and tune spacing/scale based on what is visible on the actual screen.
2. Capture fresh Shell Neural dashboard screenshots after visual approval.

### Open Issues
- Existing unrelated deleted files are still present in the worktree and were not reverted.
- `tests/test_installer_bootstrap.py::test_mac_launchers_use_bootstrap_directly` remains deselected because `Start_ShellAI.command` is missing in the current worktree.
