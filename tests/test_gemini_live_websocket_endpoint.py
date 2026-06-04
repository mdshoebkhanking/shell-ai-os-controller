from pathlib import Path


def test_gemini_live_websocket_uses_official_bidi_endpoint():
    source = Path("shell_web_ui/src/services/shell-voice-ai.ts").read_text(encoding="utf-8")

    assert (
        "wss://generativelanguage.googleapis.com/ws/"
        "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
    ) in source
    assert "generativelanguage.googleapis.com/v1beta/${modelPath}:BidiGenerateContent" not in source
    assert "new URLSearchParams({ key: this.apiKey })" in source


def test_gemini_live_uses_supported_native_audio_model_and_client_content_text():
    source = Path("shell_web_ui/src/services/shell-voice-ai.ts").read_text(encoding="utf-8")

    assert "models/gemini-2.5-flash-native-audio-preview-12-2025" in source
    assert "models/gemini-3.1-flash-live-preview" not in source
    assert "clientContent" in source
    assert "turnComplete: true" in source


def test_gemini_live_validates_microphone_stream_has_audio_tracks():
    source = Path("shell_web_ui/src/services/shell-voice-ai.ts").read_text(encoding="utf-8")

    assert "requireAudioInputStream" in source
    assert "stream.getAudioTracks()" in source
    assert "returned no audio track" in source
    assert "createMediaStreamSource(stream)" in source


def test_gemini_live_microphone_failure_keeps_voice_output_available():
    source = Path("shell_web_ui/src/services/shell-voice-ai.ts").read_text(encoding="utf-8")
    start = source.index("async startMicrophone")
    start_microphone = source[start:source.index("scheduleAudioChunk", start)]

    assert "public hasMicrophoneInput: boolean = false" in source
    assert "const microphoneReady = await this.startMicrophone()" in source
    assert "MIC MISSING" in source
    assert "Shell can still start and speak" in source
    assert "this.notifyVoiceFailure(message" not in start_microphone
    assert "this.disconnect()" not in start_microphone
    assert "return false" in start_microphone


def test_gemini_live_auto_selects_cross_platform_microphone_labels():
    source = Path("shell_web_ui/src/services/shell-voice-ai.ts").read_text(encoding="utf-8")

    assert "Auto select best microphone" in Path("shell_web_ui/src/views/Settings.tsx").read_text(encoding="utf-8")
    for label in ("macbook", "built-in", "microphone array", "headset", "airpods", "usb", "analog stereo"):
        assert f"label.includes('{label}')" in source
