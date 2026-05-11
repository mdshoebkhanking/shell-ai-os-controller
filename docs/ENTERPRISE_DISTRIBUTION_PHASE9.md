<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 9 Enterprise Distribution

Distribution has to become predictable before Shell can be trusted by a wider
audience. The current package is a release zip with launchers. The future path
is signed installers and platform-native packages.

## Target Channels

| Platform | Beginner Path | Enterprise Path |
| --- | --- | --- |
| Windows | signed installer or MSIX | Intune/MSIX, signed package, checksums |
| macOS | signed and notarized app/DMG | signed PKG/DMG, notarized, MDM docs |
| Linux | AppImage or deb/rpm | deb/rpm repo, checksums, SBOM |
| Portable | zip release | checksum, provenance, verified launch script |

## Release Integrity

Every public release should include:

- SHA256 checksum.
- release notes.
- public package metadata.
- GitHub artifact attestation.
- future Sigstore signature.
- future SBOM.

## Signing Roadmap

1. Keep checksum generation mandatory.
2. Add Sigstore/cosign signing for zip artifacts.
3. Add Windows code signing or MSIX signing.
4. Add macOS Developer ID signing and notarization.
5. Add Linux package signing if package repositories are introduced.

## Auto-Update Strategy

Do not add auto-update before signatures exist. A safe update system needs:

- signed update manifests
- rollback support
- manual "check for update"
- visible version notes
- disabled-by-default enterprise policy option

## Enterprise Deployment Docs

Future enterprise package docs should cover:

- silent install
- install directory
- network access
- policy config
- update policy
- secrets handling
- logs and diagnostics
- uninstall/rollback

## Current Gap

Shell is not enterprise-distribution complete until signed installers,
notarization, and clean Windows/macOS/Linux acceptance tests are done.
