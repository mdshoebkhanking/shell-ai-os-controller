@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo.
echo ============================================================
echo  Shell AI OS Controller - Public Release Check
echo ============================================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  py -3.13 tools\production_release_check.py
  if %errorlevel%==0 py -3.13 tools\package_public_release.py
  if %errorlevel%==0 py -3.13 tools\production_readiness.py --run-tests
  if %errorlevel%==0 goto done
  py -3.12 tools\production_release_check.py
  if %errorlevel%==0 py -3.12 tools\package_public_release.py
  if %errorlevel%==0 py -3.12 tools\production_readiness.py --run-tests
  if %errorlevel%==0 goto done
  py -3.11 tools\production_release_check.py
  if %errorlevel%==0 py -3.11 tools\package_public_release.py
  if %errorlevel%==0 py -3.11 tools\production_readiness.py --run-tests
  if %errorlevel%==0 goto done
  py -3.10 tools\production_release_check.py
  if %errorlevel%==0 py -3.10 tools\package_public_release.py
  if %errorlevel%==0 py -3.10 tools\production_readiness.py --run-tests
  if %errorlevel%==0 goto done
)

python tools\production_release_check.py
if not %errorlevel%==0 goto failed
python tools\package_public_release.py
if not %errorlevel%==0 goto failed
python tools\production_readiness.py --run-tests
if not %errorlevel%==0 goto failed

:done
echo.
echo Public release package created in dist.
pause
exit /b 0

:failed
echo.
echo Public release checks failed. Open .shell_runtime\production_release_report.json for details.
pause
exit /b 2
