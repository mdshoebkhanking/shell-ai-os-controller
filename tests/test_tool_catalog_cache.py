from __future__ import annotations

import ast


def test_tool_catalog_disk_cache_avoids_reparse(monkeypatch, tmp_path) -> None:
    import shell_tool_catalog

    module = tmp_path / "shell_demo.py"
    module.write_text(
        "from shell_safe_executor import god_tier_tool as function_tool\n\n"
        "@function_tool\n"
        "async def hello_tool(name: str = 'Shell') -> str:\n"
        "    \"\"\"Say hello.\"\"\"\n"
        "    return name\n",
        encoding="utf-8",
    )
    cache_path = tmp_path / ".shell_runtime" / "tool_catalog_cache.json"

    monkeypatch.setattr(shell_tool_catalog, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(shell_tool_catalog, "_DISK_CACHE_PATH", cache_path)
    shell_tool_catalog._DISCOVER_TOOL_CACHE.clear()

    first = shell_tool_catalog.discover_tool_catalog()
    assert cache_path.exists()
    assert [row["id"] for row in first] == ["shell_demo:hello_tool"]

    shell_tool_catalog._DISCOVER_TOOL_CACHE.clear()
    monkeypatch.setattr(ast, "parse", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("reparsed")))

    second = shell_tool_catalog.discover_tool_catalog()
    assert second == first


def test_tool_catalog_cache_can_be_disabled(monkeypatch, tmp_path) -> None:
    import shell_tool_catalog

    module = tmp_path / "shell_demo.py"
    module.write_text(
        "from shell_safe_executor import god_tier_tool as function_tool\n\n"
        "@function_tool\n"
        "def echo_tool(text: str) -> str:\n"
        "    \"\"\"Echo text.\"\"\"\n"
        "    return text\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(shell_tool_catalog, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(shell_tool_catalog, "_DISK_CACHE_PATH", tmp_path / ".shell_runtime" / "tool_catalog_cache.json")
    monkeypatch.setenv("SHELL_DISABLE_TOOL_CATALOG_CACHE", "1")
    shell_tool_catalog._DISCOVER_TOOL_CACHE.clear()

    rows = shell_tool_catalog.discover_tool_catalog()

    assert [row["id"] for row in rows] == ["shell_demo:echo_tool"]
    assert not shell_tool_catalog._DISK_CACHE_PATH.exists()
