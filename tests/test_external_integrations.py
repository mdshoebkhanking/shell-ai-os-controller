import sys

import shell_external_integrations
from shell_external_integrations import agent_browser_skills, parse_openclaw_skills
from shell_tool_catalog import discover_tool_catalog
from shell_tool_gateway import execute_tool_sync


def test_agent_browser_skills_are_discoverable_from_clone():
    skills = agent_browser_skills()

    assert any(row["name"] == "agent-browser" for row in skills)
    assert any(row["name"] == "core" for row in skills)


def test_openclaw_skill_search_uses_local_index():
    results = parse_openclaw_skills(query="github", limit=5)

    assert results
    assert all("name" in row and "url" in row for row in results)


def test_external_integrations_have_public_repo_fallbacks(monkeypatch, tmp_path):
    monkeypatch.setattr(shell_external_integrations, "AGENT_BROWSER_ROOT", tmp_path / "missing-agent-browser")
    monkeypatch.setattr(shell_external_integrations, "OPENCLAW_ROOT", tmp_path / "missing-openclaw")

    skills = shell_external_integrations.agent_browser_skills()
    openclaw = shell_external_integrations.parse_openclaw_skills(query="github", limit=5)

    assert any(row["name"] == "agent-browser" for row in skills)
    assert any(row["name"] == "core" for row in skills)
    assert openclaw
    assert all("name" in row and "url" in row for row in openclaw)


def test_external_integration_tools_are_in_shell_catalog():
    catalog = discover_tool_catalog()
    ids = {item["id"] for item in catalog}

    assert "shell_external_integrations:external_integration_status_tool" in ids
    assert "shell_external_integrations:agent_browser_command_tool" in ids
    assert "shell_external_integrations:openclaw_skill_search_tool" in ids
    assert "shell_external_integrations:openclaw_skill_install_tool" in ids


def test_external_integration_readiness_does_not_require_selenium():
    from core.tools.registry import enrich_catalog

    row = next(
        item for item in discover_tool_catalog()
        if item["id"] == "shell_external_integrations:agent_browser_command_tool"
    )
    enriched = enrich_catalog([row])[0]

    assert enriched["readiness"]["ok"] is True
    assert "selenium" not in " ".join(enriched["readiness"].get("reasons") or [])


def test_agent_browser_command_defaults_to_permission_gate(monkeypatch):
    monkeypatch.delenv("SHELL_ALLOW_AGENT_BROWSER_EXEC", raising=False)

    result = execute_tool_sync("shell_external_integrations:agent_browser_command_tool", {"command": "skills list"})

    assert result["status"] == "success"
    assert result["result"]["status"] == "blocked"
    assert result["result"]["state"] == "NEEDS_PERMISSION"


def test_agent_browser_command_executes_when_permission_enabled(monkeypatch):
    monkeypatch.setenv("SHELL_ALLOW_AGENT_BROWSER_EXEC", "1")
    monkeypatch.setattr(
        shell_external_integrations,
        "_agent_browser_executable",
        lambda: [sys.executable, "-c", "import sys; print('AB_OK:' + ' '.join(sys.argv[1:]))"],
    )

    result = execute_tool_sync("shell_external_integrations:agent_browser_command_tool", {"command": "skills list"})

    assert result["status"] == "success"
    assert result["result"]["status"] == "success"
    assert "AB_OK:skills list" in result["result"]["output"]


def test_openclaw_install_requires_permission(monkeypatch):
    monkeypatch.delenv("SHELL_ALLOW_OPENCLAW_SKILL_INSTALL", raising=False)

    result = execute_tool_sync("shell_external_integrations:openclaw_skill_install_tool", {"skill_slug": "git-helper"})

    assert result["status"] == "success"
    assert result["result"]["status"] == "blocked"
    assert result["result"]["state"] == "NEEDS_PERMISSION"
    assert result["result"]["command"][-1] == "git-helper"
