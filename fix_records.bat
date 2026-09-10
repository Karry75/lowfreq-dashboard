@echo off
REM ============================================================
REM  fix_records.bat  v10.28.31  极简版（无心跳子进程）
REM  - 完全不启动任何后台 cmd，心跳直接砍掉
REM  - 父脚本老老实实等 Python 退出，立刻打印 RESULT
REM  - 所有命令独立成行 + CRLF，Windows 100% 安全
REM ============================================================
chcp 65001 >nul 2>&1
title fix_records_v10.28.31
cd /d "%~dp0"
echo ============================================================
echo   fix_records  v10.28.31  (pull data + generate list)
echo ============================================================
echo.
if not exist out (mkdir out)
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
del /q out\fix_records.stdout.log 2>nul
del /q out\fix_records.stderr.log 2>nul
del /q out\status.json 2>nul

REM ---- 找 python（6 种 fallback 路径）----
set PY=
where python >nul 2>&1 && (for /f "delims=" %%i in ('where python') do (set PY=%%i & goto :FOUND))
where py >nul 2>&1 && (set PY=py -3 & goto :FOUND)
if exist "C:\Python311\python.exe" (set PY="C:\Python311\python.exe" & goto :FOUND)
if exist "C:\Python310\python.exe" (set PY="C:\Python310\python.exe" & goto :FOUND)
if exist "C:\Python39\python.exe" (set PY="C:\Python39\python.exe" & goto :FOUND)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (set PY="%LOCALAPPDATA%\Programs\Python\Python311\python.exe" & goto :FOUND)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe" & goto :FOUND)

:NOTFOUND
echo [FAIL] 找不到 python.exe
echo 请安装 Python 3.10+ 并加入 PATH，或修改本文件第 30 行 set PY=...
pause
exit /b 99

:FOUND
echo [INFO] using python: %PY%
echo.
echo [INFO] running fix_records.py ...  (请耐心等待 30s~3min)
echo.

REM ---- 关键改动：直接等 Python 退出，不再 start /b 心跳 ----
%PY% -u fix_records.py 1> out\fix_records.stdout.log 2> out\fix_records.stderr.log
set RC=%ERRORLEVEL%

echo.
echo ======================== RESULT ========================
echo exit code: %RC%
echo.

if %RC% NEQ 0 (
  echo [FAIL] see out\fix_records.stderr.log
  echo ----- stderr (full) -----
  if exist out\fix_records.stderr.log type out\fix_records.stderr.log
) else (
  echo [OK] exit 0
  echo ----- stdout (last 30 lines) -----
  if exist out\fix_records.stdout.log powershell -NoProfile -Command "Get-Content 'out\fix_records.stdout.log' -Tail 30" 2>nul
  if not exist out\fix_records.stdout.log echo (no stdout)
)

if exist out\status.json (
  echo.
  echo ===== out\status.json =====
  type out\status.json
  echo.
)

echo.
echo ============================================================
echo  全部完成，按任意键关闭窗口
echo ============================================================
pause
exit /b %RC%
