@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

TITLE Document Converter

REM Use UTF-8 to avoid encoding-related crashes in console
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONHOME="
set "PYTHONPATH="
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

echo ===============================================
echo    Document Converter - Setup and Run
echo ===============================================
echo Working directory: %CD%

REM Ensure logs directory exists for installer/app logs
if not exist "logs" mkdir "logs"
 
 set "TRACE_LOG=logs\run_trace.log"
 type nul > "%TRACE_LOG%"
 echo ---- %DATE% %TIME% ---- >> "%TRACE_LOG%"
 echo Working directory: %CD% >> "%TRACE_LOG%"
 echo PATH: %PATH% >> "%TRACE_LOG%"
 echo Pre-activation: where python >> "%TRACE_LOG%"
 where python >> "%TRACE_LOG%" 2>&1
 
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

REM Use the venv interpreter directly (no activation)
set "VENV_PY=%CD%\env\Scripts\python.exe"
echo Using Python at: %VENV_PY%
"%VENV_PY%" --version
echo VENV_PY: %VENV_PY% >> "%TRACE_LOG%"

echo Updating pip and installing libraries (this may take a moment)...
rem Start a fresh pip log section with timestamp
type nul > "logs\pip_install.log"
echo ---- %DATE% %TIME% ---- >> "logs\pip_install.log"
echo Working directory: %CD% >> "logs\pip_install.log"
echo VENV_PY: %VENV_PY% >> "logs\pip_install.log"
"%VENV_PY%" -c "import sys; import sysconfig; print('sys.executable:', sys.executable); print('sys.prefix:', sys.prefix)" >> "logs\pip_install.log" 2>&1
"%VENV_PY%" -m pip --version >> "logs\pip_install.log" 2>&1

  rem --- Upgrade pip with progress dots (synchronous install) ---
  set "SPIN_FLAG=%CD%\logs\pip.running"
  type nul > "%SPIN_FLAG%"
  echo Upgrading pip (progress):
  start "" /b powershell -NoProfile -ExecutionPolicy Bypass -Command "$f = '%SPIN_FLAG%'; while (Test-Path $f) { Write-Host -NoNewline '.'; Start-Sleep -Seconds 1 }; Write-Host ''"
  "%VENV_PY%" -m pip install --upgrade pip >> "logs\pip_install.log" 2>&1
  del /q "%SPIN_FLAG%" 2>nul
  set "EXITCODE=%ERRORLEVEL%"
  if not "%EXITCODE%"=="0" (
      rem Heuristic fallback: consider success if pip reports already satisfied or successful install
      findstr /i /c:"Successfully installed pip" "logs\pip_install.log" >nul 2>&1 && set "EXITCODE=0"
      if not "%EXITCODE%"=="0" (
          findstr /i /c:"Requirement already satisfied: pip" "logs\pip_install.log" >nul 2>&1 && set "EXITCODE=0"
      )
      if not "%EXITCODE%"=="0" (
          echo ERROR: pip upgrade failed. See logs\pip_install.log for details.
          echo.
          goto :END
      )
  )

  rem --- Upgrade build tools (setuptools, wheel) with progress dots ---
  set "SPIN_FLAG=%CD%\logs\buildtools.running"
  type nul > "%SPIN_FLAG%"
  echo Upgrading build tools (setuptools, wheel) (progress):
  start "" /b powershell -NoProfile -ExecutionPolicy Bypass -Command "$f = '%SPIN_FLAG%'; while (Test-Path $f) { Write-Host -NoNewline '.'; Start-Sleep -Seconds 1 }; Write-Host ''"
  "%VENV_PY%" -m pip install -U setuptools wheel >> "logs\pip_install.log" 2>&1
  del /q "%SPIN_FLAG%" 2>nul
  set "EXITCODE=%ERRORLEVEL%"
  if not "%EXITCODE%"=="0" (
      echo ERROR: Build tools upgrade failed. See logs\pip_install.log for details.
      echo.
      goto :END
  )

  rem --- Install/upgrade project dependencies (eager) with retry + progress dots ---
  set "SPIN_FLAG=%CD%\logs\deps.running"
  type nul > "%SPIN_FLAG%"
  echo Installing/upgrading project dependencies (progress):
  start "" /b powershell -NoProfile -ExecutionPolicy Bypass -Command "$f = '%SPIN_FLAG%'; while (Test-Path $f) { Write-Host -NoNewline '.'; Start-Sleep -Seconds 1 }; Write-Host ''"
  "%VENV_PY%" -m pip install -U --upgrade-strategy eager -r "%CD%\requirements.txt" >> "logs\pip_install.log" 2>&1
  del /q "%SPIN_FLAG%" 2>nul
  set "EXITCODE=%ERRORLEVEL%"
  if not "%EXITCODE%"=="0" (
      echo WARNING: First dependency install failed. Retrying now...
      set "SPIN_FLAG=%CD%\logs\deps2.running"
      type nul > "%SPIN_FLAG%"
      start "" /b powershell -NoProfile -ExecutionPolicy Bypass -Command "$f = '%SPIN_FLAG%'; while (Test-Path $f) { Write-Host -NoNewline '.'; Start-Sleep -Seconds 1 }; Write-Host ''"
      "%VENV_PY%" -m pip install -U --upgrade-strategy eager -r "%CD%\requirements.txt" >> "logs\pip_install.log" 2>&1
      del /q "%SPIN_FLAG%" 2>nul
      set "EXITCODE=%ERRORLEVEL%"
      if not "%EXITCODE%"=="0" (
        echo ERROR: Dependency installation failed. See logs\pip_install.log for details.
        echo.
        goto :END
      )
  )

