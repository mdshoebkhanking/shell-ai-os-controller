# Phase 2 Runtime Intelligence Architecture

Phase 2 evolves Shell from a tool-based assistant into a context-aware AI
operating layer. It does not claim sentience, AGI, or human-level autonomy.
Every subsystem is designed around transparency, bounded execution, and
operator control.

## 1. Context Engine

Architectural purpose: maintain active, working, session, and long-term context
so the runtime can avoid asking repeated questions.

Subsystem boundaries: `core/context` owns context item storage, priority,
expiration, compression, and environment collection. It does not execute tools.

Event interactions: emits `ai.CONTEXT_UPDATED`.

Dependency graph: `core/context` -> `core/workspace`, `core/events`.

Runtime flow: collectors update context items; expired items are removed;
snapshots prioritize high-signal items; compressed summaries are safe to show to
the model/UI.

Failure modes: corrupt context file, unavailable workspace detector, oversized
context.

Recovery strategy: corrupt files fall back to empty context; collector errors
are stored as low-priority session context; compression truncates safely.

Scalability considerations: JSON local store is enough for current desktop
runtime; future vector indexes can attach to semantic context.

Security implications: context can contain file paths and command history, so UI
should avoid leaking it externally without consent.

Testing requirements: priority ordering, expiration, snapshot compression, and
workspace collection.

Migration plan: feed chat commands, failures, selected files, and active window
events into `ContextEngine.update()`.

## 2. Intelligent Task Orchestration

Architectural purpose: coordinate multi-step workflows with retries,
cancellation, failure isolation, and runtime resource policy.

Subsystem boundaries: `core/orchestrator` owns task graphs and state machine. It
delegates planning to `core/planner` and tool execution to an injected executor.

Event interactions: emits `ai.TASK_STARTED`, `ai.TASK_RETRY`,
`ai.TASK_FAILED`, `ai.TASK_COMPLETED`, and `ai.TASK_CANCELLED`.

Dependency graph: `core/orchestrator` -> `core/planner`, `core/runtime`,
`core/events`; default executor -> `shell_tool_gateway`.

Runtime flow: submit goal -> planner returns steps -> graph nodes execute with
retry limits -> failed node isolates the graph -> completion event emits.

Failure modes: empty plan, failed tool, timeout in executor, cancellation,
resource stress.

Recovery strategy: bounded retries, explicit failed state, cancellation set,
resource policy reducing concurrency.

Scalability considerations: current graph is sequential-safe. Independent-node
parallelism can be added when dependencies are explicit.

Security implications: orchestrator does not bypass gateway readiness or safety.

Testing requirements: retry behavior, cancellation, empty task graph, failed
tool isolation.

Migration plan: route UI workflow actions through `Orchestrator.submit()` after
capability readiness is visible in UI.

## 3. Adaptive Tool Intelligence

Architectural purpose: improve routing from observed tool outcomes instead of
static assumptions.

Subsystem boundaries: `core/tools/reputation.py` tracks success rate, average
latency, failure categories, permission failures, dependency failures, and
cancellations. It does not decide permissions.

Event interactions: emits `ai.TOOL_EXECUTED`.

Dependency graph: `shell_tool_gateway` -> `ToolReputationStore`;
`CapabilityRegistry.rank()` reads reputation adjustments.

Runtime flow: gateway records success/failure -> reputation JSON updates ->
future ranking includes reputation adjustment.

Failure modes: reputation file corruption, disk write failure, noisy early data.

Recovery strategy: corrupted reputation falls back to empty; write failures are
swallowed in gateway; ranking influence is bounded.

Scalability considerations: JSON is local-first; can be migrated to SQLite when
history grows.

Security implications: reputation logs tool IDs and failure labels, not secrets.

Testing requirements: success/failure counters, routing adjustment, gateway
recording for blocked tools.

Migration plan: show reputation in Tools UI and use it when multiple routes
match.

## 4. Predictive Assistance Engine

Architectural purpose: generate useful, non-intrusive suggestions based on
workspace and health signals.

Subsystem boundaries: `core/predictive` creates suggestions only. It never opens
popups or executes actions.

Event interactions: emits `ai.SUGGESTION_CREATED`.

Dependency graph: `core/predictive` consumes context snapshots and health
diagnostics.

Runtime flow: context + health -> rules produce max-limited suggestions -> UI
may render them in a diagnostics panel.

Failure modes: irrelevant suggestions, repeated suggestions, stale context.

Recovery strategy: suggestions are bounded and passive; future cooldown memory
can suppress repeats.

Scalability considerations: rule engine can later add provider-backed ranking
without changing output shape.

Security implications: suggestions must not trigger destructive actions.

Testing requirements: Python repo, dirty git, dependency warning, platform
warning.

Migration plan: display suggestions in a quiet control-surface panel.

## 5. Execution Sandbox

