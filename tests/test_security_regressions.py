import asyncio
import os
import sys
import types
from pathlib import Path


def _install_tool_wrapper_stub(monkeypatch):
    fake = types.ModuleType("shell_safe_executor")
    fake.god_tier_tool = lambda f: f
    monkeypatch.setitem(sys.modules, "shell_safe_executor", fake)


def test_downloader_blocks_loopback_and_path_escape(monkeypatch, tmp_path):
    _install_tool_wrapper_stub(monkeypatch)
    monkeypatch.setenv("SHELL_DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.delenv("SHELL_ALLOW_ARBITRARY_DOWNLOAD_PATH", raising=False)

    import shell_downloader as downloader

    ok, reason = downloader._validate_url("http://127.0.0.1:3333/private")
    assert not ok
    assert "loopback" in reason or "private" in reason

    escaped, error = downloader._resolve_save_path("../../agent.py")
    assert escaped is None
    assert "escapes" in error

    safe_path, error = downloader._resolve_save_path("reports/file.txt")
    assert error == ""
    assert Path(safe_path).is_relative_to(tmp_path)


def test_workflow_only_blocks_dangerous_or_escaping_actions(monkeypatch, tmp_path):
    _install_tool_wrapper_stub(monkeypatch)
    monkeypatch.delenv("SHELL_BLOCK_WORKFLOW_COMMANDS", raising=False)
    monkeypatch.delenv("SHELL_BLOCK_WORKFLOW_FILE_WRITE", raising=False)
    monkeypatch.delenv("SHELL_BLOCK_WORKFLOW_FILE_READ", raising=False)

    import brain.automation.engine as workflow_mod
    from brain.automation.engine import WorkflowEngine

    monkeypatch.setattr(workflow_mod, "WORKFLOW_DIR", str(tmp_path / "workflows"))
    monkeypatch.setattr(workflow_mod, "WORKFLOW_FILES_DIR", str(tmp_path / "workflow_files"))
    engine = WorkflowEngine()
    engine.workflows = {
        "x": {
            "name": "x",
            "steps": [
                {"id": "cmd", "action": "run_command", "params": {"command": "rm -rf /"}},
                {"id": "write", "action": "write_file", "params": {"filename": "../blocked.txt", "content": "x"}},
                {"id": "safe_write", "action": "write_file", "params": {"filename": "ok.txt", "content": "safe"}},
                {"id": "safe_read", "action": "read_file", "params": {"filename": "ok.txt"}},
            ],
        }
    }

    report = asyncio.run(engine.execute_workflow("x"))
    assert "flagged as dangerous" in report
    assert "path escapes managed workflow files directory" in report
    assert "File written:" in report
    assert "safe" in report
    assert (tmp_path / "workflow_files" / "ok.txt").exists()


def test_workflow_creation_writes_managed_definition_by_default(monkeypatch, tmp_path):
    _install_tool_wrapper_stub(monkeypatch)
    monkeypatch.delenv("SHELL_BLOCK_WORKFLOW_FILE_WRITE", raising=False)

    import brain.automation.engine as workflow_mod
    from brain.automation.engine import WorkflowEngine

    monkeypatch.setattr(workflow_mod, "WORKFLOW_DIR", str(tmp_path / "workflows"))
    monkeypatch.setattr(workflow_mod, "WORKFLOW_FILES_DIR", str(tmp_path / "workflow_files"))
    engine = WorkflowEngine()
    result = engine.create_workflow("../escape", "bad", [])
    assert "created" in result
    assert (tmp_path / "workflows" / "escape.json").exists()


def test_project_scaffold_is_allowed_by_default_without_core_code_write(monkeypatch):
    import shell_safety_gate

    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    monkeypatch.delenv("SHELL_BLOCK_PROJECT_SCAFFOLD", raising=False)

    code_ok, code_reason = shell_safety_gate.check_code_write("test")
    scaffold_ok, scaffold_reason = shell_safety_gate.check_project_scaffold("test")

    assert code_ok is False
    assert "Core/runtime code mutation" in code_reason
    assert scaffold_ok is True
    assert scaffold_reason == "permitted"


def test_project_scaffold_can_be_disabled(monkeypatch):
    import shell_safety_gate

    monkeypatch.setenv("SHELL_BLOCK_PROJECT_SCAFFOLD", "1")

    ok, reason = shell_safety_gate.check_project_scaffold("test")

    assert ok is False
    assert "SHELL_BLOCK_PROJECT_SCAFFOLD" in reason


def test_terminal_allows_safe_commands_by_default_and_blocks_damage(monkeypatch):
    import shell_terminal

    monkeypatch.delenv("SHELL_ALLOW_TERMINAL_EXEC", raising=False)
    monkeypatch.delenv("SHELL_BLOCK_TERMINAL_EXEC", raising=False)
    run_command = getattr(shell_terminal.run_command_tool, "__wrapped__", shell_terminal.run_command_tool)

    safe = asyncio.run(run_command("echo shell-ok"))
    dangerous = asyncio.run(run_command("rm -rf /"))

    assert "shell-ok" in safe
    assert dangerous.startswith("BLOCKED:")


def test_workspace_code_write_allowed_by_default_but_path_escape_blocked(monkeypatch, tmp_path):
    import shell_code_engine

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    write_code = getattr(shell_code_engine.write_code_tool, "__wrapped__", shell_code_engine.write_code_tool)

    saved = asyncio.run(write_code("hello.py", "print('hi')"))
    escaped = asyncio.run(write_code("escape.py", "print('bad')", path=str(tmp_path.parent)))

    assert "Code Saved" in saved
    assert (tmp_path / "shell_workspace" / "hello.py").exists()
    assert "Save refused" in escaped


def test_execute_code_blocks_dangerous_workspace_content(monkeypatch, tmp_path):
    import shell_code_engine

    monkeypatch.chdir(tmp_path)
    workspace = tmp_path / "shell_workspace"
    workspace.mkdir()
    (workspace / "bad.py").write_text("import os\nos.system('rm -rf /')\n", encoding="utf-8")
    execute_code = getattr(shell_code_engine.execute_code_tool, "__wrapped__", shell_code_engine.execute_code_tool)

    result = asyncio.run(execute_code("bad.py"))

    assert "Execution refused" in result


def test_secret_env_values_are_redacted(monkeypatch):
    _install_tool_wrapper_stub(monkeypatch)
    import shell_terminal

    assert shell_terminal._display_env_value("GOOGLE_API_KEY", "abc123") == "<redacted:set>"
    assert shell_terminal._display_env_value("PATH", "abc123") == "abc123"


def test_email_attachment_validation_fails_missing_file():
    import shell_email_tool

    ok, reason, paths = shell_email_tool._validate_attachment_paths("missing_report.pdf")

    assert ok is False
    assert "does not exist" in reason
    assert paths == []


def test_email_attachment_validation_accepts_real_file(monkeypatch, tmp_path):
    import shell_email_tool

    monkeypatch.chdir(tmp_path)
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF-1.4\n")

    ok, reason, paths = shell_email_tool._validate_attachment_paths(str(report))

    assert ok is True, reason
    assert paths == [str(report)]


def test_email_gmail_auth_error_is_actionable():
    import smtplib
    import shell_email_tool

    message = shell_email_tool._friendly_smtp_error(
        smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
    )

    assert "Google App Password" in message
    assert "normal Gmail password" in message


def test_email_web_fallback_selenium_error_is_actionable():
    import shell_email_tool

    message = shell_email_tool._friendly_web_fallback_error(
        "Gmail web fallback import failed: No module named 'selenium'"
    )

    assert "Selenium is not installed" in message
    assert "Repair Shell AI" in message


def test_api_key_delete_removes_env_line(monkeypatch, tmp_path):
    import shell_api_manager

    env_path = tmp_path / ".env"
    example_path = tmp_path / ".env.example"
    env_path.write_text(
        "OPENAI_API_KEY=old\n"
        "UNRELATED=value\n",
        encoding="utf-8",
    )
    example_path.write_text("OPENAI_API_KEY=\n", encoding="utf-8")

    monkeypatch.setattr(shell_api_manager, "_ENV_PATH", env_path)
    monkeypatch.setattr(shell_api_manager, "_ENV_EXAMPLE_PATH", example_path)
    monkeypatch.setenv("OPENAI_API_KEY", "old")

    ok, msg = shell_api_manager.delete_api_key("OPENAI_API_KEY")

    assert ok, msg
    saved = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in saved
    assert "UNRELATED=value" in saved
    assert "OPENAI_API_KEY" not in os.environ


def test_settings_manager_persists_and_updates_backend_env(monkeypatch, tmp_path):
    import shell_settings_manager

    settings_path = tmp_path / ".shell_settings.json"
    monkeypatch.setattr(shell_settings_manager, "_SETTINGS_PATH", settings_path)
    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    monkeypatch.delenv("SHELL_TEMPERATURE", raising=False)

    ok, msg, applied = shell_settings_manager.set_settings({
        "shell_allow_code_write": True,
        "temperature_pct": 82,
    })

    assert ok, msg
    assert applied["shell_allow_code_write"] is True
    assert settings_path.exists()
    assert os.environ["SHELL_ALLOW_CODE_WRITE"] == "1"
    assert os.environ["SHELL_TEMPERATURE"] == "0.82"


def test_settings_manager_accepts_ui_aliases(monkeypatch, tmp_path):
    import shell_settings_manager

    settings_path = tmp_path / ".shell_settings.json"
    monkeypatch.setattr(shell_settings_manager, "_SETTINGS_PATH", settings_path)
    monkeypatch.delenv("SHELL_SPEECH_RATE", raising=False)

    ok, msg, applied = shell_settings_manager.set_settings({"tts_rate": 155})

    assert ok, msg
    assert applied["tts_rate"] == 155
    assert os.environ["SHELL_SPEECH_RATE"] == "155"


def test_settings_manager_persists_reply_language(monkeypatch, tmp_path):
    import shell_settings_manager

    settings_path = tmp_path / ".shell_settings.json"
    monkeypatch.setattr(shell_settings_manager, "_SETTINGS_PATH", settings_path)
    monkeypatch.delenv("SHELL_LANGUAGE", raising=False)

    ok, msg, applied = shell_settings_manager.set_settings({"language": "hinglish"})

    assert ok, msg
    assert applied["language"] == "hinglish"
    assert applied["shell_language"] == "hinglish"
    assert os.environ["SHELL_LANGUAGE"] == "hinglish"


def test_settings_manager_persists_telegram_remote_safety(monkeypatch, tmp_path):
    import shell_settings_manager

    settings_path = tmp_path / ".shell_settings.json"
    monkeypatch.setattr(shell_settings_manager, "_SETTINGS_PATH", settings_path)
    monkeypatch.delenv("SHELL_TELEGRAM_ALLOWED_CHAT_IDS", raising=False)
    monkeypatch.delenv("SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED", raising=False)
    monkeypatch.delenv("SHELL_TELEGRAM_ALLOW_TERMINAL", raising=False)
    monkeypatch.delenv("AUTO_START_TELEGRAM_BOT", raising=False)

    ok, msg, applied = shell_settings_manager.set_settings({
        "telegram_allowed_chat_ids": "12345,67890",
        "telegram_remote_control_enabled": True,
        "telegram_auto_start": True,
        "telegram_allow_terminal": False,
    })

    assert ok, msg
    assert applied["telegram_allowed_chat_ids"] == "12345,67890"
    assert os.environ["SHELL_TELEGRAM_ALLOWED_CHAT_IDS"] == "12345,67890"
    assert os.environ["SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED"] == "1"
    assert os.environ["AUTO_START_TELEGRAM_BOT"] == "1"
    assert os.environ["SHELL_TELEGRAM_ALLOW_TERMINAL"] == "0"


def test_telegram_pc_control_requires_enabled_allowed_chat(monkeypatch):
    import shell_telegram

    monkeypatch.setenv("SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED", "0")
    monkeypatch.setenv("SHELL_TELEGRAM_ALLOWED_CHAT_IDS", "")
    shell_telegram._reload_runtime_config()
    bot = shell_telegram.ShellTelegramBot()

    ok, message = bot._remote_control_allowed(12345, 12345)
    assert ok is False
    assert "OFF" in message

    monkeypatch.setenv("SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED", "1")
    monkeypatch.setenv("SHELL_TELEGRAM_ALLOWED_CHAT_IDS", "999")
    shell_telegram._reload_runtime_config()

    ok, message = bot._remote_control_allowed(12345, 12345)
    assert ok is False
    assert "not allowed" in message

    monkeypatch.setenv("SHELL_TELEGRAM_ALLOWED_CHAT_IDS", "12345")
    shell_telegram._reload_runtime_config()

    ok, message = bot._remote_control_allowed(12345, 12345)
    assert ok is True
    assert message == "OK"
