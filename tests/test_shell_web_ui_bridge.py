from PyQt6.QtCore import QCoreApplication
import pytest


PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def test_chart_and_voice_chat_recall_previous_task(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()

    first = bridge._chat_message(["calculate 5*9", {"source": "voice"}])
    recall = bridge._chat_message(["tumhe yaad hai maine abhi kya kaam diya tha?", {"source": "voice"}])

    assert first["success"] is True
    assert "45" in first["reply"]
    assert "calculate 5*9" in recall["reply"]
    assert "koi pehla chart ya command task saved nahi mila" not in recall["reply"]


def test_chart_entry_telemetry_prompt_stays_local(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()

    result = bridge._chat_message(["show CPU chart", {"source": "text", "entry": "chart"}])

    assert result["success"] is True
    assert result["reply"].startswith("Chart: CPU")
    assert "AI provider" not in result["reply"]


def test_gallery_save_and_list_roundtrip(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "GALLERY_DIR", tmp_path / "Pictures" / "Shell_Generated")
    monkeypatch.setattr(host, "GALLERY_META_PATH", tmp_path / "runtime" / "web_ui_gallery.json")
    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()

    saved = bridge._save_image_to_gallery([{"title": "Neon shell city", "base64Data": PNG_DATA_URL}])
    images = bridge._get_gallery_images([])

    assert saved["success"] is True
    assert saved["image"]["filename"].endswith(".png")
    assert images
    assert images[0]["displayName"] == "Neon shell city"
    assert images[0]["url"].startswith("file:")


def test_image_generation_chat_result_surfaces_gallery_path(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    gallery = tmp_path / "Pictures" / "Shell_Generated"
    gallery.mkdir(parents=True)
    image_path = gallery / "shell_ai_20260524_120000_neon_shell_1024x1024_ab12cd.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nprobe")
    monkeypatch.setattr(host, "GALLERY_DIR", gallery)
    monkeypatch.setattr(host, "GALLERY_META_PATH", tmp_path / "runtime" / "web_ui_gallery.json")
    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()

    reply = bridge._format_chat_result(
        {"tool": "shell_image_ai:generate_image_tool"},
        {"status": "success", "result": f"Image Generated\nSaved: `{image_path}`"},
    )

    assert "Gallery mein save ho gayi" in reply
    assert image_path.name in reply


@pytest.mark.parametrize(
    ("text", "meta", "expected_prompt"),
    [
        ("photo generate karo", {"source": "voice"}, "high quality original Shell AI concept image"),
        ("photo generate karke do", {"source": "text"}, "high quality original Shell AI concept image"),
        ("image banao", {"source": "text"}, "high quality original Shell AI concept image"),
        ("generate image", {"source": "text", "entry": "chart"}, "high quality original Shell AI concept image"),
        ("pic banao", {"source": "voice", "entry": "chart"}, "high quality original Shell AI concept image"),
        ("cyberpunk city ki image banao", {"source": "text"}, "cyberpunk city"),
    ],
)
def test_short_image_intents_route_to_generation_and_emit_gallery_events(
    monkeypatch, tmp_path, text, meta, expected_prompt
):
    import shell_web_ui.host as host

    gallery = tmp_path / "Pictures" / "Shell_Generated"
    gallery.mkdir(parents=True)
    image_path = gallery / f"{host.ShellBackendBridge._slug(expected_prompt)}.png"
    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    monkeypatch.setattr(host, "GALLERY_DIR", gallery)
    monkeypatch.setattr(host, "GALLERY_META_PATH", tmp_path / "runtime" / "web_ui_gallery.json")
    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []
    executed_routes = []

    def fake_emit(channel, payload):
        emitted.append((channel, payload))

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_image_ai:generate_image_tool"
        assert route["args"]["description"] == expected_prompt
        image_path.write_bytes(b"\x89PNG\r\n\x1a\nprobe")
        return {"status": "success", "result": f"Image Generated\nSaved: `{image_path}`"}

    monkeypatch.setattr(bridge, "emit_event", fake_emit)
    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)

    result = bridge._chat_message([text, meta])

    image_events = [payload for channel, payload in emitted if channel == "image-gen"]
    gallery_events = [payload for channel, payload in emitted if channel == "gallery-updated"]
    chat_events = [payload for channel, payload in emitted if channel == "chat-updated"]

    assert executed_routes
    assert result["success"] is True
    assert result["route"]["tool"] == "shell_image_ai:generate_image_tool"
    assert "Gallery mein save ho gayi" in result["reply"]
    assert image_events[0]["loading"] is True
    assert image_events[0]["prompt"] == expected_prompt
    assert image_events[-1]["loading"] is False
    assert image_events[-1]["saved"] is True
    assert gallery_events[-1]["image"]["filename"] == image_path.name
    assert chat_events[-1]["source"] == meta.get("source", "text")
    assert chat_events[-1]["voice"] is (meta.get("source") == "voice")


def test_code_write_blocked_reply_names_relevant_safety_settings():
    import shell_web_ui.host as host

    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()

    reply = bridge._format_chat_result(
        {"tool": "shell_code_engine:create_fullstack_app_tool"},
        {"status": "success", "result": "[BLOCKED] Writing LLM-generated Python to disk is disabled by default."},
    )

    assert "Code creation safety settings se blocked hai" in reply
    assert "SHELL_BLOCK_PROJECT_SCAFFOLD=1" in reply
    assert "SHELL_ALLOW_CODE_WRITE=1" in reply
