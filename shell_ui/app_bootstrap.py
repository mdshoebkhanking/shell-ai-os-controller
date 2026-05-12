from __future__ import annotations

import sys

from PyQt6.QtGui import QFont, QFontDatabase, QGuiApplication


if sys.platform == "win32":
    UI_FONT_CANDIDATES = ("Segoe UI", "Arial", "Noto Sans")
elif sys.platform == "darwin":
    UI_FONT_CANDIDATES = ("Arial", "Helvetica Neue", "Noto Sans")
else:
    UI_FONT_CANDIDATES = ("DejaVu Sans", "Arial", "Noto Sans")


def pick_installed_font(candidates: tuple[str, ...] = UI_FONT_CANDIDATES, fallback: str = "Arial") -> str:
    if QGuiApplication.instance() is None:
        return fallback
    try:
        installed = set(QFontDatabase.families())
    except Exception:
        installed = set()
    for family in candidates:
        if family in installed:
            return family
    return fallback


def configure_qt_application(app, *, pixel_size: int = 13) -> str:
    """Apply a concrete UI font so Qt never falls back to missing generics."""
    family = pick_installed_font()
    font = QFont(family)
    font.setPixelSize(pixel_size)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)
    return family
