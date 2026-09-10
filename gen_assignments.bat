@echo off
REM ============================================================
REM gen_assignments.bat - Generate today visit list
REM ============================================================
REM Pure ASCII wrapper; Chinese output goes through PowerShell.
REM The Python script receives C names via PowerShell quoting.
REM ============================================================
chcp 437 >nul 2>&1
title gen_assignments
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto :nopython
if not exist "out\records.json" goto :nosync

REM Delegate everything to PowerShell. PS internal encoding handles CN names safely.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$dir = (Get-Location).Path;" ^
  "Set-Location $dir;" ^
  "Write-Host '============================================================' -ForegroundColor Cyan;" ^
  "Write-Host '  gen_assignments  (auto date)' -ForegroundColor White;" ^
  "Write-Host '============================================================' -ForegroundColor Cyan;" ^
  "Write-Host '';" ^
  "Write-Host 'Default staff: huapingping=30 hulianxia=30' -ForegroundColor Gray;" ^
  "Write-Host '';" ^
  "& python -X utf8 gen_assignments.py --solvers huapingping:30 hulianxia:30 2>&1 | Out-String | Write-Host;" ^
  "Write-Host '';" ^
  "Write-Host 'Done.' -ForegroundColor Green;"
if errorlevel 1 goto :fail

echo.
pause >nul
exit /b 0

:nopython
echo.
echo [FAIL] python not in PATH.
echo.
pause
exit /b 1

:nosync
echo.
echo [FAIL] out\records.json missing. Run fix_and_sync.bat first.
echo.
pause
exit /b 1

:fail
echo.
echo [FAIL] stage failed.
pause
exit /b 1
