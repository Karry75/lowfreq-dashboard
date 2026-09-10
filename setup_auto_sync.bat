@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Creating daily auto-sync task for Lowfreq Dashboard...
echo Default: run silently every day at 08:30 in background.
echo.

schtasks /Create /F /TN "LowfreqDashboardDailySync" /TR "\"%~dp0run_silent.bat\"" /SC DAILY /ST 08:30 /RU SYSTEM
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to create task. Right-click and "Run as administrator".
    pause
    exit /b 1
)

echo.
echo [OK] Daily auto-sync task created.
echo   Task name: LowfreqDashboardDailySync
echo   Runs: %~dp0run_silent.bat at 08:30 daily
echo.
echo To change time:
echo   schtasks /Change /TN "LowfreqDashboardDailySync" /ST 09:00
echo.
pause
