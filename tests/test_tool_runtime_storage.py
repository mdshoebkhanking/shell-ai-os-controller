import importlib
import json


def test_focus_mode_state_falls_back_to_runtime_storage(monkeypatch, tmp_path):
    import shell_focus_mode

    fallback = tmp_path / "runtime" / "focus_state.json"
    monkeypatch.setattr(shell_focus_mode, "STATE_PATH", tmp_path / "locked_home" / "focus.json")
    monkeypatch.setattr(shell_focus_mode, "_runtime_state_path", lambda: fallback)

    def fake_writable(path):
        return path == fallback

    monkeypatch.setattr(shell_focus_mode, "_path_is_writable", fake_writable)

    shell_focus_mode._save_state({"active": True, "sessions": [{"goal": "probe"}]})

    assert fallback.exists()
    assert shell_focus_mode._load_state()["active"] is True


def test_auto_planner_uses_configured_writable_plan_dir(monkeypatch, tmp_path):
    import shell_auto_planner

    plans = tmp_path / "plans"
    monkeypatch.setenv("SHELL_PLANS_DIR", str(plans))

    assert shell_auto_planner._plan_dir() == plans


def test_social_connections_file_uses_runtime_fallback_when_home_is_locked(monkeypatch, tmp_path):
    import shell_social_connector

    monkeypatch.delenv("SHELL_SOCIAL_CONNECTIONS_FILE", raising=False)

    home_file = tmp_path / "locked_home" / ".shell_social_connections.json"
    runtime_file = tmp_path / "runtime" / "social_connections.json"
    monkeypatch.setattr(shell_social_connector.Path, "home", lambda: tmp_path / "locked_home")
    monkeypatch.setattr(
        shell_social_connector.Path,
        "resolve",
        lambda self, *args, **kwargs: runtime_file.parent.parent / "shell_social_connector.py"
        if str(self).endswith("shell_social_connector.py")
        else self,
    )

    def fake_writable(path):
        return path != home_file

    monkeypatch.setattr(shell_social_connector, "_path_is_writable", fake_writable)

    assert shell_social_connector._connections_file() != home_file


def test_social_connector_saves_connections_to_configured_file(monkeypatch, tmp_path):
    target = tmp_path / "connections.json"
    monkeypatch.setenv("SHELL_SOCIAL_CONNECTIONS_FILE", str(target))

    import shell_social_connector

    module = importlib.reload(shell_social_connector)
    connector = module.SocialMediaConnector()
    connector.connections["telegram"]["connected"] = False
    connector._save_connections()

    assert json.loads(target.read_text(encoding="utf-8"))["telegram"]["connected"] is False
