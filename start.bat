@echo off
REM ==========================================================
REM   Low-Frequency User Dashboard - Launcher (v10.28.39)
REM   Pure ASCII, no Unicode, safe on every Windows code page.
REM   The window stays open after launch so you can read the
REM   result (and copy the URL if the browser did not open).
REM
REM   v10.28.39 改动：
REM     1) 启动前先 taskkill 残留的 pythonw.exe（防止端口被占导致 serve 起不来）
REM     2) 出错时窗口不立刻关，把错误日志留给你看
REM ==========================================================

cd /d "%~dp0"

REM ----- v10.28.39：清掉所有残留 pythonw.exe（避免上一轮 serve 占着 8173 不放）-----
taskkill /IM pythonw.exe /F >nul 2>&1

REM ----- guard: refuse to run from inside ZIP -----
if not exist "%~dp0start.py" (
    echo.
    echo  [ERROR] start.py not found!
    echo.
    echo  This usually means you double-clicked start.bat from inside
    echo  the ZIP archive directly. Please:
    echo     1) Right-click the ZIP file -^> "Extract All..."
    echo     2) Choose an empty folder, e.g. D:\lowfreq_local
    echo     3) Open that folder and double-click start.bat
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
    echo.
    echo  Please install Python 3.8 or newer from:
    echo     https://www.python.org/downloads/
    echo  During installation, CHECK "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo.
echo  =========================================================
echo   Low-Frequency User Dashboard - Starting (v10.28.39)
echo   (This window stays open so you can read the result.
echo    Minimize it after the dashboard loads in your browser.)
echo  =========================================================
echo.

%PY% "%~dp0start.py"
set "RC=%errorlevel%"

echo.
echo  =========================================================
if not "%RC%"=="0" (
    echo   [ERROR] Launcher exited with code %RC%. See messages above.
    echo   Tip: double-click troubleshoot.bat for auto-diagnostics.
) else (
    echo   [DONE] Browser should be open now.
    echo.
    echo   If your browser did NOT open, copy this URL manually:
    echo       http://127.0.0.1:8173/?sync=1
    echo.
    echo   The dashboard service keeps running in the background
    echo   (you can minimize this window, but don't close it).
)
echo  =========================================================
echo  Press any key to close this window...
pause >nul
