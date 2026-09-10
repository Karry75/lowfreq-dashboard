@echo off
REM ============================================================
REM dump_schema.bat - Export DB schema + candidate funnel
REM ============================================================
REM Pure ASCII wrapper; Chinese output goes through PowerShell.
REM READ-ONLY: only SHOW / SELECT COUNT are executed.
REM Output: out\schema_report.txt  (UTF-8)
REM ============================================================
chcp 437 >nul 2>&1
title dump_schema
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto :nopython

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Continue';" ^
  "$dir = (Get-Location).Path;" ^
  "Set-Location $dir;" ^
  "Write-Host '============================================================' -ForegroundColor Cyan;" ^
  "Write-Host '  dump_schema  (READ-ONLY: SHOW / SELECT COUNT)' -ForegroundColor White;" ^
  "Write-Host '============================================================' -ForegroundColor Cyan;" ^
  "Write-Host '';" ^
  "& python -X utf8 dump_schema.py 2>&1 | Out-String | Write-Host;" ^
  "Write-Host '';" ^
  "$r = Join-Path $dir 'out\schema_report.txt';" ^
  "if (Test-Path $r) {" ^
  "  Write-Host ('[OK] report written: ' + $r) -ForegroundColor Green;" ^
  "  Write-Host ('     size: ' + [math]::Round((Get-Item $r).Length/1KB,1) + ' KB') -ForegroundColor Gray;" ^
  "  Start-Process notepad.exe -ArgumentList $r;" ^
  "} else {" ^
  "  Write-Host '[FAIL] report not produced.' -ForegroundColor Red;" ^
  "}" ^
  "Write-Host '';" ^
  "Write-Host 'Please send out\schema_report.txt (or screenshot it).' -ForegroundColor Yellow;"
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

:fail
echo.
echo [FAIL] dump_schema failed. See messages above.
pause
exit /b 1
