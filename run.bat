@echo off
setlocal
cd /d "%~dp0"
title FlowCode

rem ---- find Python -------------------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python 3 was not found. Install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

rem ---- create or repair the virtual environment ----------------------------
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -c "import sys" >nul 2>nul || rmdir /s /q venv
)
if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment ^(first run only^)...
    %PY% -m venv venv
    if errorlevel 1 (
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)

rem ---- install required libraries (quick when already installed) -----------
echo Checking required libraries...
"venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo Could not install the libraries. Check your internet connection and try again.
    pause
    exit /b 1
)

rem ---- open the browser shortly after the server starts, then run ----------
echo.
echo FlowCode is starting at http://127.0.0.1:5000
echo Close this window ^(or press Ctrl+C^) to stop the app.
echo.
start "" /b cmd /c "ping -n 4 127.0.0.1 >nul & start http://127.0.0.1:5000"
"venv\Scripts\python.exe" app.py

echo.
echo The app has stopped.
pause
