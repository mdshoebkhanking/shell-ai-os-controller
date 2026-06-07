from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_user_model_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_OFFLINE_LLM_MODEL_DIR", str(tmp_path / "user-models"))


def test_offline_llm_result_as_dict_keeps_generation_failure_reason():
    import shell_offline_llm

    result = shell_offline_llm.OfflineLLMResult(
        False,
        "",
        "offline-llm",
        "Offline LLM generation failed: Failed to create llama_context",
        {"success": True, "reason": "Packaged offline LLM is ready.", "available": True},
    )

    payload = result.as_dict()

    assert payload["success"] is False
    assert payload["reason"] == "Offline LLM generation failed: Failed to create llama_context"
    assert payload["statusSuccess"] is True
    assert payload["statusReason"] == "Packaged offline LLM is ready."
    assert payload["available"] is True


def test_offline_llm_status_reports_disabled(monkeypatch, tmp_path):
    import shell_offline_llm

    shell_offline_llm._reset_cached_model_for_tests()
    monkeypatch.setenv("SHELL_OFFLINE_LLM", "0")
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)

    status = shell_offline_llm.offline_llm_status()

    assert status["available"] is False
    assert status["status"] == "fallback"
    assert "disabled" in status["reason"].lower()
    assert status["runtimeDownloads"] is True
    assert len(status["catalog"]["options"]) >= 4


def test_offline_llm_status_falls_back_without_model(monkeypatch, tmp_path):
    import shell_offline_llm

    shell_offline_llm._reset_cached_model_for_tests()
    monkeypatch.delenv("SHELL_OFFLINE_LLM", raising=False)
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    status = shell_offline_llm.offline_llm_status()

    assert status["available"] is False
    assert status["modelFamily"] == "Qwen2.5-0.5B-Instruct-GGUF"
    assert "download a model" in status["reason"]
    assert status["runtimeDownloads"] is True
    assert len(status["catalog"]["options"]) >= 4


def test_offline_llm_status_requires_runtime(monkeypatch, tmp_path):
    import shell_offline_llm

    shell_offline_llm._reset_cached_model_for_tests()
    model_dir = tmp_path / "models" / "llm" / "falcon-h1-1.5b-deep"
    model_dir.mkdir(parents=True)
    (model_dir / "Falcon-H1-1.5B-Deep-Instruct-Q4_K_M.gguf").write_bytes(b"gguf-probe")
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(shell_offline_llm, "_load_llama_class", lambda: (None, "runtime missing"))

    status = shell_offline_llm.offline_llm_status()

    assert status["available"] is False
    assert status["modelFile"] == "Falcon-H1-1.5B-Deep-Instruct-Q4_K_M.gguf"
    assert status["reason"] == "runtime missing"


def test_offline_llm_status_reports_selected_model_language_support(monkeypatch, tmp_path):
    import shell_offline_llm
    import shell_offline_model_catalog

    shell_offline_llm._reset_cached_model_for_tests()
    option = shell_offline_model_catalog.get_model_option("smollm2-135m-q4")
    assert option is not None
    model = shell_offline_model_catalog.model_install_dir(option.id) / option.filename
    model.parent.mkdir(parents=True)
    model.write_bytes(b"gguf-probe")
    shell_offline_model_catalog.write_model_metadata(option, model_path=model)
    monkeypatch.setenv("SHELL_LANGUAGE", "hinglish")
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(shell_offline_llm, "_load_llama_class", lambda: (None, "runtime missing"))

    status = shell_offline_llm.offline_llm_status()

    assert status["modelFile"] == option.filename
    assert status["language"] == "hinglish"
    assert status["languageSupport"] == ["english"]
    assert status["languageMismatch"] is True
    assert "hinglish prompts may be lower quality" in status["languageWarning"]


