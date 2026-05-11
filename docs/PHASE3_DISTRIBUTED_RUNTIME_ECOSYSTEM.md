# Phase 3 Distributed Runtime Ecosystem

Phase 3 evolves Shell AI OS Controller from a local intelligent operating layer
into a distributed AI runtime ecosystem. The design remains bounded: no AGI
claims, no fake consciousness, no unrestricted autonomy, and no hidden
self-modification. Every subsystem is meant to be observable, reversible, and
safe by default.

## System Diagram

```text
PyQt UI / Developer Mode
        |
        v
Event Bus + Streaming + Observability
        |
        v
Orchestrator / Workflows / Collaboration
        |
        v
Skill Graph + Runtime Manager + Execution Policy + Security
        |
        v
Distributed Queue -> Execution Nodes -> Validation -> Result Aggregator
        |
        v
Memory Fabric + Trust + Recovery + Filesystem Intelligence
```

## 1. Distributed Execution

Architecture diagram:

```text
Client -> PersistentTaskQueue -> ExecutionRouter -> NodeRegistry -> ExecutionNode
```

Responsibilities: `core/distributed` owns worker registration, heartbeat state,
queue persistence, task assignment, and capability-aware routing.

APIs/interfaces: `NodeRegistry.register()`, `NodeRegistry.heartbeat()`,
`PersistentTaskQueue.enqueue()`, `PersistentTaskQueue.assign()`,
`ExecutionRouter.route_next()`.

Event interactions: emits `ai.WORKER_REGISTERED`, `ai.WORKER_HEARTBEAT`,
`ai.DISTRIBUTED_TASK_QUEUED`, and `ai.DISTRIBUTED_TASK_ASSIGNED`.

Runtime lifecycle: node registers capabilities -> sends heartbeat -> queue
receives task -> router assigns the next ready task to the lowest-load healthy
node -> worker reports completion or failure through queue state updates.

Security implications: node capabilities are declarative only; risky execution
must still pass through `core/security` and tool gateway permissions.

Scalability model: JSON persistence supports local-first desktop use; the API
shape can move to SQLite, Redis, or a remote queue without changing callers.

Observability hooks: assignment and heartbeat events reconstruct worker health
and routing decisions in Developer Mode.

Testing strategy: cover healthy routing, stale worker rejection, retry schedule,
queue persistence, and no-node failure decisions.

Deployment model: ships as in-process local coordinator first; remote workers
can attach by writing/serving compatible node and task records later.

Rollback strategy: stop calling `ExecutionRouter`; existing local tool gateway
continues to run tools directly.

Migration plan: route long-running and remote-safe tools through the queue while
keeping interactive UI actions local.

## 2. AI Runtime Manager

Architecture diagram:

```text
Task Request -> RuntimeManager -> RuntimeMonitor Policy -> RuntimeDescriptor
```

Responsibilities: `core/runtime_manager` selects LLM, embedding, OCR, TTS, STT,
browser, and automation runtimes based on task type, offline mode, and resource
pressure.

APIs/interfaces: `RuntimeManager.register()`, `RuntimeManager.select()`,
`RuntimeManager.mark_health()`, `RuntimeManager.list()`.

Event interactions: emits `ai.RUNTIME_SELECTED` and `ai.RUNTIME_FAILED`.

Runtime lifecycle: register runtime descriptors -> collect resource snapshot ->
filter by kind/offline/health -> prefer tagged runtimes -> return selected
runtime or structured failure.

Security implications: runtime selection does not grant secret access; provider
calls still require API-key readiness and permission checks.

Scalability model: descriptors can represent local models, cloud providers,
remote nodes, or external services.

Observability hooks: selected and failed runtime events feed dashboards and
provider reliability history.

Testing strategy: offline fallback, high-RAM lightweight selection, unavailable
runtime failure, and health transitions.

Deployment model: defaults are local-light LLM, cloud reasoning, and local OCR;
production deployments should register real providers at startup.

Rollback strategy: call provider-specific code directly until manager metadata
is complete.

Migration plan: move chat, voice, OCR, browser, and automation provider choice
into `RuntimeManager.select()`.

## 3. Multi-Agent Collaboration

Architecture diagram:

```text
Goal -> Planner Agent -> Specialist Agents -> Validator -> Synthesizer
```

Responsibilities: `core/collaboration` provides role-based agents, spawn
limits, task ownership locks, and consensus rules.

APIs/interfaces: `CollaborationTeam.spawn()`,
`CollaborationTeam.acquire_lock()`, `CollaborationTeam.assignable_agents()`,
`CollaborationTeam.resolve_conflict()`.

