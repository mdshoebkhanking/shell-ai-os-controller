#!/usr/bin/env python3
"""Render the current Shell UI public demo through Remotion.

The old handcrafted cinematic/video pipeline has been retired. Public media
should now be regenerated from the real current UI captures under
``screenshots/current/`` and the Remotion composition in ``videos/instagram-reel``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REMOTION_DIR = ROOT / "videos" / "instagram-reel"
EXPECTED_OUTPUTS = [
    ROOT / "videos" / "shell-current-ui-landscape-poster.png",
    ROOT / "videos" / "shell-current-ui-landscape-demo.mp4",
]


def run_npm_script(script: str) -> int:
    result = subprocess.run(["npm", "run", script], cwd=REMOTION_DIR)
    return result.returncode


def main() -> int:
    if not (REMOTION_DIR / "package.json").exists():
        print(f"Remotion project missing: {REMOTION_DIR}", file=sys.stderr)
        return 1
    if not (REMOTION_DIR / "node_modules").exists():
        print(
            "Remotion dependencies are missing. Run `npm install` in videos/instagram-reel first.",
            file=sys.stderr,
        )
        return 1

    for script in ("still:landscape", "render:landscape"):
        exit_code = run_npm_script(script)
        if exit_code:
            return exit_code

    missing = [str(path.relative_to(ROOT)) for path in EXPECTED_OUTPUTS if not path.exists()]
    if missing:
        print(f"Render finished but expected outputs are missing: {', '.join(missing)}", file=sys.stderr)
        return 1

    for path in EXPECTED_OUTPUTS:
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
