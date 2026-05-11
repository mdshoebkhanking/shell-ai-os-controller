<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 7 Plugin And Automation Ecosystem

Shell's long-term platform value depends on safe extensions. The goal is a
plugin and automation system that is easy for developers, visible to users, and
strict about permissions.

## Plugin Model

Every plugin needs:

- manifest
- semantic version
- Shell API compatibility range
- permissions
- dependencies
- sandbox settings
- lifecycle hooks
- signed release metadata in the future

Supported plugin kinds:

- tool
- agent
- workflow
- UI panel
- provider
- automation pack

## Permission Model

Phase 7 permissions include:

- `filesystem.read`
- `filesystem.write`
- `network`
- `desktop.control`
- `shell.execute`
- `api.keys`
- `api.external`
- `events.publish`
- `events.subscribe`
- `workflow.run`
- `memory.read`
- `memory.write`
- `cloud.sync`
- `cloud.execute`
- `profile.read`
- `profile.write`
- `workspace.sync`

Permissions must be shown to users before installation.

## Lifecycle

```text
discover
  -> verify manifest
  -> dependency check
  -> security classification
  -> user approval
  -> install
  -> activate
  -> observe
  -> disable/quarantine if unstable
```

## Automation System

Future automation should support:

- event triggers
- scheduled tasks
- manual workflows
- branching
- retry policies
- dry run mode
- rollback notes
- approval steps

Example workflow:

```text
on new_downloaded_pdf
  -> OCR document
  -> summarize
  -> ask before emailing
  -> archive result
```

## Marketplace Readiness

Before public marketplace support:

- define trust levels
- require checksums
- add signing
- isolate dependencies
- validate permissions
- show changelogs
- add report-abuse workflow

## Safety Rules

- No plugin can expand its own permissions.
- No plugin can silently access API keys.
- No automation can bypass confirmation for dangerous actions.
- Broken plugins should be quarantined, not allowed to crash the app.