Event interactions: emits `ai.AGENT_SPAWNED`.

Runtime lifecycle: create team -> spawn bounded role agents -> acquire locks for
resources -> run specialists externally -> resolve conflicting proposals.

Security implications: agents are coordination records, not autonomous shell
actors. Execution still goes through security, sandbox, and gateway layers.

Scalability model: bounded spawn limit prevents recursive agent growth; future
teams can be persisted per workflow.

Observability hooks: spawn events and team snapshots support Developer Mode
coordination views.

Testing strategy: spawn limits, locks, capability filtering, and validator
consensus.

Deployment model: local in-process coordination by default.

Rollback strategy: static existing agent wrappers can remain while specific
workflows migrate to role teams.

Migration plan: convert static agents into role descriptors that share planner,
memory, and tool routing infrastructure.

## 4. AI Skill Graph

Architecture diagram:

```text
SkillNode -> dependencies -> validation -> ordered chain -> runtime score
```

Responsibilities: `core/skills` models capabilities as versioned,
dependency-aware skill nodes.

APIs/interfaces: `SkillGraph.add()`, `SkillGraph.validate()`,
`SkillGraph.chain()`, `SkillGraph.score()`.

Event interactions: emits `ai.SKILL_VALIDATED`.

Runtime lifecycle: register skill nodes -> validate dependencies and cycles ->
build execution chain -> score reliability with dependency penalty.

Security implications: a skill declares capability intent only; dangerous
actions require `core/security` classification and explicit approval.

Scalability model: in-memory graph is enough for local skill catalogs; persistent
graph storage can be added behind the same APIs.

Observability hooks: validation events show why a skill is or is not runnable.

Testing strategy: missing dependencies, cycles, chain order, and scoring.

Deployment model: bundled skills register at startup; marketplace plugins can
add skill nodes after verification.

Rollback strategy: route through existing tool catalog if a skill graph entry is
missing.

Migration plan: map high-value tools into skill nodes first, then compose
multi-step skills.

## 5. Self-Healing Recovery

Architecture diagram:

```text
Failure Event -> RecoveryEngine -> Incident -> RecoveryPolicy -> Action
```

Responsibilities: `core/recovery` records incidents and suggests bounded
recovery actions such as fallback, quarantine, restart, or manual review.

APIs/interfaces: `RecoveryEngine.record_incident()`,
`RecoveryEngine.diagnose()`, `RecoveryEngine.incidents()`.

Event interactions: emits `ai.INCIDENT_CREATED`.

Runtime lifecycle: monitor reports failure -> incident persisted -> policy
selects allowed recovery actions -> operator or orchestrator applies safe action.

Security implications: restarts are disabled by default; quarantine and fallback
are preferred over mutation.

Scalability model: incident JSON can migrate to append-only log or telemetry
store.

Observability hooks: incidents feed event stream, Developer Mode, and trust
scoring.

Testing strategy: dead APIs, runtime crashes, stuck tasks, broken plugins, and
policy denial.

Deployment model: in-process incident tracker with local persistence.

Rollback strategy: disable automatic recovery calls; incidents remain passive
logs.

Migration plan: connect tool failures, runtime failures, and plugin failures to
`record_incident()`.

## 6. Filesystem Intelligence

Architecture diagram:

```text
Project Root -> ProjectIndexer -> FileIndexEntry[] -> Search/Summary
```

Responsibilities: `core/filesystem_ai` indexes project structure, configs,
docs, tests, and code with bounded scanning.

APIs/interfaces: `ProjectIndexer.build()` and `ProjectIndexer.search()`.

Event interactions: currently passive; future indexing should emit project
index events when wired into runtime.

Runtime lifecycle: scan root with skipped heavy directories -> digest file
prefixes -> tag files -> write cache -> answer structural searches.

Security implications: indexes contain file paths and metadata; plugin access
should require filesystem or memory permissions.

Scalability model: scan limits prevent large repo stalls; incremental indexing
can compare digest and mtime later.

Observability hooks: cache summary exposes file counts and suffix distribution.

Testing strategy: tags for dependencies, docs, code, tests, skip directories,
and search ranking.

Deployment model: local cache under `.shell_runtime`.

Rollback strategy: ignore index cache and use direct filesystem search.

Migration plan: use project index in context engine, developer mode, and code
analysis tools.

## 7. Execution Economy

Architecture diagram:

```text
Prompt + Budget + Providers -> ExecutionPolicyEngine -> ProviderCandidate
```

