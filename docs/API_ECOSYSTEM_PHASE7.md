<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 7 API Ecosystem

The API ecosystem turns Shell from a desktop-only project into an extensible
platform. The current implementation adds platform contracts in
`core/platform_api/` and keeps the public surface local-first until production
auth and governance are implemented.

## API Layers

```text
Internal Python APIs
  -> orchestrator, tool gateway, runtime manager, memory, settings

Local HTTP/WebSocket APIs
  -> health, capabilities, settings, API keys, realtime events

Plugin APIs
  -> manifest permissions, lifecycle hooks, event subscriptions

Future External APIs
  -> remote workspaces, sync, hosted AI services, team administration
```

## Contract Rules

Every API route must declare:

- `route_id`
- method and path
- required scopes
- local-only or remote-ready status
- rate policy
- streaming behavior
- structured response envelope

The route contract is implemented in
`core/platform_api/contracts.py`.

## Response Envelope

All APIs should converge on a consistent envelope:

```json
{
  "ok": true,
  "request_id": "uuid",
  "trace_id": "trace",
  "data": {},
  "error": null,
  "warnings": []
}
```

This keeps UI, plugins, SDKs, and future cloud clients predictable.

## Realtime Events

Realtime events should follow a CloudEvents-compatible shape:

```json
{
  "specversion": "1.0",
  "type": "shell.runtime.updated",
  "source": "shell.hub",
  "id": "uuid",
  "time": "2026-05-12T00:00:00Z",
  "datacontenttype": "application/json",
  "data": {}
}
```

## Auth And Scopes

Initial scopes:

- `status.read`
- `settings.read`
- `settings.write`
- `secrets.write`
- `voice.token`
- `events.subscribe`
- `events.publish`
- `tool.execute`
- `workflow.run`
- `memory.read`
- `memory.write`
- `cloud.sync`
- `remote.control`
- `admin`

Remote APIs must require stronger auth than local UI tokens. Future external
access should use device approval, scoped tokens, short token lifetimes, and
server-side audit logs.

## SDK Generation Path

1. Keep the API contract layer authoritative.
2. Generate OpenAPI documents from the contract.
3. Generate TypeScript/Python SDKs from OpenAPI.
4. Keep plugin APIs versioned separately from private internal APIs.

## API Maturity Gaps

- External OAuth/device-code authentication is not implemented.
- Public hosted APIs are not implemented.
- API rate limiting is defined as metadata but not enforced centrally yet.
- OpenAPI export exists as a skeleton, not a published artifact.

Do not expose Shell beyond localhost until these gaps are closed.
