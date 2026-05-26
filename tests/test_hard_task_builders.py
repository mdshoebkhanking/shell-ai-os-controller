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

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHELL_ALLOW_CODE_WRITE", "1")
    monkeypatch.setattr(shell_code_engine, "NEURAL_ENGINE_ACTIVE", False)
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
