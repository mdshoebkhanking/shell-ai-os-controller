<!-- SPDX-License-Identifier: Apache-2.0 -->

# Enterprise Security Preparation

Shell is not enterprise-certified today, but the repository is being prepared
for enterprise-grade security posture.

## Current Security Controls

- Apache-2.0 license and notices.
- Security policy.
- GitHub Actions security workflow.
- Dependency review workflow.
- `pip-audit` on CI dependency set.
- Release package secret exclusion.
- Artifact checksums.
- Artifact attestation workflow.
- Dangerous execution flags disabled by default.
- Telegram remote control requires explicit setup.

## Supply Chain Direction

Target:

- SLSA Build L1/L2 style provenance for release artifacts.
- Signed release packages.
- Dependency review on pull requests.
- Regular vulnerability scans.
- SBOM generation in a future release.
- Plugin signing before marketplace distribution.

## Secure Update Strategy

Future updater must:

- Verify checksum.
- Verify signature/provenance.
- Show release notes.
- Never overwrite user config.
- Support rollback.
- Avoid silent code mutation.

## Permission Review Model

Every risky feature should document:

- Permission required.
- Default state.
- Approval flow.
- Audit output.
- Rollback or recovery path.

## Enterprise Gaps

- No signed installer yet.
- No notarized macOS build yet.
- No SBOM generation yet.
- No formal plugin signing infrastructure yet.
- No third-party security audit yet.

## Priority Actions

1. Add SBOM generation to release workflow.
2. Add signed Windows and macOS installers.
3. Add OpenSSF Scorecard workflow after public repo exists.
4. Add branch protection rules.
5. Add two-person review for release tags.
