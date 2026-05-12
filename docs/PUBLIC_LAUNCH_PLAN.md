<!-- SPDX-License-Identifier: Apache-2.0 -->

# Public Launch Plan

This plan prepares Shell AI OS Controller for a credible public open-source
launch. The goal is a strong first impression without overstating capability.

## Launch Positioning

One-liner:

```text
Shell AI OS Controller is an open-source AI desktop control layer for chat,
voice, tools, automation, and local workflow diagnostics.
```

Short description:

```text
Shell turns a Python desktop app into an AI workspace assistant: chat with it,
run guarded tools, use voice, configure providers, inspect runtime health, and
automate approved local workflows.
```

## Pre-Launch Checklist

Repository:

- README has real screenshots.
- Demo GIFs are added.
- Release ZIP passes production readiness.
- `.env`, logs, tokens, venvs, and generated artifacts are excluded.
- License, security policy, contributing guide, and code of conduct are present.
- GitHub Actions pass on the public repo.

Product:

- Fresh Windows install tested.
- macOS/Linux basic launch documented.
- Voice setup tested with valid provider keys.
- Telegram setup tested with safe allowlist.
- Windows-MCP unsupported OS behavior verified.
- Help Center and repair flow documented.

Community:

- Issues enabled with templates.
- Discussions prepared for setup help and ideas.
- Labels imported.
- Good first issues prepared.
- Maintainer response policy documented.

## Launch Sequence

1. Create private GitHub repo.
2. Push project privately.
3. Run CI/security/release workflows.
4. Fix any workflow failures.
5. Replace placeholder screenshots.
6. Create first GitHub release draft.
7. Run fresh Windows acceptance test.
8. Ask one non-developer to install and test.
9. Make repo public.
10. Publish launch posts.

## Release Notes Strategy

Every release should include:

- What changed.
- What is safer.
- What is faster.
- What remains limited.
- Upgrade steps.
- Known issues.
- Verification results.

Use concrete claims:

```text
Full validation: PASS on the current local gate.
Full tests: use the latest pytest count from the release run.
Package SHA256: ...
```

## Social Announcement Drafts

### Short Post

```text
I built Shell AI OS Controller: an open-source AI desktop control layer for
chat, voice, tools, automation, Telegram control, and runtime diagnostics.

It is not AGI. It is a practical, human-controlled AI workspace assistant.

GitHub: <link>
```

### Technical Post

```text
Launching Shell AI OS Controller.

It combines:
- PyQt desktop UI
- AI provider routing
- voice assistant workflow
- guarded local tools
- Telegram remote-control setup
- Windows-MCP integration
- production readiness checks
- one-click installer flow

The project focuses on safety, observability, and beginner-friendly setup.
GitHub: <link>
```

### Contributor Post

```text
Shell AI OS Controller is open for contributors.

Good first areas:
- docs and screenshots
- install testing
- voice diagnostics
- UI polish
- tool readiness states
- safe automation tests

If you like AI tools, desktop automation, or Python UI systems, this project is
a good place to build.
```

## Community Growth Ideas

- Weekly public progress notes.
- Short demo videos for one feature at a time.
- "Install test" issues for Windows/macOS/Linux.
- Contributor-friendly labels.
- A public roadmap with realistic capability states.
- A security-first remote automation guide.

## Launch Metrics

Track:

- Stars.
- Forks.
- First successful external install.
- First issue from a real user.
- First merged contributor PR.
- Number of setup failures.
- Top missing dependency.
- Voice setup success rate.

## Launch Risks

| Risk | Mitigation |
| --- | --- |
| Users expect an OS replacement | Keep "desktop control layer" wording clear |
| Voice fails due to API/audio setup | Add visible readiness and Help Center path |
| Windows-MCP confusion on macOS/Linux | Keep Windows-only messaging explicit |
| Secrets accidentally committed | Keep repo audit and package guard mandatory |
| Too many tools feel unreliable | Rank readiness and document feature states |
