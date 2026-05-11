<!-- SPDX-License-Identifier: Apache-2.0 -->

# Shell AI Design System

Shell AI OS Controller should feel like a calm AI operations cockpit: fast,
technical, trustworthy, and understandable. The visual system must support a
powerful desktop assistant without pretending that the product is sentient or
unbounded.

## Brand Position

Primary positioning:

```text
Shell AI OS Controller is an AI-native desktop control layer for chat, voice,
automation, tools, agents, and local workflows.
```

Short tagline:

```text
Control your workspace with AI, safely.
```

Do say:

- AI operating layer.
- Desktop AI control layer.
- Automation platform.
- AI workspace assistant.
- Human-controlled tool execution.

Do not say:

- AGI.
- Self-aware.
- Autonomous without limits.
- Guaranteed to control every app.
- Unrestricted self-evolving system.

## Product Personality

Shell should communicate like a reliable systems tool:

- Direct.
- Calm.
- Specific.
- Transparent about limits.
- Confident only when capability is actually available.

Avoid hype words in core UI. Prefer "Ready", "Needs API key", "Windows only",
"Blocked by safety", and "Run health check" over vague status copy.

## Color System

Primary palette:

| Token | Hex | Use |
| --- | --- | --- |
| `shell-bg` | `#071014` | App background |
| `shell-surface` | `#0D1B22` | Panels and page bands |
| `shell-surface-raised` | `#132934` | Active panels |
| `shell-border` | `#244250` | Hairline borders |
| `shell-text` | `#EAF7FB` | Primary text |
| `shell-muted` | `#91A8B3` | Secondary text |
| `shell-cyan` | `#18D7F3` | Primary action and active state |
| `shell-blue` | `#4F8CFF` | Link and info state |
| `shell-green` | `#38D996` | Ready/success |
| `shell-amber` | `#F4B860` | Needs setup/caution |
| `shell-red` | `#FF6673` | Error/blocked |

Palette rule: avoid one-color neon UI. Cyan is the signature accent, not the
whole interface. Pair it with dark neutral surfaces, green readiness, amber
setup states, and red safety states.

Runtime themes:

| Theme | Intent | Best For |
| --- | --- | --- |
| Cyber Neon | Signature Shell cockpit with cyan operational accents | Voice, tools, live demos |
| Graphite Dark | Quiet daily-work theme with restrained blue accents | Coding, chat, long sessions |
| Clean Light | Bright accessible mode for setup and support | Beginner onboarding, docs screenshots |
| Midnight | Soft low-light violet mode | Voice, ambient focus, presentations |

Every theme must pass these minimum contrast rules:

- Primary text on core surfaces: 4.5:1 or better.
- Secondary/muted labels: 3:1 or better.
- Text inside filled accent buttons: 4.5:1 or better.
- Error/warning/success labels must never rely on color alone; pair with text.

## Typography

Recommended stack:

```css
font-family:
  Inter,
  "SF Pro Text",
  "Segoe UI",
  system-ui,
  sans-serif;
```

Use:

- 28-36 px only for app/page headers.
- 18-22 px for panel titles.
- 14-16 px for body text.
- 12-13 px for metadata, diagnostics, labels.

No negative letter spacing. Do not scale text with viewport width.

## Logo Concepts

Concept A: command ring.

- A small terminal prompt mark inside a circular orbit.
- Best for app icon and GitHub avatar.

Concept B: workspace node.

- Four connected nodes around a center dot.
- Best for ecosystem, tools, and orchestration branding.

Concept C: voice signal.

- A soft particle ring around a central voice core.
- Best for voice page, demo videos, and social preview.

Current placeholder assets:

- `docs/assets/shell_logo_concept.svg`
- `banners/social-preview-concept.svg`

## Icon System

Use simple line icons for UI controls:

- Chat: message icon.
- Voice: microphone icon.
- Tools: wrench or terminal icon.
- Settings: gear icon.
- System: activity/heartbeat icon.
- Safety: shield icon.
- Health: check-circle or alert-triangle icon.

Avoid decorative icons that do not represent a real action.

## Layout Principles

- Important status should be visible without scrolling.
- Cards are for repeated items, not every page section.
- Dashboards should show live state, not marketing copy.
- Health/error states must be readable in one glance.
- Controls should stay stable when labels update.
- Empty pages must always show a useful beginner action, never a blank canvas.
- Chat, voice, tools, and settings should keep the same page shell, spacing,
  control height, and status-language patterns.
- Advanced controls can be present, but destructive or risky actions must be
  visually quieter until the user explicitly asks for them.

## Component Rules

Core components should use `shell_ui/design_tokens.py` and
`shell_ui/widgets.py` before adding new inline styles.

- Buttons: 34-40 px high, icon plus text when the action is not obvious.
- Inputs: 38-44 px high, visible focus ring, clear placeholder text.
- Cards: use one panel level at a time. Do not nest decorative cards.
- Status pills: use the canonical states Ready, Needs setup, Windows only,
  Blocked, Error, Running, and Offline.
- Notifications: short, actionable, and tied to real runtime events.
- Tooltips: required for icon-only controls and advanced settings.

## Interaction Flow

Default first screen:

1. Chat opens with a starter surface.
2. User can type, attach a file, or pick a starter chip.
3. Shell responds in text first.
4. Voice playback is optional through an explicit listen/speak control.
5. Tool execution explains what ran and whether it was local, API, MCP, or blocked.

Voice page:

1. Voice state is visible before the orb.
2. Mic, session, and visual controls are real stateful controls.
3. Transcript is always available.
4. Missing audio dependencies show setup guidance, not raw Python errors.

Settings:

1. Beginner-safe settings first.
2. API keys and remote-control features must explain requirements clearly.
3. Dangerous capabilities stay off by default and show permission language.

## Motion

Motion should help orientation:

- Short fade/slide for onboarding cards.
- Subtle particle motion for voice readiness.
- No heavy idle animations on system dashboards.
- No animation should block input or delay first response.
- Theme switching should not rebuild heavy panels unless unavoidable.
- Any long-running visual effect must stop when the page is not visible.

## Accessibility

- Minimum body text is 14 px.
- Letter spacing is 0 for regular labels and body copy.
- Keyboard focus must be visible on inputs and primary actions.
- All icon-only controls need tooltips.
- Avoid using opacity below 0.55 for meaningful text.
- Every page must be usable in dark mode, light mode, and high-contrast
  screenshots.

## Beginner Experience

Beginner users should understand Shell without reading source code:

- Use direct copy: "Add API key", "Run health check", "Open Tools".
- Replace raw exceptions with recovery text and repair guidance.
- Keep advanced AI architecture wording in docs, not first-run UI.
- Never claim a tool succeeded unless the backend returned success.
- Show platform limits clearly: Windows-MCP should say Windows only on macOS.

## README Visual Hierarchy

README order should stay:

1. Product identity.
2. What it is and what it is not.
3. Top features.
4. Screenshots/demos.
5. Install.
6. Architecture.
7. Docs.
8. Roadmap, contribution, security.

This keeps beginner users oriented and gives developers confidence quickly.
