from installer import bootstrap
import re
import uuid


def test_bootstrap_detects_known_os():
    assert bootstrap.detect_os() in {"mac", "linux", "windows", "unknown"}


def test_bootstrap_human_dependency_message_is_non_traceback():
    msg = bootstrap.human_dependency_message("sounddevice", "microphone capture")

    assert "Run Repair Shell AI" in msg
    assert "ModuleNotFoundError" not in msg


def test_bootstrap_system_dependency_commands_mac(monkeypatch):
    def fake_which(name):
        if name == "brew":
            return "/opt/homebrew/bin/brew"
        return None

    monkeypatch.setattr(bootstrap.shutil, "which", fake_which)

    assert bootstrap.system_dependency_commands("mac") == [["brew", "install", "python@3.13", "ffmpeg", "tesseract", "node"]]


def test_bootstrap_uses_managed_venv_by_default(monkeypatch):
    monkeypatch.delenv("SHELLAI_VENV_DIR", raising=False)

    assert bootstrap.venv_dir().name == ".shellai_venv"


def test_bootstrap_prefers_current_compatible_python(monkeypatch):
    monkeypatch.delenv("SHELLAI_PYTHON", raising=False)
    monkeypatch.setattr(bootstrap, "python_version_tuple", lambda _py: (3, 13, 0))
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: name if name == bootstrap.sys.executable else None)

    assert bootstrap.preferred_python_executable() == bootstrap.sys.executable


def test_bootstrap_health_report_shape():
    report = bootstrap.health_report(bootstrap.venv_dir())

    assert "state" in report
    assert "summary" in report
    assert isinstance(report["results"], list)


def test_bootstrap_python_support_policy():
    assert bootstrap.python_supported((3, 10, 0))
    assert bootstrap.python_supported((3, 13, 1))
    assert not bootstrap.python_supported((3, 9, 18))
    assert "too old" in bootstrap.python_support_message((3, 9, 18))


def test_bootstrap_refuses_unexpected_venv_rebuild(tmp_path):
    result = bootstrap.safe_rebuild_venv(tmp_path / "not-shell-venv")

    assert result.ok is False
    assert result.status == "ERROR"
    assert "Refusing" in result.message


def test_bootstrap_tail_file_reads_last_lines(tmp_path):
    path = tmp_path / "sample.log"
    path.write_text("\n".join(str(i) for i in range(10)), encoding="utf-8")

    assert bootstrap.tail_file(path, lines=3) == "7\n8\n9"


def test_windows_launchers_use_modern_diagnostic_path():
    start = open("Start_ShellAI.bat", encoding="utf-8").read()
    legacy = open("start_shell.bat", encoding="utf-8").read()
    run = open("run.bat", encoding="utf-8").read()
    one_click = open("ONE_CLICK_INSTALL.bat", encoding="utf-8").read()
    acceptance = open("Run_Windows_Acceptance_Test.bat", encoding="utf-8").read()
    installer = open("installer/install_windows.bat", encoding="utf-8").read()

    assert "installer\\bootstrap.py launch --repair-if-needed" in start
    assert "installer\\bootstrap.py install --yes" in one_click
    assert "shell_ui\\requirements_ui.txt" in one_click
    assert "shell_web_ui" in one_click
    assert ".shellai_venv" in one_click
    assert "ui.log" in start
    assert "hub.log" in start
    assert "3.13 3.12 3.11 3.10" in start
    assert "PYTHONUTF8=1" in start
    assert "SHELL_WINDOWS_MIN_VOLUME=65" in start
    assert "SHELL_WINDOWS_MIN_VOLUME=65" in one_click
    assert "SHELL_LEGACY_UI=0" in start
    assert "Start_ShellAI.bat" in legacy
    assert "Start_ShellAI.bat" in run
    assert "C:\\Users\\Administrator" not in run
    assert "ONE_CLICK_INSTALL.bat" in installer
    assert "tools\\windows_acceptance_probe.py --visible-ui-probe" in acceptance
    assert "installer\\bootstrap.py install --yes" in acceptance


