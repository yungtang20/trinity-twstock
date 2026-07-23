@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Project Python environment is missing: .venv\Scripts\python.exe
    echo Create the Python 3.12 environment before running this launcher.
    exit /b 1
)

".venv\Scripts\python.exe" -B "%~dp0main.py" %*
exit /b %ERRORLEVEL%
