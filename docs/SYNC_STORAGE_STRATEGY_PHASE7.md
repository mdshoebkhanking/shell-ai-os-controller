<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 7 Sync And Storage Strategy

Shell should stay local-first while preparing clean storage boundaries for
future cloud sync, backups, and multi-device workflows.

## Storage Layers

```text
Runtime cache
  -> temporary, rebuildable, never synced

User settings
  -> local encrypted config, optional profile sync later

Execution log
  -> append-only event history for replay and diagnostics

Memory stores
  -> local semantic/episodic/procedural memory with export controls

Sync envelopes
  -> encrypted, scoped payloads for trusted devices
```

## Recommended Technologies

| Need | Local Option | Future Cloud Option |
| --- | --- | --- |
| App state | SQLite | Postgres |
| Encrypted local secrets | OS keychain / keyring | KMS-backed secret store |
| Semantic memory | SQLite + embeddings index | Managed vector DB or Postgres pgvector |
| Logs/traces | JSONL / SQLite event log | OpenTelemetry collector |
| Large files | Local workspace folder | Object storage |

## Sync Envelope

Every synced item should carry:

- object id
- object type
- owner/device id
- schema version
- encrypted payload
- updated timestamp
- conflict strategy
- trust level
- trace id

## Conflict Resolution

| Data Type | Strategy |
| --- | --- |
| Settings | last writer wins with visible change history |
| API keys | never sync raw secrets by default |
| Workflow state | merge by task id and checkpoint number |
| Memory | semantic merge with source attribution |
| Audit logs | append-only, never rewrite |

## Offline Reconciliation

When offline:

1. Write to local event log.
2. Mark sync state as pending.
3. Continue local execution.
4. Reconcile when trusted sync is available.
5. Surface conflicts in UI before overwriting sensitive data.

## Security Requirements

- Encrypt sync payloads before leaving the device.
- Do not sync raw API keys unless the user explicitly enables encrypted secret
  sync.
- Keep memory export and reset controls visible.
- Treat cross-device sync as a privacy-sensitive feature.

## Migration Plan

1. Formalize local event log schemas.
2. Move ad hoc runtime state into typed records.
3. Add export/import for settings and workflows.
4. Add encrypted backup.
5. Add trusted-device sync.
6. Add optional cloud sync after auth and audit logs are complete.
