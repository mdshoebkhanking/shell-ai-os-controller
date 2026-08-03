"""Standalone automated E2E test runner for Shell AI.

Runs E2E environment checks, startup diagnostics, tool discovery catalog checks,
NL router validations, system health diagnostics, and invokes the E2E sanity pytest suite.
Produces a final JSON execution report.
"""
import os
import sys
import json
import time
import asyncio
import subprocess
from pathlib import Path

# Reconfigure stdout and stderr to handle UTF-8 symbols cleanly on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Insert project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


async def run_checks():
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "PASS",
        "failures": [],
        "sections": {}
    }
    
    print("=" * 80)
    print(" SHELL AI - AUTOMATED E2E WINDOWS TEST PLAN RUNNER")
    print("=" * 80)
    
    # -------------------------------------------------------------
    # 1. Startup & Environment Check
    # -------------------------------------------------------------
    print("\n[1] Environment & Configuration Check...")
    env_ok = True
    env_details = {}
    
    gkey = os.environ.get("GOOGLE_API_KEY", "")
    env_details["GOOGLE_API_KEY_set"] = bool(gkey)
    if not gkey:
        env_ok = False
        report["failures"].append("GOOGLE_API_KEY is not set.")
        
    lk_key = os.environ.get("LIVEKIT_API_KEY", "")
    lk_secret = os.environ.get("LIVEKIT_API_SECRET", "")
    lk_url = os.environ.get("LIVEKIT_URL", "")
    env_details["LIVEKIT_configured"] = bool(lk_key and lk_secret and lk_url)
    if not env_details["LIVEKIT_configured"]:
        env_ok = False
        report["failures"].append("LiveKit credentials (voice) are incomplete.")
        
    env_details["VOICE_NAME"] = os.environ.get("VOICE_NAME", "Aoede")
    
    from core.health.startup import run_startup_diagnostics
    diag = run_startup_diagnostics()
    env_details["startup_diagnostics"] = diag
    if diag["status"] != "success":
        env_ok = False
        report["failures"].append("Startup diagnostics returned fail status.")
        
    report["sections"]["1_environment"] = {
        "ok": env_ok,
        "details": env_details
    }
    print(f"    Status: {'PASS' if env_ok else 'FAIL'}")
    
    # -------------------------------------------------------------
    # 2. Tool Catalog Check
    # -------------------------------------------------------------
    print("\n[2] Tool Discovery Catalog Check...")
    catalog_ok = True
    catalog_details = {}
    
    try:
        from shell_tool_catalog import discover_tool_catalog
        tools = discover_tool_catalog(".")
        catalog_details["total_tools"] = len(tools)
        if len(tools) <= 100:
            catalog_ok = False
            report["failures"].append(f"Tool catalog size too small: {len(tools)} tools discovered.")
        else:
            catalog_details["sample_tools"] = [t["id"] for t in tools[:5]]
    except Exception as exc:
        catalog_ok = False
        catalog_details["error"] = f"{type(exc).__name__}: {exc}"
        report["failures"].append("Tool discovery raised an exception.")
        
    report["sections"]["2_tool_catalog"] = {
        "ok": catalog_ok,
        "details": catalog_details
    }
    print(f"    Discovered: {catalog_details.get('total_tools', 0)} tools")
    print(f"    Status: {'PASS' if catalog_ok else 'FAIL'}")
    
    # -------------------------------------------------------------
    # 3. Router Integration Check
    # -------------------------------------------------------------
    print("\n[3] NL Router Intent Routing Check...")
    router_ok = True
    router_details = {"routed": 0, "total": 0, "results": []}
    
    try:
        from shell_nl_router import route_natural_command
        test_prompts = [
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
        
        router_details["total"] = len(test_prompts)
        for prompt, expected in test_prompts:
            route = route_natural_command(prompt)
            if route and route["tool"] == expected:
                router_details["routed"] += 1
                router_details["results"].append({
                    "prompt": prompt,
                    "expected": expected,
                    "actual": route["tool"],
                    "confidence": route["confidence"],
                    "ok": True
                })
            else:
                actual_tool = route["tool"] if route else "None (Passthrough)"
                router_details["results"].append({
                    "prompt": prompt,
                    "expected": expected,
                    "actual": actual_tool,
                    "confidence": route["confidence"] if route else 0.0,
                    "ok": False
                })
                router_ok = False
                report["failures"].append(f"Prompt '{prompt}' misrouted to {actual_tool} (expected: {expected})")
    except Exception as exc:
        router_ok = False
        router_details["error"] = f"{type(exc).__name__}: {exc}"
        report["failures"].append("NL Router evaluation raised an exception.")
        
    report["sections"]["3_router"] = {
        "ok": router_ok,
        "details": router_details
    }
    print(f"    Routed: {router_details['routed']}/{router_details['total']}")
    print(f"    Status: {'PASS' if router_ok else 'FAIL'}")
    
    # -------------------------------------------------------------
    # 4. Voice Configuration Check
    # -------------------------------------------------------------
    print("\n[4] Voice Configuration Check...")
    voice_ok = True
    voice_details = {}
    
    try:
        from shell_voice import diagnostics
        diag_voice = diagnostics()
        voice_details["diagnostics"] = diag_voice
        if diag_voice.get("resolved_voice") != "Aoede":
            voice_ok = False
            report["failures"].append(f"Voice name resolved to {diag_voice.get('resolved_voice')} (expected: Aoede)")
    except Exception as exc:
        voice_ok = False
        voice_details["error"] = f"{type(exc).__name__}: {exc}"
        report["failures"].append("Voice diagnostics raised an exception.")
        
    report["sections"]["4_voice"] = {
        "ok": voice_ok,
        "details": voice_details
    }
    print(f"    Voice: {voice_details.get('diagnostics', {}).get('resolved_voice', 'None')}")
    print(f"    Status: {'PASS' if voice_ok else 'FAIL'}")
    
    # -------------------------------------------------------------
    # 5. System Health Scan
    # -------------------------------------------------------------
    print("\n[5] System Health Scan...")
    health_ok = True
    health_details = {}
    
    try:
        from shell_diagnostics import scan_system_health
        health_report = await scan_system_health()
        health_details["report"] = health_report
        
        # Parse CPU and RAM percentages from the text report
        cpu_usage = "N/A"
        ram_percent = "N/A"
        for line in health_report.splitlines():
            if "CPU:" in line:
                parts = line.split("CPU:")
                if len(parts) > 1:
                    cpu_usage = parts[1].split("%")[0].strip()
            if "RAM:" in line:
                parts = line.split("(")
                if len(parts) > 1:
                    ram_percent = parts[1].split("%")[0].strip()
        
        health_details["metrics"] = {
            "cpu_percent": cpu_usage,
            "ram_percent": ram_percent
        }
        print(f"    CPU Usage: {cpu_usage}%")
        print(f"    Memory Usage: {ram_percent}%")
    except Exception as exc:
        health_ok = False
        health_details["error"] = f"{type(exc).__name__}: {exc}"
        report["failures"].append("System health scan raised an exception.")
        
    report["sections"]["5_system_health"] = {
        "ok": health_ok,
        "details": health_details
    }
    print(f"    Status: {'PASS' if health_ok else 'FAIL'}")
    
    # -------------------------------------------------------------
    # 6. Pytest Sanity Suite Execution
    # -------------------------------------------------------------
    print("\n[6] Running Pytest Sanity Suite...")
    pytest_ok = True
    pytest_details = {}
    
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_e2e_windows_sanity.py", "-v"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=90
        )
        pytest_details["stdout"] = proc.stdout
        pytest_details["returncode"] = proc.returncode
        if proc.returncode != 0:
            pytest_ok = False
            report["failures"].append("Sanity Pytest suite run failed.")
            print(proc.stdout)
    except Exception as exc:
        pytest_ok = False
        pytest_details["error"] = f"{type(exc).__name__}: {exc}"
        report["failures"].append("Pytest execution raised an exception.")
        
    report["sections"]["6_pytest_sanity"] = {
        "ok": pytest_ok,
        "details": pytest_details
    }
    print(f"    Pytest exit code: {pytest_details.get('returncode', -1)}")
    print(f"    Status: {'PASS' if pytest_ok else 'FAIL'}")
    
    # -------------------------------------------------------------
    # Final Compilation
    # -------------------------------------------------------------
    all_ok = env_ok and catalog_ok and router_ok and voice_ok and health_ok and pytest_ok
    report["status"] = "PASS" if all_ok else "FAIL"
    
    print("\n" + "=" * 80)
    print(f" FINAL STATUS: {report['status']}")
    print(f" Total Failures: {len(report['failures'])}")
    print("=" * 80)
    
    out_dir = PROJECT_ROOT / ".shell_runtime"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "e2e_execution_report.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report JSON written to: {report_file}")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run_checks()))
