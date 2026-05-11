<!-- SPDX-License-Identifier: Apache-2.0 -->

# Phase 6 UI/UX Audit Report

This report captures the Phase 6 design review for Shell AI OS Controller.
The goal is a premium AI desktop product that stays understandable for a
beginner and honest about real runtime capability.

## Current Strengths

- The app already has a reusable PyQt token layer in `shell_ui/design_tokens.py`.
- The voice page now has a modern assistant layout with status, orb, controls,
  and transcript separated into clear panes.
- Navigation is predictable: Chat, Voice, System, Tools, and Settings.
- Version `1.0.0` and creator attribution are visible in the app shell.
- Starter chips make the chat page more beginner-friendly when no chat is loaded.

## Main UX Problems Found

| Area | Finding | Status |
| --- | --- | --- |
| Chat first screen | Empty saved sessions could render a blank chat canvas | Fixed |
| Theme system | Theme tokens existed but lacked user-facing metadata | Fixed |
| Accessibility | Palette contrast was not measured by a repeatable tool | Fixed |
| Design governance | UI quality was documented but not auditable | Fixed |
| Maintainability | `shell_cinematic_full.py` remains a large UI host | Still a known risk |
| Visual consistency | Inline QSS remains concentrated in legacy UI files | Still a known risk |

## What Changed

- Added a reusable `ChatPage.show_empty_state()` method.
- Empty chat sessions now restore the starter surface instead of going blank.
- Added theme metadata for Cyber Neon, Graphite Dark, Clean Light, and Midnight.
- Added palette contrast auditing in `shell_ui/design_tokens.py`.
- Added reusable status, scrollbar, and app-shell QSS helpers.
- Added `tools/ui_ux_audit.py` for repeatable UI/UX checks.

## Design System Direction

Shell should feel like a calm AI operations cockpit:

- dark, precise, and readable by default;
- enough visual energy for a voice assistant;
- no fake sci-fi clutter;
- clear runtime states instead of hype language;
- beginner controls visible first, advanced controls discoverable later.

## Accessibility Review

Minimum requirements:

- primary text contrast: 4.5:1;
- muted text contrast: 3:1;
- accent button text contrast: 4.5:1;
- icon-only controls need tooltips;
- important status cannot depend only on color.

The new UI audit checks the contrast portion automatically.

## Beginner-Friendliness Review

The app should guide a new user through:

1. open Shell;
2. type a first message;
3. understand whether AI/API voice is configured;
4. run a tool safely;
5. fix missing dependencies through health/repair flows.

The chat empty-state fix is important because a blank first screen makes the
product feel broken even when the runtime is healthy.

## Future UI Risks

- Theme switching still rebuilds a large widget tree; this is reliable today,
  but not ideal for a premium desktop app.
- The main PyQt file is still too large for long-term design evolution.
- Some legacy panels still use direct inline QSS instead of shared widgets.
- Build artifacts exist under `shell_ui/build/` and `shell_ui/dist/`; packaging
  excludes them, but the source tree should eventually separate generated output.

## Recommended Next UI Work

1. Extract `TopBar`, `SidebarNav`, `ChatPage`, `VoicePage`, and `SettingsPage`
   into real modules that own their own styles.
2. Replace repeated inline QSS with `shell_ui/widgets.py` components.
3. Add screenshot-based visual regression checks for Chat, Voice, Tools, and
   Settings.
4. Add a first-run setup wizard inside the UI.
5. Add a dedicated diagnostics/help page for non-technical users.
6. Improve light mode screenshots before public launch.

## Scores

| Category | Score |
| --- | ---: |
| UI quality | 88/100 |
| UX quality | 86/100 |
| Accessibility | 90/100 |
| Beginner friendliness | 87/100 |
| Branding consistency | 90/100 |
| Visual polish | 88/100 |

The score is not 100 because the UI still has a large legacy host file and
needs screenshot-based regression testing before public release.
