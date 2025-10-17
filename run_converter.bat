@echo off
REM Enhanced Document Converter v2.1 - Windows Quick Start Script
REM This script sets up the virtual environment, installs dependencies,
REM and launches the document converter.

setlocal enabledelayedexpansion

echo ============================================================
echo   Enhanced Document Converter v2.1 - Setup and Launch
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo [1/5] Checking Python version...
python --version

REM Check/create virtual environment
if not exist "env" (
    echo.
    echo [2/5] Creating virtual environment...
    python -m venv env
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
) else (
    echo.
    echo [2/5] Virtual environment already exists.
)

REM Upgrade pip, setuptools, and wheel
echo.
echo [3/5] Upgrading pip, setuptools, and wheel...
env\Scripts\python.exe -m pip install --upgrade pip setuptools wheel > logs\pip_install.log 2>&1
if errorlevel 1 (
    echo WARNING: Failed to upgrade pip
)

REM Install/upgrade dependencies
echo.
echo [4/5] Installing dependencies (this may take a few minutes)...
echo This process is logged to logs\pip_install.log

REM Install with progress indication
set "counter=0"
for %%i in (markitdown mistralai python-dotenv pdfplumber camelot-py[cv] pdf2image Pillow beautifulsoup4 lxml python-docx python-pptx xlrd openpyxl requests urllib3 aiofiles psutil ffmpeg-python opencv-python ghostscript PyPDF2 tabulate) do (
    set /a counter+=1
    echo Installing package !counter! of 22...
    env\Scripts\python.exe -m pip install "%%i" >> logs\pip_install.log 2>&1
)

echo.
echo [5/5] Verifying installation...
env\Scripts\python.exe -m pip check > logs\pip_check.log 2>&1
if errorlevel 1 (
    echo WARNING: Some package conflicts detected. See logs\pip_check.log
) else (
    echo All packages installed successfully.
)

REM Save installed versions
env\Scripts\python.exe -m pip list > logs\installed_versions.txt 2>&1
echo Installed package versions saved to logs\installed_versions.txt

echo.
echo ============================================================
echo   Setup complete! Launching Document Converter...
echo ============================================================
echo.

REM Check for .env file
if not exist ".env" (
    if exist ".env.example" (
        echo WARNING: .env file not found
        echo Please copy .env.example to .env and configure your API keys
        echo.
        echo Would you like to create .env from .env.example now? (Y/N)
        set /p create_env=
        if /i "!create_env!"=="Y" (
            copy .env.example .env
            echo .env file created. Please edit it with your API keys.
            echo Opening .env file in notepad...
            notepad .env
            echo.
            echo After saving your changes, press any key to continue...
            pause >nul
        )
    )
)

REM Launch the application
env\Scripts\python.exe main.py %*

REM Pause if there was an error
if errorlevel 1 (
    echo.
    echo ============================================================
    echo   An error occurred. Press any key to exit...
    echo ============================================================
    pause >nul
)

endlocal
