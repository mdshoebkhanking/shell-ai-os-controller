def test_distributed_os_places_workload_by_trust_load_and_locality():
    from core.distributed_os import DistributedOSFabric

    fabric = DistributedOSFabric()
    remote = fabric.register_node("cloud", "remote-gpu", capabilities=["vision"], locality="remote", trust_score=0.9, load=0.1)
    local = fabric.register_node("desktop", "mac", capabilities=["vision"], locality="local", trust_score=0.8, load=0.2)
    placement = fabric.place_workload("w1", "vision", preferred_locality="local")
    continuity = fabric.continuity_plan(local.node_id, remote.node_id, "w1")

    assert placement.node.node_id == local.node_id
    assert continuity["requires_confirmation"] is True
    assert fabric.negotiate_capability("vision")


def test_federated_cluster_schedules_and_migrates_workloads():
    from core.federation import FederatedClusterEngine, FederatedTask

    cluster = FederatedClusterEngine()
    source = cluster.register_worker("cpu", "local", capabilities=["ocr"], capacity=1, load=0.9)
    target = cluster.register_worker("gpu", "edge", capabilities=["ocr"], capacity=2, load=0.1)
    decision = cluster.schedule(FederatedTask("task-1", "ocr", priority=10, locality_hint="edge"))
    migration = cluster.migrate("task-1", source.worker_id, "ocr")

    assert decision["worker"]["worker_id"] == target.worker_id
    assert migration["to"] == target.worker_id
    assert migration["requires_checkpoint"] is True


def test_semantic_network_routes_over_trusted_encrypted_channel():
    from core.semantic_network import SemanticNetworkLayer

    network = SemanticNetworkLayer()
    channel = network.open_channel("desktop", "edge", "workflow sync", dependencies=["memory"], trust_score=0.9)
    route = network.route("workflow", dependency="memory")
    event = network.stream_event(channel.channel_id, {"state": "running"})

    assert route["channel"]["channel_id"] == channel.channel_id
    assert event["encrypted"] is True


def test_distributed_cognition_partitions_and_resolves_conflict():
    from core.distributed_cognition import DistributedCognitionFabric

    fabric = DistributedCognitionFabric()
    shards = fabric.partition("debug workflow", ["node-a", "node-b"])
    coordination = fabric.coordinate(shards, [{"result": "a", "confidence": 0.5}, {"result": "b", "confidence": 0.8}])
    resolution = fabric.resolve_conflict([{"result": "a", "confidence": 0.5}, {"result": "b", "confidence": 0.8}])

    assert len(shards) == 2
    assert coordination["conflicts"] is True
    assert resolution["resolution"]["result"] == "b"


def test_node_runtime_exposes_capabilities_health_and_trust():
    from core.node_runtime import AINodeRuntime, NodeRuntimeState

    runtime = AINodeRuntime()
    node = runtime.register(capabilities=["llm"], trust_score=0.8, models=["small"], memory_permissions=["semantic"])
    runtime.heartbeat(node.node_id, state=NodeRuntimeState.READY, capacity={"cpu": 0.5})

    assert runtime.discover("llm")[0].node_id == node.node_id
    assert runtime.negotiate_trust(node.node_id, required=0.7)["ok"] is True


def test_service_mesh_routes_and_fails_over_semantic_services():
    from core.service_mesh import ServiceMesh

    mesh = ServiceMesh()
    slow = mesh.register("memory-a", "memory", capabilities=["retrieve"], trust_score=0.9, latency_ms=100)
    fast = mesh.register("memory-b", "memory", capabilities=["retrieve"], trust_score=0.9, latency_ms=20)
    route = mesh.route("retrieve")
    failover = mesh.failover(fast.service_id, "retrieve")

    assert route["service"]["service_id"] == fast.service_id
    assert failover["service"]["service_id"] == slow.service_id
    assert mesh.trace()


def test_global_context_reconciles_encrypted_newer_context():
    from core.global_context import GlobalContextEngine

    engine = GlobalContextEngine()
    local = engine.update("workflow", {"state": "old"}, version=1)
    remote = engine.update("workflow", {"state": "new"}, version=2)
    result = engine.reconcile(local, remote)
    checkpoint = engine.checkpoint("wf-1")

    assert result["accepted"]["payload"]["state"] == "new"
    assert checkpoint["encrypted"] is True


def test_memory_governance_enforces_private_boundaries():
    from core.memory_governance import MemoryGovernanceEngine, MemoryPolicy

    policy = MemoryPolicy(owner="user", namespace="project", allowed_nodes=["node-a"], encrypted=True, private=True, ttl_s=60)
    engine = MemoryGovernanceEngine()
    denied = engine.evaluate(policy, node_id="node-b", operation="read")
    allowed = engine.evaluate(policy, node_id="node-a", operation="read")

    assert denied.allowed is False
    assert allowed.allowed is True
    assert engine.lifecycle_action(policy)["action"] == "expire"


