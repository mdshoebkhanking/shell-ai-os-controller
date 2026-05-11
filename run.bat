@echo off
setlocal
cd /d "%~dp0"
title Shell AI

echo run.bat now uses the production launcher.
echo.
call "%~dp0Start_ShellAI.bat"
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
