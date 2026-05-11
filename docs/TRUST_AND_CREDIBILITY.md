<!-- SPDX-License-Identifier: Apache-2.0 -->

# Trust And Credibility Framework

Shell must earn trust through visible behavior, clear language, and repeatable
verification. This document defines how the project should present capability.

## Claim Levels

| Level | Meaning | Example |
| --- | --- | --- |
| Verified | Covered by tests or real runtime probe | `production_readiness.py PASS` |
| Supported | Implemented and documented | Windows one-click launcher |
| Conditional | Works when dependency/key/platform is present | Gemini voice |
| Experimental | Real but unstable or gated | External browser automation |
| Planned | Roadmap only | Plugin marketplace |

Every public claim should map to one of these levels.

## Trust Signals

Keep these visible:

- Apache-2.0 license.
- Security policy.
- Code of conduct.
- Contributing guide.
- Release process.
- Production readiness score.
- Test count.
- Known limitations.
- External gates required for GA.

## Terminology Rules

Use:

- "AI desktop control layer".
- "AI workspace assistant".
- "Guarded tool execution".
- "Human-controlled automation".
- "Readiness state".

Avoid:

- "God mode" in public product copy.
- "Unlimited evolution".
- "Fully autonomous".
- "Self-aware".
- "Can do anything".

Legacy internal names can remain in code temporarily, but public docs and UI
should use professional wording.

## User Control Requirements

Risky actions must provide:

- Preview or dry-run when possible.
- Clear action summary.
- Permission boundary.
- Audit/log output.
- Cancellation or rollback path where feasible.

## Public README Claims

README must always include:

- What Shell is.
- What Shell is not.
- Supported platforms.
- Setup requirements.
- Safety defaults.
- Known limitations.

## Verification Language

Good:

```text
Full tests: 260 passed locally.
Production readiness: 100/100 local automated gates.
Windows GA still requires fresh install and signing checks.
```

Bad:

```text
Production ready for everyone.
Works on all machines.
Fully autonomous operating system.
```