Architectural purpose: isolate risky generated work in temporary workspaces with
path controls, snapshots, rollback, command allowlists, and timeouts.

Subsystem boundaries: `sandbox` owns isolated workspace file writes and command
execution. It does not grant shell access by default.

Event interactions: emits `ai.SANDBOX_VIOLATION`.

Dependency graph: `sandbox` -> `core/events`.

Runtime flow: create workspace -> write files through guarded paths -> snapshot
-> run allowlisted command -> rollback if needed -> cleanup.

Failure modes: path escape, unapproved command, timeout, failed command.

Recovery strategy: block path escape, block unknown commands, return structured
timeout/error results, rollback snapshots.

Scalability considerations: process isolation is local; stronger OS sandboxing
can wrap this API.

Security implications: no shell=True; no unrestricted filesystem mutation.

Testing requirements: path escape, command block, snapshot rollback, timeout.

Migration plan: route generated-code tools through sandbox before promoting
artifacts to the real workspace.

## 6. Advanced Memory System

Architectural purpose: persist episodic, procedural, semantic, and failure
memory.

Subsystem boundaries: `core/memory` owns local JSON memory records, indexing,
search, summaries, and compaction. It does not call LLMs.

Event interactions: currently local; future writes should emit
`ai.MEMORY_UPDATED`.

Dependency graph: standalone local-first store.

Runtime flow: remember event -> lexical retrieval -> summarize/compact by
namespace.

Failure modes: corrupt memory file, stale records, noisy memories.

Recovery strategy: corrupt file falls back to empty; compaction trims older
records.

Scalability considerations: vector DB hooks can attach later; JSON remains
offline-safe.

Security implications: memory may contain sensitive workflow details; plugin
access must require permissions.

Testing requirements: namespace writes, retrieval, summary, compaction.

Migration plan: record successful workflows, repeated user preferences, and
failure patterns.

## 7. Workspace Awareness

Architectural purpose: detect coding, writing, research, media, browsing, or
general session mode.

Subsystem boundaries: `core/workspace` detects project root, languages, recent
files, git branch, dirty state, and project signals.

Event interactions: consumed by context engine.

Dependency graph: `core/workspace` -> stdlib subprocess for bounded git calls.

Runtime flow: detect root -> scan bounded file list -> infer mode -> read git
state with timeout -> return `WorkspaceState`.

Failure modes: huge repo scan, git timeout, inaccessible files.

Recovery strategy: scan limit, timeouts, empty fallback.

Scalability considerations: can add cached file index and file watcher later.

Security implications: exposes file names and branch status only.

Testing requirements: Python project detection, writing/media mode, git dirty.

Migration plan: call from context engine on startup and active-project changes.

## 8. Live System Intelligence

Architectural purpose: monitor runtime pressure and adapt execution policy.

Subsystem boundaries: `core/runtime` returns system snapshots and resource
policy. It does not kill processes or mutate settings.

Event interactions: emits runtime warning events when policy restricts work.

Dependency graph: optional `psutil`; stdlib disk fallback.

Runtime flow: collect CPU/RAM/disk/battery -> compute concurrency/heavy-task
policy.

Failure modes: psutil unavailable, missing battery data.

Recovery strategy: disk-only fallback and conservative policy.

Scalability considerations: snapshots can feed UI charts and orchestrator.

Security implications: process names should be redacted before external logs.

Testing requirements: high-pressure policy behavior.

Migration plan: orchestrator already reads policy before running task graphs.

## 9. AI Event Bus

Architectural purpose: reduce tight coupling through domain events with replay
support.

Subsystem boundaries: `core/events` is a facade over the existing
observability bus.

Event interactions: all Phase 2 subsystems publish events here.

Dependency graph: `core/events` -> `core/observability`.

Runtime flow: publish domain event -> bounded in-memory buffer -> subscribers
receive callbacks -> replay can filter by type/time.

Failure modes: subscriber exception, process restart loses buffer.

Recovery strategy: subscriber errors are swallowed; persistent event log is a
future backend.

Scalability considerations: in-process bus is sufficient for desktop runtime;
can bridge to SQLite/WebSocket later.

Security implications: payloads must avoid secrets.

Testing requirements: publish, subscribe, replay filter.

Migration plan: replace direct UI callbacks with event subscriptions gradually.

## 10. Extension SDK

Architectural purpose: allow external tools, agents, workflows, UI panels,
providers, and automation packs with explicit manifests.

Subsystem boundaries: `sdk` validates manifests and permissions. It does not
load arbitrary code yet.

Event interactions: future lifecycle events: install, enable, disable, error.

Dependency graph: standalone manifest parser.

Runtime flow: parse manifest -> validate kind/permissions -> future plugin
loader applies sandbox boundaries.

Failure modes: invalid permission, unsupported kind, missing entrypoint.

Recovery strategy: validation error before load.

