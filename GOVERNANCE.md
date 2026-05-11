<!-- SPDX-License-Identifier: Apache-2.0 -->

# Governance

Shell AI OS Controller starts as a creator-led open-source project by
**mdshoebking**. The governance model should mature as contributors, plugin
authors, and maintainers join.

## Current Model

- Creator/maintainer: mdshoebking.
- Default decision mode: maintainer review.
- Security decisions override feature requests.
- Dangerous automation remains disabled unless explicitly reviewed.

## Decision Principles

1. Safety before capability.
2. Reliability before hype.
3. Clear docs before launch claims.
4. Local-first behavior before cloud dependency.
5. User control before automation convenience.

## Future Maintainer Roles

- Core maintainer.
- UI maintainer.
- Installer/release maintainer.
- Security reviewer.
- Documentation maintainer.
- Plugin marketplace reviewer.
- Community moderator.

## Contribution Review

Pull requests should be reviewed for:

- user impact
- tests
- security boundary changes
- documentation updates
- install/release impact
- API or plugin compatibility

## Roadmap Governance

Roadmap items should be marked:

- `verified`
- `in progress`
- `planned`
- `experimental`
- `blocked`

Avoid implying features are production-ready before tests and release gates
confirm them.
