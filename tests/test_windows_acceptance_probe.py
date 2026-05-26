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
