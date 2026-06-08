from __future__ import annotations

import json


def test_agent_first_orchestrator_wraps_math_tool_as_reasoning_capability():
    from core.agent_orchestrator import AgentFirstOrchestrator

    plan = AgentFirstOrchestrator().orchestrate("what is 2 + 3 * 4")
    data = plan.to_dict()

    assert data["status"] == "planned"
    assert data["selected_agent_id"] == "reasoning_agent"
    assert data["capability"] == "capability.reasoning"
    assert data["low_level_tool_id"] == "shell_calculator:calculate_tool"
    assert data["args"] == {"expression": "2 + 3 * 4"}
    assert data["execution_allowed"] is True
    assert any("tool selected as internal capability" in reason for reason in data["reasons"])


def test_agent_first_orchestrator_routes_desktop_action_to_desktop_agent():
    from core.agent_orchestrator import AgentFirstOrchestrator

    data = AgentFirstOrchestrator().orchestrate("open calculator").to_dict()

    assert data["selected_agent_id"] == "desktop_automation_agent"
    assert data["capability"] == "capability.desktop"
    assert data["low_level_tool_id"] == "shell_window_CTRL:open_app"
    assert data["risk_level"] == "caution"


def test_agent_first_orchestrator_routes_desktop_folder_workflow_without_planner_block():
    from core.agent_orchestrator import AgentFirstOrchestrator

    data = AgentFirstOrchestrator().orchestrate("Shell, create a folder called 'Reels Export' on Desktop and open it.").to_dict()

    assert data["status"] == "planned"
    assert data["selected_agent_id"] == "desktop_automation_agent"
    assert data["capability"] == "capability.desktop"
    assert data["low_level_tool_id"] == "shell_windows_workflows:create_desktop_folder_tool"
    assert data["args"] == {"folder_name": "Reels Export", "open_folder": True}
    assert data["execution_allowed"] is True


def test_agent_first_orchestrator_routes_focus_assist_workflow_without_planner_block():
    from core.agent_orchestrator import AgentFirstOrchestrator

    data = AgentFirstOrchestrator().orchestrate("Shell, turn on Focus Assist for 30 minutes").to_dict()

    assert data["status"] == "planned"
    assert data["selected_agent_id"] == "system_monitoring_agent"
    assert data["capability"] == "capability.system"
    assert data["low_level_tool_id"] == "shell_windows_workflows:open_focus_assist_tool"
    assert data["args"] == {"minutes": 30}
    assert data["execution_allowed"] is True


def test_agent_first_orchestrator_blocks_risky_terminal_without_approval():
    from core.agent_orchestrator import AgentFirstOrchestrator

    data = AgentFirstOrchestrator().orchestrate("terminal echo hello").to_dict()

    assert data["selected_agent_id"] == "coding_agent"
    assert data["capability"] == "capability.coding"
    assert data["low_level_tool_id"] == "shell_terminal:run_command_tool"
    assert data["risk_level"] == "dangerous"
    assert data["requires_approval"] is True
    assert data["execution_allowed"] is False
    assert any("approval" in reason for reason in data["reasons"])


def test_agent_first_orchestrator_uses_planner_when_no_capability_route_exists():
    from core.agent_orchestrator import AgentFirstOrchestrator

    data = AgentFirstOrchestrator().orchestrate("make Shell more emotionally intelligent").to_dict()

    assert data["status"] == "needs_planning"
    assert data["selected_agent_id"] == "planner_agent"
    assert data["capability"] == "plan.goal"
    assert data["execution_allowed"] is False


def test_agent_orchestrator_tool_does_not_execute_by_default():
    import shell_agent_orchestrator

    raw = shell_agent_orchestrator.orchestrate_shell_goal(
        "what is 2 + 3 * 4",
        execute=False,
    )
    data = json.loads(raw)

    assert data["selected_agent_id"] == "reasoning_agent"
    assert data["low_level_tool_id"] == "shell_calculator:calculate_tool"
    assert data["execution_requested"] is False
    assert "execution_result" not in data


def test_agent_orchestrator_is_cataloged_as_agent_boundary():
    from shell_tool_catalog import discover_tool_catalog

    rows = {
        row["id"]: row
        for row in discover_tool_catalog()
        if row["id"].startswith("shell_agent_orchestrator:")
    }

    assert rows["shell_agent_orchestrator:orchestrate_shell_goal_tool"]["kind"] == "agent"
    assert rows["shell_agent_orchestrator:list_orchestration_agents_tool"]["kind"] == "agent"
