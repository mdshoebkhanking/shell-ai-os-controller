from __future__ import annotations


def test_task_mode_keeps_basic_creation_offline():
    from shell_task_mode import classify_task_mode

    decision = classify_task_mode("mere liyye login page banao html main or desktop pe save kardo")

    assert decision.mode == "offline"
    assert decision.requires_online is False
    assert decision.level == 1


def test_task_mode_requires_online_for_hard_full_app():
    from shell_task_mode import classify_task_mode

    decision = classify_task_mode("Build a full app with authentication, backend API, and database")

    assert decision.mode == "online"
    assert decision.requires_online is True
    assert decision.level == 2
    assert "cloud" in decision.reason


def test_document_file_route_stays_offline_even_when_topic_mentions_full_app():
    from shell_task_mode import classify_task_mode

    decision = classify_task_mode(
        "Make a PDF summary of this full app architecture",
        route_tool="shell_workspace_tools:create_user_file_tool",
    )

    assert decision.mode == "offline"
    assert decision.requires_online is False
    assert decision.capability == "document"


def test_level_1_static_portfolio_website_is_offline():
    from shell_task_mode import classify_task_mode

    decision = classify_task_mode("Make a portfolio website for me")

    assert decision.mode == "offline"
    assert decision.requires_online is False
    assert decision.capability == "template"


def test_level_1_small_script_is_offline():
    from shell_task_mode import classify_task_mode

    decision = classify_task_mode("Write a PowerShell script helper to move files")

    assert decision.mode == "offline"
    assert decision.requires_online is False
    assert decision.capability == "local-code"


def test_configured_cloud_keys_ignore_placeholders(monkeypatch):
    from shell_task_mode import CLOUD_PROVIDER_KEY_GROUPS, configured_cloud_key_names

    for group in CLOUD_PROVIDER_KEY_GROUPS:
        for key in group:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "your_openai_api_key_here")

    assert configured_cloud_key_names() == []


def test_online_full_version_requires_key_and_enabled_mode(monkeypatch):
    from shell_task_mode import CLOUD_PROVIDER_KEY_GROUPS, online_full_version_ready

    for group in CLOUD_PROVIDER_KEY_GROUPS:
        for key in group:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("SHELL_CHAT_PROVIDER_MODE", raising=False)
    monkeypatch.delenv("SHELL_WEB_CHAT_PROVIDER_MODE", raising=False)

    assert online_full_version_ready() is False

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-000000")
    assert online_full_version_ready() is False

    monkeypatch.setenv("SHELL_CHAT_PROVIDER_MODE", "online")
    assert online_full_version_ready() is True
