import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_public_launch_audit_module():
    path = ROOT / "tools" / "public_github_launch_audit.py"
    spec = importlib.util.spec_from_file_location("public_github_launch_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_official_logo_and_showcase_assets_exist():
    required = [
        "assets/brand/shell-official-logo.png",
        "assets/brand/README.md",
        "screenshots/showcase/chat-interface.png",
        "screenshots/showcase/voice-interface.png",
        "screenshots/showcase/system-dashboard.png",
        "screenshots/showcase/settings-panel.png",
        "screenshots/showcase/tools-catalog.png",
        "screenshots/showcase/windows-chat-acceptance.png",
    ]

    for path in required:
        assert (ROOT / path).exists(), path


def test_readme_uses_official_logo_and_real_showcase_gallery():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "assets/brand/shell-official-logo.png" in readme
    assert "screenshots/showcase/chat-interface.png" in readme
    assert "screenshots/showcase/voice-interface.png" in readme
    assert "Replace these placeholders" not in readme


def test_public_github_launch_audit_has_no_high_findings():
    module = load_public_launch_audit_module()
    report = module.build_report()

    assert report["status"] == "pass"
    assert report["summary"]["visual_presentation_score"] >= 90
    assert report["summary"]["branding_quality_score"] >= 90
    assert report["summary"]["security_maturity_score"] >= 90


def test_public_launch_docs_and_ci_gate_are_linked():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "PUBLIC_GITHUB_RELEASE_PLAYBOOK.md" in docs_index
    assert "PUBLIC_GITHUB_RELEASE_PLAYBOOK.md" in readme
    assert "tools/public_github_launch_audit.py" in ci
    assert "tools/public_github_launch_audit.py" in release
