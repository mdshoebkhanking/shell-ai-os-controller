from __future__ import annotations

import json


def test_platform_supervisor_snapshot_covers_ai_os_domains():
    from core.platform_supervisor import build_platform_snapshot

    snapshot = build_platform_snapshot(include_catalog=False)
    domains = {domain["name"]: domain for domain in snapshot["domains"]}

    assert snapshot["profile"] == "realtime_ai_os"
    assert snapshot["status"] in {"ready", "optimal", "attention"}
    assert snapshot["score"] >= 70
    assert {
        "realtime",
        "voice",
        "agents",
        "memory",
        "multimodal",
        "packaging",
        "hybrid_runtime",
    }.issubset(domains)
    assert domains["voice"]["metrics"]["gemini_voice"] == "Aoede"
    assert domains["voice"]["metrics"]["premium_voice_first"] is True
    assert domains["agents"]["metrics"]["risky_terminal_blocked"] is True


def test_platform_supervisor_tool_is_redacted(monkeypatch):
    import shell_platform_supervisor

    monkeypatch.setenv("GOOGLE_API_KEY", "secret-value-that-must-not-leak")
    payload = shell_platform_supervisor.shell_platform_status(include_catalog=False)
    data = json.loads(payload)

    assert data["profile"] == "realtime_ai_os"
    assert "secret-value-that-must-not-leak" not in payload


def test_platform_status_is_cataloged_as_system_capability():
    from shell_tool_catalog import discover_tool_catalog

    rows = {
        row["id"]: row
        for row in discover_tool_catalog()
        if row["id"].startswith("shell_platform_supervisor:")
    }

    tool = rows["shell_platform_supervisor:shell_platform_status_tool"]
    assert tool["kind"] == "tool"
    assert tool["category"] == "system"


def test_natural_platform_status_route():
    from shell_nl_router import route_natural_command

    route = route_natural_command("show shell platform health")

    assert route["tool"] == "shell_platform_supervisor:shell_platform_status_tool"
    assert route["args"] == {"include_catalog": True}
