@echo off
setlocal
cd /d "%~dp0"

TITLE Document Converter

echo ===============================================
echo    Document Converter - Setup and Run
echo ===============================================
echo Working directory: %CD%

REM Create local venv if missing (prefer folder 'env')
if not exist "env\Scripts\python.exe" (
  echo Creating virtual environment...
  REM Try 'py -3' first (Windows Python launcher), then 'python3', then 'python'
  where py >nul 2>nul && (py -3 -m venv env) || (where python3 >nul 2>nul && (python3 -m venv env) || (python -m venv env))
  if errorlevel 1 (
      echo ERROR: Python not found or venv creation failed. Please install Python and ensure it is in your PATH.
      pause
      exit /b 1
  )
)

REM Activate the virtual environment
call "env\Scripts\activate.bat"

echo Using Python at:
where python
python --version

echo Updating pip and installing libraries (this may take a moment)...
python -m pip install --upgrade pip >nul
python -m pip install -U --upgrade-strategy eager -r requirements.txt

if errorlevel 1 (
    echo WARNING: Installation encountered issues. Trying again with verbose output...
    python -m pip install -U --upgrade-strategy eager -r requirements.txt
)

echo Setup complete.
echo.

echo ===============================================
echo    Starting Document Converter
echo ===============================================

REM Run the Python script. The script itself handles the final pause.
python main.py

IF %ERRORLEVEL% NEQ 0 (
  ECHO Python exited with error %ERRORLEVEL%.
)
ECHO.
PAUSE

endlocal
