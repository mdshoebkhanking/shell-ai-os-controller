<!-- SPDX-License-Identifier: Apache-2.0 -->

# Media Kit

This page lists the current public visual and video assets for Shell AI OS
Controller.

## Primary Brand Assets

| Asset | Path | Use |
| --- | --- | --- |
| Official logo | `assets/brand/shell-official-logo.png` | README, app header, video intro, social previews |
| README banner | `banners/shell-ai-os-controller-banner.svg` | GitHub README hero |
| Social preview concept | `banners/social-preview-concept.svg` | Launch/social planning |

## Current Screenshots

Use these PNG captures as the primary README, launch page, and video source
assets. They are captured from the running Shell Web UI through PyQt WebEngine.
Before publishing, re-check that no local private state is visible.

| Screenshot | Path |
| --- | --- |
| Dashboard | `screenshots/current/dashboard.png` |
| Control Center | `screenshots/current/control.png` |
| Gallery | `screenshots/current/gallery.png` |
| Settings | `screenshots/current/settings.png` |
| Apps | `screenshots/current/apps.png` |
| Notes | `screenshots/current/notes.png` |
| Phone | `screenshots/current/phone.png` |
| Macros | `screenshots/current/macros.png` |

Legacy/reference WebEngine captures remain available under `screenshots/showcase/`.

Before using screenshots publicly, confirm that no API key, Telegram chat ID,
email address, local username, private file path, or machine-specific value is
visible.

## Current Videos

| Video | Path | Notes |
| --- | --- | --- |
| Current 16:9 Web UI demo | `videos/shell-current-ui-landscape-demo.mp4` | Primary English landscape Remotion demo |
| Current 16:9 Web UI poster | `videos/shell-current-ui-landscape-poster.png` | Primary README poster frame |
| Current vertical Web UI demo | `videos/shell-current-state-demo.mp4` | Secondary vertical current-state demo |
| Current vertical Web UI poster | `videos/shell-current-state-demo-poster.png` | Secondary vertical poster |
| Classic launch demo | `videos/shell-launch-demo.mp4` | Earlier cinematic launch video with voiceover |
| Real workflow reel | `videos/shell-ai-real-workflow-reel-60s.mp4` | Existing vertical workflow reel |

## Remotion Source

The current video source lives in:

```text
videos/instagram-reel/
```

Useful commands:

```bash
npm run still:landscape
npm run render:landscape
npm run still:current
npm run render:current
```

The primary current demo composition is `ShellCurrentUiLandscape` at 1920x1080.
It uses English on-screen copy and current PNG UI captures from
`videos/instagram-reel/public/current-ui/`.

The secondary vertical demo composition is `ShellCurrentStateDemo`. It uses:

- real checked-in screenshots from `videos/instagram-reel/public/screenshots/`
- official logo from `videos/instagram-reel/public/brand/`
- local ambient and UI sound effects from `videos/instagram-reel/public/audio/`

## Capture Standard

- Use real Shell UI captures, not fabricated app screens.
- Keep dark Shell branding consistent with the README banner.
- Prefer short, direct captions over exaggerated AI claims.
- Show safe automation boundaries and setup requirements clearly.
- Do not claim a tool succeeded unless the backend/tool probe verified it.
