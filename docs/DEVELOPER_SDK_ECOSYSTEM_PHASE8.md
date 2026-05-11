<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 8 Developer SDK Ecosystem

Third-party developers should eventually build Shell tools, plugins,
automation packs, and agent modules without touching core runtime files.

## SDK Surfaces

- plugin manifests
- tool API wrappers
- event subscriptions
- workflow blocks
- agent profile definitions
- automation template validation
- local API contracts
- future CLI scaffolding

## Developer Workflow

```text
create plugin
  -> declare manifest
  -> declare permissions
  -> run validation
  -> run sandbox tests
  -> package bundle
  -> publish after review
```

## Permission Expansion

Phase 8 adds explicit permissions for:

- `agent.spawn`
- `agent.delegate`
- `automation.share`
- `marketplace.publish`
- `marketplace.install`
- `multimodal.capture`

These permissions are intentionally separate from shell, desktop, filesystem,
network, and API key access.

## CLI Direction

Future CLI commands:

```text
shellsdk init plugin
shellsdk validate manifest.json
shellsdk test --sandbox
shellsdk package
shellsdk publish --dry-run
```

## Documentation Requirements

Every extension surface needs:

- examples
- permission descriptions
- risk guidance
- test commands
- compatibility matrix
- migration notes

## Community Scaling

Good ecosystem growth requires issue templates, review guidelines, verified
publishers, starter templates, docs contributor paths, and clear moderation
rules before marketplace launch.
