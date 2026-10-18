@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0aglass_gui.py"
    exit /b 0
)
where pythonw.exe >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install 64-bit Python with Tcl/Tk, then see README.md.
    pause
    exit /b 1
)
start "" pythonw.exe "%~dp0aglass_gui.py"
