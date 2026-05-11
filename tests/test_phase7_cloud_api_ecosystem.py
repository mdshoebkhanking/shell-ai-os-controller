import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_cloud_audit_module():
    path = ROOT / "tools" / "cloud_readiness_audit.py"
    spec = importlib.util.spec_from_file_location("cloud_readiness_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_platform_api_contract_declares_scopes_and_openapi_skeleton():
    from core.platform_api import ApiAuthContext, ApiScope, PlatformAPIContract

    contract = PlatformAPIContract()
    findings = contract.validate()
    openapi = contract.openapi_skeleton()
    auth = ApiAuthContext(subject="local-ui", scopes=[ApiScope.STATUS_READ.value])

    assert findings == []
    assert openapi["openapi"] == "3.1.0"
    assert "/health" in openapi["paths"]
    assert contract.authorize("health.read", auth).ok is True
    assert contract.authorize("settings.save", auth).ok is False


def test_api_envelope_and_realtime_event_are_stable_for_sdk_clients():
    from core.platform_api import ApiEnvelope, ApiError, RealtimeEvent

    ok = ApiEnvelope.success({"ready": True}, request_id="req-1", trace_id="trace-1")
    failed = ApiEnvelope.failure(ApiError("BAD_REQUEST", "Invalid payload", status=400), request_id="req-2")
    event = RealtimeEvent(type="shell.runtime.updated", source="shell.test", data={"ok": True})

    assert ok.to_dict()["data"]["ready"] is True
    assert failed.to_dict()["error"]["code"] == "BAD_REQUEST"
    assert event.validate() == []
    assert event.to_cloudevent()["specversion"] == "1.0"


def test_plugin_manifest_accepts_cloud_api_event_and_workflow_permissions():
    from sdk.manifest import ExtensionManifest

    manifest = ExtensionManifest.from_dict(
        {
            "name": "phase7-sync-pack",
            "version": "1.0.0",
            "shell_api": "1.x",
            "kind": "automation_pack",
            "entrypoint": "plugin.py",
            "permissions": ["cloud.sync", "api.external", "events.publish", "events.subscribe", "workflow.run", "workspace.sync"],
        }
    )

    assert "cloud.sync" in manifest.permissions
    assert "workflow.run" in manifest.permissions


def test_cloud_readiness_audit_reports_scores_without_high_findings():
    module = load_cloud_audit_module()
    report = module.build_report()

    assert report["status"] == "pass"
    assert report["contract"]["route_count"] >= 8
    assert report["summary"]["api_maturity_score"] >= 90
    assert report["summary"]["security_maturity_score"] >= 80


def test_phase7_docs_are_linked_from_public_documentation_index():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required = [
        "CLOUD_INFRASTRUCTURE_PHASE7.md",
        "API_ECOSYSTEM_PHASE7.md",
        "AI_ORCHESTRATION_PHASE7.md",
        "SYNC_STORAGE_STRATEGY_PHASE7.md",
        "SECURITY_INFRASTRUCTURE_PHASE7.md",
        "PLUGIN_AUTOMATION_ECOSYSTEM_PHASE7.md",
        "DEVOPS_CLOUD_DEPLOYMENT_PHASE7.md",
        "ENTERPRISE_TEAM_PRODUCT_STRATEGY_PHASE7.md",
    ]

    for doc in required:
        assert (ROOT / "docs" / doc).exists()
        assert doc in docs_index
        assert doc in readme


def test_ci_and_release_run_cloud_readiness_gate():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "tools/cloud_readiness_audit.py" in ci
    assert "tools/cloud_readiness_audit.py" in release
    assert "--fail-on-high" in ci
    assert "--fail-on-high" in release
