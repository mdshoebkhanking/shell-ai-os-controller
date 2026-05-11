def test_semantic_os_routes_yesterdays_debugging_workspace():
    from core.semantic_os import SemanticOperatingLayer

    layer = SemanticOperatingLayer()
    workspace = layer.create_workspace(
        "backend debugging",
        entities=[
            {"type": "repo", "name": "shell", "tags": ["backend"]},
            {"type": "file", "name": "server.py", "tags": ["backend"]},
            {"type": "browser_tab", "name": "API docs", "tags": ["docs"]},
        ],
        workflow_state="debugging",
        temporal_context="yesterday evening",
    )
    route = layer.route_intent("Continue yesterday backend debugging work")
    plan = layer.reconstruction_plan(workspace)

    assert route["selected_workspace"]["workspace_id"] == workspace.workspace_id
    assert layer.group_files(workspace)["backend"] == ["server.py"]
    assert plan["requires_confirmation"] is True


def test_cognitive_orchestrator_routes_to_low_load_semantic_node():
    from core.cognitive_orchestrator import CognitiveOrchestrator

    orch = CognitiveOrchestrator()
    slow = orch.add_node("agent", "debug", load_score=0.8, metadata={"tags": ["frontend"]})
    fast = orch.add_node("tool", "debug", load_score=0.1, metadata={"tags": ["backend"]})
    orch.connect(slow.node_id, fast.node_id, "fallback")
    route = orch.route("debug", semantic_tags=["backend"])

    assert route["selected"]["node_id"] == fast.node_id
    assert orch.graph()["edges"][0]["relation"] == "fallback"


def test_ecosystem_coordinator_routes_to_trusted_capable_node():
    from core.ecosystem import EcosystemCoordinator

    eco = EcosystemCoordinator()
    eco.register_node("mobile", "phone", capabilities=["camera"], trust_score=0.6)
    workstation = eco.register_node("desktop", "workstation", capabilities=["llm", "memory"], trust_score=0.9)
    eco.sync_context("active_project", "shell", source_node=workstation.node_id)
    route = eco.route("llm", min_trust=0.8)

    assert route.node.node_id == workstation.node_id
    assert eco.shared_context["active_project"]["value"] == "shell"


def test_timeline_records_checkpoints_and_reconstructs_project(tmp_path):
    from core.timeline import TimelineEngine

    timeline = TimelineEngine(tmp_path / "timeline.json")
    timeline.record("shell", "note", "started backend debugging", tags=["backend"])
    checkpoint = timeline.record("shell", "checkpoint", "fixed routing bug", snapshot={"branch": "main"}, tags=["debug"])

    rows = timeline.reconstruct("shell")
    found = timeline.semantic_search("routing debug", project="shell")

    assert rows[-1]["record_id"] == checkpoint.record_id
    assert timeline.last_checkpoint("shell")["snapshot"]["branch"] == "main"
    assert found


def test_collaboration_ai_signals_uncertainty_and_approval():
    from core.collaboration_ai import CollaborationAIEngine

    engine = CollaborationAIEngine()
    proposal = engine.propose("refactor runtime routing", context={"risky": True}, confidence=0.6)
    approval = engine.approval_record(proposal, approved=False)

    assert proposal.requires_approval is True
    assert proposal.uncertainty == "medium"
    assert approval["approved"] is False


def test_governance_blocks_restricted_non_reversible_contract():
    from core.governance import ExecutionContract, GovernanceEngine

    contract = ExecutionContract(
        action="desktop.control",
        actor="assistant",
        permissions=["desktop.control"],
        zone="restricted",
        reversible=False,
    )
    decision = GovernanceEngine().evaluate(contract)

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert "restricted" in " ".join(decision.reasons)


def test_semantic_graph_connects_and_clusters_relationships():
    from core.semantic_graph import SemanticGraph

    graph = SemanticGraph()
    file_node = graph.add_node("file", "server.py", cluster="backend")
    task_node = graph.add_node("task", "fix API timeout", cluster="backend")
    graph.connect(file_node.node_id, task_node.node_id, "implements", score=0.9, temporal=True)

    assert graph.neighbors(file_node.node_id, min_score=0.8)[0]["node"]["label"] == "fix API timeout"
    assert graph.clusters()["backend"] == [file_node.node_id, task_node.node_id]


def test_workflow_intelligence_predicts_next_step():
    from core.workflow_intelligence import WorkflowIntelligenceEngine

    engine = WorkflowIntelligenceEngine()
    engine.record_sequence("debug flow", ["open logs", "search error", "patch code", "run tests"])
    prediction = engine.predict_next(["open logs", "search error"])

    assert prediction["next"] == "patch code"
    assert engine.templates()


