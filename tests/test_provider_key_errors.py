import asyncio


def test_gemini_invalid_key_error_is_human_readable():
    from brain.providers.gemini_p import _humanize_gemini_error

    message = _humanize_gemini_error(
        Exception(
            "400 INVALID_ARGUMENT {'error': {'reason': 'API_KEY_INVALID', "
            "'message': 'API key not valid. Please pass a valid API key.'}}"
        )
    )

    assert "Invalid GOOGLE_API_KEY" in message
    assert "API_KEY_INVALID" not in message
    assert "googleapis.com" not in message


def test_gemini_placeholder_key_is_not_accepted(monkeypatch):
    from brain.providers.gemini_p import GeminiProvider

    monkeypatch.setenv("GOOGLE_API_KEY", "your_google_api_key")

    try:
        GeminiProvider()
        created = True
    except ValueError as exc:
        created = False
        assert "placeholder" in str(exc).lower()

    assert created is False


def test_api_manager_rejects_placeholder_secret(monkeypatch, tmp_path):
    import shell_api_manager

    env_path = tmp_path / ".env"
    monkeypatch.setattr(shell_api_manager, "_ENV_PATH", env_path)
    monkeypatch.setattr(shell_api_manager, "_ENV_EXAMPLE_PATH", tmp_path / ".env.example")

    ok, msg = shell_api_manager.set_api_key("GOOGLE_API_KEY", "your_google_api_key")

    assert ok is False
    assert "placeholder" in msg.lower()


def test_api_manager_normalizes_pasted_google_env_assignment(monkeypatch, tmp_path):
    import shell_api_manager

    env_path = tmp_path / ".env"
    monkeypatch.setattr(shell_api_manager, "_ENV_PATH", env_path)
    monkeypatch.setattr(shell_api_manager, "_ENV_EXAMPLE_PATH", tmp_path / ".env.example")

    ok, msg = shell_api_manager.set_api_key(
        "GOOGLE_API_KEY",
        "GOOGLE_API_KEY='fake-google-key-value-1234567890'",
    )

    assert ok is True, msg
    assert "GOOGLE_API_KEY=fake-google-key-value-1234567890" in env_path.read_text(encoding="utf-8")
    assert "GOOGLE_API_KEY=GOOGLE_API_KEY" not in env_path.read_text(encoding="utf-8")
    assert shell_api_manager.get_configured_secret_value("GOOGLE_API_KEY") == "fake-google-key-value-1234567890"


def test_api_manager_accepts_gemini_alias_assignment_for_google_key(monkeypatch, tmp_path):
    import shell_api_manager

    env_path = tmp_path / ".env"
    monkeypatch.setattr(shell_api_manager, "_ENV_PATH", env_path)
    monkeypatch.setattr(shell_api_manager, "_ENV_EXAMPLE_PATH", tmp_path / ".env.example")

    ok, msg = shell_api_manager.set_api_key(
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY=fake-gemini-alias-key-value-1234567890",
    )

    assert ok is True, msg
    assert "GOOGLE_API_KEY=fake-gemini-alias-key-value-1234567890" in env_path.read_text(encoding="utf-8")


def test_llm_client_does_not_retry_invalid_api_key():
    import shell_llm_client

    calls = {"n": 0}

    async def bad_call():
        calls["n"] += 1
        raise RuntimeError("API_KEY_INVALID: API key not valid")

    try:
        asyncio.run(shell_llm_client._retry_async(bad_call, attempts=4, base_delay=0))
    except RuntimeError:
        pass

    assert calls["n"] == 1
