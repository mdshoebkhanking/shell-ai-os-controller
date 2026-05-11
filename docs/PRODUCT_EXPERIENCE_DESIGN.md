<!-- SPDX-License-Identifier: Apache-2.0 -->

# Product Experience Design

Shell AI OS Controller should feel like real desktop software, not a developer
demo. The best experience is direct, fast, clear, and honest about what is
configured.

## First Launch Flow

Recommended first-run sequence:

1. Splash: Shell AI OS Controller v1.0.0, created by mdshoebking.
2. Health check: Python runtime, packages, audio, browser, OCR, API keys.
3. Beginner setup: reply language, voice mode, optional API providers.
4. Safety setup: explain remote control, terminal execution, and automation
   permissions.
5. First action: open chat with starter chips.

## Page Experience

### Chat

- Start with a visible starter surface.
- Show text responses first.
- Voice playback should be user-triggered for text chat.
- Attachments should be visible before sending.
- Tool output should explain which tool ran and why.

### Voice

- Voice state should be readable in one glance: Ready, Listening, Speaking,
  Muted, Error.
- The orb is feedback, not the product. Controls and transcript matter more.
- Missing dependencies should show setup guidance, not stack traces.

### Tools

- Tools should be grouped by capability and readiness.
- Disabled tools should explain why: needs API key, Windows only, missing
  dependency, blocked by safety.
- Test buttons should show real execution output.

### Settings

- Beginner mode should be the default.
- API keys should be add/remove/edit from UI.
- Dangerous actions need explicit opt-in and clear consequences.
- Theme selection should preview the selected theme with readable labels.

### System

- System panels should show real metrics only.
- Fake random telemetry is not allowed.
- Diagnostics should link to repair actions where possible.

## Error Language

Bad:

```text
ModuleNotFoundError: No module named sounddevice
```

Good:

```text
Voice input dependency is missing. Run Repair Shell AI to install audio support.
```

Bad:

```text
Email sent.
```

Good:

```text
Email failed: Gmail rejected the login. Use a Google App Password.
```

## Interaction Principles

- Immediate feedback beats decorative animation.
- Text chat should not trigger voice unless the user asks.
- Dangerous automation must show confirmation and audit state.
- The UI should never imply a feature is available when dependencies are
  missing.
- Remote-control features must show who is allowed to control the machine.

## Future Product Upgrades

- First-run setup wizard.
- Health and repair dashboard.
- Tool readiness matrix.
- Screenshot-based UI regression suite.
- Plugin panel framework.
- Workspace dashboard for recent files, tasks, and automations.
