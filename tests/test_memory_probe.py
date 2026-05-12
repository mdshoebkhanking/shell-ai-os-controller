from __future__ import annotations


def test_memory_probe_report_shape_without_ui() -> None:
    from tools.memory_probe import build_report

    report = build_report(include_ui=False, include_tts=False)

    assert report["ok"] is True
    assert report["peak_rss_mb"] > 0
    names = [item["name"] for item in report["snapshots"]]
    assert names == [
        "process_start",
        "after_import_tool_catalog",
        "after_catalog_discovery",
        "after_calculator_tool",
        "after_catalog_stress",
        "after_tool_stress",
    ]
    for item in report["snapshots"]:
        assert "rss_mb" in item
        assert "delta_from_start_mb" in item
        assert "delta_from_previous_mb" in item


def test_memory_probe_tool_execution_is_successful() -> None:
    from tools.memory_probe import build_report

    report = build_report(include_ui=False, include_tts=False)
    tool_snapshot = next(item for item in report["snapshots"] if item["name"] == "after_calculator_tool")
    stress_snapshot = next(item for item in report["snapshots"] if item["name"] == "after_tool_stress")

    assert tool_snapshot["tool_result"]["status"] == "success"
    assert tool_snapshot["tool_result"]["has_result"] is True
    assert stress_snapshot["tool_result"]["status"] == "success"
    assert stress_snapshot["tool_result"]["iterations"] == 10


def test_memory_probe_listener_thread_cleanup() -> None:
    from tools.memory_probe import build_report

    report = build_report(include_ui=False, include_tts=False, include_listener=True, stress_iterations=1)
    listener_snapshot = next(item for item in report["snapshots"] if item["name"] == "after_listener_probe")

    assert listener_snapshot["listener"]["thread_cleaned_up"] is True
    assert listener_snapshot["listener"]["thread_count_after"] <= listener_snapshot["listener"]["thread_count_before"]


def test_memory_probe_realtime_thread_cleanup() -> None:
    from tools.memory_probe import build_report

    report = build_report(include_ui=False, include_tts=False, include_realtime=True, stress_iterations=1)
    realtime_snapshot = next(item for item in report["snapshots"] if item["name"] == "after_realtime_probe")
    realtime = realtime_snapshot["realtime"]

    assert realtime["started"] is True
    assert realtime["thread_cleaned_up"] is True
    assert realtime["thread_count_after"] <= realtime["thread_count_before"]
    assert realtime["modules_after"]["livekit_rtc"] is False


def test_memory_probe_network_thread_cleanup() -> None:
    from tools.memory_probe import build_report

    report = build_report(include_ui=False, include_tts=False, include_network=True, stress_iterations=1)
    network_snapshot = next(item for item in report["snapshots"] if item["name"] == "after_network_probe")
    network = network_snapshot["network"]

    assert network["connected_before_stop"] is True
    assert network["final_connected"] is False
    assert network["emit_ok"] is True
    assert network["thread_cleaned_up"] is True
    assert network["thread_count_after"] <= network["thread_count_before"]
    assert network["modules_after"] == network["modules_before"]


def test_memory_probe_ai_runtime_stays_lazy() -> None:
    from tools.memory_probe import build_report

    report = build_report(include_ui=False, include_tts=False, include_ai_runtime=True, stress_iterations=1)
    ai_snapshot = next(item for item in report["snapshots"] if item["name"] == "after_ai_runtime_probe")
    ai_runtime = ai_snapshot["ai_runtime"]

    assert ai_runtime["providers_loaded"] is False
    assert ai_runtime["metrics"]["loaded"] is False
    assert ai_runtime["modules_after"] == ai_runtime["modules_before"]
