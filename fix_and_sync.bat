@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 防止用户直接从 zip 压缩包里双击运行（Windows 只会把 .bat 抽到临时目录，导致 .py 文件找不到）
if not exist "%~dp0fix_and_sync.py" (
    echo ============================================
    echo  请勿直接从 zip 压缩包里运行本程序
    echo ============================================
    echo.
    echo  你当前是从 zip 压缩包内部双击打开的，
    echo  Windows 没有把同目录的 fix_and_sync.py 解压出来，所以会报错。
    echo.
    echo  正确步骤：
    echo    1. 右键点击 lowfreq_local_v10_5_3.zip
echo    2. 选择"全部解压缩..."（Extract All...）
echo    3. 选择一个文件夹，例如 D:\lowfreq_local
echo    4. 进入解压后的 lowfreq_local 文件夹
echo    5. 再双击 fix_and_sync.bat
    echo.
    pause
    exit /b 1
)

echo ============================================
echo  Lowfreq Dashboard - Auto Fix + Sync + Serve
echo ============================================
echo.

set "PY="
for %%P in (python python3 py) do (
    where %%P >nul 2>nul
    if not defined PY (
        for /f "delims=" %%V in ('%%P -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%V"
    )
)

if not defined PY (
    echo [ERROR] Python not found. Install Python 3.8+ first:
    echo   https://www.python.org/downloads/
    echo   Check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [INFO] Using Python: %PY%
echo [INFO] Running diagnosis and sync...
echo.

"%PY%" "%~dp0auto_update.py"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Diagnosis or sync failed. See out\fix_and_sync.log
    pause
    exit /b %errorlevel%
)

echo.
echo [DONE] Service started. Browser should open automatically.
pause
