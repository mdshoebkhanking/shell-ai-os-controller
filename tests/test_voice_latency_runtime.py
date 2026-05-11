def test_voice_aliases_resolve_to_aoede(monkeypatch):
    monkeypatch.delenv("VOICE_NAME", raising=False)

    from shell_voice import describe_voice, resolve_voice

    assert resolve_voice("adreno") == "Aoede"
    assert resolve_voice("aode") == "Aoede"
    assert "Aoede" in describe_voice("adreno")


def test_tts_command_detection_is_non_throwing(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import TTSSpeaker, _system_tts_available

    speaker = TTSSpeaker()
    assert isinstance(speaker._detect_system_tts_command(), str)
    assert isinstance(_system_tts_available(), bool)


def test_tts_speak_reports_no_audio_output(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    speaker._engine = "system"
    monkeypatch.setattr(speaker, "_speak_system", lambda _text: False)

    assert speaker._do_speak("hello") is False


def test_cloud_voice_does_not_silently_use_local_fallback(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("SHELL_CLOUD_TTS_LOCAL_FALLBACK", raising=False)

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    monkeypatch.setattr(speaker, "_speak_system", lambda _text: (_ for _ in ()).throw(AssertionError("local fallback used")))
    monkeypatch.setattr(speaker, "_speak_pyttsx3", lambda _text: (_ for _ in ()).throw(AssertionError("local fallback used")))

    assert speaker._do_speak("hello") is False
    assert "Gemini voice is selected" in speaker._last_error


def test_set_voice_keeps_gemini_voice_name(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import TTSSpeaker

    speaker = TTSSpeaker()
    speaker.set_voice("Charon")

    assert speaker._gemini_voice_name == "Charon"


def test_gemini_pcm_audio_is_wrapped_as_wav(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_ui.shell_cinematic_full import TTSSpeaker

    path = tmp_path / "speech.wav"
    TTSSpeaker._write_gemini_audio_file(b"\x00\x00\x01\x00", "audio/l16;rate=24000", str(path))

    assert path.read_bytes().startswith(b"RIFF")


def test_speak_tool_cloud_mode_requires_gemini_not_local(monkeypatch):
    import asyncio

    monkeypatch.setenv("SHELL_VOICE_MODE", "cloud")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.delenv("SHELL_CLOUD_TTS_LOCAL_FALLBACK", raising=False)

    from shell_speech import speak_tool

    result = asyncio.run(speak_tool("hello"))

    assert "Gemini voice is selected" in result
    assert "Spoke" not in result


def test_voice_page_has_no_test_voice_button(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication
    from shell_ui.shell_cinematic_full import VoicePage
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    page = VoicePage()

    assert not hasattr(page, "test_voice_requested")
    assert not hasattr(page, "test_voice_btn")
    page.close()


def test_tool_gateway_awaits_async_tool_results(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from shell_tool_gateway import execute_tool_sync

    result = execute_tool_sync("shell_speech:voice_status_tool", {})

    assert result["status"] == "success"
    assert "coroutine object" not in str(result["result"])
    assert "Shell Voice Status" in str(result["result"])


def test_active_context_import_is_cross_platform_safe():
    import active_context_engine

    assert hasattr(active_context_engine, "get_selected_file_context_tool")
    assert isinstance(active_context_engine.WINDOWS_CONTEXT_AVAILABLE, bool)
