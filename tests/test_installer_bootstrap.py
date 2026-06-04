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


def test_bootstrap_node_support_policy():
    assert bootstrap.node_supported((20, 19, 0))
    assert bootstrap.node_supported((22, 12, 0))
    assert bootstrap.node_supported((24, 0, 0))
    assert not bootstrap.node_supported((20, 18, 1))
    assert not bootstrap.node_supported((22, 11, 0))
    assert not bootstrap.node_supported((21, 7, 0))
    assert "too old" in bootstrap.node_support_message((20, 11, 0))


def test_bootstrap_refuses_unexpected_venv_rebuild(tmp_path):
    result = bootstrap.safe_rebuild_venv(tmp_path / "not-shell-venv")

    assert result.ok is False
    assert result.status == "ERROR"
    assert "Refusing" in result.message


def test_bootstrap_tail_file_reads_last_lines(tmp_path):
    path = tmp_path / "sample.log"
    path.write_text("\n".join(str(i) for i in range(10)), encoding="utf-8")

    assert bootstrap.tail_file(path, lines=3) == "7\n8\n9"


def test_wait_for_hub_uses_fast_ready_endpoint(monkeypatch, tmp_path):
    class FakeProcess:
        def poll(self):
            return None

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    calls = []

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        if url.endswith("/ready"):
            return FakeResponse()
        raise OSError("health diagnostics not ready yet")

    monkeypatch.setattr(bootstrap, "PORT_HINT", tmp_path / ".shell_hub_port")
    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", fake_urlopen)

    ok, port = bootstrap.wait_for_hub(FakeProcess(), timeout_s=0.1)

    assert ok is True
    assert port == "5000"
    assert calls[0][0].endswith(":5000/ready")


def test_windows_launchers_use_modern_diagnostic_path():
    start = open("Start_ShellAI.bat", encoding="utf-8").read()
    one_click = open("ONE_CLICK_INSTALL.bat", encoding="utf-8").read()
    repair = open("Repair_ShellAI.bat", encoding="utf-8").read()
    acceptance = open("Run_Windows_Acceptance_Test.bat", encoding="utf-8").read()
    exe_builder = open("Build_Windows_EXE.bat", encoding="utf-8").read()
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
    assert "SHELL_IMAGE_LOCAL_FALLBACK=1" in start
    assert "SHELL_IMAGE_LOCAL_FALLBACK=1" in one_click
    assert "SHELL_IMAGE_LOCAL_FALLBACK=1" in repair
    assert "SHELL_IMAGE_LOCAL_FALLBACK=1" in acceptance
    assert "tools\\build_windows_installer.py" in exe_builder
    assert "JRSoftware.InnoSetup" in exe_builder
    assert "shell-ai-os-controller-setup-[VERSION].exe" in exe_builder
    assert "exit /b %SHELL_RC%" in repair
    assert "SHELL_LEGACY_UI=0" in start
    assert "SHELL_LEGACY_UI=0" in acceptance
    for script in (start, one_click, repair, acceptance):
        assert "call :refresh_path" in script
        assert ":refresh_path" in script
        assert "Microsoft\\WinGet\\Links" in script
        assert "ProgramFiles%\\nodejs" in script
    assert not (bootstrap.ROOT / "start_shell.bat").exists()
    assert not (bootstrap.ROOT / "run.bat").exists()
    assert "ONE_CLICK_INSTALL.bat" in installer
    assert "tools\\windows_acceptance_probe.py --visible-ui-probe" in acceptance
    assert "installer\\bootstrap.py install --yes" in acceptance


def test_windows_inno_setup_installer_config_creates_shortcuts_and_startup_option():
    iss = open("tools/windows_installer/ShellAI_Setup.iss", encoding="utf-8").read()
    builder = open("tools/build_windows_installer.py", encoding="utf-8").read()

    assert "OutputBaseFilename=shell-ai-os-controller-setup-{#AppVersion}" in iss
    assert "DefaultDirName={localappdata}\\Programs\\ShellAI" in iss
    assert "ONE_CLICK_INSTALL.bat" in iss
    assert "Start_ShellAI.bat" in iss
    assert "{userstartup}\\Shell AI OS Controller" in iss
    assert "PrivilegesRequired=lowest" in iss
    assert "validate_release_file_set(files)" in builder
    assert "Windows .exe installer compilation requires Windows with Inno Setup." in builder


def test_mac_launchers_use_bootstrap_directly():
    install = open("ONE_CLICK_INSTALL.command", encoding="utf-8").read()
    start = open("start_shellai.command", encoding="utf-8").read()

    assert "installer/bootstrap.py install --yes" in install
    assert "shell_ui/requirements_ui.txt" in install
    assert "shell_web_ui" in install
    assert "Python 3.10+" in install
    assert "SHELL_LEGACY_UI" in start
    assert "SHELL_IMAGE_LOCAL_FALLBACK" in install
    assert "SHELL_IMAGE_LOCAL_FALLBACK" in start
    assert "installer/bootstrap.py launch --repair-if-needed" in start
    assert "exec ./start_shellai.command" not in start


def test_linux_launchers_enforce_python_policy_and_image_fallback():
    install = open("installer/install_linux.sh", encoding="utf-8").read()
    start = open("start_shellai.sh", encoding="utf-8").read()
    repair = open("repair_shellai.sh", encoding="utf-8").read()

    for script in (install, start, repair):
        assert "SHELL_IMAGE_LOCAL_FALLBACK" in script
    assert "sys.version_info >= (3, 10)" in install
    assert "sys.version_info >= (3, 10)" in start


