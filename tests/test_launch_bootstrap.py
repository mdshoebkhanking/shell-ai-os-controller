from pathlib import Path


def test_launcher_loads_env_before_ui_brain_import():
    source = Path("launch.py").read_text(encoding="utf-8")

    config_import = source.index("from shell_config import config")
    ui_import = source.index("from shell_cinematic_full import ShellHoloUI")

    assert config_import < ui_import
    assert "sys.stdout.isatty()" in source


def test_launcher_keeps_webengine_renderer_fallback_safe():
    source = Path("launch.py").read_text(encoding="utf-8")

    assert "_default_webengine_flags" in source
    assert "--enable-unsafe-swiftshader" in source
    assert "--disable-software-rasterizer-fallback-when-hardware-fails" not in source
    assert "renderer in {\"compat\", \"force-gpu\"}" in source


def test_chat_has_inprocess_ai_fallback_when_shell_v2_is_down():
    source = Path("shell_ui/shell_cinematic_full.py").read_text(encoding="utf-8")

    assert "_start_inprocess_ai_fallback" in source
    assert "Shell-v2 down, using local brain" in source
