@echo off
cd /d "%~dp0"
title SHELL DEBUG MODE
color 0C
cls

echo ==================================================
echo   SHELL A.I. EMERGENCY DEBUGGER
echo ==================================================
echo.

echo [1/4] Checking Python Environment...
set "PYTHON="
if exist "venv\Scripts\python.exe" (
    echo    [OK] Venv Python found
    "venv\Scripts\python.exe" --version
    set "PYTHON=venv\Scripts\python.exe"
) else (
    echo    [WARN] venv not found. Checking system Python...
    python --version >nul 2>&1
    if errorlevel 1 (
        echo    [ERROR] No Python found! Install Python first.
        pause
        exit /b 1
    )
    python --version
    set "PYTHON=python"
)

echo.
echo [2/4] Testing Imports...
%PYTHON% -c "from dotenv import load_dotenv; print('  dotenv OK')"
%PYTHON% -c "from shell_config import config; print('  shell_config OK')"
%PYTHON% -c "from shell_safe_executor import god_tier_tool; print('  shell_safe_executor OK')"
%PYTHON% -c "import livekit; print('  livekit OK')" 2>&1
if %errorlevel% neq 0 (
    echo    [WARN] Some imports may have failed. Continuing anyway...
)

echo.
echo [3/4] Launching Components...

echo    -> Starting Hub...
start "Shell Hub" /min %PYTHON% shell_hub.py

echo    -> Windows-MCP is on-demand via uvx windows-mcp
echo       Legacy Shell MCP server is not started in this flow.

echo.
echo [4/4] Starting Agent (CONSOLE MODE)...
echo    If this crashes, send the error below.
echo --------------------------------------------------
%PYTHON% agent.py console
echo --------------------------------------------------
echo.
echo    AGENT STOPPED.
pause
