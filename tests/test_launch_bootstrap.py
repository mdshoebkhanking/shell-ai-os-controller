from pathlib import Path


def test_launcher_loads_env_before_ui_brain_import():
    source = Path("launch.py").read_text(encoding="utf-8")

    config_import = source.index("from shell_config import config")
    electron_launch = source.index("electron:dev")

    assert config_import < electron_launch
    assert "sys.stdout.isatty()" in source


def test_launcher_uses_electron_not_pyqt_webengine():
    source = Path("launch.py").read_text(encoding="utf-8")

    assert "electron:dev" in source
    assert "SHELL_ELECTRON_HOST" in source
    assert "PyQt6" not in source
    assert "QTWEBENGINE" not in source


def test_chat_has_inprocess_ai_fallback_when_shell_v2_is_down():
    source = Path("shell_ui/shell_cinematic_full.py").read_text(encoding="utf-8")

    assert "_start_inprocess_ai_fallback" in source
    assert "Shell-v2 down, using local brain" in source
