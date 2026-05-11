def test_meta_orchestrator_routes_to_lowest_load_matching_unit():
    from core.meta_orchestrator import MetaOrchestrator

    meta = MetaOrchestrator()
    slow = meta.register("workflow-orch", "workflow", capabilities=["plan"], load=0.8)
    fast = meta.register("semantic-orch", "semantic", capabilities=["plan"], load=0.2)
    meta.link(slow.unit_id, fast.unit_id, "fallback")
    route = meta.route("plan")

    assert route["selected"]["unit_id"] == fast.unit_id
    assert meta.hierarchy()["links"][0]["relation"] == "fallback"


def test_execution_topology_routes_by_locality_and_heatmap():
    from core.topology import ExecutionTopology

    topology = ExecutionTopology()
    topology.add_node("runtime", "remote", capabilities=["ocr"], heat=0.1)
    local = topology.add_node("runtime", "local", capabilities=["ocr"], heat=0.2)
    route = topology.route("ocr", preferred_locality="local")

    assert route["selected"]["node_id"] == local.node_id
    assert topology.heatmap()["local"] == 0.2


def test_distributed_memory_merges_by_trust_and_version():
    from core.distributed_memory import DistributedMemoryFabric

    fabric = DistributedMemoryFabric()
    old = fabric.replicate("node-a", "project", "routing bug fixed", version=1, trust_score=0.9)
    new = fabric.replicate("node-b", "project", "routing bug fixed", version=2, trust_score=0.8)
    bad = fabric.replicate("node-c", "project", "bad memory", version=3, trust_score=0.2)
    merged = fabric.merge([old, new, bad])

    assert merged.accepted[0].replica_id == new.replica_id
    assert merged.rejected[0].replica_id == bad.replica_id
    assert fabric.retrieve("routing", namespace="project")


def test_cognitive_execution_selects_semantic_strategy_for_complex_goal():
    from core.cognitive_execution import CognitiveExecutionEngine

    plan = CognitiveExecutionEngine().plan(
        "debug distributed workflow and refactor runtime architecture",
        context={"steps": 4, "risky": True},
        available_tools=["search", "inspect", "patch", "test"],
    )

    assert plan.strategy == "semantic_multi_step"
    assert plan.requires_validation is True
    assert plan.tool_chain


def test_trusted_autonomy_blocks_unapproved_shell_and_supports_shutdown():
    from core.trusted_autonomy import TrustedAutonomyFramework

    framework = TrustedAutonomyFramework()
    blocked = framework.decide("shell.execute")
    shutdown = framework.emergency_shutdown("test")

    assert blocked.allowed is False
    assert blocked.requires_human_override is True
    assert shutdown.zone == "SHUTDOWN"


def test_policy_dsl_denies_restricted_permission():
    from core.policy import PolicyEngine

    engine = PolicyEngine.from_lines([
        "id=deny-shell effect=deny permission=shell.execute reason=no-shell",
        "id=allow-standard effect=allow zone=standard",
    ])
    decision = engine.evaluate({"action": "run", "zone": "standard", "permissions": ["shell.execute"]})

    assert decision.allowed is False
    assert "deny-shell" in decision.matched_rules


def test_operating_fabric_publishes_stateful_replayable_events():
    from core.operating_fabric import OperatingFabric

    fabric = OperatingFabric()
    event = fabric.publish("workflow.status", {"state": "running"}, semantic_tags=["workflow"])

    assert fabric.state()["workflow.status"]["event_id"] == event.event_id
    assert fabric.replay(topic="workflow.status")[0]["payload"]["state"] == "running"
    assert fabric.coordinate("workflow")


def test_resilience_engine_selects_failover_and_checkpoint_restore():
    from core.resilience import RecoveryStrategy, ResilienceEngine

    engine = ResilienceEngine()
    failover = engine.decide({"kind": "node_failure", "target": "worker-1"})
    restore = engine.decide({"kind": "memory_inconsistency", "target": "memory"})

    assert failover.strategy == RecoveryStrategy.FAILOVER
    assert restore.strategy == RecoveryStrategy.RESTORE_CHECKPOINT
    assert restore.safe_to_apply is False


def test_resource_economy_allocates_by_priority_and_forecasts():
    from core.resource_economy import ResourceBudget, ResourceEconomyEngine, ResourceWorkload

    engine = ResourceEconomyEngine()
    high = ResourceWorkload("high", 10, ResourceBudget(1, 100, 10, 10, tokens=100))
    low = ResourceWorkload("low", 1, ResourceBudget(10, 1000, 10, 10, tokens=100))
    result = engine.allocate([low, high], ResourceBudget(2, 200, 50, 50, tokens=500))
    forecast = engine.forecast([ResourceBudget(1, 100, 10, 10), ResourceBudget(3, 300, 30, 30)])

    assert result["accepted"] == ["high"]
    assert result["throttled"] == ["low"]
    assert forecast.compute == 2


