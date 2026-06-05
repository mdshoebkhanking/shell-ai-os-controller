from installer import bootstrap
import importlib.util
import re
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_tool_module(module_name: str):
    module_path = ROOT / "tools" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"_shell_test_{module_name}", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    public_release = open("Build_Public_Release.bat", encoding="utf-8").read()
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
    assert "bundle ShellAI.exe with PyInstaller" in exe_builder
    assert "JRSoftware.InnoSetup" in exe_builder
    assert "--installer-engine inno" in exe_builder
    assert "shell-ai-os-controller-setup-[VERSION].exe" in exe_builder
    assert "installer\\bootstrap.py repair --yes --skip-system" in exe_builder
    assert "tools\\stage_kokoro_tts_assets.py --variant int8" in exe_builder
    assert "tools\\stage_qwen_offline_llm_assets.py --variant q4_k_m_ggml" in exe_builder
    assert "llama-cpp-python" in exe_builder
    assert "installer\\bootstrap.py repair --yes --skip-system" in public_release
    assert "EnableDelayedExpansion" in public_release
    assert "!ERRORLEVEL!" in public_release
    assert "SHELLAI_TEST_PYTHON=%CD%\\.shellai_venv\\Scripts\\python.exe" in public_release
    assert "if %errorlevel%==0" not in public_release
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


def test_windows_nsis_installer_config_creates_shortcuts_startup_and_icons():
    nsi = open("tools/windows_installer/ShellAI_Setup.nsi", encoding="utf-8").read()
    iss = open("tools/windows_installer/ShellAI_Setup.iss", encoding="utf-8").read()
    builder = open("tools/build_windows_installer.py", encoding="utf-8").read()
    desktop_entry = open("tools/windows_app/shellai_desktop_entry.py", encoding="utf-8").read()

    assert 'OutFile "${OutputDir}\\shell-ai-os-controller-setup-${AppVersion}.exe"' in nsi
    assert 'InstallDir "$LOCALAPPDATA\\Programs\\ShellAI"' in nsi
    assert '!define AppExeName "ShellAIApp\\ShellAI.exe"' in nsi
    assert "ONE_CLICK_INSTALL.bat" not in nsi
    assert "ONE_CLICK_INSTALL.bat" not in iss
    assert "Start_ShellAI.bat" not in nsi
    assert "ShellAIApp\\ShellAI.exe" in builder
    assert "APP_ICON_STAGE" in builder
    assert "stage_installed_icon(app_icon)" in builder
    assert "shutil.copy2(app_icon, APP_ICON_STAGE)" in builder
    assert "/DAppIconName" in builder
    assert "build_bundled_desktop_app" in builder
    assert "PyInstaller" in builder
    assert "--windowed" in builder
    assert "shell_hub" in builder
    assert "aiohttp_cors" in builder
    assert "engineio.async_drivers.aiohttp" in builder
    assert "_available_pyinstaller_copy_metadata" in builder
    assert "PackageNotFoundError" in builder
    assert "Skipping PyInstaller metadata for missing optional package" in builder
    assert "copy_web_ui_dist_to_stage" in builder
    assert "offline_tts_stage_report" in builder
    assert '"offline_tts": offline_tts_report' in builder
    assert "offline_llm_stage_report" in builder
    assert '"offline_llm": offline_llm_report' in builder
    assert "No packaged natural offline TTS model assets detected" in builder
    assert "No packaged GGUF offline LLM model assets detected" in builder
    assert 'CreateShortCut "$SMSTARTUP\\Shell AI OS Controller.lnk"' in nsi
    assert '!define AppIconName "shell-ai.ico"' in nsi
    assert 'CreateShortCut "$DESKTOP\\Shell AI OS Controller.lnk" "$INSTDIR\\${AppExeName}" "" "$INSTDIR\\${AppIconName}" 0' in nsi
    assert 'CreateShortCut "$SMPROGRAMS\\Shell AI OS Controller\\Repair Shell AI.lnk" "$INSTDIR\\Repair_ShellAI.bat" "" "$INSTDIR\\${AppIconName}" 0' in nsi
    assert "Function RefreshShellIcons" in nsi
    assert "Function un.RefreshShellIcons" in nsi
    assert "SHChangeNotify" in nsi
    assert "Call RefreshShellIcons" in nsi
    assert "Call un.RefreshShellIcons" in nsi
    assert '#define AppIconName "shell-ai.ico"' in iss
    assert 'IconFilename: "{app}\\{#AppIconName}"' in iss
    assert "procedure RefreshShellIcons" in iss
    assert "SHChangeNotify@shell32.dll" in iss
    assert "RequestExecutionLevel user" in nsi
    assert 'Icon "${InstallerIcon}"' in nsi
    assert "prepare_windows_icon" in builder
    assert "--icon" in builder
    assert "NSIS_SCRIPT" in builder
    assert 'installer_engine: str = "inno"' in builder
    assert "validate_release_file_set(files)" in builder
    assert "Windows .exe installer compilation requires Windows with" in builder
    assert "NSIS compiler not found" in builder
    assert "Inno Setup compiler not found" in builder
    assert "SolidCompression=no" in iss
    assert "--shell-ai-hub" in desktop_entry
    assert "SHELL_HUB_URL" in desktop_entry
    assert "CREATE_NO_WINDOW" in desktop_entry
    assert "installer/bootstrap.py launch" not in desktop_entry


