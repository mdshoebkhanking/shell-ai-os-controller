from __future__ import annotations


def test_shell_tool_classifies_safe_ask_and_block(tmp_path) -> None:
    from shellai.config import ShellAIConfig
    from shellai.tools import ShellTool, ToolRequest

    tool = ShellTool(ShellAIConfig())

    safe = tool.run(ToolRequest(tool_name="shell", args={"command": "pwd"}, working_dir=str(tmp_path), dry_run=True))
    assert safe.status == "dry_run"
    assert safe.metadata["risk"]["level"] == "SAFE"

    ask = tool.run(ToolRequest(tool_name="shell", args={"command": "rm some-file"}, working_dir=str(tmp_path)))
    assert ask.status == "needs_confirmation"
    assert ask.metadata["risk"]["level"] == "ASK"

    blocked = tool.run(ToolRequest(tool_name="shell", args={"command": "rm -rf /"}, approved=True))
    assert blocked.status == "blocked"
    assert blocked.metadata["risk"]["level"] == "BLOCK"


def test_shell_tool_executes_safe_command_and_traces(tmp_path) -> None:
    from shellai.config import ShellAIConfig
    from shellai.observability import TRACE_STORE
    from shellai.tools import ShellTool, ToolRequest

    TRACE_STORE.clear()
    trace = TRACE_STORE.start_trace("run pwd")
    tool = ShellTool(ShellAIConfig())
    result = tool.run(
        ToolRequest(
            tool_name="shell",
            args={"command": "pwd"},
            working_dir=str(tmp_path),
            trace=trace,
        )
    )

    assert result.status == "ok"
    assert result.exit_code == 0
    assert str(tmp_path) in result.stdout
    assert trace.steps[-1].name == "Tool:shell"
    assert trace.steps[-1].metadata["risk"]["level"] == "SAFE"


def test_file_tool_basic_operations(tmp_path) -> None:
    from shellai.tools import FileTool, ToolRequest

    tool = FileTool()
    write = tool.run(
        ToolRequest(
            tool_name="file",
            working_dir=str(tmp_path),
            args={"operation": "write_file", "path": "notes.txt", "content": "hello"},
        )
    )
    assert write.status == "ok"

    append = tool.run(
        ToolRequest(
            tool_name="file",
            working_dir=str(tmp_path),
            args={"operation": "append_file", "path": "notes.txt", "content": "\nworld"},
        )
    )
    assert append.status == "ok"

    read = tool.run(
        ToolRequest(
            tool_name="file",
            working_dir=str(tmp_path),
            args={"operation": "read_file", "path": "notes.txt"},
        )
    )
    assert read.stdout == "hello\nworld"

    listed = tool.run(ToolRequest(tool_name="file", working_dir=str(tmp_path), args={"operation": "list_dir", "path": "."}))
    assert "notes.txt" in listed.stdout


def test_os_tool_info_expand_and_open_stub(tmp_path) -> None:
    from shellai.tools import OSTool, ToolRequest

    tool = OSTool()
    info = tool.run(ToolRequest(tool_name="os", args={"operation": "get_os_info"}))
    assert info.status == "ok"
    assert "system" in info.metadata

    expanded = tool.run(ToolRequest(tool_name="os", working_dir=str(tmp_path), args={"operation": "expand_user_path", "path": "."}))
    assert expanded.status == "ok"
    assert expanded.stdout == str(tmp_path.resolve())

    opened = tool.run(ToolRequest(tool_name="os", args={"operation": "open_path", "path": str(tmp_path)}))
    assert opened.status == "not_implemented"


def test_tool_registry_lookup_and_error_path() -> None:
    import pytest

    from shellai.tools import ToolRegistry

    registry = ToolRegistry()
    assert registry.get_tool("shell").metadata.name == "shell"
    assert {tool["name"] for tool in registry.list_tools()} >= {"shell", "file", "os"}
    with pytest.raises(KeyError):
        registry.get_tool("missing")
