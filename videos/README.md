<!-- SPDX-License-Identifier: Apache-2.0 -->

# Videos

Do not commit large video files directly unless they are small and optimized.
Prefer YouTube, GitHub Releases, or Git LFS for large videos.

## Current Assets

- `shell-current-ui-landscape-demo.mp4`: primary English 16:9 Remotion demo
  for the current Shell Web UI and repository presentation.
- `shell-current-ui-landscape-poster.png`: primary README poster frame for the
  current landscape demo.
- `shell-current-state-demo.mp4`: secondary vertical Remotion-rendered current
  Web UI demo.
- `shell-current-state-demo-poster.png`: poster frame for the secondary
  vertical Web UI demo.
- `shell-launch-demo.mp4`: compressed classic public launch demo with
  voiceover.
- `shell-launch-demo-poster.png`: README poster frame for the classic launch
  demo.
- `shell-launch-demo-voiceover.md`: script used to generate the voiceover.
- `shell-launch-trailer.svg`: public launch trailer storyboard for README,
  launch posts, and video production planning.
- `instagram-reel/`: Remotion source project for current and reel-style video
  generation.

## Regenerate

For the current Remotion demo:

```bash
cd videos/instagram-reel
npm run still:landscape
npm run render:landscape
npm run still:current
npm run render:current
```

For the older cinematic launch demo, on macOS with FFmpeg available:

```bash
python tools/build_launch_video.py
```

Recommended launch videos:

- 36-second current 16:9 English Web UI demo.
- 60-second quick demo.
- 2-minute beginner setup walkthrough.
- 5-minute technical architecture overview.
