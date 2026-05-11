<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 7 Enterprise, Team, And Product Strategy

Shell can remain open source while preparing for future team, enterprise, and
hosted product options. The architecture should not hardcode commercial
features, but it should avoid choices that block them later.

## Enterprise Readiness Targets

- organization/workspace model
- role-based permissions
- policy packs
- admin diagnostics
- audit logs
- managed plugin allowlist
- secure update channels
- exportable reports

## Team Collaboration Model

```text
Organization
  -> Workspace
  -> User / Device
  -> Role
  -> Policy
  -> Workflow / Plugin / Memory Scope
```

Personal Shell installs should not require this model, but the data structures
should leave room for it.

## Multi-Device Product Path

1. Local profiles.
2. Export/import backup.
3. Trusted device sync.
4. Cloud backup.
5. Shared workspaces.
6. Team collaboration.

## Future Product Opportunities

- hosted sync
- premium automation packs
- enterprise policy management
- team dashboards
- plugin marketplace
- cloud AI acceleration
- mobile companion app
- browser extension
- developer workflow packs

## Open-Source Friendly Monetization

Keep the core desktop app open and useful. Commercial features should be
optional services around the ecosystem:

- managed sync
- hosted inference routing
- enterprise admin tools
- verified plugin distribution
- support plans

## Launch Positioning

Professional positioning:

> Shell AI OS Controller is a local-first AI workspace control layer that
> combines chat, voice, automation, tools, and runtime diagnostics with
> safety-first execution.

Avoid claiming AGI, self-awareness, unrestricted autonomy, or guaranteed task
completion. Trust comes from clear boundaries.

## Strategic Milestones

1. Stabilize local UX and installer.
2. Finish API contracts and local observability.
3. Add storage migration and local database.
4. Add encrypted backup/export.
5. Add trusted-device sync.
6. Add plugin marketplace verification.
7. Add hosted services only after security gates are complete.
