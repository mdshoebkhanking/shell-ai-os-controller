from __future__ import annotations


def test_offline_llm_status_reports_disabled(monkeypatch, tmp_path):
    import shell_offline_llm

    shell_offline_llm._reset_cached_model_for_tests()
    monkeypatch.setenv("SHELL_OFFLINE_LLM", "0")
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)

    status = shell_offline_llm.offline_llm_status()

    assert status["available"] is False
    assert status["status"] == "fallback"
    assert "disabled" in status["reason"].lower()
    assert status["runtimeDownloads"] is False


def test_offline_llm_status_falls_back_without_model(monkeypatch, tmp_path):
    import shell_offline_llm

    shell_offline_llm._reset_cached_model_for_tests()
    monkeypatch.delenv("SHELL_OFFLINE_LLM", raising=False)
    monkeypatch.setattr(shell_offline_llm, "PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)

    status = shell_offline_llm.offline_llm_status()

    assert status["available"] is False
    assert status["modelFamily"] == "Falcon-H1-1.5B-Deep-Instruct-GGUF"
    assert "No packaged GGUF" in status["reason"]


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

    shell_offline_llm._reset_cached_model_for_tests()
    model_dir = tmp_path / "models" / "llm" / "falcon-h1-1.5b-deep"
    model_dir.mkdir(parents=True)
    model = model_dir / "Falcon-H1-1.5B-Deep-Instruct-Q4_K_M.gguf"
    model.write_bytes(b"gguf-probe")
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
