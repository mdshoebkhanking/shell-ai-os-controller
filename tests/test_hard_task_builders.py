import subprocess
import threading
import webbrowser

import pytest


@pytest.mark.asyncio
async def test_known_game_builder_writes_playable_html_without_ai(monkeypatch, tmp_path):
    import shell_game_builder

    opened: list[str] = []

    async def fail_if_ai_called(_game: str, _custom_features: str = ""):
        raise AssertionError("known game templates should not need provider AI")

    monkeypatch.setattr(shell_game_builder, "_output_dir", lambda: tmp_path)
    monkeypatch.setattr(shell_game_builder, "_ai_generate", fail_if_ai_called)
    monkeypatch.setattr(shell_game_builder.webbrowser, "open", lambda uri: opened.append(uri) or True)

    result = await shell_game_builder.build_game_tool("snake", "")

    files = list(tmp_path.glob("snake_*.html"))
    assert "Game ready" in result
    assert files
    assert "<canvas" in files[0].read_text(encoding="utf-8")
    assert opened == [files[0].as_uri()]


@pytest.mark.asyncio
async def test_fullstack_app_builder_writes_project_when_safety_enabled(monkeypatch, tmp_path):
    import shell_code_engine

    launched: list[list[str]] = []

    class NoopThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

    class NoopProcess:
        pass

    class FailingHyperCortex:
        def synergize_project(self, *_args, **_kwargs):
            raise AssertionError("provider blueprint should stay off unless core code write is enabled")

    from shell_task_mode import CLOUD_PROVIDER_KEY_GROUPS

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    monkeypatch.delenv("SHELL_BLOCK_PROJECT_SCAFFOLD", raising=False)
    monkeypatch.delenv("SHELL_CHAT_PROVIDER_MODE", raising=False)
    monkeypatch.delenv("SHELL_WEB_CHAT_PROVIDER_MODE", raising=False)
    for group in CLOUD_PROVIDER_KEY_GROUPS:
        for key in group:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(shell_code_engine, "NEURAL_ENGINE_ACTIVE", True)
    monkeypatch.setattr(shell_code_engine, "hyper_cortex", FailingHyperCortex())
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **_kwargs: launched.append(list(argv)) or NoopProcess())
    monkeypatch.setattr(threading, "Thread", NoopThread)
    monkeypatch.setattr(webbrowser, "open", lambda _url: True)

    result = await shell_code_engine.create_fullstack_app_tool("todo_with_login", "todo app banao with login")

    project = tmp_path / "shell_projects" / "todo_with_login"
    assert "[SUCCESS]" in result
    assert (project / "app.py").exists()
    assert (project / "templates" / "index.html").exists()
    assert (project / "static" / "css" / "style.css").exists()
    assert (project / "run_app.bat").exists()
    html = (project / "templates" / "index.html").read_text(encoding="utf-8")
    assert "todo app banao with login" not in html.lower()
    assert "Command Center" in html
    assert "Core Workflow" in html
    assert launched


@pytest.mark.asyncio
async def test_fullstack_app_builder_uses_cloud_blueprint_for_hard_task_with_key(monkeypatch, tmp_path):
    import shell_code_engine

    launched: list[list[str]] = []

    class NoopProcess:
        pass

    class FakeHyperCortex:
        def refresh_providers(self):
            return [{"name": "OpenAI", "type": "openai", "model": "test"}]

        def synergize_project(self, project_name, app_type):
            assert project_name == "crm_full_app"
            assert "full app" in app_type.lower()
            return {
                "frontend": {
                    "html_body": "<main><h1>Cloud CRM Console</h1><p>Provider-generated blueprint.</p></main>",
                    "css_vars": ":root { --primary:#00d4ff; --secondary:#2de2a6; --bg:#090919; --text:#fff; }",
                    "js_logic": "window.shellCloudBlueprint = true;",
                },
                "backend": {
                    "python_packages": ["flask", "flask_sqlalchemy", "flask_cors"],
                    "routes_code": "@app.route('/api/health')\ndef health():\n    return jsonify({'status': 'cloud-blueprint'})",
                },
                "meta": {"archetype": "cloud-full-app"},
            }

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    monkeypatch.delenv("SHELL_BLOCK_PROJECT_SCAFFOLD", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder-000000")
    monkeypatch.setenv("SHELL_CHAT_PROVIDER_MODE", "online")
    monkeypatch.setattr(shell_code_engine, "NEURAL_ENGINE_ACTIVE", True)
    monkeypatch.setattr(shell_code_engine, "hyper_cortex", FakeHyperCortex())
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **_kwargs: launched.append(list(argv)) or NoopProcess())
    monkeypatch.setattr(webbrowser, "open", lambda _url: True)

    result = await shell_code_engine.create_fullstack_app_tool(
        "crm_full_app",
        "Build a full app with authentication, backend API, and database",
    )

    project = tmp_path / "shell_projects" / "crm_full_app"
    assert "[SUCCESS]" in result
    html = (project / "templates" / "index.html").read_text(encoding="utf-8")
    js = (project / "static" / "js" / "script.js").read_text(encoding="utf-8")
    assert "Cloud CRM Console" in html
    assert "shellCloudBlueprint" in js
    assert launched


@pytest.mark.asyncio
async def test_fullstack_app_builder_respects_project_scaffold_opt_out(monkeypatch, tmp_path):
    import shell_code_engine

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    monkeypatch.setenv("SHELL_BLOCK_PROJECT_SCAFFOLD", "1")
    monkeypatch.setattr(shell_code_engine, "NEURAL_ENGINE_ACTIVE", False)

    result = await shell_code_engine.create_fullstack_app_tool("blocked_app", "todo app")

    assert result.startswith("[BLOCKED]")
    assert not (tmp_path / "shell_projects" / "blocked_app").exists()
