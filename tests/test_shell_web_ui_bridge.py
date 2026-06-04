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


def test_creator_identity_reply_is_deterministic_for_chat_and_voice(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))

    text_result = bridge._chat_message(["Shell tumhe kisne banaya hai?", {"source": "text"}])
    voice_result = bridge._chat_message(["who made you", {"source": "voice"}])
    chart_result = bridge._chat_message(["shell tume kisne banaya hai", {"source": "text", "entry": "chart"}])
    shell_ko_result = bridge._chat_message(["shell ko kisne banaya hai", {"source": "text", "entry": "chart"}])
    creator_result = bridge._chat_message(["shell ka creator kaun hai?", {"source": "text", "entry": "chart"}])

    assert text_result["reply"] == "Mujhe Md Shoeb King ne banaya hai."
    assert voice_result["reply"] == "Mujhe Md Shoaib King ne banaya hai."
    assert chart_result["reply"] == "Mujhe Md Shoeb King ne banaya hai."
    assert shell_ko_result["reply"] == "Mujhe Md Shoeb King ne banaya hai."
    assert creator_result["reply"] == "Mujhe Md Shoeb King ne banaya hai."
    assert voice_result["route"] is None
    assert [payload["voice"] for channel, payload in emitted if channel == "chat-updated"][1] is True


def test_deep_research_chat_emits_activity_events(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []
    executed_routes = []

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_agents:research_agent_tool"
        assert route["args"]["task"] == "AI chips"
        return {"status": "success", "result": "[ResearchAgent] (success | 7/7 steps | 1.2s) AI chips research summary [Tool Execution: 1.2s]"}

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)

    result = bridge._chat_message(["AI chips ke bare mein deep recerch karo", {"source": "text"}])

    activity_events = [payload for channel, payload in emitted if channel == "activity-updated"]
    assert executed_routes
    assert result["success"] is True
    assert result["route"]["tool"] == "shell_agents:research_agent_tool"
    assert result["reply"].startswith("Deep research complete:")
    assert "shell_agents:research_agent_tool complete" not in result["reply"]
    assert "[ResearchAgent]" not in result["reply"]
    assert "Tool Execution" not in result["reply"]
    assert activity_events[0]["kind"] == "research"
    assert activity_events[0]["status"] == "running"
    assert activity_events[-1]["status"] == "done"
    assert activity_events[-1]["progress"] == 100


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


def test_image_failure_reply_is_user_friendly():
    import shell_web_ui.host as host

    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []

    bridge.emit_event = lambda channel, payload: emitted.append((channel, payload))

    reply = bridge._format_chat_result(
        {"tool": "shell_image_ai:generate_image_tool", "args": {"description": "city"}},
        {
            "status": "success",
            "result": (
                "❌ **Image generation failed.**\n\n"
                "No provider returned a valid image.\n\n"
                "**Provider attempts:**\n- skip OpenAI Images: OPENAI_API_KEY missing\n"
                "- fail Pollinations AI: empty response\n"
                "[Tool Execution: 0.64s]"
            ),
        },
    )

    assert "Image generate nahi ho payi" in reply
    assert "Provider attempts" not in reply
    assert "Tool Execution" not in reply
    assert [payload for channel, payload in emitted if channel == "image-gen"][-1]["error"] is True


def test_chat_message_includes_attached_text_context(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    monkeypatch.setattr(host, "UPLOADS_DIR", tmp_path / "uploads")
    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    seen = {}

    def fake_fallback(text, previous_messages):
        seen["text"] = text
        return "Attached file context received."

    monkeypatch.setattr(bridge, "_brain_chat_fallback", fake_fallback)

    result = bridge._chat_message([
        "is file ko summarize karo",
        {
            "source": "text",
            "entry": "chart",
            "attachments": [
                {
                    "name": "notes.txt",
                    "type": "text/plain",
                    "size": 12,
                    "text": "hello shell file",
                }
            ],
        },
    ])
    history = bridge._read_history_file()

    assert result["success"] is True
    assert "Attached files" in seen["text"]
    assert "hello shell file" in seen["text"]
    assert "Attached: notes.txt" in history[-2]["parts"][0]["text"]


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