Scalability considerations: version compatibility fields prepare for API
evolution.

Security implications: plugin permissions are explicit and deny unknown values.

Testing requirements: valid/invalid manifests.

Migration plan: adapt `shell_plugin_loader.py` to consume `ExtensionManifest`.

## 11. Reasoning Transparency

Architectural purpose: expose concise decision summaries without leaking hidden
chain-of-thought.

Subsystem boundaries: `core/reasoning` explains tool choice and failures from
route/readiness/result data.

Event interactions: gateway embeds explanations in execution result payloads.

Dependency graph: `shell_tool_gateway` -> `core/reasoning`.

Runtime flow: route/result -> explanation summary, confidence, factors,
diagnostics.

Failure modes: missing route fields, overconfident explanation.

Recovery strategy: conservative confidence defaults.

Scalability considerations: can aggregate execution graph explanations later.

Security implications: no hidden model reasoning is exposed.

Testing requirements: explanation shape, readiness factors, failure factors.

Migration plan: render explanations in tool detail UI and task timeline.

## 12. Cross-Platform Design

Architectural purpose: prepare automation, notifications, filesystem access,
permissions, and process control for Windows, Mac, Linux, and companion apps.

Subsystem boundaries: `shell_desktop` remains the desktop automation facade.

Event interactions: desktop controllers should emit tool and platform events.

Dependency graph: Windows controller -> Windows-MCP; Mac/Linux currently return
structured unsupported results.

Runtime flow: caller asks facade -> platform controller either executes or
returns unsupported state.

Failure modes: platform not implemented, missing runtime.

Recovery strategy: structured unsupported results instead of crashes.

Scalability considerations: platform controllers can be developed independently.

Security implications: desktop control permissions must remain explicit.

Testing requirements: structured unsupported result on non-Windows.

Migration plan: move UI workers to `shell_desktop.get_desktop_controller()`.

## 13. Performance Engineering

Architectural purpose: support startup profiling, execution benchmarks, lazy
loading, and future resource pooling.

Subsystem boundaries: `core/performance` currently provides lightweight
profiling spans.

Event interactions: future profiler can emit startup mark events.

Dependency graph: standalone stdlib.

Runtime flow: mark/span -> report.

Failure modes: measurement overhead.

Recovery strategy: no-op level overhead is small and local.

Scalability considerations: can write reports to diagnostics panel.

Security implications: profiling metadata should not include secrets.

Testing requirements: span duration and mark recording.

Migration plan: wrap hub/UI/agent startup phases.

## 14. UI Evolution

Architectural purpose: move from cinematic-only UI to high-information control
surface.

Subsystem boundaries: current UI is unchanged; Phase 2 exposes data surfaces:
context snapshots, health diagnostics, events, traces, reputation, task graphs,
and suggestions.

Event interactions: UI should subscribe to `core/events` through hub endpoints
or Socket.IO forwarding.

Dependency graph: UI -> hub -> health/capabilities/events.

Runtime flow: runtime events feed task timeline, dependency status, memory
activity, active context display, and routing visualization.

Failure modes: visual overload, stale diagnostics.

Recovery strategy: quiet panels, manual refresh, bounded event buffers.

Scalability considerations: event filtering and pagination needed for long
sessions.

Security implications: avoid displaying secrets from context/memory.

Testing requirements: endpoint payload shape and no UI import regressions.

Migration plan: add panels incrementally behind existing Tools/System pages.

## 15. Testing Infrastructure

Architectural purpose: continuous validation for context, sandbox, routing,
failure injection, and orchestration.

Subsystem boundaries: tests cover modules without requiring external API keys.

Event interactions: tests validate replay and reputation events.

Dependency graph: pytest -> core modules -> no network.

Runtime flow: unit tests simulate dependency and failure states.

Failure modes: accidental platform assumptions.

Recovery strategy: tests branch on `os.name` where necessary.

Scalability considerations: add integration tests for Windows-MCP on Windows CI.

Security implications: sandbox tests confirm path and command blocking.

Migration plan: add stress and UI endpoint tests after panels are wired.

## 16. AI Safety Model

Architectural purpose: classify actions as `SAFE`, `CAUTION`, `DANGEROUS`, or
`CRITICAL`.

Subsystem boundaries: `core/safety` classifies and audits. It does not ask the
user or execute actions.

Event interactions: future confirmation UI can publish approval/denial events.

Dependency graph: standalone stdlib.

Runtime flow: action text + metadata -> safety decision -> audit log.

Failure modes: false positive or false negative classification.

Recovery strategy: conservative defaults for shell, code, registry, workflow,
and communication actions.

Scalability considerations: policies can be made declarative later.

Security implications: critical actions are never allowed by default.

Testing requirements: shell execution dangerous, critical mutation blocked,
audit written.

Migration plan: gateway and orchestrator can require confirmation based on
`SafetyDecision`.

