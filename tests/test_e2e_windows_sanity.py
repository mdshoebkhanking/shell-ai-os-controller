"""E2E Windows Sanity Tests for Shell AI."""
import os
import sys
import asyncio
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env variables
load_dotenv(PROJECT_ROOT / ".env")


def test_e2e_env_variables():
    """Verify that the key environment variables required by Shell AI are present."""
    # Google API Key is critical for Gemini brain
    gkey = os.environ.get("GOOGLE_API_KEY", "")
    assert gkey, "GOOGLE_API_KEY is not set in environment or .env"
    assert gkey.startswith("AIzaSy"), "GOOGLE_API_KEY does not look like a Google API Key"

    # LiveKit credentials for real-time voice
    lk_key = os.environ.get("LIVEKIT_API_KEY", "")
    lk_secret = os.environ.get("LIVEKIT_API_SECRET", "")
    lk_url = os.environ.get("LIVEKIT_URL", "")
    
    # Check if voice is configured
    voice_configured = bool(lk_key and lk_secret and lk_url)
    assert voice_configured, "LiveKit credentials (LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL) are not set"


def test_e2e_startup_diagnostics():
    """Run backend startup diagnostics and verify platform/safety readiness."""
    from core.health.startup import run_startup_diagnostics
    
    diag = run_startup_diagnostics()
    assert diag["status"] == "success", f"Startup diagnostics failed: {diag}"
    assert "platform" in diag
    assert "dependencies" in diag
    assert "safety" in diag
    assert "summary" in diag


def test_e2e_tool_catalog():
    """Ensure that the tool catalog discovers a healthy number of tools (>100)."""
    from shell_tool_catalog import discover_tool_catalog
    
    tools = discover_tool_catalog(".")
    assert len(tools) > 100, f"Discovered only {len(tools)} tools. Expecting >100."
    
    # Check for crucial tool groups
    tool_ids = {t["id"] for t in tools}
    assert "shell_window_CTRL:open_app" in tool_ids
    assert "shell_window_CTRL:close_app" in tool_ids
    assert "shell_desktop_tools:desktop_click_tool" in tool_ids
    assert "shell_screenshot:take_screenshot_tool" in tool_ids
    assert "shell_workspace_tools:list_workspace_files_tool" in tool_ids
    assert "shell_calculator:calculate_tool" in tool_ids


def test_e2e_nl_router_routing():
    """Verify routing of critical intents by the NL Router."""
    from shell_nl_router import route_natural_command
    
    cases = [
        ("open Notepad", "shell_window_CTRL:open_app"),
        ("play Arijit Singh on YouTube", "shell_browser_CTRL:play_youtube_video"),
        ("what is 25 * 48", "shell_calculator:calculate_tool"),
        ("generate image of a sunset", "shell_image_ai:generate_image_tool"),
        ("create a snake game", "shell_game_builder:build_game_tool"),
        ("send email to test@test.com subject Hello body Hi there", "shell_email_tool:send_email_tool"),
        ("scan system health", "shell_platform_supervisor:shell_platform_status_tool"),
        ("take a screenshot", "shell_screenshot:take_screenshot_tool"),
        ("list workspace files", "shell_workspace_tools:list_workspace_files_tool"),
        ("open Instagram", "shell_desktop_tools:open_url_tool"),
        ("voice status", "shell_neural_voice:shell_streaming_voice_status_tool"),
        ("email setup status", "shell_email_tool:email_setup_status_tool"),
    ]
    
    for prompt, expected_tool in cases:
        route = route_natural_command(prompt)
        assert route is not None, f"Failed to route prompt: '{prompt}'"
        assert route["tool"] == expected_tool, f"Prompt '{prompt}' routed to {route['tool']} instead of {expected_tool}"
        assert route["confidence"] >= 0.80, f"Low confidence ({route['confidence']}) for prompt: '{prompt}'"


def test_e2e_voice_diagnostics():
    """Verify local voice configuration and hardware availability snapshot."""
    from shell_voice import diagnostics
    
    diag_res = diagnostics()
    assert isinstance(diag_res, dict)
    assert "resolved_voice" in diag_res
    assert "resolved_persona" in diag_res
    assert "catalog_size" in diag_res
    
    # Check that Aoede voice is configured
    assert diag_res["resolved_voice"] == "Aoede"


@pytest.mark.asyncio
async def test_e2e_system_health_scan():
    """Verify that the platform health supervisor scan executes without errors."""
    from shell_diagnostics import scan_system_health
    
    health_report = await scan_system_health()
    
    assert "SYSTEM DIAGNOSTIC REPORT" in health_report
    assert "CPU" in health_report
    assert "RAM" in health_report
    assert "Conclusion" in health_report
