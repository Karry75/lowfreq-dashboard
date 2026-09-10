@echo off
chcp 65001 >nul
cd /d "%~dp0"
set TASKNAME=LowfreqDashboardDailySync
set /p ST=Enter daily sync time (HH:MM, default 08:00):
if "%ST%"=="" set ST=08:00
set SCRIPT=%~dp0run_silent.bat
schtasks /create /tn "%TASKNAME%" /tr "%SCRIPT%" /sc daily /st %ST% /f
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to create. Run as administrator if no admin rights.
    pause
    exit /b 1
)
echo Task "%TASKNAME%" created, syncs daily at %ST%.
pause
