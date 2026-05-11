<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 8 Automation Marketplace

The automation marketplace is a future ecosystem for sharing workflows,
templates, plugins, and agent packs. It must be built around trust, review, and
reversibility.

## Marketplace Objects

- automation templates
- workflow packs
- tool plugins
- agent profiles
- provider integrations
- UI panels
- multimodal skills

## Publishing Lifecycle

```text
author
  -> manifest
  -> permission review
  -> static validation
  -> sandbox test
  -> signing
  -> human review
  -> listing
  -> reputation monitoring
```

## Template Requirements

Automation templates need:

- clear name and description
- trigger type
- step list
- required permissions
- risk level
- approval points
- rollback notes
- publisher identity
- version

## Import And Export

Users should be able to export templates as signed bundles later. Imports must
show permissions and risks before installation.

## Community Safety

- No silent install.
- No hidden network permission.
- No secret access without explicit approval.
- No marketplace listing for unaudited dangerous automations.
- Broken templates should be quarantined.

## Future Marketplace Milestones

1. local template import/export
2. signed local bundles
3. verified publisher identity
4. community review workflow
5. public marketplace registry
6. reputation and abuse reporting
