<!-- SPDX-License-Identifier: Apache-2.0 -->

# Videos

Do not commit large video files directly unless they are small and optimized.
Prefer YouTube, GitHub Releases, or Git LFS for large videos.

## Current Asset

- `shell-launch-demo.mp4`: 57-second compressed public launch demo with
  voiceover.
- `shell-launch-demo-poster.png`: README poster frame for the launch demo.
- `shell-launch-demo-voiceover.md`: script used to generate the voiceover.
- `shell-launch-trailer.svg`: public launch trailer storyboard for README,
  launch posts, and video production planning.

## Regenerate

On macOS with FFmpeg available:

```bash
python tools/build_launch_video.py
```

Recommended launch videos:

- 60-second quick demo.
- 2-minute beginner setup walkthrough.
- 5-minute technical architecture overview.
