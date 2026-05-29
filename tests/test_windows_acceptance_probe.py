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
