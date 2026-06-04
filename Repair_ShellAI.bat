@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Repair Shell AI
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SHELL_TTS_ENGINE=fast"
set "SHELL_LEGACY_UI=0"
set "SHELL_V2_STREAM=1"
set "SHELL_IMAGE_LOCAL_FALLBACK=1"
set "SHELL_WINDOWS_MIN_VOLUME=65"
call :refresh_path
set "PY_CMD="
call :choose_python
if not defined PY_CMD (
  winget install --id Python.Python.3.13 -e --accept-source-agreements --accept-package-agreements
  call :refresh_path
  call :choose_python
)
if not defined PY_CMD (
  echo Compatible Python is still missing. Install Python 3.10+ and rerun this repair tool.
  pause
  exit /b 1
)
echo Repairing Shell AI with !PY_CMD!...
%PY_CMD% installer\bootstrap.py repair --yes
set "SHELL_RC=%ERRORLEVEL%"
echo.
if "%SHELL_RC%"=="0" (
  echo Repair complete. Now run Start_ShellAI.bat.
) else (
  echo Repair finished with problems. Exit code: %SHELL_RC%
  echo Health report: .shell_runtime\install_health.json
)
pause
endlocal
exit /b %SHELL_RC%

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