def test_mac_launchers_use_bootstrap_directly():
    install = open("ONE_CLICK_INSTALL.command", encoding="utf-8").read()
    start = open("start_shellai.command", encoding="utf-8").read()

    assert "installer/bootstrap.py install --yes" in install
    assert "shell_ui/requirements_ui.txt" in install
    assert "shell_web_ui" in install
    assert "Python 3.10+" in install
    assert "SHELL_LEGACY_UI" in start
    assert "installer/bootstrap.py launch --repair-if-needed" in start
    assert "exec ./start_shellai.command" not in start


def test_bootstrap_installs_ui_requirements(monkeypatch, tmp_path):
    calls = []

    def fake_run_cmd(argv, **kwargs):
        calls.append([str(part) for part in argv])
        return bootstrap.StepResult(kwargs.get("name", "cmd"), True, "OK", "")

    monkeypatch.setattr(bootstrap, "run_cmd", fake_run_cmd)
    bootstrap.install_python_deps(tmp_path)

    assert any("shell_ui/requirements_ui.txt" in " ".join(call).replace("\\", "/") for call in calls)
    assert "PyQt6.QtWebEngineWidgets" in bootstrap.UI_IMPORTS


def test_bootstrap_installs_and_builds_shell_web_ui(monkeypatch):
    calls = []

    def fake_run_cmd(argv, **kwargs):
        calls.append((kwargs.get("cwd", bootstrap.ROOT), [str(part) for part in argv], kwargs.get("name", "")))
        return bootstrap.StepResult(kwargs.get("name", "cmd"), True, "OK", "")

    monkeypatch.setattr(bootstrap, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: "/usr/bin/npm" if name == "npm" else None)

    results = bootstrap.install_node_deps()

    assert all(result.ok for result in results)
    assert any(cwd == bootstrap.WEB_UI_ROOT and "install Shell Web UI" in name for cwd, _argv, name in calls)
    assert any(cwd == bootstrap.WEB_UI_ROOT and argv == ["npm", "run", "build"] for cwd, argv, _name in calls)


def test_web_ui_build_readiness_reports_missing_dist(monkeypatch):
    monkeypatch.delenv("SHELL_WEB_UI_URL", raising=False)
    monkeypatch.setattr(bootstrap.Path, "exists", lambda self: False if self == bootstrap.WEB_UI_DIST_INDEX else True)

    result = bootstrap.web_ui_build_readiness()

    assert result.ok is False
    assert result.status == "ERROR"
    assert "shell_web_ui/dist/index.html" in result.message


def test_windows_preflight_helpers_are_safe_on_non_windows():
    assert bootstrap.windows_audio_preflight().ok is True
    assert bootstrap.windows_mcp_readiness(bootstrap.venv_dir()).ok is True


def test_windows_audio_preflight_guids_are_valid():
    script = open("installer/windows_audio_preflight.ps1", encoding="utf-8").read()
    guids = re.findall(r'\[Guid\("([^"]+)"\)\]', script)

    assert guids
    for value in guids:
        uuid.UUID(value)


def test_mac_audio_preflight_is_safe_on_non_mac(monkeypatch):
    monkeypatch.setattr(bootstrap, "detect_os", lambda: "linux")

    result = bootstrap.mac_audio_preflight()

    assert result.ok is True
    assert result.status == "OK"
    assert "Not required" in result.message


def test_mac_audio_preflight_reports_coreaudio_failure(monkeypatch):
    monkeypatch.setattr(bootstrap, "detect_os", lambda: "mac")
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: "/usr/bin/afplay" if name == "afplay" else None)
    monkeypatch.setattr(bootstrap, "_silent_wav_probe_path", lambda: bootstrap.ROOT / "probe.wav")
    monkeypatch.setattr(bootstrap.Path, "exists", lambda self: self.name == "BlackHole2ch.driver")

    def fake_run_cmd(*_args, **_kwargs):
        return bootstrap.StepResult(
            "mac audio",
            False,
            "ERROR",
            "Error: AudioQueueStart failed (-66680)",
            {"returncode": 1},
        )

    monkeypatch.setattr(bootstrap, "run_cmd", fake_run_cmd)

    result = bootstrap.mac_audio_preflight()

    assert result.ok is True
    assert result.status == "WARN"
    assert "Shell voice cannot be heard" in result.message
    assert "AudioQueueStart failed" in result.message
    assert "BlackHole is installed" in result.message
