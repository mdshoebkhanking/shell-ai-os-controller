#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any

from core.workflow_checkpoints import (
    WorkflowCheckpointConfig,
    WorkflowCheckpointManager,
    workflow_checkpoints_enabled,
)
from shell_safe_executor import god_tier_tool as function_tool


def _disabled_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "enabled": False,
        "message": "Workflow checkpoints disabled. Set SHELL_WORKFLOW_CHECKPOINTS_ENABLED=1 to persist agent checkpoints.",
    }


def _manager() -> WorkflowCheckpointManager:
    return WorkflowCheckpointManager(WorkflowCheckpointConfig.from_environment())


def _mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError(f"{field_name} must be a JSON object")
        return dict(parsed)
    raise ValueError(f"{field_name} must be a dict or JSON object string")


def save_checkpoint(
    workflow_id: str,
    state: dict[str, Any],
    *,
    action: str = "",
    step_index: int | None = None,
    rollback_state: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    status: str = "running",
) -> dict[str, Any]:
    checkpoint = _manager().save_checkpoint(
        workflow_id,
        dict(state or {}),
        action=action,
        step_index=step_index,
        rollback_state=rollback_state,
        metadata=metadata,
        status=status,
    )
    return {"ok": True, "checkpoint": checkpoint.to_dict()}


def load_checkpoint(workflow_id: str, checkpoint_id: str = "") -> dict[str, Any]:
    checkpoint = _manager().load_checkpoint(workflow_id, checkpoint_id=checkpoint_id)
    if not checkpoint:
        return {"ok": False, "error": "checkpoint not found", "workflow_id": workflow_id, "checkpoint_id": checkpoint_id}
    return {"ok": True, "checkpoint": checkpoint.to_dict()}


def rollback(workflow_id: str, checkpoint_id: str = "") -> dict[str, Any]:
    return _manager().rollback(workflow_id, checkpoint_id=checkpoint_id)


@function_tool(category="agent")
async def workflow_checkpoint_save_tool(
    workflow_id: str,
    action: str,
    state_json: str,
    rollback_state_json: str = "",
    step_index: int = -1,
    metadata_json: str = "",
) -> dict[str, Any]:
    """
    Persist an agent workflow checkpoint after a completed step.
    Args:
        workflow_id: Stable workflow/task identifier.
        action: Last action completed by the agent.
        state_json: JSON object representing current workflow state.
        rollback_state_json: Optional JSON object representing state before this step.
        step_index: Optional numeric step index. Use -1 for auto-increment.
        metadata_json: Optional JSON object with extra trace metadata.
    """
    if not workflow_checkpoints_enabled():
        return _disabled_payload()
    try:
        return save_checkpoint(
            workflow_id,
            _mapping(state_json, field_name="state_json"),
            action=action,
            step_index=None if int(step_index) < 0 else int(step_index),
            rollback_state=_mapping(rollback_state_json, field_name="rollback_state_json"),
            metadata=_mapping(metadata_json, field_name="metadata_json"),
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "workflow_id": workflow_id}


@function_tool(category="agent")
async def workflow_checkpoint_load_tool(workflow_id: str, checkpoint_id: str = "") -> dict[str, Any]:
    """
    Load the latest or selected checkpoint for a workflow so an agent can resume.
    Args:
        workflow_id: Stable workflow/task identifier.
        checkpoint_id: Optional checkpoint id. Empty loads latest.
    """
    if not workflow_checkpoints_enabled():
        return _disabled_payload()
    return load_checkpoint(workflow_id, checkpoint_id=checkpoint_id)


@function_tool(category="agent")
async def workflow_checkpoint_rollback_tool(workflow_id: str, checkpoint_id: str = "") -> dict[str, Any]:
    """
    Roll a workflow back to the rollback_state stored on the latest or selected checkpoint.
    Args:
        workflow_id: Stable workflow/task identifier.
        checkpoint_id: Optional checkpoint id. Empty rolls back latest.
    """
    if not workflow_checkpoints_enabled():
        return _disabled_payload()
    return rollback(workflow_id, checkpoint_id=checkpoint_id)


@function_tool(category="agent")
async def workflow_checkpoint_status_tool(workflow_id: str = "") -> dict[str, Any]:
    """
    Return checkpoint backend status and latest workflow metadata.
    Args:
        workflow_id: Optional workflow id for detailed status.
    """
    return _manager().status(workflow_id=workflow_id)


__all__ = [
    "load_checkpoint",
    "rollback",
    "save_checkpoint",
    "workflow_checkpoint_load_tool",
    "workflow_checkpoint_rollback_tool",
    "workflow_checkpoint_save_tool",
    "workflow_checkpoint_status_tool",
]
