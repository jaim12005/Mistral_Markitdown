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

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

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

REM Install from requirements.txt (recommended approach)
echo Installing core dependencies from requirements.txt...
env\Scripts\python.exe -m pip install -r requirements.txt >> logs\pip_install.log 2>&1

REM Optional: Install development dependencies (uncomment if needed)
REM env\Scripts\python.exe -m pip install -r requirements-dev.txt >> logs\pip_install.log 2>&1

REM Optional: Install optional features (uncomment if needed)
REM env\Scripts\python.exe -m pip install -r requirements-optional.txt >> logs\pip_install.log 2>&1

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
echo   Setup complete!
echo ============================================================
echo.

REM Check for .env file
if not exist ".env" (
    echo.
    echo ============================================================
    echo   CONFIGURATION REQUIRED
    echo ============================================================
    echo.
    echo WARNING: .env file not found
    echo.
    echo The converter needs a .env file with your configuration.
    echo.
    echo Please create a .env file with your configuration:
    echo   1. Create a new file named .env in this directory
    echo   2. Add your MISTRAL_API_KEY and other settings
    echo   3. See README.md for complete configuration options
    echo.
    echo ============================================================
    echo.
    set /p "create_env=Would you like to create a basic .env file now? (Y/N): "
    echo.
    
    if /i "!create_env!"=="Y" (
        echo Creating basic .env file...
        echo # Enhanced Document Converter Configuration > .env
        echo # Add your API key below: >> .env
        echo MISTRAL_API_KEY="" >> .env
        echo # See README.md for all configuration options >> .env
        echo.
        echo Basic .env file created successfully!
        echo.
        echo Opening .env file in notepad for you to add your API key...
        echo Please add your MISTRAL_API_KEY and save the file.
        echo.
        notepad .env
        echo.
        echo Configuration saved.
        pause
    ) else (
        echo.
        echo Skipping .env creation.
        echo NOTE: You will need to create a .env file manually before using
        echo       Mistral OCR features. See README.md for details.
        echo.
        pause
    )
)

echo.
echo ============================================================
echo   Launching Document Converter...
echo ============================================================
echo.

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
