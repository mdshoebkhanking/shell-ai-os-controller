@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Shell AI Launcher
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SHELL_TTS_ENGINE=fast"
set "SHELL_V2_STREAM=1"
set "SHELL_LEGACY_UI=0"
set "SHELL_WINDOWS_MIN_VOLUME=65"

set "LOG_DIR=%CD%\.shell_runtime\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

set "PY_CMD="
call :choose_python

if not defined PY_CMD (
  echo Compatible Python is missing. Trying winget install...
  winget install --id Python.Python.3.13 -e --accept-source-agreements --accept-package-agreements
  call :choose_python
  if not defined PY_CMD (
    echo Python install failed or PATH has not refreshed. Reopen this launcher after installing Python 3.10+.
    pause
    exit /b 1
  )
)

echo.
echo Starting Shell AI...
echo Root: %CD%
echo Python: !PY_CMD!
echo Logs:
echo   %LOG_DIR%\hub.log
echo   %LOG_DIR%\ui.log
echo.

%PY_CMD% installer\bootstrap.py launch --repair-if-needed
set "SHELL_RC=%ERRORLEVEL%"
if not "%SHELL_RC%"=="0" (
  echo.
  echo Shell AI could not start. Exit code: %SHELL_RC%
  echo.
  echo Last UI log lines:
  if exist "%LOG_DIR%\ui.log" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -Path '%LOG_DIR%\ui.log' -Tail 80" 2>nul
  ) else (
    echo   ui.log not found.
  )
  echo.
  echo Last Hub log lines:
  if exist "%LOG_DIR%\hub.log" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -Path '%LOG_DIR%\hub.log' -Tail 80" 2>nul
  ) else (
    echo   hub.log not found.
  )
  echo.
  echo Run Repair_ShellAI.bat, then Start_ShellAI.bat again.
  pause
  exit /b %SHELL_RC%
)
endlocal
exit /b 0

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
