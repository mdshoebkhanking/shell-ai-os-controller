@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
title Shell AI Installer

call "%CD%\ONE_CLICK_INSTALL.bat"
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
