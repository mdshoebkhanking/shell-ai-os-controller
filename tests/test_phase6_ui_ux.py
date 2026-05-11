import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_phase6_theme_metadata_and_contrast_are_complete():
    from shell_ui import design_tokens as tokens

    assert set(tokens.THEME_METADATA) == set(tokens.PALETTES)
    assert not tokens.audit_palette_contrast()

    for name in tokens.PALETTES:
        meta = tokens.theme_metadata(name)
        assert meta.display_name
        assert meta.intent
        assert meta.best_for


def test_phase6_chat_empty_state_survives_clear_and_first_load():
    app = _app()
    from shell_ui.shell_cinematic_full import ChatPage

    page = ChatPage()
    page.resize(1000, 700)
    page.show()
    app.processEvents()

    assert page._empty_state is not None
    assert page._empty_state.isVisible()
    assert page._empty_state.minimumHeight() >= 360

    page.add_message("user", "hello")
    app.processEvents()
    assert page._empty_state is None

    page._clear_chat()
    app.processEvents()
    assert page._empty_state is not None
    assert page._empty_state.isVisible()

    page.close()


def test_phase6_empty_saved_sessions_restore_starter_surface():
    src = (ROOT / "shell_ui" / "shell_cinematic_full.py").read_text(encoding="utf-8")

    assert "def show_empty_state" in src
    assert "rendered = 0" in src
    assert "if rendered == 0" in src
    assert "self.chat_page.show_empty_state()" in src


def test_phase6_ui_ux_audit_tool_and_docs_are_wired():
    import importlib.util
    import sys

    audit_path = ROOT / "tools" / "ui_ux_audit.py"
    spec = importlib.util.spec_from_file_location("ui_ux_audit", audit_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    report = module.build_report()
    assert report["status"] == "pass"
    assert report["theme"]["metadata_complete"] is True
    assert report["theme"]["contrast_issues"] == []
    assert report["docs"]["UI/UX report"] is True
    assert report["docs"]["Product experience plan"] is True
    assert report["docs"]["Screenshot demo strategy"] is True
    assert report["media"]["screenshots"] is True

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "docs/UI_UX_PHASE6_REPORT.md" in readme
    assert "UI_UX_PHASE6_REPORT.md" in docs_index
    assert "tools/ui_ux_audit.py --fail-on-high" in ci
    assert "tools/ui_ux_audit.py --fail-on-high" in release