Responsibilities: `core/execution_policy` selects providers by cost, speed,
quality, local preference, offline mode, and token limits.

APIs/interfaces: `ExecutionPolicyEngine.estimate_tokens()`,
`ExecutionPolicyEngine.choose_provider()`,
`ExecutionPolicyEngine.compression_needed()`.

Event interactions: passive policy engine; callers should emit runtime or
routing events.

Runtime lifecycle: estimate prompt tokens -> filter by budget and offline mode
-> sort by local/cost/quality/speed -> return provider or `None`.

Security implications: cost policy never bypasses provider permission or API-key
checks.

Scalability model: scoring stays deterministic and cheap; advanced cost models
can replace sort keys.

Observability hooks: provider choice should be recorded by runtime manager.

Testing strategy: offline local selection, budget rejection, max token rejection,
and compression threshold.

Deployment model: local deterministic library.

Rollback strategy: fall back to provider defaults if no policy result exists.

Migration plan: call policy before choosing premium cloud providers.

## 8. Operating Memory Fabric

Architecture diagram:

```text
Layer Query -> MemoryFabric -> LocalMemoryStore namespaces -> ranked records
```

Responsibilities: `core/memory/fabric.py` unifies active, semantic, execution,
skill, workflow, project, and incident memory layers.

APIs/interfaces: `MemoryFabric.retrieve()`,
`MemoryFabric.resolve_conflicts()`, `MemoryQuery`.

Event interactions: memory writes should emit `ai.MEMORY_UPDATED` as stores are
expanded.

Runtime lifecycle: query selected layers -> search mapped namespaces -> compute
temporal score -> rank -> deduplicate conflicts.

Security implications: memory can contain sensitive user and project data;
access must be transparent, editable, and permission-gated for plugins.

Scalability model: local JSON keeps offline compatibility; vector DB hooks can
attach to the same layer model.

Observability hooks: Developer Mode can show retrieval layers and ranking
without exposing hidden chain-of-thought.

Testing strategy: layer mapping, ranking, deduplication, stale memory decay, and
empty result behavior.

Deployment model: local-first memory store.

Rollback strategy: use existing namespace-specific `LocalMemoryStore.search()`.

Migration plan: migrate user, workflow, tool, incident, and project facts into
layered memory records.

## 9. Real-Time Event Streaming

Architecture diagram:

```text
EventBus -> EventStream.current() -> JSONL persistence -> timeline replay
```

Responsibilities: `core/streaming` exposes live events, trace reconstruction,
and JSONL persistence for debugging.

APIs/interfaces: `EventStream.current()`, `EventStream.persist_current()`,
`EventStream.reconstruct()`.

Event interactions: consumes all `core.events` records.

Runtime lifecycle: collect current event buffer -> optionally append JSONL ->
filter by trace id -> return sorted timeline.

Security implications: event payloads may include tool names, errors, and file
paths; redact secrets before publishing events.

Scalability model: in-memory bus is local; JSONL supports basic replay; future
websocket streaming can wrap the same timeline events.

Observability hooks: primary feed for Developer Mode event debugger.

Testing strategy: event capture, trace filtering, persistence, and ordering.

Deployment model: local event stream by default.

Rollback strategy: disable persistence; event bus remains in-memory.

Migration plan: expose event stream to UI diagnostics and runtime panels.

## 10. Developer Mode

Architecture diagram:

```text
DeveloperInspector -> traces + memory + events + tool routing
```

Responsibilities: `developer_mode` gives debuggable views into execution graph,
memory summary, event replay, and tool routing.

APIs/interfaces: `DeveloperInspector.execution_graph()`,
`DeveloperInspector.memory()`, `DeveloperInspector.events()`,
`DeveloperInspector.tool_routing()`.

Event interactions: reads event replay and observability traces.

Runtime lifecycle: UI requests inspector data -> inspector reads current
subsystems -> returns serializable debug payloads.

Security implications: Developer Mode can reveal sensitive runtime state and
should be operator-only.

Scalability model: lightweight local queries; future remote deployments should
gate with auth and pagination.

Observability hooks: this is the operator surface for traces, memory, events,
and routing.

Testing strategy: smoke-test inspector methods and validate serializable output.

Deployment model: local debug panel.

Rollback strategy: hide Developer Mode UI without affecting runtime.

Migration plan: add PyQt panels for execution graph, memory, routing, and event
timeline.

## 11. Sandboxed Plugin Marketplace

Architecture diagram:

```text
ExtensionManifest -> SecurityModel -> digest verification -> install record
```

