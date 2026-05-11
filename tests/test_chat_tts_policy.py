import ast
from pathlib import Path


SRC_PATH = Path(__file__).resolve().parents[1] / "shell_ui" / "shell_cinematic_full.py"
SRC = SRC_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SRC)


def _function(name: str) -> ast.FunctionDef:
    for node in ast.walk(TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function not found: {name}")


def _calls_tts_speak(fn: ast.FunctionDef) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "speak":
            continue
        owner = func.value
        if isinstance(owner, ast.Attribute) and owner.attr == "_tts":
            return True
    return False


def test_typed_chat_reply_handlers_do_not_auto_speak():
    for name in (
        "_on_agent_reply",
        "_on_ai_reply",
        "_on_stream_done",
        "_on_ai_error",
        "_deliver_local_reply",
    ):
        assert not _calls_tts_speak(_function(name)), name


def test_backend_command_speaks_only_for_voice_origin():
    src = ast.get_source_segment(SRC, _function("_finish_backend_command")) or ""
    assert 'if origin == "voice":' in src
    assert "self._tts.speak(text, force=True)" in src
    assert src.index('if origin == "voice":') < src.index("self._tts.speak(text, force=True)")


def test_voice_page_replies_force_tts_even_when_chat_voice_off():
    for name in (
        "_on_voice_stream_chunk",
        "_on_voice_stream_done",
        "_on_voice_ai_reply",
    ):
        src = ast.get_source_segment(SRC, _function(name)) or ""
        assert "force=True" in src, name


def test_manual_bubble_speak_forces_tts():
    speaker = _function("speak")
    assert any(arg.arg == "force" for arg in speaker.args.args)

    bubble_handler = _function("_on_bubble_speak")
    forced = False
    for node in ast.walk(bubble_handler):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "speak":
            continue
        for kw in node.keywords:
            if kw.arg == "force" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                forced = True
    assert forced


def test_chat_payload_requests_text_only_backend_mode():
    src = ast.get_source_segment(SRC, _function("_on_chat_send")) or ""
    assert '"response_mode": "text"' in src
    assert '"speak": False' in src
    assert "Listen to this reply" in SRC


def test_streaming_reply_keeps_bubble_actions_on_full_text():
    chunk_src = ast.get_source_segment(SRC, _function("_on_stream_chunk")) or ""
    done_src = ast.get_source_segment(SRC, _function("_on_stream_done")) or ""
    assert "_raw_text = self._streaming_text" in chunk_src
    assert "_raw_text = final_text" in done_src
