import json
import os
import shutil
import sys
import textwrap

from shell_tool_catalog import mcp_action_catalog
from shell_windows_mcp import (
    call_windows_mcp_tool_sync,
    windows_mcp_command,
    windows_mcp_tool_catalog,
)


def test_windows_mcp_catalog_replaces_legacy_mcp_actions():
    catalog = mcp_action_catalog()
    ids = {item["id"] for item in catalog}
    names = {item["name"] for item in catalog}

    assert "windows-mcp:Click" in ids
    assert "windows-mcp:Screenshot" in ids
    assert "windows-mcp:Shell" in ids
    assert "Click" in names
    assert all(item["kind"] == "windows_mcp_tool" for item in catalog)
    assert all(item["module"] == "windows-mcp" for item in catalog)
    assert "mcp:open_google" not in ids
    assert "mcp:test" not in ids


def test_windows_mcp_command_override(monkeypatch):
    monkeypatch.setenv("SHELL_WINDOWS_MCP_COMMAND", '["uv", "--directory", "C:/Windows-MCP", "run", "windows-mcp"]')

    assert windows_mcp_command() == ["uv", "--directory", "C:/Windows-MCP", "run", "windows-mcp"]


def test_windows_mcp_command_finds_venv_uvx(monkeypatch, tmp_path):
    scripts = tmp_path / ("Scripts" if os.name == "nt" else "bin")
    scripts.mkdir()
    exe_name = "uvx.exe" if os.name == "nt" else "uvx"
    uvx = scripts / exe_name
    uvx.write_text("", encoding="utf-8")
    py = scripts / ("python.exe" if os.name == "nt" else "python")
    py.write_text("", encoding="utf-8")

    monkeypatch.delenv("SHELL_WINDOWS_MCP_COMMAND", raising=False)
    monkeypatch.delenv("SHELL_WINDOWS_MCP_EXE", raising=False)
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(sys, "executable", str(py))

    assert windows_mcp_command() == [str(uvx), "windows-mcp"]


def test_windows_mcp_default_non_windows_is_guarded(monkeypatch):
    monkeypatch.delenv("SHELL_WINDOWS_MCP_ALLOW_NON_WINDOWS", raising=False)
    if os.name == "nt":
        return

    result = call_windows_mcp_tool_sync("Screenshot", {})

    assert result["status"] == "error"
    assert result["state"] == "WINDOWS_ONLY"
    assert result["transport"] == "windows-mcp"
    assert result["supported"] is False
    assert result["required_platform"] == "Windows"
    assert "requires Windows" in result["message"]


def test_windows_mcp_tool_call_uses_json_rpc_stdio(tmp_path):
    fake_server = tmp_path / "fake_windows_mcp.py"
    fake_server.write_text(
        textwrap.dedent(
            """
            import json
            import sys

            for line in sys.stdin:
                msg = json.loads(line)
                if msg.get("method") == "notifications/initialized":
                    continue
                rid = msg.get("id")
                method = msg.get("method")
                if method == "initialize":
                    result = {"protocolVersion": "2024-11-05", "serverInfo": {"name": "fake-windows-mcp"}}
                elif method == "tools/list":
                    result = {"tools": [{"name": "Click"}, {"name": "Screenshot"}]}
                elif method == "tools/call":
                    result = {
                        "content": [{"type": "text", "text": "called"}],
                        "name": msg["params"]["name"],
                        "arguments": msg["params"]["arguments"],
                    }
                else:
                    result = {}
                print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}), flush=True)
            """
        ),
        encoding="utf-8",
    )

    result = call_windows_mcp_tool_sync(
        "Click",
        {"x": 10, "y": 20},
        command=[sys.executable, str(fake_server)],
        timeout=5,
    )

    assert result["status"] == "success"
    assert result["transport"] == "windows-mcp"
    assert result["tool"] == "Click"
    assert result["result"]["name"] == "Click"
    assert result["result"]["arguments"] == {"x": 10, "y": 20}


def test_windows_mcp_static_catalog_has_ui_params():
    click = next(item for item in windows_mcp_tool_catalog() if item["name"] == "Click")

    assert click["id"] == "windows-mcp:Click"
    assert click["risk"] == "guarded"
    assert [param["name"] for param in click["params"]] == ["x", "y", "button"]
