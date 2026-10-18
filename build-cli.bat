@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" tools\build_exe.py --target cli
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" tools\check_exe.py --target cli
if errorlevel 1 exit /b 1
echo Ready: release\aGlass2OSC-Windows-x64-cli.zip
