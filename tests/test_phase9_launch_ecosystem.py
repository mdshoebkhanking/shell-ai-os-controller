import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_launch_audit_module():
    path = ROOT / "tools" / "launch_readiness_audit.py"
    spec = importlib.util.spec_from_file_location("launch_readiness_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_launch_plan_scores_and_distribution_matrix_are_stable():
    from core.launch import DistributionArtifact, DistributionChannel, LaunchChecklistItem, LaunchPlan, LaunchStage, TrustSignal

    plan = LaunchPlan(
        "1.0.0",
        LaunchStage.RELEASE_CANDIDATE,
        checklist=[
            LaunchChecklistItem("license", "trust", "License", LaunchStage.PUBLIC_BETA, True),
            LaunchChecklistItem("signed", "distribution", "Signed installer", LaunchStage.ENTERPRISE_READY, False),
        ],
        artifacts=[DistributionArtifact("zip", DistributionChannel.PORTABLE_ZIP, "zip", checksum=True)],
        trust_signals=[TrustSignal.LICENSE, TrustSignal.SECURITY_POLICY, TrustSignal.CODE_OF_CONDUCT, TrustSignal.CONTRIBUTING, TrustSignal.CHECKSUMS, TrustSignal.TESTS, TrustSignal.RELEASE_NOTES],
    )

    assert plan.blockers() == []
    assert plan.readiness_score() == 100
    assert plan.trust_score() == 100
    assert plan.distribution_matrix()["portable_zip"]["checksum"] is True


def test_phase9_required_community_health_files_exist():
    required = [
        "README.md",
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SUPPORT.md",
        "GOVERNANCE.md",
        "CHANGELOG.md",
    ]

    for path in required:
        assert (ROOT / path).exists()


def test_launch_readiness_audit_reports_scores_without_high_findings():
    module = load_launch_audit_module()
    report = module.build_report()

    assert report["status"] == "pass"
    assert report["summary"]["launch_readiness_score"] >= 75
    assert report["summary"]["community_scalability_score"] >= 95
    assert report["summary"]["ecosystem_trust_score"] >= 90
    assert report["summary"]["distribution_readiness_score"] >= 50


def test_phase9_docs_are_linked_from_public_docs_and_readme():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required = [
        "GLOBAL_LAUNCH_PHASE9.md",
        "ENTERPRISE_DISTRIBUTION_PHASE9.md",
        "BRAND_AUTHORITY_TRUST_PHASE9.md",
        "COMMUNITY_GROWTH_PHASE9.md",
        "CONTENT_EDUCATION_PHASE9.md",
        "WEBSITE_PUBLIC_PRESENCE_PHASE9.md",
        "ENTERPRISE_ADOPTION_PHASE9.md",
        "ANALYTICS_PRODUCT_INSIGHT_PHASE9.md",
        "SUSTAINABILITY_PHASE9.md",
        "COMPETITIVE_POSITIONING_PHASE9.md",
        "LONG_TERM_GOVERNANCE_PHASE9.md",
    ]

    for doc in required:
        assert (ROOT / "docs" / doc).exists()
        assert doc in docs_index
        assert doc in readme


def test_ci_and_release_run_launch_readiness_gate():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "tools/launch_readiness_audit.py" in ci
    assert "tools/launch_readiness_audit.py" in release
    assert "--fail-on-high" in ci
    assert "--fail-on-high" in release
