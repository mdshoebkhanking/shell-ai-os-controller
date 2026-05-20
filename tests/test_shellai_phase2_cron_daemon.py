from __future__ import annotations


def _config(tmp_path, monkeypatch=None):
    from shellai.config import ShellAIConfig, ShellAIPaths

    path = tmp_path / ".shellai" / "config.json"
    if monkeypatch is not None:
        monkeypatch.setenv("SHELLAI_CONFIG", str(path))
    config = ShellAIConfig.load(path)
    config.paths = ShellAIPaths.from_config_path(path)
    config.paths.ensure_runtime_dirs()
    return config


def test_cron_registry_dry_run_and_idempotent_execution(tmp_path) -> None:
    from shellai.cron import list_jobs, run_job
    from shellai.memory import MemoryStore

    config = _config(tmp_path)
    memory = MemoryStore(tmp_path / "memory.sqlite3", config=config)
    jobs = {job["name"] for job in list_jobs()}
    assert {"memory_maintenance", "skill_usage_report", "trace_cleanup"} <= jobs

    dry = run_job("skill_usage_report", dry_run=True, config=config, memory_store=memory)
    assert dry["status"] == "ok"
    assert dry["dry_run"] is True

    first = run_job("trace_cleanup", dry_run=False, config=config, memory_store=memory)
    second = run_job("trace_cleanup", dry_run=False, config=config, memory_store=memory)
    assert first["status"] == "ok"
    assert second["status"] == "ok"


def test_daemon_enqueue_process_and_stop(monkeypatch, tmp_path) -> None:
    from shellai.daemon import ShellAIDaemon

    config = _config(tmp_path, monkeypatch)
    monkeypatch.setenv("SHELLAI_DAEMON_ENABLED", "1")
    daemon = ShellAIDaemon(config)

    started = daemon.start()
    assert started["running"] is True
    task = daemon.enqueue_task("!pwd", context={"cwd": str(tmp_path), "source": "test"})
    assert task["text"] == "!pwd"
    assert daemon.status()["queued_tasks"] == 1

    processed = daemon.process_all()
    assert len(processed) == 1
    assert processed[0]["result"]["status"] == "ok"
    assert daemon.status()["queued_tasks"] == 0

    stopped = daemon.stop()
    assert stopped["running"] is False


def test_daemon_start_disabled_by_default(monkeypatch, tmp_path) -> None:
    from shellai.daemon import ShellAIDaemon

    config = _config(tmp_path, monkeypatch)
    monkeypatch.delenv("SHELLAI_DAEMON_ENABLED", raising=False)
    status = ShellAIDaemon(config).start()

    assert status["enabled"] is False
    assert status["running"] is False


def test_phase2_cli_surfaces_smoke(monkeypatch, tmp_path, capsys) -> None:
    from shellai.cli import main

    _config(tmp_path, monkeypatch)

    assert main(["monitor", "--limit", "2"]) == 0
    assert "traces" in capsys.readouterr().out

    assert main(["optimize"]) == 0
    assert "suggestions" in capsys.readouterr().out

    assert main(["cron", "list"]) == 0
    assert "memory_maintenance" in capsys.readouterr().out

    assert main(["daemon", "status"]) == 0
    assert "queued_tasks" in capsys.readouterr().out
