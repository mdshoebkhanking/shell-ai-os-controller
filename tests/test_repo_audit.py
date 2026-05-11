import importlib.util
import sys
from pathlib import Path


def test_repo_audit_report_builds():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("repo_audit_under_test", root / "tools" / "repo_audit.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    report = module.build_report()

    assert "summary" in report
    assert "issues" in report
    assert report["summary"]["status"] in {"pass", "fail"}
    assert report["file_count"] > 0


def test_repo_audit_required_public_files_are_tracked():
    root = Path(__file__).resolve().parents[1]
    required = {
        "README.md",
        "LICENSE",
        "NOTICE",
        "LEGAL.md",
        "SECURITY.md",
        "THIRD_PARTY_NOTICES.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
    }
    for rel in required:
        assert (root / rel).exists(), rel
