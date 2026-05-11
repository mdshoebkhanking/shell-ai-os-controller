<!-- SPDX-License-Identifier: Apache-2.0 -->

# Monetization Readiness

Shell can remain open source while still leaving room for future commercial
services. The architecture should separate open core, optional services, and
enterprise support.

## Open Core

Always keep open:

- Desktop UI.
- Local tool gateway.
- Safety policy defaults.
- Installer and repair flow.
- Local configuration.
- Core docs.
- Public plugin SDK contracts.

## Optional Commercial Layers

Possible future paid offerings:

- Hosted sync.
- Team policy management.
- Managed plugin registry.
- Enterprise connectors.
- Priority support.
- Signed enterprise builds.
- Cloud workflow runners.

## Architecture Requirements

Commercial layers must not:

- Break local-first usage.
- Require cloud login for core desktop features.
- Hide automation.
- Remove user control.
- Lock basic safety features behind payment.

## Plugin Marketplace Model

Marketplace can support:

- Free community plugins.
- Verified plugins.
- Enterprise plugins.
- Paid automation packs.

Requirements before monetization:

- Manifest schema.
- Permission display.
- Signing/verification.
- Disable/uninstall path.
- Review process.
- Vulnerability reporting.

## Recommended Path

1. Build public trust first.
2. Keep the desktop core free.
3. Add optional hosted services only after local workflow is stable.
4. Offer enterprise packaging/support later.
5. Avoid dark patterns or forced accounts.
