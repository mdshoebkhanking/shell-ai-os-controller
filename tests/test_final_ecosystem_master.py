import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_master_audit_module():
    path = ROOT / "tools" / "ecosystem_master_audit.py"
    spec = importlib.util.spec_from_file_location("ecosystem_master_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ecosystem_scorecard_weights_core_dimensions():
    from core.ecosystem_maturity import EcosystemDimension, EcosystemScorecard

    scorecard = EcosystemScorecard(
        {
            EcosystemDimension.ARCHITECTURE: 90,
            EcosystemDimension.SECURITY: 90,
            EcosystemDimension.DEVOPS: 80,
            EcosystemDimension.UI_UX: 90,
        }
    )

    assert 85 <= scorecard.overall() <= 90
    assert scorecard.to_dict()["overall_ecosystem_maturity"] == scorecard.overall()


def test_ecosystem_master_audit_reports_world_class_scores_without_high_findings():
    module = load_master_audit_module()
    report = module.build_report()

    assert report["status"] == "pass"
    assert report["summary"]["overall_ecosystem_maturity"] >= 85
    assert report["summary"]["architecture"] >= 90
    assert report["summary"]["open_source"] >= 95
    assert report["summary"]["plugin"] >= 90
    assert report["summary"]["enterprise"] < 90


def test_final_master_report_is_linked_publicly():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert (ROOT / "docs" / "FINAL_MASTER_ECOSYSTEM_REPORT.md").exists()
    assert "FINAL_MASTER_ECOSYSTEM_REPORT.md" in readme
    assert "FINAL_MASTER_ECOSYSTEM_REPORT.md" in docs_index


def test_ci_and_release_run_ecosystem_master_gate():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "tools/ecosystem_master_audit.py" in ci
    assert "tools/ecosystem_master_audit.py" in release
    assert "--fail-on-high" in ci
    assert "--fail-on-high" in release
