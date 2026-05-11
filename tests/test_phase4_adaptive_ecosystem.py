def test_multimodal_context_links_screenshot_ocr_and_terminal():
    from core.multimodal import ModalType, MultimodalContextEngine

    engine = MultimodalContextEngine()
    shot = engine.add_observation(ModalType.SCREENSHOT, "voice page error banner", metadata={"window": "Shell"})
    ocr = engine.add_observation(ModalType.OCR, "ERROR sounddevice not installed", confidence=0.8)
    term = engine.add_observation(ModalType.TERMINAL, "Traceback: import sounddevice failed")
    engine.link(shot.observation_id, ocr.observation_id, "ocr_extract", confidence=0.9)
    model = engine.build()

    assert "vision" in model.route_hints
    assert "debug" in model.route_hints
    assert "terminal" in model.route_hints
    assert term.content in model.summary


def test_vision_layer_parses_ui_elements_and_only_previews_navigation():
    from core.vision import UIElementType, VisionOperatingLayer

    layer = VisionOperatingLayer()
    state = layer.parse(
        screenshot_id="screen-1",
        ocr_text="ERROR\nStart Voice\nSettings menu",
        elements=[{"label": "Visual On", "type": "button", "bounds": [1, 2, 3, 4]}],
        active_window="Shell",
    )
    preview = layer.navigation_preview(state, "click Start Voice")

    assert any(element.element_type == UIElementType.BUTTON for element in state.elements)
    assert preview["status"] == "preview"
    assert preview["requires_confirmation"] is True


def test_long_task_engine_checkpoints_and_resumes(tmp_path):
    from core.long_tasks import LongTaskEngine, LongTaskState

    engine = LongTaskEngine(tmp_path / "long_tasks.json")
    task = engine.create_task("index large repo", resume_after=0)
    checkpointed = engine.checkpoint(task.task_id, "scanned sources", {"files": 12}, progress=0.4)
    paused = engine.pause(task.task_id)
    due = engine.list_due()
    resumed = engine.resume(task.task_id)

    assert checkpointed.progress == 0.4
    assert len(checkpointed.checkpoints) == 1
    assert paused.state == LongTaskState.PAUSED
    assert due
    assert resumed.state == LongTaskState.RUNNING


def test_adaptive_reasoning_selects_deep_for_uncertain_complex_work():
    from core.reasoning import AdaptiveReasoningEngine, ReasoningDepth

    profile = AdaptiveReasoningEngine().select_profile(
        "debug intermittent distributed workflow failure and refactor architecture",
        {"steps": 5, "missing_context": True, "risky": True},
    )

    assert profile.depth == ReasoningDepth.DEEP
    assert profile.validation_required is True
    assert profile.max_tool_calls >= 10


def test_environmental_intelligence_pauses_cloud_on_bad_conditions():
    from core.environment import EnvironmentSnapshot, EnvironmentalIntelligence, NetworkQuality

    snapshot = EnvironmentSnapshot(
        network_quality=NetworkQuality.UNSTABLE,
        battery_percent=15,
        power_plugged=False,
        thermal_state="hot",
    )
    policy = EnvironmentalIntelligence().assess(snapshot)

    assert policy.pause_cloud_workflows is True
    assert policy.reduce_heavy_tasks is True
    assert policy.max_concurrency == 1


def test_supervisor_blocks_runaway_execution():
    from core.supervisor import SupervisionState, Supervisor

    decision = Supervisor().evaluate(SupervisionState(recursion_depth=4, loop_iterations=120))

    assert decision.allowed is False
    assert decision.action == "stop_workflow"


def test_interaction_engine_confirms_restricted_and_previews_visual():
    from core.interaction import InteractionEngine, InteractionMode
    from core.security import SecurityClass

    engine = InteractionEngine()
    restricted = engine.decide(mode=InteractionMode.COMMAND, security_class=SecurityClass.RESTRICTED, confidence=0.9)
    visual = engine.decide(mode=InteractionMode.VISUAL, security_class=SecurityClass.SAFE, confidence=0.9)

    assert restricted.action == "confirm"
    assert restricted.requires_confirmation is True
    assert visual.action == "preview"


def test_realtime_coordinator_streams_incremental_updates():
    from core.realtime import RealtimeCoordinator

    coordinator = RealtimeCoordinator()
    session = coordinator.open_session("live coding", ["user", "assistant"])
    update = coordinator.publish(session.session_id, "progress", {"message": "indexed 10 files"})

    assert coordinator.latest(session.session_id)[-1].update_id == update.update_id
    assert coordinator.close(session.session_id).open is False


def test_knowledge_fabric_links_cross_source_items():
    from core.knowledge import KnowledgeFabric, KnowledgeSourceType

    fabric = KnowledgeFabric()
    docs = fabric.add_item(KnowledgeSourceType.DOCS, "Voice setup", "sounddevice is required")
    log = fabric.add_item(KnowledgeSourceType.LOG, "Voice error", "sounddevice import failed")
    fabric.link(docs.item_id, log.item_id, "explains", confidence=0.9)

    rows = fabric.retrieve("sounddevice")

    assert fabric.summarize()["edges"] == 1
    assert rows[0]["edges"]