Responsibilities: `marketplace` verifies plugin manifests, checks permissions,
stores install records, and blocks unsafe plugins.

APIs/interfaces: `MarketplaceRegistry.verify_manifest()`,
`MarketplaceRegistry.install()`, `MarketplaceRegistry.list()`.

Event interactions: emits `ai.PLUGIN_VERIFIED`.

Runtime lifecycle: parse SDK manifest -> compute digest -> classify
permissions -> install only verified manifests.

Security implications: `shell.execute` and similarly restricted permissions are
blocked by verification; signing/digest checks create a path to stronger trust.

Scalability model: local registry works for desktop; remote marketplace can
serve signed manifests compatible with the same verifier.

Observability hooks: verification events and install records feed trust and
developer views.

Testing strategy: safe install, digest mismatch, restricted permission denial,
and invalid manifest rejection.

Deployment model: local plugin registry.

Rollback strategy: remove installed plugin record; runtime should ignore missing
marketplace entries.

Migration plan: require every external tool, agent, provider, workflow, and UI
panel to ship an `ExtensionManifest`.

## 12. Workflow Engine

Architecture diagram:

```text
Trigger -> Workflow -> Step -> Handler -> Retry/Skip -> Completion
```

Responsibilities: `core/workflows` runs conditional, retryable multi-step
workflows through explicit handlers.

APIs/interfaces: `WorkflowEngine.create()` and `WorkflowEngine.run()`.

Event interactions: emits `ai.WORKFLOW_STARTED` and `ai.WORKFLOW_COMPLETED`.

Runtime lifecycle: create workflow -> evaluate step conditions -> call handler
-> retry bounded failures -> skip false conditions -> return structured result.

Security implications: handlers must perform their own safety checks; workflow
definitions do not grant filesystem or shell permissions.

Scalability model: sequential by default for reliability; task graph execution
can be added for independent branches.

Observability hooks: workflow start/completion events and results appear in the
event stream.

Testing strategy: conditions, retries, missing handlers, failed steps, and
skipped steps.

Deployment model: local workflow runner first.

Rollback strategy: execute existing direct UI actions without workflow wrapper.

Migration plan: convert common routines into explicit workflows after handler
coverage exists.

## 13. Local-First Runtime

Architecture diagram:

```text
Offline Flag + Local Cache + RuntimeManager + ExecutionPolicy -> local runtime
```

Responsibilities: local-first behavior is enforced across runtime manager,
execution policy, memory, filesystem index, and distributed local nodes.

APIs/interfaces: `RuntimeManager.select(offline=True)`,
`ExecutionBudget(offline=True)`, local memory and cache APIs.

Event interactions: runtime failures and selections show when cloud fallback is
or is not used.

Runtime lifecycle: detect offline/budget state -> prefer local candidates ->
avoid remote providers -> continue with cached memory and local tools.

Security implications: offline mode prevents accidental cloud usage but does not
make local execution automatically safe.

Scalability model: local-first is the base profile; cloud and LAN nodes are
accelerators.

Observability hooks: runtime and provider events must show when remote
acceleration is selected.

Testing strategy: offline provider filtering and local cache behavior.

Deployment model: desktop local runtime.

Rollback strategy: disable offline flag and use normal runtime selection.

Migration plan: add a visible UI mode switch and provider readiness status.

## 14. Advanced Security

Architecture diagram:

```text
Action + Metadata -> SecurityModel -> SecurityDecision -> audit/event
```

Responsibilities: `core/security` classifies actions as `SAFE`, `ELEVATED`,
`RESTRICTED`, or `CRITICAL`.

APIs/interfaces: `SecurityModel.classify()`, `SecurityDecision.to_dict()`.

Event interactions: emits `ai.SECURITY_DECISION`.

Runtime lifecycle: caller describes action -> classifier assigns tier -> caller
blocks or asks for confirmation according to decision.

Security implications: restricted and critical actions are denied by default and
require secure mode plus explicit user confirmation in higher layers.

Scalability model: deterministic classifier can later consume policy files and
enterprise rules.

Observability hooks: every decision emits a structured event.

Testing strategy: shell execution, secrets, registry, delete, wipe, plugin, and
desktop-control classifications.

Deployment model: local policy engine.

Rollback strategy: continue using Phase 2 safety policy while migrating call
sites.

Migration plan: call `SecurityModel.classify()` from marketplace, workflows,
distributed workers, and tool gateway.

## 15. Reputation And Trust

Architecture diagram:

```text
Tool/Plugin History -> TrustEngine -> TrustSubject score -> routing policy
```

