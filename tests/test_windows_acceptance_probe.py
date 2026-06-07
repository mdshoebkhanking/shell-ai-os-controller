from pathlib import Path

import tools.windows_acceptance_probe as probe


def test_find_executable_falls_back_to_managed_venv_scripts(monkeypatch, tmp_path):
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    uvx = scripts / "uvx.exe"
    uvx.write_text("", encoding="utf-8")

    monkeypatch.setattr(probe.shutil, "which", lambda _exe: None)
    monkeypatch.setattr(probe.platform, "system", lambda: "Windows")

    found = probe.find_executable("uvx", scripts / "python.exe")

    assert found == str(uvx)


def test_find_executable_prefers_path_lookup(monkeypatch, tmp_path):
    npm = tmp_path / "npm.cmd"
    npm.write_text("", encoding="utf-8")

    monkeypatch.setattr(probe.shutil, "which", lambda exe: str(npm) if exe == "npm" else None)
    monkeypatch.setattr(probe.platform, "system", lambda: "Windows")

    found = probe.find_executable("npm", Path("C:/venv/Scripts/python.exe"))

    assert found == str(npm)


def test_check_hub_accepts_fast_ready_endpoint(monkeypatch, tmp_path):
    class FakeProcess:
        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    calls = []

    def fake_popen(*_args, **_kwargs):
        return FakeProcess()

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        if url.endswith("/ready"):
            return FakeResponse()
        raise OSError("health diagnostics not ready yet")

    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(probe.urllib.request, "urlopen", fake_urlopen)

    result = probe.check_hub(tmp_path / "python")

    assert result.ok is True
    assert result.status == "PASS"
    assert result.details["path"] == "/ready"
    assert calls[0][0].endswith(":5000/ready")


def test_ui_probe_skips_mcp_and_reports_json_errors(monkeypatch, tmp_path):
    captured = {}

    def fake_run_cmd(argv, *, name, timeout=120, env=None):
        captured["argv"] = [str(part) for part in argv]
        report_path = Path(captured["argv"][captured["argv"].index("--json-out") + 1])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text('{"ok": false, "errors": ["backend command worker did not finish"]}', encoding="utf-8")
        return probe.Check(name, False, "FAIL", "}\n", {"returncode": 1, "command": captured["argv"]})

    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "SCREENS_DIR", tmp_path / "screens")
    monkeypatch.setattr(probe, "run_cmd", fake_run_cmd)

    result = probe.check_ui_probe(tmp_path / "python.exe", visible=False)

    assert "--skip-mcp-smoke" in captured["argv"]
    assert result.status == "FAIL"
    assert "backend command worker did not finish" in result.message
    assert result.details["probe_errors"] == ["backend command worker did not finish"]


def test_windows_app_open_smoke_is_opt_in(monkeypatch, tmp_path):
    monkeypatch.setattr(probe.platform, "system", lambda: "Windows")
    monkeypatch.delenv("SHELL_ACCEPTANCE_OPEN_APPS", raising=False)

    result = probe.check_windows_app_open_smoke(tmp_path / "python.exe")

    assert result.ok is True
    assert result.status == "WARN"
    assert "SHELL_ACCEPTANCE_OPEN_APPS=1" in result.message


def test_bundled_exe_memory_is_opt_in(monkeypatch, tmp_path):
    app_exe = tmp_path / "ShellAIApp" / "ShellAI.exe"
    app_exe.parent.mkdir()
    app_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(probe.platform, "system", lambda: "Windows")
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe, "APP_EXE", app_exe)
    monkeypatch.delenv("SHELL_ACCEPTANCE_LAUNCH_EXE", raising=False)

    result = probe.check_bundled_exe_memory()

    assert result.ok is True
    assert result.status == "WARN"
    assert "SHELL_ACCEPTANCE_LAUNCH_EXE=1" in result.message
    assert result.details["fail_mb"] == probe.RAM_FAIL_MB


def test_env_flag_accepts_common_truthy_values(monkeypatch):
    monkeypatch.setenv("SHELL_ACCEPTANCE_OPEN_APPS", "yes")

    assert probe.env_flag("SHELL_ACCEPTANCE_OPEN_APPS") is True


