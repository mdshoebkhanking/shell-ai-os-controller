@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SHELL_TTS_ENGINE=fast"
set "SHELL_LEGACY_UI=0"
set "SHELL_V2_STREAM=1"
set "SHELL_IMAGE_LOCAL_FALLBACK=1"
call :refresh_path

echo.
echo ============================================================
echo  Shell AI OS Controller - Public Release Check
echo ============================================================
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
  echo Python install failed or compatible Python is still unavailable.
  echo Install Python 3.10+ from https://www.python.org/downloads/ and tick "Add Python to PATH".
  set "SHELL_RC=1"
  goto failed
)

echo Using Python command: !PY_CMD!
echo.

echo Preparing release environment...
%PY_CMD% installer\bootstrap.py repair --yes --skip-system
set "SHELL_RC=!ERRORLEVEL!"
if not "!SHELL_RC!"=="0" goto failed

echo Running public release check...
%PY_CMD% tools\production_release_check.py
set "SHELL_RC=!ERRORLEVEL!"
if not "!SHELL_RC!"=="0" goto failed

echo Building public release zip...
%PY_CMD% tools\package_public_release.py
set "SHELL_RC=!ERRORLEVEL!"
if not "!SHELL_RC!"=="0" goto failed

echo Running production readiness tests...
set "SHELLAI_TEST_PYTHON=%CD%\.shellai_venv\Scripts\python.exe"
%PY_CMD% tools\production_readiness.py --run-tests
set "SHELL_RC=!ERRORLEVEL!"
if not "!SHELL_RC!"=="0" goto failed

:done
echo.
echo Public release package created in dist.
pause
endlocal & exit /b 0

:failed
echo.
echo Public release checks failed. Exit code: !SHELL_RC!
echo Public release checks failed. Open .shell_runtime\production_release_report.json for details.
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
