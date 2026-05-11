@echo off
REM Shell Premium UI - Build Script
REM Creates standalone .exe file

echo ========================================
echo Shell Premium UI - Build System
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "..\..\venv" (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv ..\..\venv
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call ..\..\venv\Scripts\activate.bat

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements_ui.txt

REM Build .exe
echo.
echo Building .exe file...
echo This may take a few minutes...
pyinstaller --clean --noconfirm shell_ui.spec

REM Check if build was successful
if exist "dist\Shell_Premium_UI.exe" (
    echo.
    echo ========================================
    echo BUILD SUCCESSFUL!
    echo ========================================
    echo.
    echo Executable created: dist\Shell_Premium_UI.exe
    echo.
    echo You can now run the .exe file without Python installed!
    echo.
) else (
    echo.
    echo ========================================
    echo BUILD FAILED!
    echo ========================================
    echo Please check the error messages above.
    echo.
)

pause
