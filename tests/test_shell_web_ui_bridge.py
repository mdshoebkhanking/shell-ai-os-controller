from PyQt6.QtCore import QCoreApplication


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
