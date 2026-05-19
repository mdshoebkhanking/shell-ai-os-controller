from __future__ import annotations


def test_provider_runtime_snapshot_redacts_secret_values_and_preserves_lazy_load(monkeypatch):
    import shell_ai_runtime

    monkeypatch.setattr(shell_ai_runtime, "_BRAIN", None)
    for name in shell_ai_runtime.provider_key_names():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "real-google-key-value-12345")
    monkeypatch.setenv("OPENAI_API_KEY", "your_openai_api_key_here")

    snapshot = shell_ai_runtime.provider_runtime_snapshot(load=False)

    assert snapshot["configured_key_count"] == 1
    assert snapshot["configured_keys"] == ["GOOGLE_API_KEY"]
    assert snapshot["brain_loaded"] is False
    assert snapshot["loaded_provider_count"] == 0
    assert "real-google-key-value" not in repr(snapshot)


def test_provider_key_names_are_safe_diagnostic_names():
    from shell_ai_runtime import provider_key_names

    names = provider_key_names()

    assert "GOOGLE_API_KEY" in names
    assert "OPENAI_API_KEY" in names
    assert all("secret" not in name.lower() for name in names)
