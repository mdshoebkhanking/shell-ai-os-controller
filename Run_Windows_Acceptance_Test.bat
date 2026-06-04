@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Shell AI Windows Acceptance Test
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SHELL_TTS_ENGINE=fast"
set "SHELL_V2_STREAM=1"
set "SHELL_LEGACY_UI=0"
set "SHELL_IMAGE_LOCAL_FALLBACK=1"
set "SHELL_WINDOWS_MIN_VOLUME=65"
call :refresh_path

echo.
echo ============================================================
echo  Shell AI OS Controller - Windows Fresh Install/UAT Test
echo ============================================================
echo  This will:
echo   - create/repair the managed virtual environment
echo   - install dependencies using the normal one-click bootstrap
echo   - run health, hub, UI, voice, and Windows-MCP readiness probes
echo   - verify image-provider/fallback readiness in install health
echo   - write .shell_runtime\windows_acceptance_report.json
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
  echo Python setup failed. Install Python 3.10+ and tick "Add Python to PATH", then run this again.
  pause
  exit /b 1
)

echo Using Python command: !PY_CMD!
echo.
%PY_CMD% installer\bootstrap.py install --yes
if not "%ERRORLEVEL%"=="0" (
  echo.
  echo Install/repair failed. Report: .shell_runtime\install_health.json
  pause
  exit /b 2
)

echo.
echo Running Windows acceptance probe...
%PY_CMD% tools\windows_acceptance_probe.py --visible-ui-probe
set "PROBE_RC=%ERRORLEVEL%"

echo.
echo ============================================================
echo  Manual visible UI checks
echo ============================================================
echo  1. Double-click Start_ShellAI.bat.
echo  2. In Chat, ask: open calculator
echo  3. Then ask: close calculator
echo  4. Ask a normal text question and confirm reply is text-only.
echo  5. Open Voice page, start voice, and confirm audio is audible.
echo  6. Settings: add a test API key, restart, confirm it persists.
echo.
echo Automated report:
echo   .shell_runtime\windows_acceptance_report.json
echo.
pause
endlocal & exit /b %PROBE_RC%

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
