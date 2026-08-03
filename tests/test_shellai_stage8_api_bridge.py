from __future__ import annotations


def _set_temp_shellai_home(monkeypatch, tmp_path):
    config_path = tmp_path / ".shellai" / "config.json"
    monkeypatch.setenv("SHELLAI_CONFIG", str(config_path))
    return config_path


def test_run_shellai_task_explicit_shell_command_returns_structured_result(monkeypatch, tmp_path) -> None:
    import platform
    _set_temp_shellai_home(monkeypatch, tmp_path)

    from shellai.api import run_shellai_task

    cmd = "dir" if platform.system().lower() == "windows" else "pwd"
    result = run_shellai_task(f"!{cmd}", context={"source": "test", "cwd": str(tmp_path)})

    assert isinstance(result, dict)
    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result.get("summary")
    assert isinstance(result.get("steps"), list)
    assert result["steps"][0]["tool"] == "shell"
    assert result["steps"][0]["metadata"]["command"] == cmd
    if cmd == "pwd":
        assert str(tmp_path) in result["steps"][0]["stdout"]
    else:
        assert str(tmp_path).lower().replace('/', '\\') in result["steps"][0]["stdout"].lower()


def test_run_shellai_task_returns_structured_error_for_bad_config(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / ".shellai" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("SHELLAI_CONFIG", str(config_path))

    from shellai.api import run_shellai_task

    result = run_shellai_task("!pwd", context={"source": "test", "cwd": str(tmp_path)})

    assert result["ok"] is False
    assert result["status"] == "error"
    assert "error" in result
    assert result["error"]["details"]["stage"] == "config_load"
    assert result["steps"] == []


def test_desktop_bridge_defaults_to_classic(monkeypatch, tmp_path) -> None:
    import platform
    _set_temp_shellai_home(monkeypatch, tmp_path)
    monkeypatch.delenv("SHELLAI_BACKEND_MODE", raising=False)

    from core.shellai_bridge import handle_user_request

    cmd = "dir" if platform.system().lower() == "windows" else "pwd"
    assert handle_user_request(f"!{cmd}", context={"source": "test", "cwd": str(tmp_path)}) is None


def test_desktop_bridge_shellai_core_mode_smoke(monkeypatch, tmp_path) -> None:
    import platform
    _set_temp_shellai_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SHELLAI_BACKEND_MODE", "shellai_core")

    from core.shellai_bridge import format_shellai_reply, handle_user_request

    cmd = "dir" if platform.system().lower() == "windows" else "pwd"
    result = handle_user_request(f"!{cmd}", context={"source": "test", "cwd": str(tmp_path)})
    reply = format_shellai_reply(result)

    assert isinstance(result, dict)
    assert result["ok"] is True
    assert result["steps"][0]["tool"] == "shell"
    assert result["steps"][0]["metadata"]["command"] == cmd
    assert reply
