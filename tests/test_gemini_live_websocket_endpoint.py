from pathlib import Path


def test_gemini_live_websocket_uses_official_bidi_endpoint():
    source = Path("shell_web_ui/src/services/shell-voice-ai.ts").read_text(encoding="utf-8")

    assert (
        "wss://generativelanguage.googleapis.com/ws/"
        "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
    ) in source
    assert "generativelanguage.googleapis.com/v1beta/${modelPath}:BidiGenerateContent" not in source
    assert "new URLSearchParams({ key: this.apiKey })" in source
