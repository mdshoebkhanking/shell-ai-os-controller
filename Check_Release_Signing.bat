@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Shell AI Signing Readiness
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PY_CMD="
for %%V in (3.13 3.12 3.11 3.10) do (
  py -%%V --version >nul 2>&1
  if not errorlevel 1 (
    set "PY_CMD=py -%%V"
    goto run
  )
)
python --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=python"

:run
if not defined PY_CMD (
  echo Python 3.10+ is required for this check.
  pause
  exit /b 1
)

%PY_CMD% tools\signing_notarization_check.py --strict
set "RC=%ERRORLEVEL%"
echo.
echo Report: .shell_runtime\signing_notarization_report.json
pause
endlocal & exit /b %RC%
