from __future__ import annotations

import json


def _config(tmp_path):
    from shellai.config import ShellAIConfig, ShellAIPaths

    path = tmp_path / ".shellai" / "config.json"
    config = ShellAIConfig.load(path)
    config.paths = ShellAIPaths.from_config_path(path)
    config.paths.ensure_runtime_dirs()
    return config


def test_policy_reload_default_admin_and_audit_log(tmp_path) -> None:
    from shellai.policy import audit_log_path, evaluate_command, load_policy, policy_path, record_audit

    config = _config(tmp_path)
    policy_file = policy_path(config)
    policy_file.write_text(
        json.dumps(
            {
                "mode": "default",
                "allowed_patterns": [r"^echo safe$"],
                "blocked_patterns": [r"^echo blocked$"],
                "admin": {"allowed_patterns": [r"^rm temp\.txt$"]},
            }
        ),
        encoding="utf-8",
    )

    policy = load_policy(config)
    assert policy["mode"] == "default"
    assert evaluate_command("echo safe", config=config, policy=policy).level.value == "SAFE"
    blocked = evaluate_command("echo blocked", config=config, policy=policy)
    assert blocked.level.value == "BLOCK"

    policy_file.write_text(
        json.dumps({"mode": "admin", "admin": {"allowed_patterns": [r"^rm temp\.txt$"]}}),
        encoding="utf-8",
    )
    admin_policy = load_policy(config)
    assert evaluate_command("rm temp.txt", config=config, policy=admin_policy).level.value == "SAFE"

    record_audit(config, blocked)
    assert audit_log_path(config).exists()
    assert "echo blocked" in audit_log_path(config).read_text(encoding="utf-8")


def test_shell_tool_uses_policy_and_block_never_executes(tmp_path) -> None:
    from shellai.policy import policy_path, read_audit_log
    from shellai.tools import ShellTool, ToolRequest

    config = _config(tmp_path)
    marker = tmp_path / "should_not_exist"
    policy_path(config).write_text(
        json.dumps({"blocked_patterns": [r"^touch should_not_exist$"]}),
        encoding="utf-8",
    )
    result = ShellTool(config).run(
        ToolRequest(
            tool_name="shell",
            args={"command": "touch should_not_exist"},
            working_dir=str(tmp_path),
            approved=True,
        )
    )

    assert result.status == "blocked"
    assert result.metadata["risk"]["level"] == "BLOCK"
    assert not marker.exists()
    assert read_audit_log(config, limit=5)[0]["level"] == "BLOCK"


def test_monitor_empty_and_after_task_with_redaction(tmp_path) -> None:
    from shellai.agent_loop import create_user_request, run_agent_task
    from shellai.monitor import list_trace_snapshots, record_trace_snapshot, redact_text
    from shellai.observability import TRACE_STORE

    config = _config(tmp_path)
    assert list_trace_snapshots(config) == []

    result = run_agent_task(create_user_request("!whoami", context={"cwd": str(tmp_path)}), config=config)
    rows = list_trace_snapshots(config)
    assert len(rows) == 1
    assert rows[0]["trace_id"] == result["trace_id"]
    assert rows[0]["status"] == "ok"

    trace = TRACE_STORE.start_trace("deploy token=secret123")
    record_trace_snapshot(config, trace, status="error", summary="failed with --token abc123")
    redacted_rows = list_trace_snapshots(config, status_filter="error")
    assert "secret123" not in json.dumps(redacted_rows)
    assert "abc123" not in json.dumps(redacted_rows)
    assert "<redacted>" in redact_text("--token abc123")


def test_optimizer_suggests_recurring_tasks_and_safety_patterns(tmp_path) -> None:
    from shellai.agents_optimizer import OptimizerAgent
    from shellai.memory import MemoryStore
    from shellai.monitor import record_trace_snapshot
    from shellai.observability import TRACE_STORE
    from shellai.policy import evaluate_command, record_audit

    config = _config(tmp_path)
    memory = MemoryStore(tmp_path / "memory.sqlite3", config=config)
    for _index in range(2):
        trace = TRACE_STORE.start_trace("!git status")
        record_trace_snapshot(config, trace, status="ok", summary="git status ok")
        risk = evaluate_command("rm temp.txt", config=config)
        record_audit(config, risk, trace=trace)

    report = OptimizerAgent(config=config, memory_store=memory).generate_report()
    types = {item["type"] for item in report["suggestions"]}

    assert report["mutated"] is False
    assert "skill_candidate" in types
    assert "safety_pattern" in types
