from __future__ import annotations

from shell_ui.app_bootstrap import UI_FONT_CANDIDATES, pick_installed_font
from shell_ui.design_tokens import T


def test_font_candidates_are_concrete_qt_families() -> None:
    assert UI_FONT_CANDIDATES
    assert all("sans-serif" not in family.lower() for family in UI_FONT_CANDIDATES)
    assert all("system-ui" not in family.lower() for family in UI_FONT_CANDIDATES)


def test_pick_installed_font_returns_fallback_when_candidates_missing() -> None:
    assert pick_installed_font(("Definitely Missing Shell Font",), fallback="Arial") == "Arial"


def test_design_token_fonts_are_single_qt_families() -> None:
    for family in (T.family, T.family_mono):
        assert "," not in family
        assert "sans-serif" not in family.lower()
        assert "system-ui" not in family.lower()
