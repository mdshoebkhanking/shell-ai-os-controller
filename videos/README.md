<!-- SPDX-License-Identifier: Apache-2.0 -->

# Videos

Do not commit large video files directly unless they are small and optimized.
Prefer YouTube, GitHub Releases, or Git LFS for large videos.

## Current Assets

- `shell-current-ui-landscape-demo.mp4`: primary English 16:9 Remotion demo
  rendered from real current Shell Web UI screenshots.
- `shell-current-ui-landscape-poster.png`: primary README poster frame for the
  current landscape demo.
- `instagram-reel/`: Remotion source project for the current 16:9 landscape
  demo. The directory name is kept for path stability.

## Regenerate

For the current Remotion demo:

```bash
cd videos/instagram-reel
npm run still:landscape
npm run render:landscape
```

Before regenerating the landscape demo, refresh the current UI captures:

```bash
node tools/capture_current_ui_screens.mjs 9235 .shell_runtime/current_ui_capture
```

Older classic demos, vertical reels, storyboard placeholders, and reference
captures have been removed from tracked media.

Recommended launch videos:

- 36-second current 16:9 English Web UI demo.
- 2-minute beginner setup walkthrough.
- 5-minute technical architecture overview.
