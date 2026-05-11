# Shell AI OS Controller Productionization Architecture

This document records the first compatibility-preserving production refactor.
The goal is to stabilize and modularize without destroying the existing working
architecture.

## 1. Monolithic UI

Problem analysis: `shell_ui/shell_cinematic_full.py` is a large file containing
transport helpers, chat, voice, tools, settings, system telemetry, themes, and
host window code. Moving classes blindly would break signal wiring.

Architectural reasoning: create stable module seams first, then migrate classes
one page at a time with tests.

Implementation strategy: added compatibility modules under `shell_ui/chat`,
`shell_ui/voice`, `shell_ui/tools`, `shell_ui/settings`, `shell_ui/system`,
`shell_ui/shared`, `shell_ui/themes`, `shell_ui/animations`, and
`shell_ui/layouts`. The existing `shell_ui/widgets.py` module is preserved
because turning it into a package would break current imports.

File structure: new page-level modules live under `shell_ui/*/page.py`.

Migration plan: new code imports from the page modules. Future commits can move
one class at a time out of `shell_cinematic_full.py` without changing call
sites.

Compatibility considerations: existing imports from `shell_cinematic_full.py`
continue to work.

Rollback strategy: remove the new package files; no runtime logic depends on
them yet.

Production risks: the monolith still exists. This pass creates migration seams,
not a full extraction.

Testing strategy: `tests/test_production_foundation.py` verifies modular import
seams.

## 2. Tool Registry And Readiness

Problem analysis: hundreds of tools create ambiguity and encourage unavailable
or unsafe tool calls.

Architectural reasoning: readiness metadata should be attached to the existing
catalog instead of inventing a second catalog.

Implementation strategy: added `core/tools` with `ToolMetadata`,
`CapabilityRegistry`, ranking, duplicate detection, and catalog enrichment.
`shell_tool_catalog.discover_capabilities()` now returns `metadata`,
`readiness`, `runtime_state`, and summary counts.

File structure: `core/tools/metadata.py`, `core/tools/registry.py`.

Migration plan: UI and agent routing can filter by `readiness.ok`, category,
safety level, platform, and API requirements.

Compatibility considerations: existing `actions`, `tools`, `catalog`, and
`summary` keys remain.

Rollback strategy: revert `shell_tool_catalog.py` enrichment and remove
`core/tools`.

Production risks: readiness inference is conservative and should be tuned from
real telemetry.

Testing strategy: tests verify Windows-MCP readiness and catalog metadata.

## 3. Observability

Problem analysis: current logging is scattered and tool events are UI-oriented,
not execution-trace-oriented.

Architectural reasoning: add an in-process event bus and tracer that can feed
logs, UI dashboards, and future persistent storage.

Implementation strategy: added `core/observability` with `EventBus`,
`DebugEvent`, `ExecutionTracer`, `ExecutionTrace`, and `TraceSpan`.
`shell_safe_executor` emits debug events for tool start/end. The gateway wraps
local tool execution in traces.

File structure: `core/observability/events.py`,
`core/observability/tracing.py`.

Migration plan: agent routing, planner, and UI dashboard can subscribe to the
event bus or query `/health`.

Compatibility considerations: telemetry errors are swallowed and never break
tool execution.

Rollback strategy: remove optional imports from `shell_safe_executor.py` and
`shell_tool_gateway.py`.

Production risks: the current in-memory buffer is process-local. Persistent log
shipping is a later step.

Testing strategy: gateway and planner tests exercise trace creation paths.

## 4. Dependency Health Engine

Problem analysis: users see failures only after clicking a tool or opening the
voice page.

Architectural reasoning: startup diagnostics and per-capability readiness should
make missing keys, missing packages, unsupported OS, and safety blocks explicit.

Implementation strategy: added `core/health` with runtime states:
`READY`, `MISSING_DEPENDENCY`, `NEEDS_API_KEY`, `WINDOWS_ONLY`,
`BLOCKED_BY_SAFETY`, `OFFLINE_ONLY`, and `EXPERIMENTAL`.
`run_startup_diagnostics()` reports API keys, Python packages, executables,
platform, and safety flags.

File structure: `core/health/states.py`, `core/health/checks.py`,
`core/health/startup.py`.

Migration plan: UI can show readiness chips from `/capabilities` and system
health from `/health`.

Compatibility considerations: diagnostics do not mutate runtime state.

Rollback strategy: remove `/health` endpoint and `core/health`.

Production risks: invalid API key validation is not yet live-call verified.

Testing strategy: tests assert structured diagnostics.

## 5. Platform Abstraction

Problem analysis: Windows-MCP was directly imported by UI workers and routing
logic.

Architectural reasoning: keep Windows-MCP intact but expose a future-safe
controller interface.

Implementation strategy: added `shell_desktop/base_controller.py` and platform
controllers. Windows delegates to `shell_windows_mcp.call_windows_mcp_tool_sync`;
Mac/Linux return structured unsupported results. The physical package is named
`shell_desktop` because this repo already has a `Desktop/` asset folder, which
collides with lowercase `desktop/` on case-insensitive macOS filesystems.

File structure: `shell_desktop/windows`, `shell_desktop/mac`,
`shell_desktop/linux`.

Migration plan: future UI and planner code should call
`shell_desktop.get_desktop_controller()`.

Compatibility considerations: existing Windows-MCP functions are unchanged.

Rollback strategy: remove `shell_desktop/`; no existing API is removed.

Production risks: Mac/Linux controllers are intentionally unsupported stubs
until real adapters exist.

Testing strategy: tests verify structured controller results.

## 6. Planner And Agent Direction

Problem analysis: static agents duplicate wrappers and make stronger autonomy
claims than the implementation can guarantee.

Architectural reasoning: introduce a conservative planner that annotates
readiness before execution.

Implementation strategy: added `core/planner`. It uses the deterministic
natural-language router and capability readiness. It does not invent tools.

File structure: `core/planner/planner.py`.

Migration plan: dynamic agents can share this planner before executing tools.

Compatibility considerations: existing `shell_agents.py` functions remain.

Rollback strategy: remove `core/planner`.

Production risks: this is a planning foundation, not a full multi-step executor.

Testing strategy: tests verify unready route detection.

## 7. Memory

Problem analysis: memory is spread across old JSON files and brain modules.

Architectural reasoning: add a small local-first store with namespaces and keep
vector DB hooks outside the core dependency path.

Implementation strategy: added `core/memory/LocalMemoryStore` with namespaces
for conversation, workflow, tool success, and user preferences.

File structure: `core/memory/store.py`.

Migration plan: route tool success telemetry into this store after UI validation.

Compatibility considerations: no existing memory files are changed.

Rollback strategy: remove `core/memory`.

Production risks: search is lexical until a vector provider is wired.

Testing strategy: covered by import and future unit tests.
