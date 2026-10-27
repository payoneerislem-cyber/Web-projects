@echo off
setlocal
cd /d "%~dp0"
title Farouk Islem Portfolio

echo ============================================
echo   Farouk Islem - Portfolio startup
echo ============================================
echo.

where py >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3"
    goto python_found
)
where python >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
    goto python_found
)
goto no_python

:python_found
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating the virtual environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto venv_failed
) else (
    echo [1/3] Using the existing virtual environment...
)

echo.
echo [2/3] Installing/checking required packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto pip_failed

echo.
echo [3/3] Starting the website...
echo When the server says it is running, open: http://127.0.0.1:5000
echo Keep this window open while using the website.
echo To stop the website, press CTRL+C.
echo.
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto app_failed
goto end

:no_python
echo ERROR: Python 3 was not found on this computer.
echo Install Python 3.12 or newer from https://www.python.org/downloads/windows/
echo During installation, enable "Add python.exe to PATH".
pause
goto end

:venv_failed
echo ERROR: Could not create the virtual environment.
echo Make sure Python is installed correctly, then run this file again.
pause
goto end

:pip_failed
echo ERROR: Packages could not be installed.
echo Check your internet connection, then run this file again.
echo If the error mentions DNS or name resolution, reconnect to the internet and retry.
pause
goto end

:app_failed
echo ERROR: The application stopped. Read the error shown above.
pause

:end
endlocal
