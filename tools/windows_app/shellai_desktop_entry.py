from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name.lower() == "shellaiapp":
            return exe_dir.parent
        return exe_dir
    return Path(__file__).resolve().parents[2]


ROOT = _app_root()
os.chdir(ROOT)
for candidate in (ROOT, ROOT / "shell_ui", ROOT / "shell_web_ui"):
    text = str(candidate)
    if text not in sys.path:
        sys.path.insert(0, text)

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("SHELL_LEGACY_UI", "0")
os.environ.setdefault("SHELL_V2_STREAM", "1")
os.environ.setdefault("SHELL_IMAGE_LOCAL_FALLBACK", "1")
os.environ.setdefault("SHELL_DESKTOP_BUNDLED", "1")

launch_path = ROOT / "launch.py"
if not launch_path.exists():
    raise RuntimeError(f"Bundled Shell AI launcher is missing: {launch_path}")

runpy.run_path(str(launch_path), run_name="__main__")
