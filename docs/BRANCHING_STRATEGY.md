<!-- SPDX-License-Identifier: Apache-2.0 -->

# Branching Strategy

## Branches

| Branch | Purpose |
| --- | --- |
| `main` | Stable public release branch |
| `develop` | Optional integration branch for larger feature batches |
| `feature/*` | New features |
| `fix/*` | Bug fixes |
| `docs/*` | Documentation-only work |
| `release/*` | Release preparation |

## Rules

- Protect `main`.
- Require pull requests into `main`.
- Require tests and production release checks before release tags.
- Do not merge code that enables dangerous automation by default.
- Do not merge secrets, local logs, runtime folders, or generated venv files.

## Versioning

Use semantic versioning:

- Patch: `1.0.1`
- Minor: `1.1.0`
- Major: `2.0.0`

## Recommended Labels

- `bug`
- `feature`
- `docs`
- `security`
- `installer`
- `ui`
- `voice`
- `telegram`
- `automation`
- `good first issue`
- `help wanted`