def test_image_provider_readiness_warns_with_local_fallback(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("SHELL_IMAGE_LOCAL_FALLBACK=1\n", encoding="utf-8")

    for key in ("OPENAI_API_KEY", "STABILITY_API_KEY", "REPLICATE_API_KEY", "HUGGINGFACE_API_KEY", "HF_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)

    result = bootstrap.image_provider_readiness()

    assert result.ok is True
    assert result.status == "WARN"
    assert "local preview fallback" in result.message


def test_image_provider_readiness_reports_configured_provider(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-test\nSHELL_IMAGE_LOCAL_FALLBACK=1\n", encoding="utf-8")

    for key in ("OPENAI_API_KEY", "STABILITY_API_KEY", "REPLICATE_API_KEY", "HUGGINGFACE_API_KEY", "HF_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)

    result = bootstrap.image_provider_readiness()

    assert result.ok is True
    assert result.status == "OK"
    assert "OpenAI Images" in result.message
    assert "sk-test" not in result.message


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
    monkeypatch.setattr(bootstrap, "command_version_tuple", lambda _command, version_arg="--version": (22, 12, 0))

    results = bootstrap.install_node_deps()

    assert all(result.ok for result in results)
    assert any(cwd == bootstrap.WEB_UI_ROOT and "install Shell Web UI" in name for cwd, _argv, name in calls)
    assert any(cwd == bootstrap.WEB_UI_ROOT and argv == ["npm", "run", "build"] for cwd, argv, _name in calls)


def test_windows_npm_commands_use_resolved_cmd_path(monkeypatch, tmp_path):
    project = tmp_path / "web"
    project.mkdir()
    (project / "package.json").write_text("{}", encoding="utf-8")
    (project / "package-lock.json").write_text("{}", encoding="utf-8")
    npm_cmd = r"C:\Program Files\nodejs\npm.cmd"
    calls = []

    class FakeCompletedProcess:
        returncode = 0
        stdout = "ok"

    def fake_which(name):
        return npm_cmd if name == "npm" else None

    def fake_subprocess_run(cmd, **_kwargs):
        calls.append(cmd)
        return FakeCompletedProcess()

    monkeypatch.setattr(bootstrap, "detect_os", lambda: "windows")
    monkeypatch.setattr(bootstrap.shutil, "which", fake_which)
    monkeypatch.setattr(bootstrap.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(bootstrap, "command_version_tuple", lambda _command, version_arg="--version": (22, 12, 0))

    results = bootstrap._npm_project_install(project, "Shell Web UI", build=True)

    assert all(result.ok for result in results)
    assert calls == [
        [npm_cmd, "ci"],
        [npm_cmd, "run", "build"],
    ]


def test_web_ui_toolchain_blocks_missing_build_with_old_node(monkeypatch, tmp_path):
    monkeypatch.delenv("SHELL_WEB_UI_URL", raising=False)
    monkeypatch.setattr(bootstrap, "WEB_UI_DIST_INDEX", tmp_path / "missing" / "index.html")
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: f"/usr/bin/{name}" if name in {"node", "npm"} else None)
    monkeypatch.setattr(bootstrap, "command_version_tuple", lambda _command, version_arg="--version": (20, 11, 0))

    result = bootstrap.web_ui_toolchain_readiness()

    assert result.ok is False
    assert result.status == "ERROR"
    assert "Node.js 20.11.0 is too old" in result.message


def test_windows_system_dependency_upgrades_old_node(monkeypatch):
    def fake_which(name):
        if name in {"winget", "node", "npm", "ffmpeg", "tesseract", "uvx"}:
            return f"C:/{name}.exe"
        return None

    monkeypatch.setattr(bootstrap, "detect_os", lambda: "windows")
    monkeypatch.setattr(bootstrap, "refresh_windows_process_path", lambda: bootstrap.StepResult("windows PATH", True, "OK", ""))
    monkeypatch.setattr(bootstrap, "preferred_python_executable", lambda: "python")
    monkeypatch.setattr(bootstrap.shutil, "which", fake_which)
    monkeypatch.setattr(bootstrap, "command_version_tuple", lambda _command, version_arg="--version": (20, 11, 0))

    commands = bootstrap.system_dependency_commands("windows")

    assert ["winget", "upgrade", "-e", "--accept-source-agreements", "--accept-package-agreements", "--id", "OpenJS.NodeJS.LTS"] in commands


def test_install_runs_system_dependencies_before_node_build(monkeypatch, tmp_path):
    order = []
    py = tmp_path / "python"
    py.write_text("", encoding="utf-8")

    monkeypatch.setattr(bootstrap, "venv_dir", lambda: tmp_path)
    monkeypatch.setattr(bootstrap, "python_in_venv", lambda _path: py)
    monkeypatch.setattr(bootstrap, "ensure_venv", lambda _path, rebuild_unsupported=False: bootstrap.StepResult("venv", True, "OK", ""))
    monkeypatch.setattr(bootstrap, "install_system_deps", lambda yes=False: order.append("system") or [])
    monkeypatch.setattr(bootstrap, "install_python_deps", lambda _path, repair=False: order.append("python") or [])
    monkeypatch.setattr(bootstrap, "install_node_deps", lambda: order.append("node") or [])
    monkeypatch.setattr(bootstrap, "health_report", lambda _path=None: {"ok": True, "results": [], "state": "READY"})
    monkeypatch.setattr(bootstrap, "print_health", lambda _report: None)

    assert bootstrap.install(yes=True) == 0
    assert order == ["system", "python", "node"]


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
