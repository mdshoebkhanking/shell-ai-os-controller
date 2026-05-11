<!-- SPDX-License-Identifier: Apache-2.0 -->

# Enterprise Architecture Review

This review describes how Shell AI OS Controller should scale from a desktop
assistant into a maintainable AI platform without a rewrite.

## Current Strengths

- Large functional surface already exists: UI, tools, agents, voice, Telegram,
  Windows-MCP, installer, release gates, health checks, and production docs.
- `core/` now contains clear future-facing modules for planning, memory,
  orchestration, safety, distributed routing, observability, and runtime
  management.
- Public release packaging excludes local secrets, logs, venvs, external cloned
  repos, and generated build output.
- Dangerous automation defaults are off.
- Tests cover release readiness, safety regressions, product ecosystem assets,
  installer checks, voice latency behavior, and tool routing.

## Current Risks

| Area | Risk | Impact |
| --- | --- | --- |
| UI | `shell_ui/shell_cinematic_full.py` still owns too much behavior | Slower changes, higher UI regression risk |
| Tools | Many tools live as flat Python modules | Routing ambiguity and uneven readiness metadata |
| Config | Legacy `.env` access is scattered | Harder profile management and enterprise policy |
| Observability | In-process events are useful but not yet universal | Some failures remain hard to reconstruct |
| Plugins | External integrations exist but are not a signed plugin ecosystem | Marketplace cannot be trusted yet |
| AI providers | Multiple provider paths exist with mixed patterns | Model selection and fallback need one runtime contract |

## Target Architecture

```text
UI / Voice / Telegram / API
  -> Interaction Controller
  -> Policy + Config Profile
  -> Planner / Router
  -> Tool Gateway / Agent Runtime / Workflow Engine
  -> Providers / Local Tools / Plugins / Desktop Controllers
  -> Observability + Audit + Memory
```

## Recommended Module Boundaries

| Boundary | Owns | Must Not Own |
| --- | --- | --- |
| `shell_ui/` | Rendering, user events, UI state | Tool execution policy |
| `core/config/` | Profiles, defaults, validation, redaction | Secrets storage |
| `core/policy/` | Permission and execution rules | UI rendering |
| `core/tools/` | Tool metadata, readiness, reputation | Provider-specific chat logic |
| `core/runtime_manager/` | Provider/model/runtime selection | User-facing copy |
| `core/observability/` | Events, traces, diagnostics | Business decisions |
| `plugins/` / `sdk/` | Extension contracts | Unreviewed arbitrary execution |

## Scalability Review

Scales well:

- Event-driven core concepts.
- Release packaging guardrails.
- Safety and governance modules.
- Local-first memory and runtime planning modules.

Needs continued work:

- UI file decomposition.
- Tool catalog normalization.
- Provider runtime contract.
- Plugin manifest and sandbox enforcement.
- Cross-process observability export.

## Maintainability Review

High-value maintenance actions:

1. Move UI pages into page-specific modules behind stable public classes.
2. Move tool metadata into structured manifests or typed registries.
3. Route all risky execution through policy checks.
4. Make config profile validation part of startup health.
5. Keep product claims mapped to verified, supported, conditional, experimental,
   or planned states.

## Future Cloud Support

Cloud support should remain optional. The cloud boundary should be:

- Runtime provider.
- Sync provider.
- Hosted workflow runner.
- Telemetry export target.

Do not move core control logic to a cloud-only service. Shell should remain
installable and useful in local mode.

## Migration Plan

Short term:

- Keep legacy APIs working.
- Add enterprise config profile checks.
- Generate redacted diagnostics reports.
- Add docs and tests around platform boundaries.

Medium term:

- Create a provider runtime interface.
- Move tools into category manifests.
- Split the UI page implementations further.
- Add plugin manifest validation.

Long term:

- Add signed plugin support.
- Add optional cloud sync.
- Add local model runtime manager.
- Add hosted enterprise policy templates.

## Rollback Strategy

All Phase 5 additions are additive. If any layer causes issues:

- Disable use of `core/config` and keep `shell_config`.
- Ignore diagnostics tools.
- Keep existing launchers, UI, and runtime unchanged.
- Remove docs/tests only if they block release packaging.
