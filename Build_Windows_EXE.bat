@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Build Shell AI Windows EXE Installer
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "SHELL_TTS_ENGINE=fast"
set "SHELL_LEGACY_UI=0"
set "SHELL_V2_STREAM=1"
set "SHELL_IMAGE_LOCAL_FALLBACK=1"
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
echo  Shell AI OS Controller - Windows EXE Installer Build
echo ============================================================
echo  Output:
echo   dist\shell-ai-os-controller-setup-[VERSION].exe
echo.
echo  This will:
echo   - validate the release package inputs
echo   - build the React renderer
echo   - bundle ShellAI.exe with PyInstaller
echo   - stage a clean installer tree without secrets/runtime files
echo   - compile a Windows setup EXE with Inno Setup
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
  pause
  exit /b 1
)

where ISCC.exe >nul 2>nul
if errorlevel 1 (
  echo Inno Setup compiler was not found. Trying winget install...
  winget install --id JRSoftware.InnoSetup -e --accept-source-agreements --accept-package-agreements
  call :refresh_path
)

where ISCC.exe >nul 2>nul
if errorlevel 1 (
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "INNO_SETUP_COMPILER=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)
if not defined INNO_SETUP_COMPILER (
  if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "INNO_SETUP_COMPILER=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

echo Using Python command: !PY_CMD!
if defined INNO_SETUP_COMPILER echo Using Inno Setup compiler: !INNO_SETUP_COMPILER!
echo.

echo Preparing installer build environment...
%PY_CMD% installer\bootstrap.py repair --yes --skip-system
set "SHELL_RC=!ERRORLEVEL!"
if not "!SHELL_RC!"=="0" goto failed

echo Installing bundled offline LLM runtime...
%PY_CMD% -m pip install --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu llama-cpp-python
set "SHELL_RC=!ERRORLEVEL!"
if not "!SHELL_RC!"=="0" goto failed

echo Staging offline TTS assets...
%PY_CMD% tools\stage_kokoro_tts_assets.py --variant int8
set "SHELL_RC=!ERRORLEVEL!"
if not "!SHELL_RC!"=="0" goto failed

echo Offline LLM models are installed on demand from Shell Settings.

echo Staging offline STT assets...
%PY_CMD% tools\stage_sherpa_stt_assets.py
set "SHELL_RC=!ERRORLEVEL!"
if not "!SHELL_RC!"=="0" goto failed

%PY_CMD% tools\build_windows_installer.py --no-strict --installer-engine inno
set "SHELL_RC=!ERRORLEVEL!"

echo.
if "!SHELL_RC!"=="0" (
  echo ============================================================
  echo  Windows setup EXE created in dist.
  echo  Installer shortcuts launch ShellAIApp\ShellAI.exe.
  echo  Upload the setup EXE as the release asset for Settings updates.
  echo ============================================================
) else (
  goto failed
)
pause
endlocal & exit /b 0

:failed
echo.
echo ============================================================
echo  EXE build failed. Exit code: !SHELL_RC!
echo  Report: dist\windows_installer_package.json
echo ============================================================
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
set "PATH=%ProgramFiles%\NSIS;%ProgramFiles(x86)%\NSIS;%ProgramFiles%\Inno Setup 6;%ProgramFiles(x86)%\Inno Setup 6;%ProgramFiles%\nodejs;%ProgramFiles(x86)%\nodejs;%LOCALAPPDATA%\Microsoft\WinGet\Links;%USERPROFILE%\.local\bin;%APPDATA%\Python\Scripts;%PATH%"
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$machine=[Environment]::GetEnvironmentVariable('Path','Machine'); $user=[Environment]::GetEnvironmentVariable('Path','User'); Write-Output ($machine + ';' + $user)" 2^>nul`) do set "PATH=%%P;%PATH%"
goto :eof
