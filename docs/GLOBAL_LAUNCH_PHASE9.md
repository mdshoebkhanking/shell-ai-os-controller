<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 9 Global Open-Source Launch Strategy

Shell should launch in stages. The goal is adoption momentum without promising
capabilities that are not production-tested.

## Launch Roadmap

1. Private alpha: maintainer testing, installer repair, voice basics.
2. Public beta: open repo, clear known issues, invite install testers.
3. Release candidate: signed package plan, screenshots, demos, full audit gates.
4. Public GA: stable installer, real Windows acceptance test, support docs.
5. Enterprise-ready: signed installers, policy docs, deployment guide, SLAs only
   if a support offering exists.

## Launch-Day Checklist

- README screenshots are real.
- Demo GIF/video links are present.
- Release zip checksum is published.
- CI, release, security, cloud, agent, and launch audits pass.
- Windows install tested on a fresh machine.
- Known limitations are visible.
- Security and support paths are clear.
- First good-first-issues are ready.

## Release Communication

Use direct wording:

> Shell AI OS Controller is an open-source AI desktop control layer for chat,
> voice, tools, automation, and runtime diagnostics.

Avoid:

- AGI claims.
- "Controls everything" claims.
- Unverified enterprise claims.
- Hidden autonomy language.

## Contributor Onboarding

First contributor tracks:

- install testing
- docs and screenshots
- UI polish
- tool readiness tests
- voice diagnostics
- safe automation examples

## Launch Metrics

- successful installs
- setup failure reasons
- issue quality
- first external PR
- voice setup success rate
- release download count
- docs page views if analytics are opt-in and privacy-safe
