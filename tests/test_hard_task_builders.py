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

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    monkeypatch.delenv("SHELL_BLOCK_PROJECT_SCAFFOLD", raising=False)
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
