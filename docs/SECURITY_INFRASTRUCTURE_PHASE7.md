<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 7 Security Infrastructure

Shell controls local tools, desktop automation, credentials, and future remote
workflows. Security must be designed around least privilege and zero-trust
style assumptions: no device, plugin, token, or remote caller should be trusted
without explicit validation.

## Security Goals

- Keep local-only defaults.
- Deny remote control by default.
- Require scoped permissions for every API and plugin.
- Store secrets securely.
- Make risky actions visible, reversible where possible, and audited.

## Trust Boundaries

```text
User UI
  -> trusted local session

Local HTTP/WebSocket API
  -> bearer token + loopback restriction

Telegram / external controllers
  -> explicit user setup + command policy

Plugins
  -> manifest permissions + sandbox policy

Future cloud services
  -> device trust + scoped tokens + audit logs
```

## Authentication Roadmap

| Stage | Scope |
| --- | --- |
| Current | Local bearer token and local CORS protection |
| Next | Per-device tokens with expiry and revocation |
| Cloud beta | OAuth/device-code flow and RBAC |
| Enterprise | Organization roles, audit retention, policy packs |

## Secure Token Handling

- Do not print tokens in logs.
- Redact token IDs in diagnostics.
- Store long-lived secrets in OS keychain where available.
- Use short-lived runtime tokens for UI sessions.
- Rotate remote tokens on suspicious behavior.

## API Protection

- Scope every route.
- Rate-limit mutating routes.
- Require confirmation for desktop-control and file-write operations.
- Attach trace IDs to remote calls.
- Record audit events for risky execution.

## Sandboxing Strategy

Plugins and automation packs must declare:

- required permissions
- network access
- filesystem access
- desktop-control access
- workflow execution rights
- cloud sync access

Unknown or unsigned plugins should run disabled until the user approves them.

## Secure Update Channel

Future releases should include:

- checksum files
- artifact attestations
- signed release packages
- dependency vulnerability monitoring
- rollback notes

## Do Not Ship Remote Mode Until

- RBAC is implemented.
- Remote tokens can be revoked.
- Audit logs are visible in UI.
- Desktop-control commands have confirmation gates.
- Secrets are encrypted at rest.
- Cloud sync payloads are encrypted end to end.