def test_ui_probe_reports_settings_typing_latency():
    source = (Path(__file__).resolve().parents[1] / "tools" / "e2e_ui_probe.py").read_text(encoding="utf-8")

    assert "typing_latency" in source
    assert "settings_latency_threshold_ms = 250.0" in source
    assert "target_input.insert(char)" in source
    assert "settings typing latency exceeded" in source


def test_hard_task_probe_covers_pdf_and_fresh_image_routes():
    source = (Path(__file__).resolve().parents[1] / "tools" / "windows_acceptance_probe.py").read_text(encoding="utf-8")

    assert "AI tools ke bare mein pdf bana do" in source
    assert '"destination": "documents"' in source
    assert "cat ke photo generate karo" in source
    assert '"force_fresh": True' in source
    assert '"use_cache": False' in source


def test_frozen_offline_llm_catalog_accepts_on_demand_options(monkeypatch, tmp_path):
    app_exe = tmp_path / "ShellAIApp" / "ShellAI.exe"
    app_exe.parent.mkdir()
    app_exe.write_text("", encoding="utf-8")
    captured = {}

    def fake_run_cmd(argv, *, name, timeout=120, env=None):
        captured["argv"] = [str(part) for part in argv]
        return probe.Check(
            name,
            True,
            "PASS",
            (
                '{"available": false, "installedModelsCount": 0, "optionsCount": 6, '
                '"reason": "No offline GGUF model is installed yet.", "runtimeDownloads": true, "success": true}'
            ),
            {"returncode": 0, "command": captured["argv"]},
        )

    monkeypatch.setattr(probe, "APP_EXE", app_exe)
    monkeypatch.setattr(probe, "run_cmd", fake_run_cmd)

    result = probe.check_frozen_offline_llm_catalog(tmp_path / "python.exe")

    assert result.ok is True
    assert result.status == "PASS"
    assert "6 model options" in result.message
    assert "optionsCount" in captured["argv"][2]


def test_offline_llm_catalog_ready_accepts_no_installed_model_with_options():
    ready, count = probe._offline_llm_catalog_ready(
        {
            "available": False,
            "runtimeDownloads": True,
            "reason": "No offline GGUF model is installed yet.",
            "catalog": {"options": [{}, {}, {}, {}, {}, {}]},
        }
    )

    assert ready is True
    assert count == 6


def test_windows_acceptance_covers_packaged_runtime_probe():
    source = (Path(__file__).resolve().parents[1] / "tools" / "windows_acceptance_probe.py").read_text(encoding="utf-8")
    desktop_entry = (Path(__file__).resolve().parents[1] / "tools" / "windows_app" / "shellai_desktop_entry.py").read_text(
        encoding="utf-8"
    )

    assert "--app-root" in source
    assert "--runtime-only" in source
    assert "check_frozen_offline_llm_catalog" in source
    assert "check_frozen_runtime_probe" in source
    assert "llm_catalog_ready" in source
    assert "--shell-ai-runtime-probe" in source
    assert "_candidate_failure_summary(tts)" in source
    assert "SHELL_RUNTIME_PROBE_JSON" in desktop_entry
    assert "offline_tts_module" in desktop_entry
    assert "kokoroModelFiles" in desktop_entry
    assert "import_checks" in desktop_entry
    assert "onnxruntime.capi.onnxruntime_pybind11_state" in desktop_entry
    assert "not llm_status.get(\"available\") and not _offline_llm_catalog_ready(llm_status)" in desktop_entry


def test_windows_acceptance_summarizes_offline_tts_candidates():
    from tools.windows_acceptance_probe import _candidate_failure_summary

    summary = _candidate_failure_summary(
        {
            "reason": "Kokoro offline voice is not ready.",
            "candidates": [
                {
                    "engine": "kokoro",
                    "reason": "kokoro_onnx runtime is not installed in the app bundle.",
                    "modelDir": r"C:\Users\me\AppData\Local\Programs\ShellAI\models\tts\kokoro",
                }
            ],
        }
    )

    assert "Kokoro offline voice is not ready." in summary
    assert "kokoro_onnx runtime is not installed" in summary
    assert r"models\tts\kokoro" in summary