def test_semantic_workflow_composes_and_refines_failures():
    from core.semantic_workflows import SemanticWorkflowEngine

    engine = SemanticWorkflowEngine()
    workflow = engine.compose("debug", "fix backend", [{"intent": "inspect", "action": "read logs"}])
    refinement = engine.predict_refinement(workflow, failures=["read logs failed"])

    assert workflow.confidence < 0.7
    assert "add validation step before failing action" in refinement["suggestions"]


def test_interface_layer_syncs_context_and_continuity_plan():
    from core.interface_layer import UniversalInterfaceLayer

    layer = UniversalInterfaceLayer()
    desktop = layer.register("desktop", "Mac", capabilities=["visual"])
    mobile = layer.register("mobile", "Phone", capabilities=["voice"])
    layer.sync_context(desktop.endpoint_id, {"project": "shell"})
    plan = layer.continuity_plan(desktop.endpoint_id, mobile.endpoint_id)

    assert layer.compatible("voice")[0].endpoint_id == mobile.endpoint_id
    assert plan["context"]["project"] == "shell"
    assert plan["requires_confirmation"] is True


def test_runtime_virtualization_snapshots_and_clones_universes():
    from core.runtime_virtualization import RuntimeVirtualizationEngine

    engine = RuntimeVirtualizationEngine()
    universe = engine.create_universe("local", "small", context={"task": "ocr"})
    sandbox = engine.snapshot(universe, permissions=["memory.read"])
    clone = engine.clone(universe, context_updates={"task": "debug"})

    assert sandbox.universe_id == universe.universe_id
    assert clone.universe_id != universe.universe_id
    assert clone.context["task"] == "debug"


def test_self_observation_reports_bottlenecks_and_risks():
    from core.self_observation import SelfObservationEngine

    report = SelfObservationEngine().analyze({"failures": 3, "total": 10, "retries": 5, "ambiguous_routes": 2, "avg_latency_ms": 3000})

    assert "latency" in report.bottlenecks
    assert report.reliability_score == 0.7
    assert report.predictive_failures


def test_semantic_analytics_summarizes_ecosystem_health():
    from core.semantic_analytics import SemanticAnalyticsEngine

    analytics = SemanticAnalyticsEngine()
    analytics.record("workflow", "success", 5)
    analytics.record("workflow", "risk_timeout", 1)

    assert analytics.summarize("workflow")["by_label"]["success"] == 5
    assert analytics.ecosystem_health() < 1.0


def test_security_fabric_requires_isolation_for_low_trust_or_plugins():
    from core.security_fabric import SecurityFabric

    decision = SecurityFabric().validate("plugin-a", "filesystem.read", trust_score=0.4, metadata={"plugin": True})
    channel = SecurityFabric().secure_channel_plan("desktop", "node")

    assert decision.allowed is False
    assert decision.isolation_required is True
    assert channel["encryption"] == "required"


def test_human_governance_records_approval_and_dashboard():
    from core.human_governance import HumanGovernanceLayer

    layer = HumanGovernanceLayer()
    request = layer.request_approval("restart runtime", {"runtime": "ocr"}, risk="medium", reversible=True)
    decision = layer.decide(request, approved=True)
    dashboard = layer.governance_dashboard([request])

    assert decision["approved"] is True
    assert decision["rollback_available"] is True
    assert dashboard["emergency_stop_available"] is True


def test_ecosystem_sdk_validates_hooks_and_sandbox_requirements():
    from core.ecosystem_sdk import EcosystemSDK
    from sdk import ExtensionManifest

    manifest = ExtensionManifest.from_dict({
        "name": "runner",
        "version": "1.0.0",
        "shell_api": "6.x",
        "kind": "tool",
        "entrypoint": "runner:main",
        "permissions": ["shell.execute"],
    })
    sdk = EcosystemSDK()
    bad = sdk.validate_manifest(manifest, hooks=[])
    contract = sdk.scaffold_contract("tool")

    assert bad.ok is False
    assert any("sandbox" in reason for reason in bad.reasons)
    assert contract["sandbox_required"] is True


def test_ai_operations_center_snapshot_is_operator_visible():
    from developer_mode import DeveloperInspector

    snapshot = DeveloperInspector().ai_operations_center()

    assert snapshot["operator_visible"] is True
    assert "recent_events" in snapshot
    assert "governance" in snapshot
