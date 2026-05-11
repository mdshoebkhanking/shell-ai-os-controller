<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 8 AI Memory System

Memory should improve continuity without becoming hidden profiling. Users must
be able to inspect, edit, export, and reset memory.

## Memory Layers

| Layer | Purpose |
| --- | --- |
| Short-term | Current task and recent turns |
| Contextual | Active app, workspace, files, errors |
| Conversation | Chat history and user instructions |
| Workspace | Project-specific state |
| Semantic | Retrieved knowledge and documentation |
| Failure | Repeated errors and recovery outcomes |
| Long-term | User-approved persistent preferences |

## Retrieval Flow

```text
AgentTask
  -> requested memory scopes
  -> policy check
  -> local retrieval
  -> ranking
  -> redaction
  -> context bundle
```

## Privacy Rules

- Memory is local-first.
- Raw API keys are never memory.
- Sensitive memory scopes require explicit permission.
- Cloud memory sync must be encrypted and opt-in.
- Users need clear reset/export controls.

## Vector Storage Plan

Initial local options:

- SQLite metadata store
- local embeddings cache
- file-backed index for small installs

Future options:

- pgvector for hosted workspace sync
- local vector DB for large projects
- encrypted semantic index for private memories

## Testing Requirements

- retrieval ranking tests
- privacy scope tests
- memory reset tests
- failure memory tests
- sync conflict tests before cloud release