def test_workspace_orchestrator_returns_dry_run_restore_plan():
    from core.workspace_orchestrator import WorkspaceOrchestrator

    orchestrator = WorkspaceOrchestrator()
    plan = orchestrator.plan_restore("coding", project_root="/tmp/project", recent_files=["app.py"], docs=["https://docs.local"])
    dry_run = orchestrator.dry_run_restore(plan)

    assert plan.requires_confirmation is True
    assert any(action["type"] == "terminal_suggestion" for action in dry_run["actions"])


def test_execution_graph_tracks_dependencies_and_failures():
    from core.execution_graph import ExecutionGraph

    graph = ExecutionGraph()
    first = graph.add_node("plan", "planner")
    second = graph.add_node("execute", "tool")
    graph.add_edge(first.node_id, second.node_id)
    graph.mark(second.node_id, "failed", {"error": "timeout"})

    assert graph.failures()[0]["metadata"]["error"] == "timeout"
    assert [row["label"] for row in graph.replay_order()] == ["plan", "execute"]


def test_optimization_engine_recommends_safe_resource_actions():
    from core.optimization import OptimizationEngine

    recs = OptimizationEngine().recommend({"startup_ms": 4500, "ram_percent": 88, "plugin_count": 80, "cache_hit_rate": 0.2})
    targets = {rec.target for rec in recs}

    assert {"startup", "memory", "plugins", "cache"} <= targets
    assert all(rec.safe_to_apply for rec in recs)


def test_trusted_automation_layer_produces_audited_dry_run(tmp_path):
    from core.automation import TrustedAutomationLayer

    layer = TrustedAutomationLayer(tmp_path / "automation.jsonl")
    plan = layer.preview("open settings", [{"kind": "desktop.control", "target": "settings", "reversible": True}])
    dry_run = layer.dry_run(plan)

    assert plan.requires_confirmation is True
    assert plan.risk == "ELEVATED"
    assert dry_run["status"] == "dry_run"
    assert (tmp_path / "automation.jsonl").exists()


def test_ai_shell_plans_project_clean_as_dry_run_only():
    from core.ai_shell import AIShellEngine

    plan = AIShellEngine().plan("clean this project", project_summary={"languages": ["python"]})

    assert plan.dry_run is True
    assert plan.requires_confirmation is True
    assert any("__pycache__" in command for command in plan.commands)


def test_dev_platform_analyzer_understands_python_project(tmp_path):
    from core.dev_platform import DevPlatformAnalyzer
    from core.filesystem_ai import ProjectIndexer

    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "test_app.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    analysis = DevPlatformAnalyzer(ProjectIndexer(tmp_path / "index.json")).analyze(tmp_path)

    assert "python" in analysis.languages
    assert "requirements.txt" in analysis.build_files
    assert "test_app.py" in analysis.test_files


def test_personalization_engine_is_transparent_and_exportable(tmp_path):
    from core.personalization import PersonalizationEngine
    from core.user_model import UserModel

    model = UserModel(tmp_path / "user.json")
    model.record_tool_use("analyze_code")
    engine = PersonalizationEngine(model)
    engine.set_preference("voice.auto_play", False)
    suggestions = engine.suggest()

    assert any(s.key == "favorite_tool" for s in suggestions)
    assert any(s.value == "text_first" for s in suggestions)


def test_high_trust_safety_framework_requires_approval_for_risky_actions():
    from core.safety import HighTrustSafetyFramework
    from core.security import SecurityClass

    checkpoint = HighTrustSafetyFramework().evaluate("shell.execute", intent="list files", metadata={"command": "ls"})

    assert checkpoint.security_class == SecurityClass.RESTRICTED
    assert checkpoint.allowed is False
    assert checkpoint.requires_approval is True


def test_federated_registry_returns_capable_trusted_nodes():
    from core.federated import FederatedRegistry

    registry = FederatedRegistry()
    low = registry.register("old laptop", "lan://old", capabilities=["ocr"], trust_score=0.3)
    high = registry.register("workstation", "lan://workstation", capabilities=["ocr", "llm"], trust_score=0.9)
    registry.sync(high.node_id, {"ram": "64gb"})

    rows = registry.capable("ocr", min_trust=0.5)

    assert rows[0].node_id == high.node_id
    assert low.node_id not in {node.node_id for node in rows}


def test_operating_dashboard_and_developer_inspector_snapshot():
    from developer_mode import DeveloperInspector

    snapshot = DeveloperInspector().operating_dashboard()

    assert "runtime_map" in snapshot
    assert "recent_events" in snapshot
    assert isinstance(snapshot["event_count"], int)
