import asyncio


def test_distributed_router_assigns_high_priority_task_to_healthy_node(tmp_path):
    from core.distributed import ExecutionRouter, NodeRegistry, PersistentTaskQueue, TaskQueueState

    registry = NodeRegistry(tmp_path / "nodes.json", stale_after_s=60)
    queue = PersistentTaskQueue(tmp_path / "queue.json")
    node = registry.register(
        name="mac-local",
        endpoint="local://shell",
        capabilities=["analyze_code"],
        max_concurrency=2,
    )
    task = queue.enqueue("shell_code:analyze", {"path": "."}, required_capability="analyze_code", priority=9)

    decision = ExecutionRouter(registry, queue).route_next()

    assert decision is not None
    assert decision.node.node_id == node.node_id
    assert decision.task.task_id == task.task_id
    assert queue.get(task.task_id).state == TaskQueueState.ASSIGNED


def test_runtime_manager_prefers_local_when_offline_and_cloud_for_coding():
    from core.runtime import RuntimeSnapshot
    from core.runtime_manager import RuntimeKind, RuntimeManager

    manager = RuntimeManager()
    snapshot = RuntimeSnapshot(ts=1, cpu_percent=5, ram_percent=20, disk_percent=10)

    offline = manager.select(RuntimeKind.LLM, offline=True, snapshot=snapshot)
    coding = manager.select(RuntimeKind.LLM, task_type="coding", offline=False, snapshot=snapshot)

    assert offline.runtime_id == "local-light-llm"
    assert coding.runtime_id == "cloud-reasoning"


def test_collaboration_team_bounds_agents_locks_and_validator_consensus():
    from core.collaboration import AgentRole, CollaborationTeam

    team = CollaborationTeam(max_agents=2)
    planner = team.spawn(AgentRole.PLANNER, ["plan"])
    validator = team.spawn(AgentRole.VALIDATOR, ["validate"])

    assert team.acquire_lock(planner.agent_id, "workflow:1") is True
    assert team.acquire_lock(validator.agent_id, "workflow:1") is False
    assert team.assignable_agents("validate") == [validator]

    decision = team.resolve_conflict([
        {"role": "executor", "decision": "patch"},
        {"role": "validator", "decision": "reject"},
    ])

    assert decision["decision"] == "reject"


def test_skill_graph_validates_dependencies_and_scores_chain():
    from core.skills import SkillGraph, SkillNode

    graph = SkillGraph()
    graph.add(SkillNode("read_file", "1.0.0", "Read file", reliability_score=0.9))
    graph.add(SkillNode("analyze_code", "1.0.0", "Analyze code", dependencies=["read_file"], reliability_score=0.8))

    result = graph.validate("analyze_code")
    chain = graph.chain("analyze_code")

    assert result.ok is True
    assert [node.skill_id for node in chain] == ["read_file", "analyze_code"]
    assert graph.score("analyze_code") > 0.7


def test_recovery_engine_records_incident_and_suggests_bounded_fallback(tmp_path):
    from core.recovery import RecoveryEngine

    engine = RecoveryEngine(tmp_path / "incidents.json")
    incident = engine.record_incident("dead_api", "openai", "provider timeout")
    actions = engine.diagnose(incident)

    assert engine.incidents()[0]["kind"] == "dead_api"
    assert actions[0].action == "fallback_provider"
    assert actions[0].allowed is True


def test_filesystem_indexer_tags_project_files_and_searches(tmp_path):
    from core.filesystem_ai import ProjectIndexer

    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Shell docs\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "test_app.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    index = ProjectIndexer(tmp_path / "index.json").build(tmp_path)
    results = ProjectIndexer().search(index, "dependency code test")

    assert index.summary["file_count"] == 4
    assert any("dependency-config" in row["tags"] for row in results)
    assert any("test" in row["tags"] for row in results)


def test_execution_policy_is_budget_and_offline_aware():
    from core.execution_policy import ExecutionBudget, ExecutionPolicyEngine, ProviderCandidate

    engine = ExecutionPolicyEngine()
    providers = [
        ProviderCandidate("local-small", True, 0.1, 0.6, 0.5, 2048),
        ProviderCandidate("cloud-large", False, 0.8, 0.5, 0.9, 32000),
    ]

    selected = engine.choose_provider(providers, budget=ExecutionBudget(offline=True), prompt="short task")

    assert selected.provider_id == "local-small"
    assert engine.compression_needed("x" * 200, budget=ExecutionBudget(max_tokens=10)) is True


