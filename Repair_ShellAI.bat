@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Repair Shell AI
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SHELL_TTS_ENGINE=fast"
set "SHELL_LEGACY_UI=0"
set "SHELL_WINDOWS_MIN_VOLUME=65"
set "PY_CMD="
call :choose_python
if not defined PY_CMD (
  winget install --id Python.Python.3.13 -e --accept-source-agreements --accept-package-agreements
  call :choose_python
)
if not defined PY_CMD (
  echo Compatible Python is still missing. Install Python 3.10+ and rerun this repair tool.
  pause
  exit /b 1
)
echo Repairing Shell AI with !PY_CMD!...
%PY_CMD% installer\bootstrap.py repair --yes
pause
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
