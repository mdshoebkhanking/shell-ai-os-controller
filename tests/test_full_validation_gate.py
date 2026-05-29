from __future__ import annotations

import sys

from tools.full_validation import ValidationStep, build_steps, run_step


def test_full_validation_gate_covers_release_blockers() -> None:
    names = [step.name for step in build_steps("python")]

    assert names[0] == "unit_and_regression_tests"
    assert "ui_e2e_probe" in names
    assert "latency_probe_ui" in names
    assert "memory_probe_ui_tts" in names
    latency_step = next(step for step in build_steps("python") if step.name == "latency_probe_ui")
    assert "--provider-runtime" in latency_step.command
    memory_step = next(step for step in build_steps("python") if step.name == "memory_probe_ui_tts")
    assert "--listener" in memory_step.command
    assert "--realtime" in memory_step.command
    assert "--network" in memory_step.command
    assert "--ai-runtime" in memory_step.command
    assert "--provider-runtime" in memory_step.command
    assert "--provider-transport" in memory_step.command
    assert "strict_public_release_check" in names
    assert "config_diagnostics" in names
    assert "build_public_release_package" in names
    assert "production_readiness" in names
    assert "public_github_launch_audit" in names
    assert "ecosystem_master_audit" in names


def test_full_validation_gate_uses_selected_python() -> None:
    steps = build_steps("/tmp/shell-python")

    assert all(step.command[0] == "/tmp/shell-python" for step in steps)
    assert all(step.required for step in steps)


def test_full_validation_steps_use_isolated_shellai_config(monkeypatch) -> None:
    monkeypatch.setenv("SHELLAI_CONFIG", "/Users/example/.shellai/config.json")
    probe = (
        "import os; "
        "from pathlib import Path; "
        "path = os.environ.get('SHELLAI_CONFIG', ''); "
        "print(path); "
        "parts = Path(path).parts; "
        "raise SystemExit(0 if parts[-3:] == ('.shell_runtime', 'full_validation_shellai', 'config.json') else 7)"
    )
    result = run_step(ValidationStep("env_probe", (sys.executable, "-c", probe), 10))

    assert result["status"] == "pass"
    assert "full_validation_shellai" in result["output_tail"]
