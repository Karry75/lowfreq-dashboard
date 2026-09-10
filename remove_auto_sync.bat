@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Removing daily auto-sync task for Lowfreq Dashboard...
schtasks /Delete /F /TN "LowfreqDashboardDailySync"
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to remove. Task may not exist, or admin rights needed.
    pause
    exit /b 1
)
echo.
echo [OK] Auto-sync task removed.
pause
