import os


def test_voice_page_modern_layout_smoke():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication, QFrame
    from shell_ui.shell_cinematic_full import VoicePage

    app = QApplication.instance() or QApplication([])
    page = VoicePage()
    page.resize(1120, 720)
    page.show()
    app.processEvents()

    panes = {w.objectName() for w in page.findChildren(QFrame)}
    assert "voiceAssistantPane" in panes
    assert "voiceTranscriptPane" in panes
    assert page.status_badge.text() == "READY"
    assert page._subtitle_lbl.text() == "Ready for voice"
    assert page.term_btn.text() == "Start Voice"
    assert page.mute_btn.text() == "Mic On"
    assert page.visuals_btn.text() == "Visual On"
    assert page.visualizer.width() == 260
    assert page.visualizer.height() == 260
    assert page.visualizer.parent() is page.stage
    initial_visualizer_geo = page.visualizer.geometry()

    page._terminate_session()
    app.processEvents()
    assert page._session_active is True
    assert page.status_badge.text() == "LISTENING"
    assert page.term_btn.text() == "Pause Voice"
    assert page.visualizer.geometry() == initial_visualizer_geo

    page._toggle_mute()
    app.processEvents()
    assert page._muted is True
    assert page.mute_btn.text() == "Muted"
    assert page.visualizer.geometry() == initial_visualizer_geo

    page._toggle_visuals()
    app.processEvents()
    assert page._visuals_on is False
    assert page.visuals_btn.text() == "Visual Off"
    assert page.visualizer.isVisible() is False
    assert page.visualizer.graphicsEffect() is None
    assert page.visualizer.geometry() == initial_visualizer_geo

    page._toggle_visuals()
    app.processEvents()
    assert page._visuals_on is True
    assert page.visuals_btn.text() == "Visual On"
    assert page.visualizer.isVisible() is True
    assert page.visualizer.graphicsEffect() is None
    assert page.visualizer.geometry() == initial_visualizer_geo

    page._toggle_visuals()
    page._toggle_visuals()
    app.processEvents()
    assert page._visuals_on is True
    assert page.visualizer.isVisible() is True
    assert page.visualizer.graphicsEffect() is None
    assert page.visualizer.geometry() == initial_visualizer_geo

    page.set_error_state("sounddevice not installed")
    app.processEvents()
    assert page._session_active is False
    assert page.status_badge.text() == "ERROR"
    assert page.term_btn.text() == "Start Voice"
    assert "sounddevice not installed" in page._desc.text()
    assert getattr(page.visualizer, "_state", "") == "error"
    assert getattr(page.stage, "_state", "") == "error"
    assert page.visualizer.geometry() == initial_visualizer_geo

    page.add_transcript("user", "hello shell")
    page.add_transcript("shell", "I am listening.")
    app.processEvents()
    assert page._hint_lbl.isVisible() is False
    assert page._transcript_layout.count() >= 3

    page.close()
