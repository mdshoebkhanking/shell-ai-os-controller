import asyncio
import json


def test_secure_sandbox_flag_default_off(monkeypatch):
    monkeypatch.delenv("SHELL_SECURE_SANDBOX_ENABLED", raising=False)

    from core.secure_sandbox import secure_sandbox_enabled

    assert secure_sandbox_enabled() is False


def test_secure_sandbox_scrubs_secret_environment(tmp_path):
    from core.secure_sandbox import scrub_environment

    env = scrub_environment(
        {"PATH": "/bin", "OPENAI_API_KEY": "secret", "NORMAL": "value"},
        home=tmp_path,
    )

    assert env["PATH"] == "/bin"
    assert env["HOME"] == str(tmp_path)
    assert "OPENAI_API_KEY" not in env
    assert "NORMAL" not in env


def test_secure_sandbox_runs_python_and_audits(tmp_path):
    from core.secure_sandbox import SandboxConfig, SecureCodingSandbox

    sandbox = SecureCodingSandbox(
        SandboxConfig(
            timeout_s=5,
            root_dir=tmp_path / "runs",
            audit_path=tmp_path / "audit.jsonl",
        )
    )

    result = asyncio.run(sandbox.run_python("print('hello sandbox')"))

    assert result.ok is True
    assert "hello sandbox" in result.stdout
    assert result.rolled_back is True
    rows = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["status"] == "ok"
    assert rows[0]["code_sha256"]


def test_secure_sandbox_timeout_rolls_back(tmp_path):
    from core.secure_sandbox import SandboxConfig, SecureCodingSandbox

    sandbox = SecureCodingSandbox(
        SandboxConfig(
            timeout_s=0.1,
            root_dir=tmp_path / "runs",
            audit_path=tmp_path / "audit.jsonl",
        )
    )

    result = asyncio.run(sandbox.run_python("import time\ntime.sleep(2)"))

    assert result.ok is False
    assert result.timed_out is True
    assert result.rolled_back is True


def test_secure_sandbox_blocks_network_import_when_disabled(tmp_path):
    from core.secure_sandbox import SandboxConfig, SecureCodingSandbox

    sandbox = SecureCodingSandbox(
        SandboxConfig(
            timeout_s=5,
            network_enabled=False,
            root_dir=tmp_path / "runs",
            audit_path=tmp_path / "audit.jsonl",
        )
    )

    result = asyncio.run(sandbox.run_python("import requests\nprint('no')"))

    assert result.ok is False
    assert "network disabled" in result.error


def test_secure_sandbox_tools_and_existing_python_tool(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_SECURE_SANDBOX_ENABLED", "1")
    monkeypatch.setenv("SHELL_SECURE_SANDBOX_ROOT", str(tmp_path))
    monkeypatch.setenv("SHELL_SECURE_SANDBOX_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.delenv("SHELL_ALLOW_TERMINAL_EXEC", raising=False)

    import shell_secure_sandbox
    import shell_terminal

    direct = asyncio.run(shell_secure_sandbox.secure_sandbox_run_python_tool.__wrapped__("print(2 + 2)", 5))
    assert direct["ok"] is True
    assert "4" in direct["stdout"]

    routed = asyncio.run(shell_terminal.run_python_tool.__wrapped__("print('routed')"))
    assert "Sandbox OK" in routed
    assert "routed" in routed


def test_execute_code_tool_uses_sandbox_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_SECURE_SANDBOX_ENABLED", "1")
    monkeypatch.setenv("SHELL_SECURE_SANDBOX_ROOT", str(tmp_path))
    monkeypatch.setenv("SHELL_SECURE_SANDBOX_AUDIT", str(tmp_path / "audit.jsonl"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "script.py").write_text("print('file sandbox')\n", encoding="utf-8")

    import shell_code_engine

    result = asyncio.run(shell_code_engine.execute_code_tool.__wrapped__("script.py", str(workspace)))

    assert "Sandbox OK" in result
    assert "file sandbox" in result


def test_secure_sandbox_tool_respects_disabled_flag(monkeypatch):
    monkeypatch.delenv("SHELL_SECURE_SANDBOX_ENABLED", raising=False)

    import shell_secure_sandbox

    result = asyncio.run(shell_secure_sandbox.secure_sandbox_run_python_tool.__wrapped__("print(1)", 5))
    assert result["ok"] is False


def test_tool_catalog_discovers_secure_sandbox_tools():
    from shell_tool_catalog import discover_tool_catalog

    ids = {item["id"] for item in discover_tool_catalog()}
    assert "shell_secure_sandbox:secure_sandbox_run_python_tool" in ids
    assert "shell_secure_sandbox:secure_sandbox_run_file_tool" in ids
    assert "shell_secure_sandbox:secure_sandbox_status_tool" in ids
