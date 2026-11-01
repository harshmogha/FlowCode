@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Run run.bat once first to set up the environment.
    pause
    exit /b 1
)
"venv\Scripts\python.exe" -m pip install -q -r requirements-dev.txt
"venv\Scripts\python.exe" -m pytest -q
pause
