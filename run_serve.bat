@echo off
REM ==========================================================
REM   Low-Frequency User Dashboard - Direct serve launcher
REM   (v10.28.13) Pure ASCII. Runs serve.py in the FOREGROUND
REM   so you can see real-time logs and any startup errors.
REM   Keep this window open (you may minimize it) while using
REM   the dashboard. Closing this window stops the dashboard.
REM ==========================================================

cd /d "%~dp0"

REM ----- guard: serve.py must exist in this folder -----
if not exist "%~dp0serve.py" (
    echo.
    echo  [ERROR] serve.py not found in this folder!
    echo  Make sure you extracted the WHOLE zip into this folder.
    echo.
    pause
    exit /b 1
)

REM ----- pick a working Python interpreter -----
set "PY="
where python >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY (
    where py >nul 2>&1
    if not errorlevel 1 set "PY=py -3"
)

if not defined PY (
    echo.
    echo  [ERROR] Python not found in PATH.
    echo  Install Python 3.8 or newer from:
    echo     https://www.python.org/downloads/
    echo  During install, CHECK "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo.
echo  =========================================================
echo   Serving dashboard on  http://localhost:8173
echo   Open this in your browser:
echo       http://localhost:8173/?sync=1
echo   (Keep this window open. Close it to stop the dashboard.)
echo  =========================================================
echo.

%PY% "%~dp0serve.py"

echo.
echo  serve.py has stopped (exit code %errorlevel%).
echo  Press any key to close this window...
pause >nul