rem --- Post-install verification ---
echo Running pip check... >> "%TRACE_LOG%"
"%VENV_PY%" -m pip check >> "logs\pip_install.log" 2>&1
echo Recording installed versions to logs\installed_versions.txt >> "%TRACE_LOG%"
"%VENV_PY%" -m pip freeze > "logs\installed_versions.txt" 2>nul
echo Pip install completed OK >> "%TRACE_LOG%"

REM Ensure .env exists (create from template if available)
if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    rem Avoid parentheses in ECHO inside IF blocks to prevent parser issues
    echo Created .env from .env.example. Edit .env to add API keys such as MISTRAL_API_KEY.
  )
)

echo After .env ensure >> "%TRACE_LOG%"

echo Setup complete.
echo.

echo ===============================================
echo    Starting Document Converter
echo ===============================================

echo Running smoke test...
rem Pre-create app_startup.log and add timestamp and interpreter used
echo Before app_startup.log creation >> "%TRACE_LOG%"
type nul > "logs\app_startup.log"
echo ---- %DATE% %TIME% ---- >> "logs\app_startup.log"
echo Using Python (VENV_PY) at: %VENV_PY% >> "logs\app_startup.log"
"%VENV_PY%" -c "import sys; print('sys.executable:', sys.executable)" >> "logs\app_startup.log" 2>&1
echo After app_startup.log creation >> "%TRACE_LOG%"
echo Before smoke test >> "%TRACE_LOG%"
"%VENV_PY%" "%CD%\main.py" --test --no-interactive >> "logs\app_startup.log" 2>&1 || (
  ECHO Smoke test failed. See logs\app_startup.log for details.
  ECHO.
  GOTO :END
)
echo Smoke test OK >> "%TRACE_LOG%"

REM Run the Python script with the venv interpreter
echo Launching main >> "%TRACE_LOG%"
"%VENV_PY%" "%CD%\main.py"

IF %ERRORLEVEL% NEQ 0 (
  ECHO Python exited with error %ERRORLEVEL%.
)
ECHO.
GOTO :END

:WAIT_FOR_FILE
rem Usage: CALL :WAIT_FOR_FILE "path_to_flag_file"
set "FLAGFILE=%~1"
<nul set /p=" "
:__WF_LOOP
if exist "%FLAGFILE%" goto __WF_END
<nul set /p="."
timeout /t 1 /nobreak >nul
goto __WF_LOOP
:__WF_END
echo.
exit /b 0

:END
PAUSE

endlocal
