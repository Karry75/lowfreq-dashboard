@echo off
chcp 65001 >nul
cd /d "%~dp0"
set TASKNAME=LowfreqDashboardDailySync
schtasks /delete /tn "%TASKNAME%" /f
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to remove. Task may not exist, or admin rights needed.
    pause
    exit /b 1
)
echo Task "%TASKNAME%" removed.
pause
