from shell_tool_catalog import discover_tool_catalog
from shell_tool_gateway import execute_tool_sync


def test_workspace_tools_are_in_catalog():
    ids = {item["id"] for item in discover_tool_catalog()}

    assert "shell_workspace_tools:create_workspace_file_tool" in ids
    assert "shell_workspace_tools:create_user_file_tool" in ids
    assert "shell_workspace_tools:read_workspace_file_tool" in ids
    assert "shell_workspace_tools:list_workspace_files_tool" in ids


def test_workspace_create_read_and_list(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_WORKSPACE_PATH", str(tmp_path))

    created = execute_tool_sync(
        "shell_workspace_tools:create_workspace_file_tool",
        {"path": "notes/test.md", "content": "hello from Shell"},
    )
    assert created["status"] == "success"
    assert created["result"]["ok"] is True
    assert created["result"]["relative_path"] == "notes/test.md"
    assert (tmp_path / "notes" / "test.md").read_text(encoding="utf-8") == "hello from Shell"

    read = execute_tool_sync("shell_workspace_tools:read_workspace_file_tool", {"path": "notes/test.md"})
    assert read["status"] == "success"
    assert read["result"]["content"] == "hello from Shell"

    listed = execute_tool_sync("shell_workspace_tools:list_workspace_files_tool", {"limit": 20})
    assert listed["status"] == "success"
    assert listed["result"]["count"] == 1
    assert listed["result"]["files"][0]["relative_path"] == "notes/test.md"


def test_workspace_tools_reject_path_escape(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_WORKSPACE_PATH", str(tmp_path))

    result = execute_tool_sync(
        "shell_workspace_tools:create_workspace_file_tool",
        {"path": "../outside.txt", "content": "bad"},
    )

    assert result["status"] == "success"
    assert result["result"]["ok"] is False
    assert "Path traversal is not allowed" in result["result"]["message"]
    assert not (tmp_path.parent / "outside.txt").exists()


def test_create_user_file_writes_to_desktop(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    result = execute_tool_sync(
        "shell_workspace_tools:create_user_file_tool",
        {
            "filename": "shell-note.txt",
            "content": "hello desktop",
            "destination": "desktop",
            "file_type": "txt",
        },
    )

    assert result["status"] == "success"
    assert result["result"]["ok"] is True
    output = tmp_path / "Desktop" / "shell-note.txt"
    assert output.read_text(encoding="utf-8").strip() == "hello desktop"


def test_create_user_file_can_write_pdf(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    result = execute_tool_sync(
        "shell_workspace_tools:create_user_file_tool",
        {
            "filename": "shell-report.pdf",
            "content": "Shell PDF content",
            "destination": "desktop",
            "file_type": "pdf",
        },
    )

    assert result["status"] == "success"
    assert result["result"]["ok"] is True
    output = tmp_path / "Desktop" / "shell-report.pdf"
    assert output.read_bytes().startswith(b"%PDF")


def test_create_user_file_rejects_unsupported_extension(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    result = execute_tool_sync(
        "shell_workspace_tools:create_user_file_tool",
        {
            "filename": "run.exe",
            "content": "blocked",
            "destination": "desktop",
        },
    )

    assert result["status"] == "success"
    assert result["result"]["ok"] is False
    assert not (tmp_path / "Desktop" / "run.exe").exists()
