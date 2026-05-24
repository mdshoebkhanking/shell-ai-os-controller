import os
import subprocess
import sys
from pathlib import Path


def test_pyqtgraph_chart_backend_has_flag_and_legacy_backup():
    source = Path("shell_ui/shell_cinematic_full.py").read_text(encoding="utf-8")

    assert "SHELL_PYQTGRAPH_ENABLED" in source
    assert "class PyQtGraphLineChart" in source
    assert "class _LegacyLiveLineChart" in source
    assert "SYSTEM_CHART_BACKEND" in source


def test_live_line_chart_selected_backend_keeps_runtime_api():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from shell_ui.shell_cinematic_full import LiveLineChart, SYSTEM_CHART_BACKEND

    chart = LiveLineChart("CPU usage", "%", value_max=100.0)
    try:
        chart.push(42)
        chart._tick()
        chart.advance()

        assert SYSTEM_CHART_BACKEND in {"pyqtgraph", "legacy_qpainter"}
        assert hasattr(chart, "_t")
        assert chart._t is not None
    finally:
        if hasattr(chart, "stop"):
            chart.stop()
        elif hasattr(chart, "_t"):
            chart._t.stop()
        chart.deleteLater()
        app.processEvents()


def test_pyqtgraph_chart_backend_can_be_disabled_with_env_flag():
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SHELL_PYQTGRAPH_ENABLED"] = "0"
    env.setdefault("PYTHONPYCACHEPREFIX", "/private/tmp/shell_pycache")

    output = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "from shell_ui.shell_cinematic_full import SYSTEM_CHART_BACKEND; print(SYSTEM_CHART_BACKEND)",
        ],
        env=env,
        text=True,
    )

    assert output.strip() == "legacy_qpainter"
