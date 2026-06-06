@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Shell AI One-Click Install
color 0B
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SHELL_TTS_ENGINE=fast"
set "SHELL_LEGACY_UI=0"
set "SHELL_V2_STREAM=1"
set "SHELL_IMAGE_LOCAL_FALLBACK=1"
set "SHELL_WINDOWS_MIN_VOLUME=65"
set "SHELL_WINDOWS_PERFORMANCE_MODE=balanced"
set "SHELL_OFFLINE_LLM_CONTEXT=1024"
set "SHELL_OFFLINE_LLM_BATCH=64"
set "SHELL_OFFLINE_LLM_MAX_TOKENS=160"
set "OPENBLAS_NUM_THREADS=1"
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
set "NUMEXPR_NUM_THREADS=1"
call :refresh_path

echo.
echo ============================================================
echo  Shell AI OS Controller - One-Click Installer
echo ============================================================
echo  This will automatically:
echo   - find or install Python 3.10+
echo   - create the managed .shellai_venv virtual environment
echo   - install Python requirements
echo   - install all UI requirements from shell_ui\requirements_ui.txt
echo   - install and build the React Shell Web UI in shell_web_ui
echo   - install Playwright Chromium
echo   - install ffmpeg, OCR, uv/uvx, and Node.js 20.19+/22.12+ where winget supports it
echo   - keep image generation usable with local fallback if cloud image APIs are not configured
echo   - create .env and runtime folders
echo   - run health checks
echo.

set "PY_CMD="
call :choose_python

if not defined PY_CMD (
  echo Compatible Python was not found. Trying winget Python 3.13 install...
  winget install --id Python.Python.3.13 -e --accept-source-agreements --accept-package-agreements
  call :refresh_path
  call :choose_python
)

if not defined PY_CMD (
  echo.
  echo Python install failed or compatible Python is still unavailable.
  echo Install Python 3.10+ from https://www.python.org/downloads/ and tick "Add Python to PATH".
  echo Then run ONE_CLICK_INSTALL.bat again.
  pause
  exit /b 1
)

echo Using Python command: !PY_CMD!
echo.
%PY_CMD% installer\bootstrap.py install --yes
set "SHELL_RC=%ERRORLEVEL%"

echo.
if "%SHELL_RC%"=="0" (
  echo ============================================================
  echo  Install complete.
  echo  Now double-click Start_ShellAI.bat to open Shell AI.
  echo  Optional final check: Run_Windows_Acceptance_Test.bat
  echo ============================================================
) else (
  echo ============================================================
  echo  Install finished with problems. Exit code: %SHELL_RC%
  echo  Run Repair_ShellAI.bat, then Start_ShellAI.bat.
  echo  Health report: .shell_runtime\install_health.json
  echo ============================================================
)
echo.
pause
endlocal & exit /b %SHELL_RC%

:choose_python
for %%V in (3.13 3.12 3.11 3.10) do (
  py -%%V --version >nul 2>&1
  if not errorlevel 1 (
    set "PY_CMD=py -%%V"
    goto :eof
  )
)
python --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=python"
goto :eof

:refresh_path
set "PATH=%ProgramFiles%\nodejs;%ProgramFiles(x86)%\nodejs;%LOCALAPPDATA%\Microsoft\WinGet\Links;%USERPROFILE%\.local\bin;%APPDATA%\Python\Scripts;%PATH%"
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$machine=[Environment]::GetEnvironmentVariable('Path','Machine'); $user=[Environment]::GetEnvironmentVariable('Path','User'); Write-Output ($machine + ';' + $user)" 2^>nul`) do set "PATH=%%P;%PATH%"
goto :eof
