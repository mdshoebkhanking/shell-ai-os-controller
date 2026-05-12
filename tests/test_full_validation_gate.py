from __future__ import annotations

from tools.full_validation import build_steps


def test_full_validation_gate_covers_release_blockers() -> None:
    names = [step.name for step in build_steps("python")]

    assert names[0] == "unit_and_regression_tests"
    assert "ui_e2e_probe" in names
    assert "latency_probe_ui" in names
    assert "memory_probe_ui_tts" in names
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
