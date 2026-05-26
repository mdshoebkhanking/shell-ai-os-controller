import asyncio
import os


def test_context_engine_prioritizes_and_expires(tmp_path):
    from core.context import ContextEngine, ContextLayer

    engine = ContextEngine(tmp_path / "context.json")
    engine.update(ContextLayer.SESSION_CONTEXT, "recent_command", "count words", priority=0.4)
    engine.update(ContextLayer.ACTIVE_CONTEXT, "active_project", "shell", priority=0.9)
    engine.update(ContextLayer.ACTIVE_CONTEXT, "temp", "gone", priority=1.0, ttl_s=-1)

    assert engine.expire() == 1
    snapshot = engine.snapshot()
    assert snapshot.items[0].key == "active_project"
    assert "ACTIVE_CONTEXT:active_project" in snapshot.summary


def test_workspace_detector_identifies_python_project(tmp_path):
    from core.workspace import WorkspaceDetector, WorkspaceMode

    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")

    state = WorkspaceDetector().detect(tmp_path)

    assert state.mode == WorkspaceMode.CODING
    assert "python" in state.languages
    assert state.signals["has_requirements"] is True


def test_tool_reputation_tracks_success_failure_and_adjustment(tmp_path):
    from core.tools.reputation import ToolReputationStore

    store = ToolReputationStore(tmp_path / "rep.json")
    store.record("shell_calculator:calculate_tool", ok=True, latency_ms=100)
    store.record("shell_calculator:calculate_tool", ok=False, failure_category="exception", error="boom")

    rep = store.get("shell_calculator:calculate_tool")

    assert rep.total == 2
    assert rep.successes == 1
    assert rep.failures == 1
    assert rep.failure_categories["exception"] == 1
    assert store.routing_adjustment("shell_calculator:calculate_tool") <= 0.5


def test_predictive_engine_is_contextual_not_intrusive():
    from core.predictive import PredictiveEngine

    suggestions = PredictiveEngine().suggest(
        context={
            "mode": "coding",
            "languages": ["python"],
            "dirty_git": True,
            "signals": {"has_requirements": True},
        },
        health={"platform": {"os": "mac"}, "summary": {"dependencies_missing": ["ffmpeg"]}},
    )

    titles = [s.title for s in suggestions]
    assert "Python environment detected" in titles
    assert "Git changes detected" in titles
    assert len(suggestions) <= 5


def test_sandbox_blocks_path_escape_and_unapproved_command(tmp_path):
    from sandbox import SandboxPolicy, TemporaryWorkspace

    with TemporaryWorkspace(SandboxPolicy(allowed_commands={"python3"}), root=tmp_path) as box:
        try:
            box.resolve("../escape.txt")
            escaped = False
        except PermissionError:
            escaped = True
        result = box.run(["rm", "-rf", "."])

    assert escaped is True
    assert result.status == "blocked"


def test_sandbox_snapshot_and_rollback(tmp_path):
    from sandbox import TemporaryWorkspace

    with TemporaryWorkspace(root=tmp_path) as box:
        box.write_text("a.txt", "one")
        box.snapshot()
        box.write_text("a.txt", "two")
        box.rollback()
        assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "one"


def test_orchestrator_runs_retryable_task():
    from core.orchestrator import Orchestrator, TaskState

    calls = {"n": 0}

    async def executor(tool_id, args):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"status": "error", "message": "transient"}
        return {"status": "success", "tool": tool_id, "result": args}

    orch = Orchestrator(executor=executor)
    graph = orch.submit("what is 2 + 3")
    graph.nodes[0].retry_limit = 1
    result = asyncio.run(orch.run(graph.task_id))

    assert result.state == TaskState.COMPLETED
    assert calls["n"] == 2


def test_memory_namespaces_and_compaction(tmp_path):
    from core.memory import LocalMemoryStore

    store = LocalMemoryStore(tmp_path / "memory.json")
    store.remember_episode("opened python repo")
    store.remember_procedure("runs tests before final")
    store.remember_failure("sounddevice missing")

    assert store.search("python", namespace="episodic")
    assert "failure" in store.summarize()
    assert store.compact(namespace="episodic", keep=0) == 1


def test_event_bus_replay_filters_domain_events():
    from core.events import AIEventType, publish_event, replay_events

    event = publish_event(AIEventType.MEMORY_UPDATED, {"x": 1}, source="test")

    rows = replay_events(event_type=AIEventType.MEMORY_UPDATED, since_ts=event.ts - 0.001)

    assert rows
    assert rows[-1]["event_type"] == "ai.MEMORY_UPDATED"


def test_safety_policy_classifies_shell_execution_as_dangerous(monkeypatch, tmp_path):
    from core.safety import ActionClass, SafetyPolicy

    monkeypatch.delenv("SHELL_ALLOW_TERMINAL_EXEC", raising=False)
    policy = SafetyPolicy(tmp_path / "audit.log")
    decision = policy.classify("run shell command")
    policy.audit("run shell command", decision)

    assert decision.action_class == ActionClass.DANGEROUS
    assert decision.allowed is True
    assert (tmp_path / "audit.log").exists()


def test_sdk_manifest_validation():
    from sdk import ExtensionManifest

    manifest = ExtensionManifest.from_dict({
        "name": "demo-tool",
        "version": "1.0.0",
        "shell_api": "2.x",
        "kind": "tool",
        "entrypoint": "demo:main",
        "permissions": ["filesystem.read"],
    })

    assert manifest.kind == "tool"
    assert manifest.permissions == ["filesystem.read"]


def test_runtime_policy_reduces_concurrency_under_pressure():
    from core.runtime import RuntimeMonitor, RuntimeSnapshot

    snap = RuntimeSnapshot(ts=1, cpu_percent=91, ram_percent=88, disk_percent=50, battery_percent=20, power_plugged=False)
    policy = RuntimeMonitor().policy(snap)

    assert policy.max_concurrency == 1
    assert policy.allow_heavy_tasks is False


def test_gateway_records_reputation_for_workspace_code_write(monkeypatch, tmp_path):
    from core.tools.reputation import ToolReputationStore
    from shell_tool_gateway import execute_tool_sync

    reputation_path = tmp_path / "reputation.json"
    monkeypatch.setenv("SHELL_TOOL_REPUTATION_PATH", str(reputation_path))
    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    monkeypatch.chdir(tmp_path)

    result = execute_tool_sync("shell_code_engine:write_code_tool", {"filename": "x.py", "content": "print(1)"})
    rep = ToolReputationStore(reputation_path).get("shell_code_engine:write_code_tool")

    assert result["status"] == "success"
    assert (tmp_path / "shell_workspace" / "x.py").exists()
    assert rep.successes == 1