def test_windows_installer_reports_packaged_offline_tts_assets(monkeypatch, tmp_path):
    build_windows_installer = load_tool_module("build_windows_installer")

    tts_root = tmp_path / "models" / "tts"
    monkeypatch.setattr(build_windows_installer, "TTS_MODEL_STAGE", tts_root)

    fallback = build_windows_installer.offline_tts_stage_report()
    assert fallback["status"] == "fallback"
    assert fallback["model_file_count"] == 0

    kokoro = tts_root / "kokoro" / "english"
    kokoro.mkdir(parents=True)
    (kokoro / "kokoro.onnx").write_bytes(b"model")
    (kokoro / "voices.bin").write_bytes(b"voices")

    ready = build_windows_installer.offline_tts_stage_report()
    assert ready["status"] == "ready"
    assert ready["model_file_count"] == 2
    assert ready["recommended_engine"] == "kokoro"
    assert ready["model_family"] == "Kokoro-82M"
    assert ready["language_support"] == ["english", "hinglish", "hindi"]
    assert ready["engines"]["kokoro"]["ready"] is True
    assert ready["engines"]["kokoro"]["model_family"] == "Kokoro-82M"


def test_windows_installer_reports_packaged_offline_llm_assets(monkeypatch, tmp_path):
    build_windows_installer = load_tool_module("build_windows_installer")

    llm_root = tmp_path / "models" / "llm"
    monkeypatch.setattr(build_windows_installer, "LLM_MODEL_STAGE", llm_root)

    fallback = build_windows_installer.offline_llm_stage_report()
    assert fallback["status"] == "fallback"
    assert fallback["model_file_count"] == 0

    qwen = llm_root / "qwen3"
    qwen.mkdir(parents=True)
    (qwen / "Qwen3-1.7B-Q4_K_M.gguf").write_bytes(b"model")

    ready = build_windows_installer.offline_llm_stage_report()
    assert ready["status"] == "ready"
    assert ready["model_file_count"] == 1
    assert ready["recommended_engine"] == "llama-cpp-python"
    assert ready["model_family"] == "Qwen3-1.7B-GGUF"
    assert ready["language_support"] == ["english", "hinglish", "hindi"]
    assert ready["runtime_downloads"] is False
    assert ready["engines"]["llama_cpp_python"]["ready"] is True


def test_kokoro_asset_staging_helper_dry_run(tmp_path):
    stage_kokoro = load_tool_module("stage_kokoro_tts_assets")

    report = stage_kokoro.stage_assets(output_dir=tmp_path, variant="int8", dry_run=True, force=False)

    assert report["status"] == "dry-run"
    assert report["model_family"] == "Kokoro-82M"
    assert report["variant"] == "int8"
    assert [asset["name"] for asset in report["assets"]] == ["kokoro-v1.0.int8.onnx", "voices-v1.0.bin"]
    assert not (tmp_path / "kokoro-v1.0.int8.onnx").exists()


def test_qwen_offline_llm_asset_staging_helper_dry_run(tmp_path):
    stage_qwen = load_tool_module("stage_qwen_offline_llm_assets")

    report = stage_qwen.stage_assets(output_dir=tmp_path, variant="q4_k_m_ggml", dry_run=True, force=False)

    assert report["status"] == "dry-run"
    assert report["model_family"] == "Qwen3-1.7B-GGUF"
    assert report["model_repo"] == "ggml-org/Qwen3-1.7B-GGUF"
    assert report["variant"] == "q4_k_m_ggml"
    assert [asset["name"] for asset in report["assets"]] == ["Qwen3-1.7B-Q4_K_M.gguf"]
    assert not (tmp_path / "Qwen3-1.7B-Q4_K_M.gguf").exists()


def test_release_workflow_stages_kokoro_assets_for_windows_installer():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert "kokoro-onnx" in workflow
    assert "tools/stage_kokoro_tts_assets.py --variant int8" in workflow
    assert "models/tts/kokoro" in workflow
    assert "llama-cpp-python" in workflow
    assert "tools/stage_qwen_offline_llm_assets.py --variant q4_k_m_ggml" in workflow
    assert "models/llm/qwen3" in workflow
    assert "choco install innosetup" in workflow
    assert "--installer-engine inno" in workflow


def test_shell_brand_logo_is_used_across_windows_app_surfaces():
    launch = open("launch.py", encoding="utf-8").read()
    host = open("shell_web_ui/host.py", encoding="utf-8").read()
    index = open("shell_web_ui/index.html", encoding="utf-8").read()
    builder = open("tools/build_windows_installer.py", encoding="utf-8").read()

    for content in (launch, host, index, builder):
        assert "shell-logo.png" in content
    assert "setWindowIcon" in launch
    assert "setWindowIcon" in host
    assert 'rel="icon"' in index


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
