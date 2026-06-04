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
        zf.writestr("Build_Windows_EXE.bat", "")
        zf.writestr("Run_Windows_Acceptance_Test.bat", "")
        zf.writestr("tools/build_windows_installer.py", "")
        zf.writestr("tools/windows_app/shellai_desktop_entry.py", "")
        zf.writestr("tools/windows_installer/ShellAI_Setup.iss", "")
        zf.writestr("tools/windows_installer/ShellAI_Setup.nsi", "")
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
        zf.writestr("Build_Windows_EXE.bat", "")
        zf.writestr("Run_Windows_Acceptance_Test.bat", "")
        zf.writestr("tools/build_windows_installer.py", "")
        zf.writestr("tools/windows_app/shellai_desktop_entry.py", "")
        zf.writestr("tools/windows_installer/ShellAI_Setup.iss", "")
        zf.writestr("tools/windows_installer/ShellAI_Setup.nsi", "")
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
        zf.writestr("Build_Windows_EXE.bat", "")
        zf.writestr("Run_Windows_Acceptance_Test.bat", "")
        zf.writestr("tools/build_windows_installer.py", "")
        zf.writestr("tools/windows_app/shellai_desktop_entry.py", "")
        zf.writestr("tools/windows_installer/ShellAI_Setup.iss", "")
        zf.writestr("tools/windows_installer/ShellAI_Setup.nsi", "")
        zf.writestr("tools/windows_acceptance_probe.py", "")
        zf.writestr("tools/signing_notarization_check.py", "")
        zf.writestr("PUBLIC_RELEASE.md", "")
        zf.writestr("integrations/external/agent-browser/README.md", "")

    monkeypatch.setattr(readiness, "PACKAGE_PATH", package)

    ok, details = readiness._verify_package()

    assert ok is False
    assert "integrations/external" in details


def test_production_readiness_tests_use_isolated_shellai_config(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("production_readiness_under_test_env", root / "tools" / "production_readiness.py")
    readiness = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = readiness
    spec.loader.exec_module(readiness)

    captured = {}

    class Result:
        returncode = 0
        stdout = "ok\n"

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env")
        return Result()

    monkeypatch.setenv("SHELLAI_CONFIG", "/Users/example/.shellai/config.json")
    monkeypatch.setattr(readiness, "_test_python", lambda: "/tmp/shellai-test-python")
    monkeypatch.setattr(readiness.subprocess, "run", fake_run)

    ok, details = readiness._run_tests()

    assert ok is True
    assert details == "ok"
    assert captured["args"][0] == "/tmp/shellai-test-python"
    assert captured["args"][1:3] == ["-m", "pytest"]
    assert Path(captured["env"]["SHELLAI_CONFIG"]).parts[-3:] == (
        ".shell_runtime",
        "production_readiness_shellai",
        "config.json",
    )


def test_production_readiness_prefers_configured_test_python(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("production_readiness_under_test_python", root / "tools" / "production_readiness.py")
    readiness = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = readiness
    spec.loader.exec_module(readiness)

    test_python = tmp_path / "python.exe"
    test_python.write_text("", encoding="utf-8")

    monkeypatch.setenv("SHELLAI_TEST_PYTHON", str(test_python))

    assert readiness._test_python() == str(test_python)