Responsibilities: `core/trust` aggregates tool reputation and plugin
verification into trust scores.

APIs/interfaces: `TrustEngine.score_tool()` and
`TrustEngine.score_plugin()`.

Event interactions: consumes tool reputation records and marketplace
verification results.

Runtime lifecycle: read history -> compute bounded score -> return transparent
reasons.

Security implications: low trust should reduce routing preference, not silently
override explicit user intent.

Scalability model: local scores can be extended with provider, workflow, and
node trust histories.

Observability hooks: reasons expose success rate, failures, latency, and risky
permissions.

Testing strategy: no-history neutral score, stable tool high score, failing tool
low score, risky plugin penalty.

Deployment model: local trust engine.

Rollback strategy: ignore trust score and use static routing.

Migration plan: feed trust into `CapabilityRegistry.rank()` and distributed
routing.

## 16. Performance Engine

Architecture diagram:

```text
Tasks -> BatchQueue / AsyncExecutionPool -> bounded execution
```

Responsibilities: `core/performance` provides batching and async concurrency
limits.

APIs/interfaces: `BatchQueue.add()`, `BatchQueue.flush()`,
`AsyncExecutionPool.run()`, `AsyncExecutionPool.map()`.

Event interactions: passive utility; callers should emit task events.

Runtime lifecycle: collect batch until threshold -> flush -> run async jobs
behind semaphore.

Security implications: performance utilities do not authorize execution.

Scalability model: local concurrency guard supports low-end devices and can
wrap remote dispatch later.

Observability hooks: pair with startup profiling and runtime metrics.

Testing strategy: batch threshold, flush behavior, concurrency-limited map.

Deployment model: local utility module.

Rollback strategy: call functions directly without pooling.

Migration plan: wrap expensive indexing, provider warmup, and validation jobs.

## 17. User Model

Architecture diagram:

```text
Preference/Usage Event -> UserModel -> editable local JSON -> export/reset
```

Responsibilities: `core/user_model` stores explicit preferences and lightweight
usage counts in an editable, resettable local file.

APIs/interfaces: `UserModel.set_preference()`,
`UserModel.record_tool_use()`, `UserModel.export()`, `UserModel.reset()`.

Event interactions: future preference writes should emit memory or user-model
events.

Runtime lifecycle: user changes preference or uses tool -> local model updates
-> runtime reads preferences -> user can export or reset.

Security implications: privacy-first; no hidden telemetry, no external upload,
and reset must remove local profile state.

Scalability model: simple JSON is enough for desktop; enterprise profiles can
replace storage behind the same API.

Observability hooks: Developer Mode can expose preferences and counts.

Testing strategy: set preference, record count, export, reset, corrupt file
fallback.

Deployment model: local user profile.

Rollback strategy: ignore user model file and use default settings.

Migration plan: connect settings UI and tool-routing preferences to this model.

## 18. Enterprise Observability

Architecture diagram:

```text
Events + Traces + Incidents + Streams -> Developer Mode -> Reports
```

Responsibilities: observability is now a shared infrastructure layer spanning
`core/observability`, `core/events`, `core/streaming`, `core/recovery`, and
Developer Mode.

APIs/interfaces: `publish_event()`, `replay_events()`, `ExecutionTracer`,
`EventStream`, `DeveloperInspector`.

Event interactions: all Phase 3 subsystems emit typed `ai.*` events where they
make decisions or change state.

Runtime lifecycle: subsystem emits event/trace -> stream persists/replays ->
developer mode visualizes -> incidents and trust use history.

Security implications: telemetry must not leak secrets; sensitive payloads need
redaction before publication.

Scalability model: current event bus is in-memory with JSONL persistence; a
distributed deployment can replace storage with OpenTelemetry-compatible sinks.

Observability hooks: events, traces, incidents, timeline reconstruction, routing
views, and memory summaries.

Testing strategy: event type coverage, trace replay, persistence, and inspector
smoke tests.

Deployment model: local debug-first telemetry.

Rollback strategy: turn off UI panels; event emissions are non-fatal and should
not affect execution.

Migration plan: add UI panels for health, event timeline, execution graph,
distributed workers, runtime selection, and skill graph state.

## Compatibility Notes

- Phase 3 adds modules; it does not remove existing UI, gateway, tools, agents,
  or Phase 2 APIs.
- Dangerous operations remain disabled by default.
- The distributed layer is a coordination foundation, not unrestricted remote
  code execution.
- Runtime, workflow, marketplace, and security modules return structured data so
  UI and backend can show exact failure reasons.

