@echo off
REM ============================================================
REM safe_update.bat - Safe upgrade preserving local config
REM ============================================================
REM Usage:
REM   safe_update.bat "D:\path\to\lowfreq_local_latest.zip"
REM
REM Design: this .bat is PURE ASCII (no Chinese chars) because
REM the user's cmd.exe is GBK-encoded. All Chinese output goes
REM through PowerShell which uses native system encoding.
REM ============================================================
chcp 437 >nul 2>&1
title safe_update
cd /d "%~dp0"

set "ZIP_FILE=%~1"

if "%ZIP_FILE%"=="" goto :usage
if not exist "%ZIP_FILE%" goto :nozip

echo ============================================================
echo   safe_update  (v10.28.16 + auto Unicode output)
echo ============================================================
echo.

REM 1) Generate backup timestamp (ASCII-safe)
set "STAMP=%date:~10,4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "STAMP=%STAMP: =0%"
set "BAK=.bak_%STAMP%"
mkdir "%BAK%" 2>nul

REM 2) Backup key files (all pure-ASCII paths)
copy /Y "staff_auth.json"         "%BAK%\" >nul 2>&1
copy /Y "db_conf.json"           "%BAK%\" >nul 2>&1
copy /Y "out\staff.json"         "%BAK%\" >nul 2>&1
copy /Y "out\records.json"       "%BAK%\" >nul 2>&1
copy /Y "out\staff_auth.json"    "%BAK%\" >nul 2>&1
copy /Y "out\assignments.json"   "%BAK%\" >nul 2>&1

REM 3) Run the entire workflow via PowerShell - it handles Chinese natively
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$dir = (Get-Location).Path;" ^
  "$zip = '%ZIP_FILE%';" ^
  "$bak = '%BAK%';" ^
  "Write-Host '============================================================' -ForegroundColor Cyan;" ^
  "Write-Host 'Step 1/4: backup key files' -ForegroundColor Yellow;" ^
  "foreach($f in @('staff_auth.json','db_conf.json','out\staff.json','out\records.json','out\staff_auth.json','out\assignments.json')){" ^
  "  $src = Join-Path $dir $f;" ^
  "  if (Test-Path $src) { $dst = Join-Path $bak (Split-Path $f -Leaf); Copy-Item -LiteralPath $src -Destination $dst -Force; Write-Host ('  [OK] backup ' + $f) -ForegroundColor Green; }" ^
  "  else { Write-Host ('  [--] missing ' + $f) -ForegroundColor DarkGray; }" ^
  "};" ^
  "Write-Host '';" ^
  "Write-Host 'Step 2/4: extract zip over current dir' -ForegroundColor Yellow;" ^
  "try { Expand-Archive -LiteralPath $zip -DestinationPath $dir -Force; Write-Host '  [OK] extract done' -ForegroundColor Green; }" ^
  "catch { Write-Host ('  [FAIL] ' + $_.Exception.Message) -ForegroundColor Red; exit 2; };" ^
  "Write-Host '';" ^
  "Write-Host 'Step 3/4: restore local config files (force overwrite)' -ForegroundColor Yellow;" ^
  "foreach($f in @('staff_auth.json','db_conf.json')){" ^
  "  $bkf = Join-Path $bak (Split-Path $f -Leaf);" ^
  "  if (Test-Path $bkf) { $dst = Join-Path $dir $f; Copy-Item -LiteralPath $bkf -Destination $dst -Force; Write-Host ('  [OK] restored ' + $f) -ForegroundColor Green; }" ^
  "};" ^
  "foreach($f in @('out\staff.json','out\records.json','out\staff_auth.json','out\assignments.json')){" ^
  "  $bkf = Join-Path $bak (Split-Path $f -Leaf);" ^
  "  if (Test-Path $bkf) { $dst = Join-Path $dir $f; Copy-Item -LiteralPath $bkf -Destination $dst -Force; Write-Host ('  [OK] restored ' + $f) -ForegroundColor Green; }" ^
  "};" ^
  "Write-Host '';" ^
  "Write-Host 'Step 4/4: done' -ForegroundColor Yellow;" ^
  "Write-Host '';" ^
  "Write-Host '============================================================' -ForegroundColor Cyan;" ^
  "Write-Host 'Upgrade complete.' -ForegroundColor Green;" ^
  "Write-Host ('Backup kept at: ' + $bak) -ForegroundColor DarkGray;" ^
  "Write-Host '';" ^
  "Write-Host 'Next steps (run in this order):' -ForegroundColor White;" ^
  "Write-Host '  1. double-click fix_and_sync.bat  (sync DB, ~1-2 min)' -ForegroundColor White;" ^
  "Write-Host '  2. double-click gen_assignments.bat (generate today list, ~5 sec)' -ForegroundColor White;" ^
  "Write-Host '  3. double-click run_serve.bat      (start dashboard)' -ForegroundColor White;" ^
  "Write-Host '============================================================' -ForegroundColor Cyan;"
if errorlevel 1 (
    echo.
    echo [FAIL] PowerShell stage failed.
    pause
    exit /b 1
)
echo.
echo Done. Press any key to close.
pause >nul
exit /b 0

:usage
echo.
echo Usage:
echo   safe_update.bat "D:\path\to\lowfreq_local_latest.zip"
echo.
echo This will backup your account/DB config, then safely overwrite.
echo.
pause
exit /b 1

:nozip
echo.
echo [FAIL] zip not found: %ZIP_FILE%
echo.
pause
exit /b 1