def test_runtime_economics_selects_budget_runtime():
    from core.runtime_economics import RuntimeEconomicsEngine, RuntimeOption

    options = [
        RuntimeOption("expensive", cost=0.9, latency_ms=900, energy_score=0.7, token_capacity=10000),
        RuntimeOption("cheap", cost=0.1, latency_ms=700, energy_score=0.2, token_capacity=8000),
    ]
    plan = RuntimeEconomicsEngine().choose(options, max_cost=0.5, max_latency_ms=2000, gpu_available=False, token_need=4000)

    assert plan.option.runtime_id == "cheap"
    assert plan.score > 0


def test_context_sync_rejects_untrusted_and_accepts_newer_encrypted_payload():
    from core.context_sync import ContextSyncEngine

    sync = ContextSyncEngine()
    local = sync.package("desktop", "project", {"name": "old"}, version=1, trust_score=0.9)
    untrusted = sync.package("phone", "project", {"name": "bad"}, version=2, trust_score=0.2)
    trusted = sync.package("laptop", "project", {"name": "new"}, version=3, trust_score=0.9)

    rejected = sync.reconcile(local, untrusted)
    accepted = sync.reconcile(local, trusted)

    assert rejected.accepted.envelope_id == local.envelope_id
    assert accepted.accepted.envelope_id == trusted.envelope_id
    assert accepted.conflict is True


def test_state_engine_snapshots_replay_and_rollback_preview(tmp_path):
    from core.state_engine import OperatingStateEngine

    engine = OperatingStateEngine(tmp_path / "state.json")
    first = engine.snapshot("before", {"tasks": 1})
    second = engine.snapshot("after", {"tasks": 2}, rollback_parent=first.snapshot_id)
    rollback = engine.rollback_plan(first.snapshot_id)

    assert engine.latest().snapshot_id == second.snapshot_id
    assert len(engine.replay()) == 2
    assert rollback["requires_confirmation"] is True


def test_autonomy_limits_block_permission_expansion_and_respect_approval():
    from core.autonomy_limits import AutonomyBoundarySystem

    limits = AutonomyBoundarySystem()
    blocked = limits.classify("self-expand permissions")
    approved = limits.classify("execute approved workflow", approved=True)

    assert blocked.allowed is False
    assert approved.allowed is True


def test_interaction_fabric_selects_passive_or_interrupt_channel():
    from core.interaction_fabric import InteractionFabric, InteractionSignal

    fabric = InteractionFabric()
    passive = fabric.select_channel([InteractionSignal("voice", urgency=0.4, confidence=0.9, user_busy=True)])
    urgent = fabric.select_channel([InteractionSignal("text", urgency=0.9, confidence=0.8, user_busy=False)])

    assert passive["interrupt"] is False
    assert urgent["channel"] == "notification"


def test_dev_ecosystem_reports_dependency_and_ci_state(tmp_path):
    from core.dev_ecosystem import DevEcosystemEngine
    from core.dev_platform import DevPlatformAnalyzer
    from core.filesystem_ai import ProjectIndexer

    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    report = DevEcosystemEngine(DevPlatformAnalyzer(ProjectIndexer(tmp_path / "index.json"))).inspect(tmp_path)

    assert "requirements.txt" in report.dependency_files
    assert "no CI workflow detected" in report.diagnostics


def test_analytics_records_heatmap_and_bottlenecks():
    from core.analytics import AnalyticsEngine

    analytics = AnalyticsEngine()
    analytics.record("workflow", "debug", 3)
    analytics.record("workflow", "debug", 2)
    analytics.record("runtime", "latency", 900)

    assert analytics.heatmap("workflow")["debug"] == 5
    assert analytics.bottlenecks(threshold=800)[0]["name"] == "latency"


def test_transparency_engine_creates_confidence_narrative():
    from core.transparency import TransparencyEngine

    narrative = TransparencyEngine().explain(
        "Tool selection",
        decision={"summary": "selected local OCR", "confidence": 0.8, "reasons": ["offline mode"]},
        alternatives=[{"tool": "cloud OCR"}],
    )

    assert narrative.uncertainty == "low"
    assert "alternatives considered" in narrative.reasons[-1]


def test_self_optimization_proposals_are_policy_checked():
    from core.self_optimization import SelfOptimizationEngine

    safe = SelfOptimizationEngine().propose("cache", "increase_hot_cache_ttl", reversible=True)
    unsafe = SelfOptimizationEngine().propose("shell", "shell.execute", reversible=False)

    assert safe.allowed_by_policy is True
    assert unsafe.allowed_by_policy is False


def test_experience_platform_exposes_operator_only_layout():
    from developer_mode import DeveloperInspector

    layout = DeveloperInspector().experience_layout()

    assert layout["requires_operator_access"] is True
    assert layout["panels"][0]["panel_id"] in {"execution_topology", "trust_safety"}

