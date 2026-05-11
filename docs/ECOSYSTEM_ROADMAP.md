<!-- SPDX-License-Identifier: Apache-2.0 -->

# AI Ecosystem Roadmap

This roadmap describes future ecosystem growth while keeping Shell practical,
safe, and maintainable.

## Principles

- Stability before new capability.
- Local-first by default.
- Cloud providers as optional accelerators.
- Human approval for risky actions.
- Observable tool execution.
- Clear readiness states instead of fake capability claims.

## Roadmap Layers

### Layer 1: Product Reliability

Goal: make Shell dependable for normal users.

- Improve first-run setup wizard.
- Add clearer health dashboard states.
- Improve voice readiness diagnostics.
- Add real public screenshots and demos.
- Keep installer and repair flow reliable.

### Layer 2: Local AI Runtime

Goal: make Shell useful without relying on every cloud API.

- Add local model provider abstraction.
- Add local embedding store.
- Add local TTS/STT fallback profiles.
- Add model/runtime readiness checks.
- Add resource-aware model selection.

### Layer 3: Tool And Plugin Ecosystem

Goal: make capabilities composable without unsafe sprawl.

- Stable plugin manifest.
- Permission model.
- Sandbox boundaries.
- Tool reputation and readiness scores.
- External skill audit flow.
- Marketplace metadata without automatic trust.

### Layer 4: Automation Marketplace

Goal: let users share workflows safely.

- Workflow templates.
- Dry-run preview.
- Required permission declarations.
- Versioned workflow packs.
- Safety review checklist.
- User-owned install/disable controls.

### Layer 5: API Ecosystem

Goal: let developers integrate Shell with other tools.

- Local REST API.
- Event stream API.
- Tool execution API with permission gates.
- Provider config API.
- Runtime health API.
- Plugin SDK examples.

### Layer 6: Multi-Device And Remote Control

Goal: control workflows across trusted devices.

- Telegram allowlist hardening.
- Mobile companion app concept.
- Encrypted context sync.
- Device trust scoring.
- Remote action preview and approval.
- Offline reconciliation.

### Layer 7: Agent Collaboration

Goal: support agent teams without uncontrolled recursion.

- Role-based agents.
- Task ownership.
- Shared execution timeline.
- Retry limits.
- Cancellation.
- Human-visible reasoning summaries.
- No recursive self-spawning by default.

## Feature Readiness Labels

| Label | Meaning |
| --- | --- |
| Stable | Works in normal supported setups |
| Beta | Real feature, still needs broader testing |
| Experimental | Available for testers, may change |
| Planned | Designed but not implemented |
| Blocked | Waiting on dependency, policy, or platform support |

## Near-Term Priority Order

1. Signed installer and fresh Windows acceptance test.
2. Real screenshots and demo videos.
3. First-run setup wizard polish.
4. Voice setup reliability.
5. Tool readiness ranking.
6. Documentation website.
7. Plugin manifest hardening.
