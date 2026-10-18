@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" aglass2vrc.py %*
) else (
    python aglass2vrc.py %*
)
exit /b %errorlevel%