def test_topology_intelligence_recommends_migration_for_hot_nodes():
    from core.topology_intelligence import TopologyIntelligenceEngine

    recs = TopologyIntelligenceEngine().analyze({"nodes": [{"node_id": "n1", "heat": 0.9, "healthy": True}]})

    assert recs[0].action == "migrate_workload"
    assert recs[0].requires_confirmation is True


def test_cloud_edge_orchestrator_prefers_local_offline_and_plans_replication():
    from core.cloud_edge import CloudEdgeOrchestrator, ExecutionTarget

    targets = [
        ExecutionTarget("local", "local", ["llm"], cost_score=0.1, latency_ms=30, online=True),
        ExecutionTarget("cloud", "cloud", ["llm"], cost_score=0.2, latency_ms=10, online=True),
    ]
    orch = CloudEdgeOrchestrator()
    choice = orch.choose(targets, "llm", offline=True)
    replication = orch.replication_plan("llm", targets)

    assert choice["target"]["target_id"] == "local"
    assert replication["requires_confirmation"] is True


def test_distributed_security_attests_runtime_and_scores_anomalies():
    from core.distributed_security import DistributedSecurityEngine, RuntimeAttestation

    engine = DistributedSecurityEngine()
    valid = engine.attest(RuntimeAttestation("node", "runtime", signed=True, sandboxed=True, trust_score=0.9))
    invalid_channel = engine.validate_channel("a", "b", encrypted=False, trust_score=0.9)
    score = engine.anomaly_score({"failures": 2, "denied": 1, "total": 10})

    assert valid["ok"] is True
    assert invalid_channel["ok"] is False
    assert score > 0


def test_ecosystem_registry_indexes_capabilities_and_compatibility():
    from core.ecosystem_registry import EcosystemRegistry

    registry = EcosystemRegistry()
    item = registry.register("runtime", "local-llm", capabilities=["llm"], trust_score=0.9, compatibility=["7.x"])

    assert registry.find_by_capability("llm", min_trust=0.8)[0].item_id == item.item_id
    assert registry.compatibility_report(item.item_id, "7.x")["compatible"] is True


def test_resource_orchestration_schedules_priority_and_predicts_usage():
    from core.resource_orchestration import ResourceOrchestrationEngine, ResourceRequest

    engine = ResourceOrchestrationEngine()
    high = ResourceRequest("high", cpu=1, memory_mb=100, tokens=50, priority=10)
    low = ResourceRequest("low", cpu=10, memory_mb=1000, tokens=50, priority=1)
    result = engine.schedule([low, high], {"cpu": 2, "gpu": 0, "memory_mb": 200, "tokens": 100, "bandwidth_mb": 0, "cloud_cost": 0})
    prediction = engine.predict([high, low])

    assert result["accepted"] == ["high"]
    assert result["throttled"] == ["low"]
    assert prediction["cpu"] == 11


def test_distributed_observability_tracks_trace_and_node_health():
    from core.distributed_observability import DistributedObservabilityPlatform

    obs = DistributedObservabilityPlatform()
    trace = obs.record_trace("node-a", "plan", {"ok": True}, trace_id="trace-1")
    obs.record_telemetry("node-a", {"error_rate": 0.1, "cpu": 0.7}, semantic_tags=["planner"])

    assert obs.timeline("trace-1")[0]["span"] == trace.span
    assert obs.node_health()["node-a"] == 0.9


def test_disaster_recovery_checkpoints_and_rebuilds_topology():
    from core.disaster_recovery import DisasterRecoveryEngine

    dr = DisasterRecoveryEngine()
    checkpoint = dr.checkpoint("cluster", {"nodes": 3})
    plan = dr.recover({"kind": "cluster_crash"})
    replay = dr.replay_state(checkpoint.checkpoint_id)

    assert plan["action"] == "rebuild_topology"
    assert replay["checkpoint"]["checkpoint_id"] == checkpoint.checkpoint_id
    assert replay["requires_confirmation"] is True


def test_distributed_governance_requires_full_approval_chain():
    from core.distributed_governance import DistributedGovernanceEngine

    gov = DistributedGovernanceEngine()
    approval = gov.request_chain("migrate workflow", ["owner", "admin"], ["node-a"])
    partial = gov.approve(approval, "owner")
    complete = gov.approve(partial, "admin")

    assert gov.is_complete(partial) is False
    assert gov.is_complete(complete) is True
    assert gov.dashboard([complete])["human_override"] is True


def test_distributed_dev_platform_validates_interfaces_and_governance():
    from core.distributed_dev_platform import DistributedDevPlatform, DistributedModuleSpec

    platform = DistributedDevPlatform()
    spec = DistributedModuleSpec("pack", "orchestration_pack", interfaces=["route", "recover"], governance_hooks=["approval", "audit"])
    result = platform.validate(spec)

    assert result["ok"] is True
    assert "route" in platform.api_contract("orchestration_pack")["interfaces"]


def test_distributed_command_center_exposes_operator_visible_snapshot():
    from developer_mode import DeveloperInspector

    snapshot = DeveloperInspector().distributed_command_center()

    assert snapshot["operator_visible"] is True
    assert "cluster_topology" in snapshot
    assert "recent_events" in snapshot

