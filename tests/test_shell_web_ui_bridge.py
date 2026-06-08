import pytest


PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _clear_chat_provider_env(monkeypatch, host):
    for group in host.CHAT_PROVIDER_SECRET_GROUPS:
        for key in group:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("SHELL_CHAT_PROVIDER_MODE", raising=False)
    monkeypatch.delenv("SHELL_WEB_CHAT_PROVIDER_MODE", raising=False)
    monkeypatch.delenv("SHELL_CHAT_ONLINE_CHECK", raising=False)


def test_chat_response_depth_policy_matches_intent():
    import shell_web_ui.host as host

    assert host.ShellBackendBridge._chat_response_depth("What is the shortcut to open Shell?") == "short"
    assert host.ShellBackendBridge._chat_response_depth("Explain how Shell decides between local and online modes?") == "medium"
    assert host.ShellBackendBridge._chat_response_depth("Write a full movie script from start to end") == "artifact"
    assert host.ShellBackendBridge._chat_reply_limit("Write a full movie script from start to end") >= 8000


def test_brain_fallback_passes_depth_instruction_and_limit(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    seen = {}

    monkeypatch.setattr(bridge, "_should_try_provider_chat", lambda: False)

    def fake_offline(prompt, system_prompt, previous_messages=None, *, limit=700):
        seen["system"] = system_prompt
        seen["limit"] = limit
        return "Structured explanation."

    monkeypatch.setattr(bridge, "_offline_chat_reply", fake_offline)

    reply = bridge._brain_chat_fallback("Explain how Shell decides between local and online modes?")

    assert reply == "Structured explanation."
    assert "medium-length structured answer" in seen["system"]
    assert seen["limit"] >= 1600


def test_full_movie_script_local_artifact_explains_split_limit():
    import shell_web_ui.host as host

    body = host.ShellBackendBridge._local_artifact_content(
        "Write a full movie script from start to end",
        file_type="pdf",
    )

    assert "ACT STRUCTURE" in body
    assert "FADE IN:" in body
    assert "END OF PART 1 - NATURAL BREAK" in body
    assert "I've written until" in body
    assert "I can continue with the next part if you ask." in body
    assert "Act 1" in body
    assert body.count("CUT TO:") >= 4
    assert "Ending note:" not in body
    assert "Logline:" not in body


def test_chart_and_voice_chat_recall_previous_task(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
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
    bridge = host.ShellBackendBridge()

    result = bridge._chat_message(["show CPU chart", {"source": "text", "entry": "chart"}])

    assert result["success"] is True
    assert result["reply"].startswith("Chart: CPU")
    assert "AI provider" not in result["reply"]


def test_chat_direct_tool_command_executes_catalog_tool(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()

    result = bridge._chat_message([
        '/tool shell_calculator:calculate_tool {"expression":"5*9"}',
        {"source": "text"},
    ])

    assert result["success"] is True
    assert result["route"]["tool"] == "shell_calculator:calculate_tool"
    assert result["route"]["source"] == "chat-direct-command"
    assert "Result: 45" in result["reply"]


def test_direct_tool_execution_works_inside_running_event_loop():
    import asyncio

    from shell_tool_gateway import execute_tool_sync

    async def run_inside_loop():
        return execute_tool_sync("shell_calculator:calculate_tool", {"expression": "4*11"})

    result = asyncio.run(run_inside_loop())

    assert result["status"] == "success"
    assert "Result: 44" in result["result"]


def test_voice_direct_tool_command_uses_same_chat_route(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    emitted = []

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))

    result = bridge._chat_message([
        '/tool shell_calculator:calculate_tool {"expression":"6*7"}',
        {"source": "voice"},
    ])

    assert result["success"] is True
    assert result["route"]["tool"] == "shell_calculator:calculate_tool"
    assert "Result: 42" in result["reply"]
    assert [payload for channel, payload in emitted if channel == "chat-updated"][-1]["voice"] is True


def test_chat_direct_agent_command_maps_text_to_agent_task(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    executed_routes = []

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_agents:developer_agent_tool"
        assert route["kind"] == "agent"
        assert route["args"] == {"task": "write python fibonacci function"}
        return {"status": "success", "result": "def fibonacci(n):\n    return n if n < 2 else fibonacci(n-1) + fibonacci(n-2)"}

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)

    result = bridge._chat_message([
        "/agent shell_agents:developer_agent_tool write python fibonacci function",
        {"source": "text"},
    ])

    assert executed_routes
    assert result["success"] is True
    assert result["route"]["source"] == "chat-direct-command"
    assert "def fibonacci" in result["reply"]


def test_chat_direct_tool_invalid_json_returns_clean_error(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()

    def fallback_should_not_run(*_args, **_kwargs):
        raise AssertionError("invalid direct tool command should not fall through to brain fallback")

    monkeypatch.setattr(bridge, "_brain_chat_fallback", fallback_should_not_run)

    result = bridge._chat_message([
        '/tool shell_calculator:calculate_tool {"expression":',
        {"source": "text"},
    ])

    assert result["success"] is True
    assert result["route"] is None
    assert "valid JSON object nahi" in result["reply"]


def test_unknown_actionable_chat_command_routes_to_agent_orchestrator(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    executed_routes = []

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_agent_orchestrator:orchestrate_shell_goal_tool"
        assert route["args"]["goal"] == "control my imaginary workflow safely"
        assert route["args"]["execute"] is True
        assert route["args"]["approved"] is False
        return {"status": "success", "result": '{"status":"needs_planning","selected_agent_name":"Planner Agent"}'}

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)

    result = bridge._chat_message(["control my imaginary workflow safely", {"source": "text"}])

    assert executed_routes
    assert result["success"] is True
    assert result["route"]["source"] == "web-ui-command-orchestrator"
    assert "direct safe local tool" in result["reply"]
    assert "Shell agent planner complete" not in result["reply"]


def test_direct_tool_id_with_recall_word_does_not_trigger_conversation_recall(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    executed_routes = []

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_core_memory:shell_recall_core_memory_tool"
        return {"status": "success", "result": "core memory probe"}

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)

    result = bridge._chat_message([
        '/tool shell_core_memory:shell_recall_core_memory_tool {"query":"probe","limit":1}',
        {"source": "text"},
    ])

    assert executed_routes
    assert result["success"] is True
    assert result["route"]["tool"] == "shell_core_memory:shell_recall_core_memory_tool"
    assert "core memory probe" in result["reply"]
    assert "Tumne pichla kaam" not in result["reply"]


def test_chat_message_uses_offline_llm_after_provider_failure(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    emitted = []

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(bridge, "_provider_chat_reply", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(bridge, "_offline_chat_reply", lambda *_args, **_kwargs: "Offline model se jawab aa gaya.")

    result = bridge._chat_message(["what is recursion?", {"source": "text"}])

    assert result["success"] is True
    assert result["reply"] == "Offline model se jawab aa gaya."
    assert "AI provider" not in result["reply"]
    assert [payload for channel, payload in emitted if channel == "chat-updated"][-1]["voice"] is False


def test_chart_text_prompt_can_use_offline_llm_without_voice(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    emitted = []

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(bridge, "_provider_chat_reply", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(bridge, "_offline_chat_reply", lambda *_args, **_kwargs: "Offline chart answer.")

    result = bridge._chat_message(["what is recursion?", {"source": "text", "entry": "chart"}])

    assert result["success"] is True
    assert result["reply"] == "Offline chart answer."
    assert result["route"] is None
    assert [payload for channel, payload in emitted if channel == "chat-updated"][-1]["voice"] is False


def test_voice_prompt_uses_offline_llm_and_stays_voice_originated(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    emitted = []

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(bridge, "_provider_chat_reply", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(bridge, "_offline_chat_reply", lambda *_args, **_kwargs: "Offline voice answer.")

    result = bridge._chat_message(["what is recursion?", {"source": "voice"}])

    assert result["success"] is True
    assert result["reply"] == "Offline voice answer."
    assert [payload for channel, payload in emitted if channel == "chat-updated"][-1]["voice"] is True


def test_windows_offline_llm_deferred_reply_replaces_placeholder(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    monkeypatch.setenv("SHELL_OFFLINE_LLM_ASYNC_UI", "1")
    bridge = host.ShellBackendBridge()
    emitted = []
    pending_tasks = []

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(
        host,
        "offline_llm_status",
        lambda: {"success": True, "available": True, "status": "ready", "modelPath": "local.gguf"},
    )
    monkeypatch.setattr(bridge, "_brain_chat_fallback", lambda *_args, **_kwargs: "Final local brain answer.")
    monkeypatch.setattr(bridge, "_start_background_task", lambda _name, target: pending_tasks.append(target))

    result = bridge._chat_message(["what is recursion?", {"source": "voice"}])

    assert result["success"] is True
    assert result["pending"] is True
    assert result["reply"].startswith("Local brain loading")
    assert pending_tasks

    immediate_event = [payload for channel, payload in emitted if channel == "chat-updated"][-1]
    assert immediate_event["pending"] is True
    assert immediate_event["voice"] is False

    history = bridge._read_history_file()
    assert history[-1]["pendingOfflineChatId"]
    assert "Local brain loading" in history[-1]["parts"][0]["text"]

    pending_tasks[0]()

    final_history = bridge._read_history_file()
    assert final_history[-1]["parts"][0]["text"] == "Final local brain answer."
    assert "pendingOfflineChatId" not in final_history[-1]
    final_event = [payload for channel, payload in emitted if channel == "chat-updated"][-1]
    assert final_event["pending"] is False
    assert final_event["voice"] is True


def test_chat_provider_success_skips_offline_llm(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    monkeypatch.setenv("GOOGLE_API_KEY", "g" * 32)
    bridge = host.ShellBackendBridge()
    calls = {"provider": 0, "offline": 0}

    monkeypatch.setattr(bridge, "_chat_provider_network_ready", lambda _keys: True)

    def fake_provider(*_args, **_kwargs):
        calls["provider"] += 1
        return "Gemini provider answer."

    def fake_offline(*_args, **_kwargs):
        calls["offline"] += 1
        return "Offline answer should not be used."

    monkeypatch.setattr(bridge, "_provider_chat_reply", fake_provider)
    monkeypatch.setattr(bridge, "_offline_chat_reply", fake_offline)

    result = bridge._chat_message(["what is recursion?", {"source": "text"}])

    assert result["reply"] == "Gemini provider answer."
    assert calls == {"provider": 1, "offline": 0}


def test_offline_llm_select_installed_model_updates_selected_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_OFFLINE_LLM_MODEL_DIR", str(tmp_path / "user-models"))

    import shell_offline_model_catalog
    import shell_web_ui.host as host

    option = shell_offline_model_catalog.get_model_option("qwen2.5-1.5b-q4")
    assert option is not None
    model_path = shell_offline_model_catalog.model_install_dir(option.id) / option.filename
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"gguf-probe")
    bridge = host.ShellBackendBridge()

    result = bridge._dispatch("offline-llm-select", [{"modelId": option.id}])

    assert result["success"] is True
    assert result["status"] == "selected"
    assert result["modelId"] == option.id
    assert result["catalog"]["selectedModelId"] == option.id
    assert result["catalog"]["selectedModelPath"] == str(model_path)
    assert result["catalog"]["options"][0]["installed"] is True


def test_offline_llm_select_requires_installed_model(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_OFFLINE_LLM_MODEL_DIR", str(tmp_path / "user-models"))

    import shell_web_ui.host as host

    bridge = host.ShellBackendBridge()

    result = bridge._dispatch("offline-llm-select", [{"modelId": "qwen2.5-3b-q4"}])

    assert result["success"] is False
    assert result["status"] == "missing"
    assert "Download this offline brain" in result["message"]


def test_offline_coding_llm_select_uses_separate_coding_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_OFFLINE_LLM_MODEL_DIR", str(tmp_path / "user-models"))

    import shell_offline_model_catalog
    import shell_web_ui.host as host

    option = shell_offline_model_catalog.get_model_option("qwen2.5-coder-3b-q4", "coding")
    assert option is not None
    model_path = shell_offline_model_catalog.model_install_dir(option.id) / option.filename
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"gguf-probe")
    bridge = host.ShellBackendBridge()

    result = bridge._dispatch("offline-coding-llm-select", [{"modelId": option.id}])
    chat_catalog = bridge._dispatch("offline-llm-catalog", [])

    assert result["success"] is True
    assert result["category"] == "coding"
    assert result["catalog"]["category"] == "coding"
    assert result["catalog"]["selectedModelId"] == option.id
    assert result["catalog"]["selectedModelPath"] == str(model_path)
    assert chat_catalog["category"] == "chat"
    assert chat_catalog["selectedModelId"] != option.id


def test_chat_without_api_key_skips_provider_and_uses_offline(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    bridge = host.ShellBackendBridge()

    def provider_should_not_run(*_args, **_kwargs):
        raise AssertionError("provider should be skipped when no chat API key is configured")

    monkeypatch.setattr(bridge, "_provider_chat_reply", provider_should_not_run)
    monkeypatch.setattr(bridge, "_offline_chat_reply", lambda *_args, **_kwargs: "Offline no-key answer.")

    result = bridge._chat_message(["what is recursion?", {"source": "text"}])

    assert result["reply"] == "Offline no-key answer."


def test_chat_offline_network_skips_provider_even_with_api_key(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    monkeypatch.setenv("GEMINI_API_KEY", "g" * 32)
    bridge = host.ShellBackendBridge()

    monkeypatch.setattr(bridge, "_chat_provider_network_ready", lambda _keys: False)

    def provider_should_not_run(*_args, **_kwargs):
        raise AssertionError("provider should be skipped when network probe says offline")

    monkeypatch.setattr(bridge, "_provider_chat_reply", provider_should_not_run)
    monkeypatch.setattr(bridge, "_offline_chat_reply", lambda *_args, **_kwargs: "Offline network answer.")

    result = bridge._chat_message(["what is recursion?", {"source": "text"}])

    assert result["reply"] == "Offline network answer."


def test_voice_tts_offline_network_skips_gemini_and_queues_kokoro(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    monkeypatch.setenv("GEMINI_API_KEY", "g" * 32)
    monkeypatch.setenv("SHELL_VOICE_MODE", "auto")
    bridge = host.ShellBackendBridge()

    monkeypatch.setattr(bridge, "_chat_provider_network_ready", lambda _keys: False)
    monkeypatch.setattr(
        host,
        "offline_tts_status",
        lambda: {"available": True, "engine": "kokoro", "label": "Kokoro offline voice", "reason": "ready"},
    )
    monkeypatch.setattr(
        bridge,
        "_queue_offline_tts",
        lambda text: {"success": True, "queued": True, "source": "offline-tts", "engine": "offline", "text": text},
    )

    result = bridge._speak_text(["offline voice reply"])

    assert result["success"] is True
    assert result["source"] == "offline-tts"
    assert result["engine"] == "kokoro"


def test_speech_status_payload_includes_text_for_orb_reactivity():
    import shell_web_ui.host as host

    payload = host.ShellBackendBridge._speech_status_payload(
        "speaking",
        {"engine": "kokoro", "durationMs": 1200, "amplitudeFrames": [0.2, 0.7]},
        text="Kokoro orb reaction test",
    )

    assert payload["state"] == "speaking"
    assert payload["engine"] == "kokoro"
    assert payload["text"] == "Kokoro orb reaction test"
    assert payload["amplitudeFrames"] == [0.2, 0.7]


def test_voice_tts_online_gemini_key_uses_cloud_voice(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    class _Signal:
        def connect(self, _callback):
            return None

    class _FakeSpeaker:
        instances = []

        def __init__(self, _bridge):
            self.speech_error = _Signal()
            self.speaking_finished = _Signal()
            self.calls = []
            self._engine = ""
            self.__class__.instances.append(self)

        def start(self):
            self.calls.append(("start", ""))

        def set_voice(self, voice):
            self.calls.append(("voice", voice))

        def speak(self, text, force=False):
            self.calls.append(("speak", text, force))

        def voice_identity_snapshot(self):
            return {"gemini_voice": "Aoede"}

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    monkeypatch.setenv("GOOGLE_API_KEY", "g" * 32)
    monkeypatch.setenv("SHELL_VOICE_MODE", "auto")
    monkeypatch.setattr(host, "TTSSpeaker", _FakeSpeaker)
    bridge = host.ShellBackendBridge()

    monkeypatch.setattr(bridge, "_chat_provider_network_ready", lambda _keys: True)

    result = bridge._speak_text(["cloud voice reply"])

    assert result["success"] is True
    assert result["engine"] == "gemini"
    assert _FakeSpeaker.instances[-1].calls[-1] == ("speak", "cloud voice reply", True)


def test_offline_fallback_prompt_includes_memory_and_project_rag(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    monkeypatch.setenv("SHELL_CHAT_PROVIDER_MODE", "offline")
    bridge = host.ShellBackendBridge()
    seen = {}

    monkeypatch.setattr(bridge, "_memory_context_snippet", lambda _query: "- user prefers concise Hinglish replies")
    monkeypatch.setattr(bridge, "_project_rag_context_snippet", lambda _query: "- shell_web_ui/host.py: offline routing lives here")

    def fake_offline(prompt, system_prompt, previous_messages):
        seen["prompt"] = prompt
        seen["system_prompt"] = system_prompt
        seen["previous_messages"] = previous_messages
        return "Offline context answer."

    monkeypatch.setattr(bridge, "_offline_chat_reply", fake_offline)

    reply = bridge._brain_chat_fallback(
        "offline model ka route batao",
        previous_messages=[{"role": "user", "parts": [{"text": "pehle ka task"}]}],
    )

    assert reply == "Offline context answer."
    assert "Recent conversation:" in seen["prompt"]
    assert "Relevant local memory:" in seen["prompt"]
    assert "user prefers concise Hinglish replies" in seen["prompt"]
    assert "Relevant Project RAG:" in seen["prompt"]
    assert "shell_web_ui/host.py" in seen["prompt"]
    assert "memory, and Project RAG context" in seen["system_prompt"]


def test_offline_chat_filters_stale_provider_fallback_history(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    seen = {}

    class FakeResult:
        success = True
        reply = "4"

    stale = {
        "role": "model",
        "parts": [
            {
                "text": (
                    "Mujhe sawaal mil gaya, lekin AI provider abhi available nahi hai. "
                    "API key set karoge to main is par proper detailed jawab de paungi."
                )
            }
        ],
    }
    useful = {"role": "user", "parts": [{"text": "pehla useful sawal"}]}

    def fake_generate(_prompt, system_prompt="", previous_messages=None):
        assert system_prompt == "short"
        seen["previous_messages"] = list(previous_messages or [])
        return FakeResult()

    monkeypatch.setattr(host, "generate_offline_reply", fake_generate)

    reply = bridge._offline_chat_reply("2 plus 2?", "short", [useful, stale])
    context = bridge._history_context_snippet([useful, stale])

    assert reply == "4"
    assert seen["previous_messages"] == [useful]
    assert "AI provider abhi available" not in context


def test_offline_chat_retries_when_model_repeats_stale_fallback(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    calls = []

    class FakeResult:
        def __init__(self, reply):
            self.success = True
            self.reply = reply

    def fake_generate(_prompt, system_prompt="", previous_messages=None):
        assert system_prompt == "short"
        calls.append(list(previous_messages or []))
        if previous_messages:
            return FakeResult(
                "Mujhe sawaal mil gaya, lekin AI provider abhi available nahi hai. API key set karoge."
            )
        return FakeResult("Offline answer ready.")

    monkeypatch.setattr(host, "generate_offline_reply", fake_generate)

    history = [{"role": "user", "parts": [{"text": "old context"}]}]
    reply = bridge._offline_chat_reply("offline answer do", "short", history)

    assert reply == "Offline answer ready."
    assert calls == [history, []]


def test_provider_unavailable_variants_are_never_emitted_or_saved(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    monkeypatch.setenv("GOOGLE_API_KEY", "g" * 32)
    bridge = host.ShellBackendBridge()
    emitted = []

    monkeypatch.setattr(bridge, "_chat_provider_network_ready", lambda _keys: True)
    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(bridge, "_provider_chat_reply", lambda *_args, **_kwargs: "AI provider not available. Set an API key.")
    monkeypatch.setattr(bridge, "_offline_chat_reply", lambda *_args, **_kwargs: "")

    result = bridge._chat_message(["what is recursion?", {"source": "text"}])
    history = bridge._read_history_file()

    assert result["success"] is True
    assert "provider" not in result["reply"].lower()
    assert "api key" not in result["reply"].lower()
    assert all("provider" not in bridge._history_text(item).lower() for item in history if item.get("role") == "model")
    assert [payload for channel, payload in emitted if channel == "chat-updated"][-1]["reply"] == result["reply"]


def test_brain_fallback_retries_offline_llm_with_raw_prompt_after_context_poison(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    calls = []

    def fake_offline(prompt, _system_prompt, previous_messages):
        calls.append((prompt, list(previous_messages or [])))
        if "Recent conversation:" in prompt:
            return ""
        return "Raw offline answer."

    monkeypatch.setattr(bridge, "_offline_chat_reply", fake_offline)
    monkeypatch.setattr(bridge, "_memory_context_snippet", lambda _query: "")
    monkeypatch.setattr(bridge, "_project_rag_context_snippet", lambda _query: "")
    monkeypatch.setattr(bridge, "_should_try_provider_chat", lambda: False)

    reply = bridge._brain_chat_fallback(
        "explain raw fallback retry",
        previous_messages=[{"role": "user", "parts": [{"text": "old context"}]}],
    )

    assert reply == "Raw offline answer."
    assert len(calls) == 2
    assert "Recent conversation:" in calls[0][0]
    assert calls[1] == ("explain raw fallback retry", [])


def test_creator_identity_reply_is_deterministic_for_chat_and_voice(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    emitted = []

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))

    text_result = bridge._chat_message(["Shell tumhe kisne banaya hai?", {"source": "text"}])
    voice_result = bridge._chat_message(["who made you", {"source": "voice"}])
    chart_result = bridge._chat_message(["shell tume kisne banaya hai", {"source": "text", "entry": "chart"}])
    shell_ko_result = bridge._chat_message(["shell ko kisne banaya hai", {"source": "text", "entry": "chart"}])
    creator_result = bridge._chat_message(["shell ka creator kaun hai?", {"source": "text", "entry": "chart"}])

    assert text_result["reply"] == "Mujhe mdshoebking ne banaya hai."
    assert voice_result["reply"] == "Mujhe mdshoebking ne banaya hai."
    assert chart_result["reply"] == "Mujhe mdshoebking ne banaya hai."
    assert shell_ko_result["reply"] == "Mujhe mdshoebking ne banaya hai."
    assert creator_result["reply"] == "Mujhe mdshoebking ne banaya hai."
    assert voice_result["route"] is None
    assert [payload["voice"] for channel, payload in emitted if channel == "chat-updated"][1] is True


def test_who_are_you_identity_does_not_return_creator(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()

    monkeypatch.setattr(bridge, "_provider_chat_reply", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(bridge, "_offline_chat_reply", lambda *_args, **_kwargs: "")

    result = bridge._chat_message(["tum kon ho?", {"source": "text"}])

    assert result["reply"] == "Main Shell AI hoon, tumhara desktop OS controller aur assistant."
    assert "mdshoebking" not in result["reply"]


def test_unrequested_creator_identity_from_offline_brain_is_rejected(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()

    monkeypatch.setattr(bridge, "_provider_chat_reply", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(bridge, "_offline_chat_reply", lambda *_args, **_kwargs: "Mujhe mdshoebking ne banaya hai.")

    hello = bridge._chat_message(["hello", {"source": "text"}])
    followup = bridge._chat_message(["kya karre yaar", {"source": "text"}])

    assert hello["reply"] == "Haan bhai, bolo. Main sun rahi hoon."
    assert "mdshoebking" not in hello["reply"]
    assert "mdshoebking" not in followup["reply"]
    assert "local mode" in followup["reply"]


def test_deep_research_chat_emits_activity_events(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    monkeypatch.setenv("SHELL_ALLOW_INTERNET_RESEARCH", "1")
    monkeypatch.delenv("GOOGLE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("SEARCH_ENGINE_ID", raising=False)
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


def test_research_chat_stays_offline_when_internet_research_disabled(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    monkeypatch.setenv("SHELL_ALLOW_INTERNET_RESEARCH", "0")
    bridge = host.ShellBackendBridge()

    monkeypatch.setattr(bridge, "_execute_routed_tool", lambda _route: pytest.fail("research route should not execute"))

    result = bridge._chat_message(["research 2026 web design trends", {"source": "text"}])

    assert result["success"] is True
    assert result["result"]["status"] == "offline_research_disabled"
    assert result["reply"] == host.ShellBackendBridge._internet_research_disabled_reply()


def test_allowed_research_injects_fetched_web_context(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    monkeypatch.setenv("SHELL_ALLOW_INTERNET_RESEARCH", "1")
    bridge = host.ShellBackendBridge()
    executed_routes = []

    monkeypatch.setattr(
        bridge,
        "_web_research_summary",
        lambda _query: "Title: Example trend report\nURL: https://example.com/trends\nPage excerpt: Current design systems use dense bento layouts.",
    )

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_agents:research_agent_tool"
        assert "Use this fetched web research context" in route["args"]["task"]
        assert "https://example.com/trends" in route["args"]["task"]
        return {"status": "success", "result": "[ResearchAgent] Current design systems use dense bento layouts."}

    monkeypatch.setattr(bridge, "emit_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)

    result = bridge._chat_message(["compare current AI APIs", {"source": "text"}])

    assert executed_routes
    assert result["success"] is True
    assert result["route"]["mode"] == "online-research"
    assert result["route"]["modeLabel"] == "Online research"
    assert result["reply"].startswith("Deep research complete:")


def test_gallery_save_and_list_roundtrip(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "GALLERY_DIR", tmp_path / "Pictures" / "Shell_Generated")
    monkeypatch.setattr(host, "GALLERY_META_PATH", tmp_path / "runtime" / "web_ui_gallery.json")
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
    bridge = host.ShellBackendBridge()

    reply = bridge._format_chat_result(
        {"tool": "shell_image_ai:generate_image_tool"},
        {"status": "success", "result": f"Image Generated\nSaved: `{image_path}`"},
    )

    assert "Gallery mein save ho gayi" in reply
    assert image_path.name in reply


def test_image_failure_reply_is_user_friendly():
    import shell_web_ui.host as host
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
        ("mere liye koi cat ke photo ganarete karke do ok", {"source": "text"}, "cat"),
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
    bridge = host.ShellBackendBridge()
    emitted = []
    executed_routes = []

    def fake_emit(channel, payload):
        emitted.append((channel, payload))

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_image_ai:generate_image_tool"
        assert route["args"]["description"] == expected_prompt
        assert route["args"]["use_cache"] is False
        assert route["args"]["force_fresh"] is True
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


def test_pdf_creation_chat_routes_before_brain_refusal_fallback(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    emitted = []
    executed_routes = []

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
        assert route["args"]["destination"] == "documents"
        assert route["args"]["file_type"] == "pdf"
        assert route["args"]["content"] == "Generated PDF body about AI tools."
        assert "content_request" not in route["args"]
        return {
            "status": "success",
            "result": {
                "ok": True,
                "action": "created",
                "destination": "documents",
                "path": r"C:\Users\Administrator\Documents\ai_tools.pdf",
                "filename": "ai_tools.pdf",
                "ui_hint": "open_file_location",
            },
        }

    def fallback_should_not_run(*_args, **_kwargs):
        raise AssertionError("tool-capable PDF request should not fall through to brain fallback")

    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))
    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)
    monkeypatch.setattr(
        bridge,
        "_generated_artifact_content",
        lambda request, **_kwargs: "Generated PDF body about AI tools.",
    )
    monkeypatch.setattr(bridge, "_brain_chat_fallback", fallback_should_not_run)

    result = bridge._chat_message(["AI tools ke bare mein pdf bana do", {"source": "text"}])

    assert executed_routes
    assert result["success"] is True
    assert result["route"]["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert result["reply"] == "I created ai_tools.pdf on your documents."
    assert result["ui_actions"][0]["type"] == "OPEN_FILE_LOCATION"
    assert "cannot" not in result["reply"].lower()
    chat_event = [payload for channel, payload in emitted if channel == "chat-updated"][-1]
    assert chat_event["success"] is True
    assert chat_event["ui_actions"] == result["ui_actions"]
    history = bridge._read_history_file()
    assert history[-1]["uiActions"] == result["ui_actions"]


def test_login_html_chat_saves_working_html_when_offline_brain_is_generic(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    executed_routes = []

    class GenericOfflineResult:
        success = True
        reply = (
            "Useful Content Mere Liyye Login Page Html\n"
            "Yeh document useful content ke liye Shell AI ne local mode mein draft kiya hai."
        )

    def fake_execute(route):
        executed_routes.append(route)
        args = route["args"]
        html = args["content"]
        assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
        assert args["filename"] == "login_page.html"
        assert args["destination"] == "desktop"
        assert args["file_type"] == "html"
        assert "<!doctype html>" in html.lower()
        assert "<form" in html.lower()
        assert "type=\"password\"" in html.lower()
        assert "addEventListener('submit'" in html
        assert "Useful Content" not in html
        return {"status": "success", "result": "Created login_page.html on desktop"}

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)
    monkeypatch.setattr(bridge, "_should_try_provider_chat", lambda: False)
    monkeypatch.setattr(host, "generate_offline_coding_reply", lambda *_args, **_kwargs: GenericOfflineResult())
    monkeypatch.setattr(host, "generate_offline_reply", lambda *_args, **_kwargs: GenericOfflineResult())

    result = bridge._chat_message(["mere liyye login page banao html main or osse save kardo", {"source": "text"}])

    assert executed_routes
    assert result["success"] is True
    assert result["route"]["tool"] == "shell_workspace_tools:create_user_file_tool"
    assert result["reply"] == "I created login_page.html on your desktop."


def test_hard_full_app_requires_online_key_before_code_tool(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    bridge = host.ShellBackendBridge()

    def execute_should_not_run(_route):
        raise AssertionError("hard full-app task should ask for online key before executing")

    monkeypatch.setattr(bridge, "_execute_routed_tool", execute_should_not_run)

    result = bridge._chat_message(["Build a full app with authentication, backend API, and database", {"source": "text"}])

    assert result["success"] is True
    assert result["route"]["tool"] == "shell_code_engine:create_fullstack_app_tool"
    assert result["route"]["mode"] == "local-basic-offered"
    assert result["route"]["modeLabel"] == "Local basic available"
    assert "basic version offline" in result["reply"]
    assert "API Keys" in result["reply"]


def test_hard_full_app_requires_online_mode_even_with_key(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-000000")
    bridge = host.ShellBackendBridge()

    def execute_should_not_run(_route):
        raise AssertionError("hard task should require online mode before executing")

    monkeypatch.setattr(bridge, "_chat_provider_network_ready", lambda _keys: True)
    monkeypatch.setattr(bridge, "_execute_routed_tool", execute_should_not_run)

    result = bridge._chat_message(["Build a full app with authentication, backend API, and database", {"source": "text"}])

    assert result["success"] is True
    assert result["route"]["mode"] == "local-basic-offered"
    assert "online mode enabled nahi hai" in result["reply"]


def test_pdf_summary_of_complex_topic_stays_level_1_local(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    bridge = host.ShellBackendBridge()
    executed_routes = []

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
        assert route.get("mode") == "local"
        assert route.get("modeLabel") == "Local"
        return {"status": "success", "result": "Created file: Documents/full_app_summary.pdf"}

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)
    monkeypatch.setattr(bridge, "_generated_artifact_content", lambda request, **_kwargs: "Local summary content.")

    result = bridge._chat_message(["Make a PDF summary of this full app architecture", {"source": "text"}])

    assert executed_routes
    assert result["success"] is True
    assert "online full version" not in result["reply"]


def test_pdf_summary_generation_uses_local_make_mode_without_key(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    bridge = host.ShellBackendBridge()
    monkeypatch.setattr(
        bridge,
        "_provider_chat_reply",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("local PDF summary should not use cloud")),
    )

    body = bridge._generated_artifact_content(
        "Make a PDF summary of this text: First point. Second point.",
        file_type="pdf",
    )

    assert "Summary" in body
    assert "- Make a PDF summary" in body or "- First point." in body


def test_pdf_summary_generation_uses_cloud_when_online_ready(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-000000")
    monkeypatch.setenv("SHELL_CHAT_PROVIDER_MODE", "online")
    bridge = host.ShellBackendBridge()
    monkeypatch.setattr(bridge, "_should_try_provider_chat", lambda: True)
    monkeypatch.setattr(bridge, "_provider_chat_reply", lambda *_args, **_kwargs: "Pro PDF\n\nExecutive Summary\n- Improved")

    body = bridge._generated_artifact_content(
        "Make a PDF summary of this text: rough notes",
        file_type="pdf",
    )

    assert "Executive Summary" in body
    assert "Improved" in body


def test_basic_portfolio_website_runs_level_1_local_without_key(monkeypatch, tmp_path):
    import shell_web_ui.host as host
    import json

    history_path = tmp_path / "web_ui_history.json"
    monkeypatch.setattr(host, "HISTORY_PATH", history_path)
    _clear_chat_provider_env(monkeypatch, host)
    bridge = host.ShellBackendBridge()
    executed_routes = []

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_code_engine:create_fullstack_app_tool"
        assert route.get("mode") == "local"
        assert route.get("modeLabel") == "Local"
        assert "portfolio" in route["args"]["app_type"].lower()
        return {"status": "success", "result": "[SUCCESS] PROJECT BUILT AND LAUNCHED SUCCESSFULLY!"}

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)

    result = bridge._chat_message(["Make a portfolio website for me", {"source": "text"}])

    assert executed_routes
    assert result["success"] is True
    assert "online full version" not in result["reply"]
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert history[-1]["mode"] == "local"
    assert history[-1]["modeLabel"] == "Local"


def test_hard_full_app_runs_when_online_key_is_ready(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    _clear_chat_provider_env(monkeypatch, host)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-000000")
    monkeypatch.setenv("SHELL_CHAT_PROVIDER_MODE", "online")
    bridge = host.ShellBackendBridge()
    executed_routes = []

    monkeypatch.setattr(bridge, "_chat_provider_network_ready", lambda _keys: True)

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_code_engine:create_fullstack_app_tool"
        assert route.get("mode") == "online-api"
        assert route.get("modeLabel") == "Online (API)"
        return {"status": "success", "result": "[SUCCESS] PROJECT BUILT AND LAUNCHED SUCCESSFULLY!"}

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)

    result = bridge._chat_message(["Build a full app with authentication, backend API, and database", {"source": "text"}])

    assert executed_routes
    assert result["success"] is True
    assert "online full version" not in result["reply"]


def test_movie_script_pdf_chat_generates_script_content_before_file_tool(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    executed_routes = []

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_workspace_tools:create_user_file_tool"
        assert route["args"]["file_type"] == "pdf"
        assert "Scene 1" in route["args"]["content"]
        assert "movie script" not in route["args"]["content"].lower()[:40]
        return {"status": "success", "result": "Created file: Documents/movie_script.pdf"}

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)
    monkeypatch.setattr(
        bridge,
        "_generated_artifact_content",
        lambda request, **_kwargs: "Title\n\nScene 1 - Interior\nA real script body.",
    )

    result = bridge._chat_message(["movie script ka pdf banao", {"source": "text"}])

    assert executed_routes
    assert result["success"] is True
    assert result["reply"].startswith("I created ")
    assert " on your documents." in result["reply"]


def test_file_tool_result_uses_user_message_and_open_folder_action():
    import shell_web_ui.host as host

    bridge = host.ShellBackendBridge()

    formatted = bridge._format_chat_result_payload(
        {"tool": "shell_workspace_tools:create_user_file_tool", "args": {"destination": "desktop"}},
        {
            "status": "success",
            "result": {
                "ok": True,
                "action": "created",
                "message": "Created notes.txt on desktop",
                "destination": "desktop",
                "path": r"C:\Users\Administrator\Desktop\notes.txt",
                "filename": "notes.txt",
                "bytes": 448,
                "ui_hint": "open_file_location",
            },
        },
    )

    assert formatted["user_message"] == "I created notes.txt on your desktop."
    assert formatted["ui_actions"] == [
        {
            "type": "OPEN_FILE_LOCATION",
            "label": "Open folder",
            "path": r"C:\Users\Administrator\Desktop\notes.txt",
        }
    ]
    assert "shell_workspace_tools" not in formatted["user_message"]
    assert "{" not in formatted["user_message"]


def test_tool_result_error_is_human_readable():
    import shell_web_ui.host as host

    bridge = host.ShellBackendBridge()

    reply = bridge._format_chat_result(
        {"tool": "shell_workspace_tools:create_user_file_tool", "args": {"filename": "notes.txt", "destination": "desktop"}},
        {"status": "success", "result": {"ok": False, "error": "Permission denied while writing Desktop\\notes.txt"}},
    )

    assert reply == "I couldn’t complete this action. Reason: Permission denied while writing Desktop\\notes.txt"
    assert "shell_workspace_tools" not in reply
    assert '"ok": false' not in reply.lower()


def test_known_workflow_tool_results_are_human_readable():
    import shell_web_ui.host as host

    bridge = host.ShellBackendBridge()

    slideshow = bridge._format_chat_result(
        {"tool": "shell_windows_workflows:open_recent_screenshots_slideshow_tool"},
        {"status": "success", "result": {"ok": True}},
    )
    downloads = bridge._format_chat_result(
        {
            "tool": "shell_windows_workflows:organize_downloads_setups_pdfs_tool",
            "args": {"zip_folder": "Setups", "pdf_folder": "PDFs"},
        },
        {"status": "success", "result": {"ok": True}},
    )

    assert slideshow == "I opened your Screenshots folder and Photos."
    assert downloads == "I organized your Downloads into Setups and PDFs."
    assert "shell_windows_workflows" not in slideshow
    assert "{" not in downloads


def test_gmail_request_misrouted_to_downloads_tool_explains_limitation():
    import shell_web_ui.host as host

    bridge = host.ShellBackendBridge()

    reply = bridge._format_chat_result(
        {
            "tool": "shell_windows_workflows:organize_downloads_setups_pdfs_tool",
            "request": "search Gmail for invoices and download PDFs",
            "args": {"zip_folder": "Setups", "pdf_folder": "PDFs"},
        },
        {"status": "success", "result": {"ok": True}},
    )

    assert "Local tools only support organizing local Downloads" in reply
    assert "Gmail search and download is not implemented yet" in reply
    assert "shell_windows_workflows" not in reply


def test_downloads_audit_cleanup_asks_permission_then_executes_on_approval(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    executed_routes = []

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_windows_workflows:organize_downloads_setups_pdfs_tool"
        if route["args"]["dry_run"]:
            return {
                "status": "success",
                "result": {
                    "ok": True,
                    "action": "organized_downloads",
                    "dry_run": True,
                    "downloads": r"C:\Users\Administrator\Downloads",
                    "setups_folder": r"C:\Users\Administrator\Downloads\Setups",
                    "pdfs_folder": r"C:\Users\Administrator\Downloads\PDFs",
                    "moved_count": 3,
                    "moved": [],
                },
            }
        return {
            "status": "success",
            "result": {
                "ok": True,
                "action": "organized_downloads",
                "dry_run": False,
                "moved_count": 3,
                "setups_folder": r"C:\Users\Administrator\Downloads\Setups",
                "pdfs_folder": r"C:\Users\Administrator\Downloads\PDFs",
            },
        }

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)
    monkeypatch.setattr(bridge, "emit_event", lambda *_args, **_kwargs: None)

    preview = bridge._chat_message(["Shell, audit my Downloads folder and clean it safely.", {"source": "text"}])

    assert preview["success"] is True
    assert executed_routes[0]["args"]["dry_run"] is True
    assert "I audited your Downloads" in preview["reply"]
    assert "I have not moved anything yet" in preview["reply"]
    assert preview["ui_actions"][0]["type"] == "APPROVE_ACTION"
    assert bridge._read_history_file()[-1]["pendingPermission"]["action"] == "downloads_cleanup"

    approved = bridge._chat_message(["yes", {"source": "text"}])

    assert approved["success"] is True
    assert executed_routes[-1]["args"]["dry_run"] is False
    assert executed_routes[-1]["source"] == "real-os-agent-downloads-cleanup-approved"
    assert approved["reply"] == "I organized your Downloads into Setups and PDFs."


def test_npm_test_command_asks_permission_then_runs(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    executed_routes = []

    def fake_execute(route):
        executed_routes.append(route)
        assert route["tool"] == "shell_terminal:run_command_tool"
        return {"status": "success", "result": "Output:\nPASS tests/example.test.js"}

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)
    monkeypatch.setattr(bridge, "emit_event", lambda *_args, **_kwargs: None)

    preview = bridge._chat_message(["Shell, run npm test and show me the result", {"source": "text"}])

    assert preview["success"] is True
    assert not executed_routes
    assert "I want to run `npm test`" in preview["reply"]
    assert preview["ui_actions"][0]["type"] == "APPROVE_ACTION"
    assert bridge._read_history_file()[-1]["pendingPermission"]["action"] == "run_command"

    approved = bridge._chat_message(["yes", {"source": "text"}])

    assert approved["success"] is True
    assert executed_routes
    assert executed_routes[-1]["args"]["command"] == "npm test"
    assert "I ran `npm test` successfully" in approved["reply"]
    assert "PASS tests/example.test.js" in approved["reply"]


def test_gmail_status_request_explains_missing_inbox_integration(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()

    def fake_execute(route):
        assert route["tool"] == "shell_email_tool:email_setup_status_tool"
        return {
            "status": "success",
            "result": "Email sending is not configured, so Shell must not claim that an email was sent. SMTP credentials missing.",
        }

    monkeypatch.setattr(bridge, "_execute_routed_tool", fake_execute)
    monkeypatch.setattr(bridge, "emit_event", lambda *_args, **_kwargs: None)

    result = bridge._chat_message(["Shell, what new emails did I get in Gmail?", {"source": "text"}])

    assert result["success"] is True
    assert "Gmail/email integration is not configured yet" in result["reply"]
    assert "inbox reading" in result["reply"]
    assert result["ui_actions"][0]["type"] == "OPEN_URL"
    assert result["ui_actions"][0]["url"] == "https://mail.google.com/"


def test_capture_app_context_channel_stores_browser_youtube_context(monkeypatch, tmp_path):
    import shell_app_context
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    monkeypatch.setattr(
        shell_app_context,
        "capture_app_context",
        lambda: {
            "app_type": "browser",
            "adapter": "browser",
            "app_name": "Google Chrome",
            "title": "Shell AI tutorial - YouTube",
            "url": "https://www.youtube.com/watch?v=abc123",
            "metadata": {"is_youtube": True, "video_title": "Shell AI tutorial - YouTube"},
            "captured_at": 1780930000.0,
        },
    )
    bridge = host.ShellBackendBridge()

    result = bridge._dispatch("capture-app-context", [])

    assert result["success"] is True
    assert result["context"]["app_type"] == "browser"
    assert result["context"]["metadata"]["is_youtube"] is True
    assert bridge._last_app_context["url"].startswith("https://www.youtube.com/")


def test_chat_message_injects_latest_overlay_context(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "HISTORY_PATH", tmp_path / "web_ui_history.json")
    bridge = host.ShellBackendBridge()
    bridge._last_app_context = {
        "app_type": "browser",
        "adapter": "browser",
        "app_name": "Google Chrome",
        "title": "Shell AI tutorial - YouTube",
        "url": "https://www.youtube.com/watch?v=abc123",
        "metadata": {"is_youtube": True},
        "captured_at": host.time.time(),
    }

    def fake_fallback(prompt, **_kwargs):
        assert "Active app context for this Shell overlay request" in prompt
        assert "Shell AI tutorial - YouTube" in prompt
        assert "youtube.com/watch" in prompt
        return "I can use the active YouTube context."

    monkeypatch.setattr(bridge, "_brain_chat_fallback", fake_fallback)

    result = bridge._chat_message(["what am I looking at?", {"source": "text"}])

    assert result["success"] is True
    assert result["reply"] == "I can use the active YouTube context."


def test_browser_adapter_marks_youtube_context():
    from shell_app_context import ActiveWindowInfo, BrowserAdapter

    context = BrowserAdapter().get_context(
        ActiveWindowInfo(
            app_name="Google Chrome",
            title="Build apps with Shell AI - YouTube",
            process_name="chrome",
            url="https://www.youtube.com/watch?v=xyz",
            clipboard_text="",
        )
    )

    assert context["app_type"] == "browser"
    assert context["metadata"]["is_youtube"] is True
    assert context["metadata"]["video_title"] == "Build apps with Shell AI - YouTube"


def test_blocked_planner_result_gets_friendly_policy_explanation():
    import shell_web_ui.host as host

    bridge = host.ShellBackendBridge()

    reply = bridge._format_chat_result(
        {"tool": "shell_agent_orchestrator:orchestrate_shell_goal_tool"},
        {
            "status": "success",
            "result": {
                "execution_allowed": False,
                "execution_reason": "agent policy did not allow capability execution",
                "execution_status": "blocked",
                "goal": "run npm test",
            },
        },
    )

    assert "I didn’t run `npm test`" in reply
    assert "safety policy" in reply
    assert "policy/settings" in reply
    assert "execution_allowed" not in reply
    assert "Shell agent planner complete" not in reply


def test_code_write_blocked_reply_names_relevant_safety_settings():
    import shell_web_ui.host as host
    bridge = host.ShellBackendBridge()

    reply = bridge._format_chat_result(
        {"tool": "shell_code_engine:create_fullstack_app_tool"},
        {"status": "success", "result": "[BLOCKED] Writing LLM-generated Python to disk is disabled by default."},
    )

    assert "Code creation safety settings se blocked hai" in reply
    assert "SHELL_BLOCK_PROJECT_SCAFFOLD=1" in reply
    assert "SHELL_ALLOW_CODE_WRITE=1" in reply


def test_backend_voice_input_unavailable_is_not_reported_as_full_voice_failure():
    import shell_web_ui.host as host
    bridge = host.ShellBackendBridge()
    emitted = []
    bridge.emit_event = lambda channel, payload: emitted.append((channel, payload))

    bridge._on_voice_error("sounddevice not installed")
    bridge._on_voice_stopped()

    voice_events = [payload for channel, payload in emitted if channel == "voice-status"]
    assert voice_events[0]["state"] == "mic_missing"
    assert voice_events[0]["actualRuntime"] is False
    assert "Shell can still speak" in voice_events[0]["message"]
    assert voice_events[-1]["state"] == "mic_missing"
    assert not any(payload["state"] == "error" for payload in voice_events)


def test_backend_voice_error_classifier_catches_common_no_mic_failures():
    import shell_web_ui.host as host

    bridge = host.ShellBackendBridge()

    assert bridge._is_voice_input_unavailable_error("Error querying device -1: no default input device")
    assert bridge._is_voice_input_unavailable_error("PortAudio could not open microphone")
    assert bridge._is_voice_input_unavailable_error("SpeechRecognition not installed")
    assert not bridge._is_voice_input_unavailable_error("LLM provider quota exceeded")


def test_update_check_detects_new_windows_setup_asset(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    monkeypatch.setattr(host, "UPDATES_DIR", tmp_path / "updates")
    monkeypatch.setattr(host, "UPDATE_STATE_PATH", tmp_path / "updates" / "update_state.json")
    bridge = host.ShellBackendBridge()
    emitted = []
    bridge.emit_event = lambda channel, payload: emitted.append((channel, payload))
    monkeypatch.setattr(bridge, "_get_app_version", lambda _args=None: "1.0.0")
    monkeypatch.setattr(bridge, "_update_feed_url", lambda: "https://example.test/releases/latest")
    monkeypatch.setattr(
        bridge,
        "_fetch_update_payload",
        lambda _url: {
            "tag_name": "v1.1.0",
            "body": "New Windows installer build.",
            "assets": [
                {"name": "shell-ai-os-controller-1.1.0.zip", "browser_download_url": "https://example.test/app.zip"},
                {
                    "name": "shell-ai-os-controller-setup-1.1.0.exe",
                    "browser_download_url": "https://example.test/ShellAI_Setup_1.1.0.exe",
                },
            ],
        },
    )

    result = bridge._check_for_updates([])

    assert result["success"] is True
    assert result["status"] == "available"
    assert result["version"] == "1.1.0"
    assert result["downloadUrl"].endswith(".exe")
    assert host.UPDATE_STATE_PATH.exists()
    assert [payload["status"] for channel, payload in emitted if channel == "updater-event"] == [
        "checking",
        "available",
    ]


def test_update_feed_defaults_to_actual_release_repo(monkeypatch):
    import shell_web_ui.host as host

    monkeypatch.delenv("SHELL_UPDATE_REPO", raising=False)
    monkeypatch.delenv("SHELL_UPDATE_MANIFEST_URL", raising=False)

    assert host.ShellBackendBridge()._update_feed_url() == (
        "https://api.github.com/repos/mdshoebkhanking/shell-ai-os-controller/releases/latest"
    )


def test_update_install_refuses_to_launch_exe_off_windows(monkeypatch, tmp_path):
    import shell_web_ui.host as host

    updates = tmp_path / "updates"
    updates.mkdir()
    installer = updates / "ShellAI_Setup_1.1.0.exe"
    installer.write_bytes(b"MZ")
    monkeypatch.setattr(host, "UPDATES_DIR", updates)
    monkeypatch.setattr(host, "UPDATE_STATE_PATH", updates / "update_state.json")
    host.UPDATE_STATE_PATH.write_text(
        '{"downloadedPath": "%s"}' % str(installer).replace("\\", "\\\\"),
        encoding="utf-8",
    )
    monkeypatch.setattr(host.platform, "system", lambda: "Darwin")
    bridge = host.ShellBackendBridge()

    result = bridge._install_update([])

    assert result["success"] is False
    assert "only supported on Windows" in result["message"]
