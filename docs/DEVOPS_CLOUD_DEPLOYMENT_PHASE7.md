<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 7 DevOps And Cloud Deployment Readiness

Shell is primarily a desktop app, so cloud deployment must be introduced
carefully. The first target is reliable packaging, reproducible release checks,
and clear future service boundaries.

## CI/CD Direction

Release checks should validate:

- tests across supported Python versions
- syntax compile for launch-critical modules
- production release strict checks
- config diagnostics
- package generation
- production readiness score
- enterprise diagnostics
- UI/UX audit
- cloud/API readiness audit
- checksums and attestations

## Artifact Strategy

Current release artifacts:

- installable zip
- public release package metadata
- checksum file
- GitHub artifact attestation

Future artifacts:

- signed Windows installer
- notarized macOS bundle
- Linux AppImage/deb/rpm
- backend service container if the hub is split from UI

## Container Strategy

Do not containerize the PyQt desktop UI. If cloud services are added, split the
backend into a service boundary first:

```text
shell-desktop
shell-local-hub
shell-sync-service
shell-worker
shell-observability
```

Only service components should become containers.

## Monitoring And Telemetry

Use local-first observability by default:

- structured logs
- trace IDs
- execution timelines
- dependency health
- latency metrics
- user-visible diagnostics

Future hosted services can export OpenTelemetry traces and metrics, but user
privacy must remain opt-in.

## Deployment Models

| Model | Description |
| --- | --- |
| Local desktop | Default and required |
| Local network | Advanced, explicit bind and auth |
| Cloud sync | Optional encrypted sync service |
| Hosted AI acceleration | Optional provider routing |
| Enterprise | Admin policy and audit retention |

## Rollback Strategy

- Keep release zips versioned.
- Preserve local config backups.
- Add migration version checks before changing storage schemas.
- Keep cloud features feature-flagged.
- Support disabling sync without breaking local use.