def test_offline_model_catalog_separates_chat_and_coding_models(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_OFFLINE_LLM_MODEL_DIR", str(tmp_path / "user-models"))

    import shell_offline_model_catalog

    chat_catalog = shell_offline_model_catalog.catalog_payload("chat")
    coding_catalog = shell_offline_model_catalog.catalog_payload("coding")

    assert chat_catalog["category"] == "chat"
    assert coding_catalog["category"] == "coding"
    assert all("coder" not in option["id"] for option in chat_catalog["options"])
    assert any(option["id"] == "qwen2.5-coder-0.5b-q4" for option in coding_catalog["options"])
    assert any(option["id"] == "qwen2.5-coder-1.5b-q4" for option in coding_catalog["options"])


def test_offline_coding_llm_status_uses_independent_selected_model(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_OFFLINE_LLM_MODEL_DIR", str(tmp_path / "user-models"))

    import shell_offline_llm
    import shell_offline_model_catalog

    shell_offline_llm._reset_cached_model_for_tests()
    chat_option = shell_offline_model_catalog.get_model_option("qwen2.5-0.5b-q4", "chat")
    coding_option = shell_offline_model_catalog.get_model_option("qwen2.5-coder-0.5b-q4", "coding")
    assert chat_option is not None
    assert coding_option is not None
    chat_path = shell_offline_model_catalog.model_install_dir(chat_option.id) / chat_option.filename
    coding_path = shell_offline_model_catalog.model_install_dir(coding_option.id) / coding_option.filename
    chat_path.parent.mkdir(parents=True)
    coding_path.parent.mkdir(parents=True)
    chat_path.write_bytes(b"chat-gguf")
    coding_path.write_bytes(b"coding-gguf")
    shell_offline_model_catalog.write_model_metadata(chat_option, model_path=chat_path, category="chat")
    shell_offline_model_catalog.write_model_metadata(coding_option, model_path=coding_path, category="coding")
    monkeypatch.setattr(shell_offline_llm, "_load_llama_class", lambda: (None, "runtime missing"))

    chat_status = shell_offline_llm.offline_llm_status()
    coding_status = shell_offline_llm.offline_coding_llm_status()

    assert chat_status["category"] == "chat"
    assert chat_status["selectedModelId"] == chat_option.id
    assert chat_status["modelFile"] == chat_option.filename
    assert coding_status["category"] == "coding"
    assert coding_status["selectedModelId"] == coding_option.id
    assert coding_status["modelFile"] == coding_option.filename


def test_offline_llm_status_keeps_legacy_qwen_assets_as_fallback(monkeypatch, tmp_path):
    import shell_offline_llm

    shell_offline_llm._reset_cached_model_for_tests()
    model_dir = tmp_path / "models" / "llm" / "qwen3"
    model_dir.mkdir(parents=True)
    (model_dir / "Qwen3-1.7B-Q4_K_M.gguf").write_bytes(b"gguf-probe")
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(shell_offline_llm, "_load_llama_class", lambda: (None, "runtime missing"))

    status = shell_offline_llm.offline_llm_status()

    assert status["available"] is False
    assert status["modelFamily"] == "Qwen3-1.7B-GGUF"
    assert status["modelFile"] == "Qwen3-1.7B-Q4_K_M.gguf"


def test_generate_offline_reply_uses_packaged_llama_runtime(monkeypatch, tmp_path):
    import shell_offline_llm
    import shell_offline_model_catalog

    shell_offline_llm._reset_cached_model_for_tests()
    option = shell_offline_model_catalog.get_model_option("qwen2.5-0.5b-q4")
    assert option is not None
    model = shell_offline_model_catalog.model_install_dir(option.id) / option.filename
    model.parent.mkdir(parents=True)
    model.write_bytes(b"gguf-probe")
    shell_offline_model_catalog.write_model_metadata(option, model_path=model)
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    calls = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            calls["init"] = kwargs

        def create_chat_completion(self, **kwargs):
            calls["completion"] = kwargs
            return {"choices": [{"message": {"content": "<think>hidden</think>Offline Shell answer."}}]}

    monkeypatch.setattr(shell_offline_llm, "_load_llama_class", lambda: (FakeLlama, ""))

    result = shell_offline_llm.generate_offline_reply("hello", system_prompt="short")

    assert result.success is True
    assert result.reply == "Offline Shell answer."
    assert calls["init"]["model_path"] == str(model)
    assert calls["completion"]["messages"][-1]["content"] == "hello"
    assert calls["completion"]["max_tokens"] >= 32


def test_generate_offline_reply_skips_stale_provider_fallback_history(monkeypatch, tmp_path):
    import shell_offline_llm
    import shell_offline_model_catalog

    shell_offline_llm._reset_cached_model_for_tests()
    option = shell_offline_model_catalog.get_model_option("qwen2.5-0.5b-q4")
    assert option is not None
    model = shell_offline_model_catalog.model_install_dir(option.id) / option.filename
    model.parent.mkdir(parents=True)
    model.write_bytes(b"gguf-probe")
    shell_offline_model_catalog.write_model_metadata(option, model_path=model)
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    calls = {}

    class FakeLlama:
        def __init__(self, **_kwargs):
            pass

        def create_chat_completion(self, **kwargs):
            calls["messages"] = kwargs["messages"]
            return {"choices": [{"message": {"content": "Offline answer."}}]}

    monkeypatch.setattr(shell_offline_llm, "_load_llama_class", lambda: (FakeLlama, ""))
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
    useful = {"role": "user", "parts": [{"text": "old useful context"}]}

    result = shell_offline_llm.generate_offline_reply(
        "new question",
        previous_messages=[useful, stale],
    )

    assert result.success is True
    assert [message["content"] for message in calls["messages"] if message["role"] != "system"] == [
        "old useful context",
        "new question",
    ]


def test_windows_performance_mode_caps_offline_llm_defaults(monkeypatch):
    import shell_offline_llm

    for key in (
        "SHELL_WINDOWS_PERFORMANCE_MODE",
        "SHELL_OFFLINE_LLM_CONTEXT",
        "SHELL_OFFLINE_LLM_BATCH",
        "SHELL_OFFLINE_LLM_THREADS",
        "SHELL_OFFLINE_LLM_MAX_TOKENS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(shell_offline_llm.platform, "system", lambda: "Windows")
    monkeypatch.setattr(shell_offline_llm.os, "cpu_count", lambda: 2)

    runtime = shell_offline_llm._runtime_settings()
    generation = shell_offline_llm._generation_settings()

    assert runtime["n_ctx"] == 768
    assert runtime["n_batch"] == 32
    assert runtime["n_threads"] == 1
    assert generation["max_tokens"] == 96
    assert generation["temperature"] == 0.35
    assert generation["repeat_penalty"] == 1.12
    assert generation["presence_penalty"] == 0.15


def test_generate_offline_reply_short_circuits_shell_identity(monkeypatch, tmp_path):
    import shell_offline_llm

    shell_offline_llm._reset_cached_model_for_tests()
    model_dir = tmp_path / "models" / "llm" / "falcon-h1-1.5b-deep"
    model_dir.mkdir(parents=True)
    (model_dir / "Falcon-H1-1.5B-Deep-Instruct-Q4_K_M.gguf").write_bytes(b"gguf-probe")
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    class FakeLlama:
        def __init__(self, **kwargs):
            raise AssertionError("identity guard should not load the model")

    monkeypatch.setattr(shell_offline_llm, "_load_llama_class", lambda: (FakeLlama, ""))

    result = shell_offline_llm.generate_offline_reply("Shell AI ko kisne banaya?")

    assert result.success is True
    assert result.reply == "Mujhe mdshoebking ne banaya hai."
    assert result.metadata
    assert result.metadata["identityGuard"] is True


def test_generate_offline_reply_who_are_you_does_not_return_creator(monkeypatch, tmp_path):
    import shell_offline_llm

    shell_offline_llm._reset_cached_model_for_tests()
    model_dir = tmp_path / "models" / "llm" / "falcon-h1-1.5b-deep"
    model_dir.mkdir(parents=True)
    (model_dir / "Falcon-H1-1.5B-Deep-Instruct-Q4_K_M.gguf").write_bytes(b"gguf-probe")
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    class FakeLlama:
        def __init__(self, **kwargs):
            raise AssertionError("identity guard should not load the model")

    monkeypatch.setattr(shell_offline_llm, "_load_llama_class", lambda: (FakeLlama, ""))

    result = shell_offline_llm.generate_offline_reply("tum kon ho?")

    assert result.success is True
    assert result.reply == "Main Shell AI hoon."
    assert "mdshoebking" not in result.reply
