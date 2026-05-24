import asyncio


def test_workflow_checkpoints_flag_default_off(monkeypatch):
    monkeypatch.delenv("SHELL_WORKFLOW_CHECKPOINTS_ENABLED", raising=False)

    from core.workflow_checkpoints import workflow_checkpoints_enabled

    assert workflow_checkpoints_enabled() is False


def test_sqlite_checkpoints_persist_and_track_last_action(tmp_path):
    from core.workflow_checkpoints import WorkflowCheckpointConfig, WorkflowCheckpointManager

    db_path = tmp_path / "checkpoints.sqlite3"
    manager = WorkflowCheckpointManager(WorkflowCheckpointConfig(path=db_path, backend="sqlite"))
    saved = manager.save_checkpoint(
        "wf-1",
        {"phase": "indexed"},
        action="project_rag_index",
        step_index=2,
        rollback_state={"phase": "scanned"},
        metadata={"files": 4},
    )

    assert saved.step_index == 2
    assert saved.parent_checkpoint_id == ""

    restored_manager = WorkflowCheckpointManager(WorkflowCheckpointConfig(path=db_path, backend="sqlite"))
    loaded = restored_manager.load_checkpoint("wf-1")
    status = restored_manager.status("wf-1")

    assert loaded is not None
    assert loaded.state["phase"] == "indexed"
    assert loaded.rollback_state["phase"] == "scanned"
    assert status["workflow"]["last_action"] == "project_rag_index"
    assert status["workflow"]["checkpoint_count"] == 1


def test_rollback_creates_auditable_checkpoint_with_restored_state(tmp_path):
    from core.workflow_checkpoints import WorkflowCheckpointConfig, WorkflowCheckpointManager

    manager = WorkflowCheckpointManager(WorkflowCheckpointConfig(path=tmp_path / "checkpoints.sqlite3", backend="sqlite"))
    first = manager.save_checkpoint(
        "wf-rollback",
        {"phase": "after-step"},
        action="run_step",
        rollback_state={"phase": "before-step"},
    )

    rolled = manager.rollback("wf-rollback", first.checkpoint_id)
    latest = manager.load_checkpoint("wf-rollback")

    assert rolled["ok"] is True
    assert rolled["restored_state"] == {"phase": "before-step"}
    assert latest is not None
    assert latest.status == "rolled_back"
    assert latest.action.startswith("rollback:")
    assert latest.state == {"phase": "before-step"}
    assert latest.rollback_state == {"phase": "after-step"}


def test_json_backend_save_load_and_auto_step(tmp_path):
    from core.workflow_checkpoints import WorkflowCheckpointConfig, WorkflowCheckpointManager

    manager = WorkflowCheckpointManager(WorkflowCheckpointConfig(path=tmp_path / "checkpoints.json", backend="json"))
    first = manager.save_checkpoint("wf-json", {"step": 1}, action="one")
    second = manager.save_checkpoint("wf-json", {"step": 2}, action="two")
    loaded = manager.load_checkpoint("wf-json")
    rows = manager.list_checkpoints("wf-json")

    assert first.step_index == 1
    assert second.step_index == 2
    assert loaded is not None
    assert loaded.state == {"step": 2}
    assert [row.action for row in rows[:2]] == ["two", "one"]


def test_workflow_checkpoint_tools_respect_disabled_flag(monkeypatch):
    monkeypatch.delenv("SHELL_WORKFLOW_CHECKPOINTS_ENABLED", raising=False)

    import shell_workflow_checkpoints

    result = asyncio.run(
        shell_workflow_checkpoints.workflow_checkpoint_save_tool.__wrapped__(
            "wf-tool",
            "step",
            '{"ok": true}',
        )
    )

    assert result["ok"] is False
    assert result["enabled"] is False


def test_workflow_checkpoint_tools_save_load_rollback(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_WORKFLOW_CHECKPOINTS_ENABLED", "1")
    monkeypatch.setenv("SHELL_WORKFLOW_CHECKPOINTS_BACKEND", "sqlite")
    monkeypatch.setenv("SHELL_WORKFLOW_CHECKPOINTS_PATH", str(tmp_path / "checkpoints.sqlite3"))

    import shell_workflow_checkpoints

    saved = asyncio.run(
        shell_workflow_checkpoints.workflow_checkpoint_save_tool.__wrapped__(
            "wf-tool",
            "write_code",
            '{"file": "app.py", "done": true}',
            '{"file": "app.py", "done": false}',
            3,
            '{"agent": "coder"}',
        )
    )
    loaded = asyncio.run(shell_workflow_checkpoints.workflow_checkpoint_load_tool.__wrapped__("wf-tool", ""))
    rolled = asyncio.run(shell_workflow_checkpoints.workflow_checkpoint_rollback_tool.__wrapped__("wf-tool", ""))
    status = asyncio.run(shell_workflow_checkpoints.workflow_checkpoint_status_tool.__wrapped__("wf-tool"))

    assert saved["ok"] is True
    assert loaded["checkpoint"]["state"]["done"] is True
    assert rolled["ok"] is True
    assert rolled["restored_state"]["done"] is False
    assert status["workflow"]["status"] == "rolled_back"


def test_public_api_save_load_rollback(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_WORKFLOW_CHECKPOINTS_PATH", str(tmp_path / "api.sqlite3"))
    monkeypatch.setenv("SHELL_WORKFLOW_CHECKPOINTS_BACKEND", "sqlite")

    import shell_workflow_checkpoints

    saved = shell_workflow_checkpoints.save_checkpoint(
        "wf-api",
        {"current": "step-2"},
        action="step-2",
        rollback_state={"current": "step-1"},
    )
    loaded = shell_workflow_checkpoints.load_checkpoint("wf-api")
    rolled = shell_workflow_checkpoints.rollback("wf-api")

    assert saved["ok"] is True
    assert loaded["checkpoint"]["action"] == "step-2"
    assert rolled["restored_state"] == {"current": "step-1"}


def test_tool_catalog_discovers_workflow_checkpoint_tools():
    from shell_tool_catalog import discover_tool_catalog

    ids = {item["id"] for item in discover_tool_catalog()}
    assert "shell_workflow_checkpoints:workflow_checkpoint_save_tool" in ids
    assert "shell_workflow_checkpoints:workflow_checkpoint_load_tool" in ids
    assert "shell_workflow_checkpoints:workflow_checkpoint_rollback_tool" in ids
    assert "shell_workflow_checkpoints:workflow_checkpoint_status_tool" in ids
