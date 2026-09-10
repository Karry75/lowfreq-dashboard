@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "%~dp0auto_update.py" (
    echo ============================================
    echo  Do NOT run this directly from inside the ZIP.
    echo  Please extract the whole lowfreq_local folder first,
    echo  then double-click this file inside that folder.
    echo ============================================
    pause
    exit /b 1
)

set "PY="
for %%P in (python python3 py) do (
    where %%P >nul 2>nul
    if not defined PY (
        for /f "delims=" %%V in ('%%P -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%V"
    )
)

if not defined PY (
    echo [ERROR] Python not found. Please install Python 3.8+:
    echo   https://www.python.org/downloads/
    echo   Check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [INFO] Using Python: %PY%
echo [INFO] Starting auto update and launch...
echo.
"%PY%" "%~dp0auto_update.py"
pause
