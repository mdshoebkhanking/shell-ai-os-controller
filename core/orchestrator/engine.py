from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

from core.events import AIEventType, publish_event
from core.planner import ExecutionPlan, Planner
from core.runtime import RuntimeMonitor


class TaskState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"


@dataclass
class TaskNode:
    node_id: str
    tool_id: str
    args: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    state: TaskState = TaskState.PENDING
    attempts: int = 0
    retry_limit: int = 1
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "tool_id": self.tool_id,
            "args": dict(self.args),
            "dependencies": list(self.dependencies),
            "state": self.state.value,
            "attempts": self.attempts,
            "retry_limit": self.retry_limit,
            "result": dict(self.result),
            "error": self.error,
        }


@dataclass
class TaskGraph:
    task_id: str
    goal: str
    nodes: list[TaskNode]
    state: TaskState = TaskState.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "nodes": [node.to_dict() for node in self.nodes],
        }


Executor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class Orchestrator:
    def __init__(self, planner: Planner | None = None, executor: Executor | None = None):
        self.planner = planner or Planner()
        self.executor = executor or self._default_executor
        self._tasks: dict[str, TaskGraph] = {}
        self._cancelled: set[str] = set()

    async def _default_executor(self, tool_id: str, args: dict[str, Any]) -> dict[str, Any]:
        from shell_tool_gateway import execute_tool

        return await execute_tool(tool_id, args)

    def submit(self, goal: str) -> TaskGraph:
        plan: ExecutionPlan = self.planner.plan(goal)
        nodes = [
            TaskNode(
                node_id=step.step_id,
                tool_id=step.tool_id,
                args=dict(step.args),
                retry_limit=step.retry_limit,
            )
            for step in plan.steps
            if step.tool_id
        ]
        graph = TaskGraph(task_id=uuid.uuid4().hex, goal=goal, nodes=nodes)
        self._tasks[graph.task_id] = graph
        publish_event(AIEventType.TASK_STARTED, graph.to_dict(), source="core.orchestrator")
        return graph

    def cancel(self, task_id: str) -> None:
        self._cancelled.add(task_id)
        graph = self._tasks.get(task_id)
        if graph:
            graph.state = TaskState.CANCELLED
            graph.updated_at = time.time()
            publish_event(AIEventType.TASK_CANCELLED, graph.to_dict(), source="core.orchestrator")

    async def run(self, task_id: str) -> TaskGraph:
        graph = self._tasks[task_id]
        if not graph.nodes:
            graph.state = TaskState.FAILED
            graph.updated_at = time.time()
            publish_event(AIEventType.TASK_FAILED, {**graph.to_dict(), "error": "empty task graph"}, source="core.orchestrator")
            return graph
        policy = RuntimeMonitor().policy()
        graph.state = TaskState.RUNNING
        graph.updated_at = time.time()
        semaphore = asyncio.Semaphore(max(1, policy.max_concurrency))

        for node in graph.nodes:
            if task_id in self._cancelled:
                node.state = TaskState.CANCELLED
                graph.state = TaskState.CANCELLED
                break
            async with semaphore:
                await self._run_node(node)
            if node.state == TaskState.FAILED:
                graph.state = TaskState.FAILED
                graph.updated_at = time.time()
                publish_event(AIEventType.TASK_FAILED, graph.to_dict(), source="core.orchestrator")
                return graph

        if graph.state != TaskState.CANCELLED:
            graph.state = TaskState.COMPLETED
            publish_event(AIEventType.TASK_COMPLETED, graph.to_dict(), source="core.orchestrator")
        graph.updated_at = time.time()
        return graph

    async def _run_node(self, node: TaskNode) -> None:
        while node.attempts <= node.retry_limit:
            node.attempts += 1
            node.state = TaskState.RUNNING
            try:
                result = await self.executor(node.tool_id, node.args)
                node.result = dict(result or {})
                if node.result.get("status") == "success":
                    node.state = TaskState.COMPLETED
                    return
                node.error = str(node.result.get("message") or node.result.get("state") or "tool failed")
            except Exception as exc:
                node.error = str(exc)
            if node.attempts <= node.retry_limit:
                node.state = TaskState.RETRYING
                publish_event(AIEventType.TASK_RETRY, node.to_dict(), source="core.orchestrator")
                await asyncio.sleep(0.1)
        node.state = TaskState.FAILED

    def get(self, task_id: str) -> TaskGraph | None:
        return self._tasks.get(task_id)
