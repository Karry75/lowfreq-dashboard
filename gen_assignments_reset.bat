@echo off
REM ============================================================
REM gen_assignments_reset.bat - Clear history then regenerate
REM ============================================================
REM Use ONLY when the visit list keeps coming out empty because
REM old "pending" tasks piled up in assignments.json.
REM A timestamped backup is created automatically.
REM Pure ASCII wrapper; Chinese output goes through PowerShell.
REM ============================================================
chcp 437 >nul 2>&1
title gen_assignments RESET
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto :nopython
if not exist "out\records.json" goto :nosync

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Continue';" ^
  "$dir = (Get-Location).Path;" ^
  "Set-Location $dir;" ^
  "Write-Host '============================================================' -ForegroundColor Cyan;" ^
  "Write-Host '  gen_assignments --reset' -ForegroundColor White;" ^
  "Write-Host '  Clears assignments.json history, then regenerates.' -ForegroundColor Gray;" ^
  "Write-Host '  A timestamped backup is kept automatically.' -ForegroundColor Gray;" ^
  "Write-Host '============================================================' -ForegroundColor Cyan;" ^
  "Write-Host '';" ^
  "& python -X utf8 gen_assignments.py --reset --solvers huapingping:30 hulianxia:30 2>&1 | Out-String | Write-Host;" ^
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
echo [FAIL] reset failed. See messages above.
pause
exit /b 1
