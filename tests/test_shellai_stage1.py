from __future__ import annotations

import json


def test_shell_risk_policy_safe_ask_block() -> None:
    from shellai.safety import RiskLevel, ShellRiskPolicy

    policy = ShellRiskPolicy()

    assert policy.classify("git status").level is RiskLevel.SAFE
    assert policy.classify("sudo apt update").level is RiskLevel.ASK
    assert policy.classify("rm -rf /").level is RiskLevel.BLOCK


def test_coordinator_uses_three_agent_trace_for_shell_command() -> None:
    from shellai.agents import CoordinatorAgent
    from shellai.config import ShellAIConfig
    from shellai.observability import TRACE_STORE

    TRACE_STORE.clear()
    response = CoordinatorAgent(config=ShellAIConfig()).handle("!git status")

    assert response["agents"] == ["CoordinatorAgent", "ShellAgent", "SafetyAgent"]
    assert response["status"] == "ready"
    assert response["risk"]["level"] == "SAFE"
    names = [step["name"] for step in response["trace"]["steps"]]
    assert names[0:2] == ["CoordinatorAgent", "ShellAgent"]
    assert "Policy" in names
    assert "SafetyAgent" in names
    assert names[-1] == "CoordinatorAgent"


def test_cli_run_json_smoke(capsys) -> None:
    from shellai.cli import main

    assert main(["run", "!git", "status", "--json"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["status"] == "ok"
    assert payload["steps"][0]["metadata"]["risk"]["level"] == "SAFE"
    assert payload["steps"][0]["metadata"]["command"] == "git status"


def test_config_model_set_value_without_disk_write() -> None:
    from shellai.config import ShellAIConfig

    config = ShellAIConfig()
    config.set_value("models.planning", "test-model")
    config.set_value("enabled_tools.os", "true")

    assert config.models.planning == "test-model"
    assert config.enabled_tools["os"] is True
    assert config.user_profile["language_style"].startswith("mixed Hindi + English")
    assert "android_adb" in config.user_profile["high_priority_tools"]
