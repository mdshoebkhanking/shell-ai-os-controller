from __future__ import annotations

import importlib.util
import os
import platform
import shutil
from typing import Iterable


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def any_env_present(names: Iterable[str]) -> bool:
    return any(env_present(name) for name in names)


def import_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def executable_available(name: str) -> bool:
    return shutil.which(name) is not None


def current_platform() -> str:
    if os.name == "nt":
        return "windows"
    system = platform.system().lower()
    if system == "darwin":
        return "mac"
    if system == "linux":
        return "linux"
    return system or "unknown"

