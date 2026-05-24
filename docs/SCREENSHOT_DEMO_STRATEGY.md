<!-- SPDX-License-Identifier: Apache-2.0 -->

# Screenshot And Demo Strategy

Use this plan when preparing public GitHub screenshots, README visuals, demo
GIFs, launch videos, and social previews.

## Folder Structure

| Folder | Purpose |
| --- | --- |
| `screenshots/current/` | Current real WebEngine PNG captures for README, media kit, and Remotion |
| `screenshots/showcase/` | Earlier WebEngine PNG capture references |
| `gifs/` | Short looped feature demos |
| `videos/` | Longer walkthrough/demo placeholders |
| `banners/` | GitHub/social preview assets |

## Required Screenshots

Current real PNG captures already cover:

1. Dashboard and telemetry.
2. Control Center tools and agents.
3. Gallery/media workflow.
4. Settings.
5. Apps.
6. Notes.
7. Phone.
8. Macros.

Recapture the current screenshots before major public release changes:

```bash
node tools/capture_current_ui_screens.mjs 9235 .shell_runtime/current_ui_capture
```

Then copy reviewed captures into `screenshots/current/` and
`videos/instagram-reel/public/current-ui/`.

## Demo GIFs

Keep GIFs under 12 seconds where possible.

- `gifs/chat-first-message.gif`: open app, type, see streamed reply.
- `gifs/voice-ready.gif`: open Voice, start voice, transcript updates.
- `gifs/tool-readiness.gif`: open Tools, run a safe local tool.
- `gifs/settings-api-key.gif`: add provider key with redacted value.
- `gifs/repair-flow.gif`: show a missing dependency and repair action.

## Video Plan

Current primary public launch video:

- `videos/shell-current-ui-landscape-demo.mp4`
- 16:9 landscape, 1920x1080.
- English-only on-screen copy.
- Built from the current real PNG screenshots and Remotion source.

Recommended public launch sequence:

1. 0-5s: title and app open.
2. 5-20s: chat request and fast response.
3. 20-40s: voice page and transcript.
4. 40-60s: tools and automation with safety status.
5. 60-75s: settings, API keys, and health checks.
6. 75-90s: what is real today and what is on the roadmap.

## Social Preview Direction

Use a clean dark banner:

- left: Shell logo mark;
- center: “Shell AI OS Controller”;
- subline: “Control your workspace with AI, safely.”;
- right: small panels showing Chat, Voice, Tools, and Health.

Avoid:

- fake AGI claims;
- too many glowing elements;
- unreadable terminal walls;
- screenshots containing real API keys, emails, tokens, or private chats.

## Capture Rules

- Hide private data before every capture.
- Use version `1.0.0` consistently.
- Use the same theme for a screenshot set unless the goal is a theme demo.
- Prefer real successful tool output over mock claims.
- If a feature is not configured, show the honest setup state.