def test_memory_fabric_retrieves_ranked_layers_and_deduplicates(tmp_path):
    from core.memory import LocalMemoryStore, MemoryFabric, MemoryQuery

    store = LocalMemoryStore(tmp_path / "memory.json")
    store.remember_semantic("project uses PyQt and MCP")
    store.remember_failure("MCP provider timeout")
    store.remember("conversation", "project MCP discussion")

    fabric = MemoryFabric(store)
    rows = fabric.retrieve(MemoryQuery("MCP project", ["active", "semantic", "incident"], limit=5))

    assert {row["layer"] for row in rows} >= {"active", "semantic"}
    assert fabric.resolve_conflicts(rows)


def test_event_stream_reconstructs_trace_and_persists_current(tmp_path):
    from core.events import AIEventType, publish_event
    from core.streaming import EventStream

    publish_event(AIEventType.TASK_STARTED, {"task": "phase3"}, source="test", trace_id="trace-phase3")
    stream = EventStream(tmp_path / "events.jsonl")

    rows = stream.reconstruct(trace_id="trace-phase3")

    assert rows
    assert rows[-1]["payload"]["task"] == "phase3"
    assert stream.persist_current(limit=5) >= 1
    assert (tmp_path / "events.jsonl").exists()


def test_security_model_classifies_critical_and_restricted_actions():
    from core.security import SecurityClass, SecurityModel

    model = SecurityModel()

    restricted = model.classify("shell.execute", {"command": "ls"})
    critical = model.classify("self-modify hotpatch core")

    assert restricted.security_class == SecurityClass.RESTRICTED
    assert restricted.allowed is False
    assert critical.security_class == SecurityClass.CRITICAL
    assert critical.requires_secure_mode is True


def test_trust_engine_uses_tool_reputation_and_plugin_permissions(monkeypatch, tmp_path):
    from core.tools.reputation import ToolReputationStore
    from core.trust import TrustEngine

    reputation_path = tmp_path / "tool_reputation.json"
    monkeypatch.setenv("SHELL_TOOL_REPUTATION_PATH", str(reputation_path))
    store = ToolReputationStore()
    store.record("stable_tool", ok=True, latency_ms=100)
    store.record("stable_tool", ok=True, latency_ms=120)

    engine = TrustEngine()
    tool_score = engine.score_tool("stable_tool")
    plugin_score = engine.score_plugin({"name": "writer", "permissions": ["filesystem.write"]}, verified=True)

    assert tool_score.score > 0.8
    assert plugin_score.score < 0.8


def test_user_model_is_editable_exportable_and_resettable(tmp_path):
    from core.user_model import UserModel

    model = UserModel(tmp_path / "user_model.json")
    model.set_preference("voice.auto_play", False)
    model.record_tool_use("analyze_code")

    exported = model.export()
    model.reset()

    assert exported["preferences"]["voice.auto_play"] is False
    assert exported["tool_counts"]["analyze_code"] == 1
    assert model.export()["preferences"] == {}


def test_workflow_engine_supports_conditions_and_retries():
    from core.workflows import WorkflowEngine

    calls = {"n": 0}

    def flaky(_params):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"status": "error", "error": "transient"}
        return {"status": "success", "value": 42}

    engine = WorkflowEngine({"flaky": flaky})
    workflow = engine.create(
        "demo",
        "manual",
        [
            {"action": "flaky", "condition": "mode == coding", "retry_limit": 1},
            {"action": "flaky", "condition": "missing_flag"},
        ],
    )

    result = engine.run(workflow, {"mode": "coding"})

    assert result["status"] == "success"
    assert calls["n"] == 2
    assert result["results"][-1]["status"] == "skipped"


def test_marketplace_verifies_digest_and_blocks_risky_plugins(tmp_path):
    from marketplace import MarketplaceRegistry
    from sdk import ExtensionManifest

    registry = MarketplaceRegistry(tmp_path / "marketplace.json")
    safe = ExtensionManifest.from_dict({
        "name": "reader",
        "version": "1.0.0",
        "shell_api": "3.x",
        "kind": "tool",
        "entrypoint": "reader:main",
        "permissions": ["filesystem.read"],
    })
    risky = ExtensionManifest.from_dict({
        "name": "runner",
        "version": "1.0.0",
        "shell_api": "3.x",
        "kind": "tool",
        "entrypoint": "runner:main",
        "permissions": ["shell.execute"],
    })

    verification = registry.verify_manifest(safe)
    record = registry.install(safe, verification)
    risky_result = registry.verify_manifest(risky)

    assert verification.ok is True
    assert record.name == "reader"
    assert risky_result.ok is False


def test_performance_engine_batches_and_limits_async_execution():
    from core.performance import AsyncExecutionPool, BatchQueue

    batch = BatchQueue(max_batch_size=2)

    async def double(value):
        return value * 2

    assert batch.add(1) == []
    assert batch.add(2) == [1, 2]
    assert asyncio.run(AsyncExecutionPool(concurrency=1).map(double, [1, 2, 3])) == [2, 4, 6]
