# Changelog

## 1.0.10 - Offline model packaging and voice orb proof

- Added offline Qwen LLM packaging support with build-time staging, installer
  metadata, and runtime fallback reporting without hidden app-start downloads.
- Switched the bundled Windows offline LLM asset to Qwen3 1.7B Q4_K_M so the
  setup EXE can stay under GitHub release asset size limits.
- Switched the v1.0.10 Windows setup build back to Inno Setup for bundled
  offline-model installers after NSIS hit large-datablock mmap compiler limits.
- Added Shell identity guardrails so offline/provider replies identify as Shell
  AI and answer creator questions with `mdshoebking`.
- Added real rendered UI proof tooling for the dashboard voice-reactive orb,
  including idle/reactive screenshots and screenshot-pixel metrics.
- Strengthened regression coverage for orb voice amplitude, language settings,
  offline LLM status, release staging, and Windows installer metadata.

## 1.0.9 - Offline voice readiness and UI performance

- Restored the original voice-reactive dashboard orb behavior while moving
  particle expansion onto a GPU shader path to reduce per-frame CPU uploads.
- Reduced Shell Web UI idle churn with deduped history updates, memoized
  dashboard rendering, lazy Phone view loading, staggered tab preloading, and
  tab indicator update dedupe.
- Added three-language Shell reply controls for Hinglish, English, and Hindi
  across Settings, browser fallback replies, Gemini prompts, and local speech
  locale selection.
- Added packaged offline TTS readiness detection, Settings status visibility,
  backend/browser fallback reporting, Windows acceptance checks, and installer
  package metadata for offline TTS readiness.

## 1.0.8 - Stable tab switching and refreshed setup icons

- Preloads lazy Shell Web UI tab chunks after launch so first tab switches do
  not show a blank or cropped Suspense fallback.
- Removed tab-root fade animations from the main Shell Web UI panes to prevent
  content disappearing during rapid tab changes.
- Kept the Windows setup EXE and installed shortcuts on the Shell `.ico` path
  with shell icon refresh hooks after shortcut changes.
- Added focused regression coverage for tab stability, tab preloading, and
  non-animated fallback rendering.

## 1.0.7 - Standalone Windows runtime installer

- Changed the Windows setup EXE contract so normal installs launch the bundled
  `ShellAI.exe` directly and do not run dependency bootstrap batch files during
  setup or app launch.
- Updated the bundled Windows desktop entry so `ShellAI.exe` starts the Shell
  Hub as a hidden frozen child process, sets the local hub URLs, then opens the
  PyQt Web UI without requiring external Python.
- Expanded PyInstaller hidden imports and package metadata for the bundled
  desktop runtime, including the Shell Hub, Socket.IO/aiohttp runtime, and Qt
  WebEngine bridge packages.
- Added Shell logo coverage for the Qt app/window icon and Web UI favicon.

## 1.0.6 - NSIS Windows app installer

- Switched the primary Windows setup builder to an NSIS / Nullsoft installer
  flow matching the IRIS-style `*-setup.exe` packaging family.
- Kept Inno Setup available as an explicit fallback engine while making NSIS
  the default for CI and `Build_Windows_EXE.bat`.
- Wired the existing Shell logo asset into the generated Windows `.ico`,
  PyInstaller app executable, and NSIS setup icon.
- Stabilized Shell Web UI tab switching by rendering only the active tab pane
  and reducing panel animation flicker.

## 1.0.5 - Source package release health split

- Separates source package validation from installed runtime venv health so
  GitHub release packaging can run on clean CI runners.
- Adds clearer package blocker output and keeps runtime health covered by
  installer repair, acceptance, and external Windows clean-machine gates.

## 1.0.4 - Release Web UI package readiness

- Builds the React Shell Web UI renderer inside the release package job before
  running public package health checks.
- Keeps generated `shell_web_ui/dist` out of the source zip while allowing
  release health to verify the renderer exists.

## 1.0.3 - Release test stability fix

- Updated release tests so patch-level 1.0.x installer releases are accepted
  instead of hardcoding only 1.0.0.
- Kept the ecosystem master source audit independent from generated Web UI
  runtime artifacts during pytest; dedicated release gates still run full
  runtime/package validation.

## 1.0.2 - Release CI Qt dependency fix

- Added Linux Qt runtime packages to the release workflow so PyQt tests can
  import Qt GUI modules on Ubuntu release runners.
