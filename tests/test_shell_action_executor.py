import os
import pytest

pytest.skip("ShellActionExecutor was removed during PyQt6 cleanup", allow_module_level=True)


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_action_executor_does_not_call_write_code_without_required_args():
    # ShellActionExecutor removed (PyQt6 cleanup)

    result = ShellActionExecutor.execute("shell_code_engine", "write_code_tool", "")

    assert "Tool needs filename and content" in result
    assert "missing 2 required positional arguments" not in result


def test_action_executor_parses_write_code_filename_and_content(monkeypatch, tmp_path):
    # ShellActionExecutor removed (PyQt6 cleanup)

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    result = ShellActionExecutor.execute(
        "shell_code_engine",
        "write_code_tool",
        "hello.py: print('hi')",
    )

    assert "missing 2 required positional arguments" not in result
    assert "Code Saved" in result
    assert (tmp_path / "shell_workspace" / "hello.py").exists()
