import inspect


def test_theme_engine_uses_design_token_palettes():
    from shell_ui import design_tokens as tokens
    from shell_ui.shell_cinematic_full import ThemeEngine

    engine = ThemeEngine.get()
    assert set(engine.THEMES) == set(tokens.PALETTES)

    for name, palette in tokens.PALETTES.items():
        theme = engine.THEMES[name]
        assert theme["bg"] == palette.bg
        assert theme["surface"] == palette.surface
        assert theme["primary"] == palette.accent
        assert theme["text"] == palette.text
        assert theme["glass_bg"] == palette.glass
        assert theme["glass_border"] == palette.glass_border


def test_accent_text_is_readable_for_every_theme():
    from shell_ui import design_tokens as tokens

    previous = tokens.active_palette_name()
    try:
        for name, palette in tokens.PALETTES.items():
            assert tokens.set_palette_by_name(name)
            text = tokens.accent_text_color()
            assert tokens.contrast_ratio(text, palette.accent) >= 4.5
    finally:
        tokens.set_palette_by_name(previous)


def test_shared_glass_helpers_are_theme_token_driven():
    import shell_ui.shell_cinematic_full as ui

    helper_source = "\n".join(
        inspect.getsource(fn)
        for fn in (
            ui._glass_card,
            ui._tonal_card,
            ui._glass_btn,
            ui._glass_input,
            ui._glass_pill,
        )
    )

    assert "rgba(45,55,80" not in helper_source
    assert "rgba(38,48,72" not in helper_source
    assert "rgba(55,65,88" not in helper_source
    assert "rgba(14,20,34" not in helper_source
    assert "rgba(40,50,70" not in helper_source
    assert "t['glass_bg']" in helper_source
    assert "t['glass_border" in helper_source


def test_voice_stage_uses_active_theme_for_base_layer():
    from shell_ui.shell_cinematic_full import VoiceStage

    src = inspect.getsource(VoiceStage.paintEvent)
    assert "from shell_ui.design_tokens import C as _DC" in src
    assert "QColor(_DC.surface_2)" in src
    assert "QColor(_DC.bg)" in src
