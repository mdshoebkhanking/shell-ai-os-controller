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
