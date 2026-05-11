import zipfile
import importlib.util
import sys
from pathlib import Path


def test_production_readiness_scores_all_automated_gates(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("production_readiness_under_test", root / "tools" / "production_readiness.py")
    readiness = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = readiness
    spec.loader.exec_module(readiness)

    package = tmp_path / "release.zip"
    with zipfile.ZipFile(package, "w") as zf:
        zf.writestr("release_manifest.json", "{}")
        zf.writestr("LICENSE", "")
        zf.writestr("NOTICE", "")
        zf.writestr("LEGAL.md", "")
        zf.writestr("SECURITY.md", "")
        zf.writestr("THIRD_PARTY_NOTICES.md", "")
        zf.writestr("ONE_CLICK_INSTALL.bat", "")
        zf.writestr("Start_ShellAI.bat", "")
        zf.writestr("Run_Windows_Acceptance_Test.bat", "")
        zf.writestr("tools/windows_acceptance_probe.py", "")
        zf.writestr("tools/signing_notarization_check.py", "")
        zf.writestr("PUBLIC_RELEASE.md", "")

    monkeypatch.setattr(readiness, "PACKAGE_PATH", package)
    monkeypatch.setattr(
        readiness,
        "build_release_report",
        lambda include_health=True, strict=True: {
            "status": "pass",
            "warnings": [],
            "blockers": [],
            "health": {"ok": True, "state": "READY"},
            "template_guard": {"blockers": []},
            "local_runtime_guard": {"blockers": []},
        },
    )

    report = readiness.build_readiness_report(run_tests=False)

    assert report["automated_status"] == "pass"
    assert report["automated_local_score"] == 100
    assert report["external_gates"]


def test_production_readiness_rejects_telegram_runtime_state(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("production_readiness_under_test_state", root / "tools" / "production_readiness.py")
    readiness = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = readiness
    spec.loader.exec_module(readiness)

    package = tmp_path / "release.zip"
    with zipfile.ZipFile(package, "w") as zf:
        zf.writestr("release_manifest.json", "{}")
        zf.writestr("LICENSE", "")
        zf.writestr("NOTICE", "")
        zf.writestr("LEGAL.md", "")
        zf.writestr("SECURITY.md", "")
        zf.writestr("THIRD_PARTY_NOTICES.md", "")
        zf.writestr("ONE_CLICK_INSTALL.bat", "")
        zf.writestr("Start_ShellAI.bat", "")
        zf.writestr("Run_Windows_Acceptance_Test.bat", "")
        zf.writestr("tools/windows_acceptance_probe.py", "")
        zf.writestr("tools/signing_notarization_check.py", "")
        zf.writestr("PUBLIC_RELEASE.md", "")
        zf.writestr(".telegram_users.json", "{}")

    monkeypatch.setattr(readiness, "PACKAGE_PATH", package)

    ok, details = readiness._verify_package()

    assert ok is False
    assert ".telegram_users.json" in details


def test_production_readiness_rejects_bundled_external_clones(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("production_readiness_under_test_external", root / "tools" / "production_readiness.py")
    readiness = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = readiness
    spec.loader.exec_module(readiness)

    package = tmp_path / "release.zip"
    with zipfile.ZipFile(package, "w") as zf:
        zf.writestr("release_manifest.json", "{}")
        zf.writestr("LICENSE", "")
        zf.writestr("NOTICE", "")
        zf.writestr("LEGAL.md", "")
        zf.writestr("SECURITY.md", "")
        zf.writestr("THIRD_PARTY_NOTICES.md", "")
        zf.writestr("ONE_CLICK_INSTALL.bat", "")
        zf.writestr("Start_ShellAI.bat", "")
        zf.writestr("Run_Windows_Acceptance_Test.bat", "")
        zf.writestr("tools/windows_acceptance_probe.py", "")
        zf.writestr("tools/signing_notarization_check.py", "")
        zf.writestr("PUBLIC_RELEASE.md", "")
        zf.writestr("integrations/external/agent-browser/README.md", "")

    monkeypatch.setattr(readiness, "PACKAGE_PATH", package)

    ok, details = readiness._verify_package()

    assert ok is False
    assert "integrations/external" in details
