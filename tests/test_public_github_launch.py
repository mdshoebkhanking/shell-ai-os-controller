import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_public_launch_audit_module():
    path = ROOT / "tools" / "public_github_launch_audit.py"
    spec = importlib.util.spec_from_file_location("public_github_launch_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_public_package_module():
    path = ROOT / "tools" / "package_public_release.py"
    spec = importlib.util.spec_from_file_location("package_public_release", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_official_logo_and_showcase_assets_exist():
    required = [
        "assets/brand/shell-official-logo.png",
        "assets/brand/README.md",
        "screenshots/current/dashboard.png",
        "screenshots/current/control.png",
        "screenshots/current/gallery.png",
        "screenshots/current/settings.png",
        "screenshots/current/apps.png",
        "screenshots/current/notes.png",
        "screenshots/current/phone.png",
        "screenshots/current/macros.png",
        "videos/shell-current-ui-landscape-demo.mp4",
        "videos/shell-current-ui-landscape-poster.png",
    ]

    for path in required:
        assert (ROOT / path).exists(), path


def test_readme_uses_official_logo_and_real_showcase_gallery():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "assets/brand/shell-official-logo.png" in readme
    assert "screenshots/current/dashboard.png" in readme
    assert "screenshots/current/control.png" in readme
    assert "screenshots/current/gallery.png" in readme
    assert "screenshots/current/settings.png" in readme
    assert "videos/shell-current-ui-landscape-demo.mp4" in readme
    assert "videos/shell-current-ui-landscape-poster.png" in readme
    assert "Replace these placeholders" not in readme
    assert "Add setup GIF here" not in readme
    assert "Add video demo here" not in readme


def test_public_github_launch_audit_has_no_high_findings():
    module = load_public_launch_audit_module()
    report = module.build_report()

    assert report["status"] == "pass"
    assert report["summary"]["visual_presentation_score"] >= 90
    assert report["summary"]["branding_quality_score"] >= 90
    assert report["summary"]["security_maturity_score"] >= 90


def test_launch_demo_video_is_github_friendly_size():
    current_landscape = ROOT / "videos" / "shell-current-ui-landscape-demo.mp4"
    current_landscape_poster = ROOT / "videos" / "shell-current-ui-landscape-poster.png"

    assert current_landscape.exists()
    assert current_landscape_poster.exists()
    assert current_landscape.stat().st_size < 15_000_000
    assert current_landscape_poster.stat().st_size < 5_000_000


def test_public_launch_docs_and_ci_gate_are_linked():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "PUBLIC_GITHUB_RELEASE_PLAYBOOK.md" in docs_index
    assert "PUBLIC_GITHUB_RELEASE_PLAYBOOK.md" in readme
    assert "tools/public_github_launch_audit.py" in ci
    assert "tools/public_github_launch_audit.py" in release


def test_public_release_package_includes_web_ui_source_and_windows_launchers():
    module = load_public_package_module()

    rel_paths = {path.relative_to(ROOT).as_posix() for path in module.iter_release_files()}

    assert module.REQUIRED_PACKAGE_FILES <= rel_paths
    assert "shell_web_ui/package.json" in rel_paths
    assert "shell_web_ui/src/App.tsx" in rel_paths
    assert "ONE_CLICK_INSTALL.bat" in rel_paths
    assert "Build_Windows_EXE.bat" in rel_paths
    assert "Run_Windows_Acceptance_Test.bat" in rel_paths
    assert "tools/build_windows_installer.py" in rel_paths
    assert "tools/windows_installer/ShellAI_Setup.iss" in rel_paths
    assert "AGENT_FIX.md" not in rel_paths
    assert "SESSION_LOG.md" not in rel_paths
    assert not any(path.startswith("shell_web_ui/dist/") for path in rel_paths)
    assert not any(path.startswith("shell_web_ui/node_modules/") for path in rel_paths)


def test_public_release_validation_fails_when_web_ui_package_is_missing():
    module = load_public_package_module()
    files = [
        ROOT / rel
        for rel in module.REQUIRED_PACKAGE_FILES
        if rel != "shell_web_ui/package.json"
    ]

    with pytest.raises(RuntimeError, match="shell_web_ui/package.json"):
        module.validate_release_file_set(files)


def test_public_release_validation_rejects_generated_web_ui_outputs():
    module = load_public_package_module()
    files = [ROOT / rel for rel in module.REQUIRED_PACKAGE_FILES]
    files.append(ROOT / "shell_web_ui" / "dist" / "index.html")

    with pytest.raises(RuntimeError, match="shell_web_ui/dist/index.html"):
        module.validate_release_file_set(files)


def test_public_release_package_supports_dry_run(monkeypatch, tmp_path):
    module = load_public_package_module()
    required_files = [ROOT / rel for rel in module.REQUIRED_PACKAGE_FILES]

    monkeypatch.setattr(module, "DIST_DIR", tmp_path)
    monkeypatch.setattr(module, "build_report", lambda include_health=True, strict=True: {"status": "pass", "warnings": []})
    monkeypatch.setattr(module, "iter_release_files", lambda: required_files)

    report = module.build_package(dry_run=True)

    assert report["status"] == "dry-run"
    assert report["file_count"] == len(required_files) + 1
    assert not any(tmp_path.iterdir())