- Kept the bundled Windows desktop app installer changes from 1.0.1.

## 1.0.1 - Bundled Windows desktop app installer

- Replaced the Windows setup shortcut target with a bundled
  `ShellAIApp\ShellAI.exe` desktop executable.
- Added PyInstaller packaging for the Shell AI desktop entry before Inno Setup
  compilation.
- Built and staged the React Shell Web UI renderer inside the Windows installer
  so first launch does not depend on source-mode bootstrap.
- Kept one-click install and repair scripts available as optional fallback
  tools instead of the default app launch path.

## 1.0.0 - Current repository refresh

- Added a primary English 16:9 landscape Remotion demo for the current Shell
  Web UI and repository presentation.
- Replaced the handcrafted SVG showcase with real 1440x900 PNG captures from
  the running Shell Web UI: Dashboard, Control Center, Gallery, Settings, Apps,
  Notes, Phone, and Macros.
- Promoted the landscape demo and actual current UI screenshots to the README, media kit,
  screenshot docs, video docs, public release docs, and current status docs.
- Removed old placeholder screenshots, legacy showcase screenshots, vertical
  reels, classic launch videos, storyboard files, and unused Remotion media so
  public assets now reflect only the current Shell UI.
- Updated README positioning for the current React/Vite Shell Web UI embedded
  in PyQt WebEngine.
- Added current repository status and media kit documentation.
- Replaced the stale current-system E2E audit with the 2026-05-24 Web UI and
  CI-green audit state.
- Updated architecture docs and diagrams for QWebChannel, Shell bridge,
  tool gateway, 468 catalog entries, 37 agents, memory/RAG/sandbox/checkpoints,
  and safety-gated OS automation.
- Added Remotion source/scripts for the current Web UI demo video and poster.
- Documented current screenshots, demo media, and public release asset flow.
- Hardened the synthetic memory probe listener cleanup path after Python 3.10
  CI exposed a flaky QThread cleanup timing issue.

## 1.0.0

- Added public production release guardrails.
- Added one-command public release validation.
- Added Windows audio preflight and Windows-MCP readiness checks.
- Hardened one-click install, repair, and launch scripts for Windows.
- Added production diagnostics report output under `.shell_runtime/`.
- Kept unsafe automation, code writing, remote unauthenticated control, and Telegram terminal execution disabled by default.
- Standardized UI branding to Shell OS 1.0.0 and creator credit `mdshoebking`.
- Prepared Apache-2.0 licensing, NOTICE, third-party notices, security policy, and beginner-friendly legal report.
- Added GitHub Actions CI, security, dependency review, release packaging, artifact attestation, and repository audit workflows.
- Added developer, architecture, API, troubleshooting, FAQ, advanced usage, roadmap, and community documentation.
- Added repository audit tooling and tightened release package exclusions for local/generated artifacts.
- Removed deprecated `google-generativeai` from required dependency lists; Shell now installs the modern `google-genai` SDK by default while keeping legacy fallback code optional.
- Added product experience, design system, trust framework, website plan, ecosystem roadmap, and public launch plan for Phase 4 launch preparation.
- Updated first-launch onboarding copy to set realistic expectations and guide users toward health, setup, and repair paths.
- Added Phase 5 enterprise configuration profiles, config diagnostics, redacted enterprise diagnostics, AI infrastructure planning, enterprise architecture review, DX plan, security prep, monetization readiness, and long-term ecosystem strategy.
- Added Phase 6 UI/UX audit tooling, design-system metadata, product experience docs, screenshot strategy, and a chat empty-state fix for blank saved sessions.
- Added Phase 7 platform API contracts, plugin cloud/event permissions, cloud readiness audit tooling, and cloud/API/sync/security/DevOps/enterprise strategy documentation.
- Added Phase 8 agent ecosystem contracts, marketplace automation template validation, agent ecosystem audit tooling, expanded extension permissions, and agent/orchestration/memory/marketplace/safety/SDK documentation.
- Added Phase 9 launch strategy primitives, support/governance files, launch readiness audit tooling, and global launch/distribution/community/trust/analytics/sustainability documentation.
- Added final ecosystem maturity scoring, master audit tooling, and the final master ecosystem report for long-term product, engineering, launch, and governance direction.
- Integrated the official Shell logo into public branding, promoted real UI captures into the showcase gallery, added the public GitHub release playbook, and added a public GitHub launch audit gate.
