<!-- SPDX-License-Identifier: Apache-2.0 -->

# Product Experience

Shell should feel like a real desktop product, not a developer script. The
experience should make beginners comfortable while still exposing enough
runtime detail for power users.

## Product Promise

Shell helps users control local workflows through chat, voice, tools, and
safe automation.

The product promise is not "Shell can do everything." The promise is:

```text
Shell shows what is ready, explains what is missing, and runs approved tools
through a visible desktop interface.
```

## First-Time User Journey

The ideal first-time flow:

1. Download release zip.
2. Run the one-click installer.
3. Installer runs dependency and environment checks.
4. App launches into a welcome tour.
5. User sees what is ready and what needs setup.
6. User adds API keys only when a feature needs them.
7. User tests chat.
8. User tests voice.
9. User opens the Help Center if something is missing.

## Welcome Flow

The welcome tour should answer five questions quickly:

- What is Shell?
- What can I do first?
- Is my setup healthy?
- How do I enable voice?
- Where do I go when something fails?

Recommended steps:

| Step | Goal | User Confidence Signal |
| --- | --- | --- |
| Welcome | Explain Shell in one sentence | No fake AGI claims |
| Chat | Show the safest first action | Text response appears |
| Voice | Explain mic/API readiness | Clear "ready" or "needs setup" |
| Tools | Show guarded tool execution | Dry-run/safety states visible |
| Help | Show repair and diagnostics | User knows recovery path |

## Friendly Error Handling

Every error should include:

- What happened.
- Why it probably happened.
- What the user can do next.
- Whether Shell can auto-repair it.

Bad:

```text
ModuleNotFoundError: selenium
```

Good:

```text
Browser automation dependency is missing. Open Help Center -> Repair Shell AI,
or run Repair_ShellAI.bat.
```

## Product States

Shell should consistently use these states:

| State | Meaning |
| --- | --- |
| `READY` | Feature can run now |
| `NEEDS_SETUP` | User action required |
| `NEEDS_API_KEY` | API key missing or invalid |
| `MISSING_DEPENDENCY` | Install/repair needed |
| `WINDOWS_ONLY` | Not available on current OS |
| `BLOCKED_BY_SAFETY` | Unsafe until explicitly approved |
| `EXPERIMENTAL` | Available but not guaranteed stable |

## Beginner Acceptance Criteria

A non-technical user should be able to:

- Start Shell without reading source code.
- Understand why voice may be unavailable.
- Add an API key from Settings or setup docs.
- Run a chat request.
- See where logs and health checks live.
- Repair dependencies without manually activating a venv.

## Power User Acceptance Criteria

A technical user should be able to:

- Inspect runtime health.
- Run tests.
- Package a release.
- Understand tool routing boundaries.
- See where automation is gated.
- Contribute without guessing project structure.

## UX Rules

- Do not autoplay voice for text chat responses.
- Do not hide failed tool execution.
- Do not show dangerous tools as ready by default.
- Do not imply Windows-only tools work on macOS/Linux.
- Do not bury setup status behind decorative UI.

## Measurement

Track these product metrics manually before public launch:

| Metric | Target |
| --- | --- |
| First useful chat response | Under 10 seconds after app launch |
| Health check clarity | User understands next step without logs |
| Install path | One installer plus one launcher |
| Voice setup | User can identify missing mic/API/provider |
| Recovery | Repair flow visible from docs and UI |
