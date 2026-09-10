@echo off
REM ==========================================================
REM   v10.28.39 troubleshoot.bat - 一键诊断服务为何打不开
REM   运行：双击本文件即可，无需管理员权限。
REM   用途：当浏览器显示「127.0.0.1 拒绝连接」/「同事打不开」时排查。
REM ==========================================================

cd /d "%~dp0"
chcp 65001 >nul 2>&1
title 低频看板 troubleshoot

echo ============================================================
echo   低频看板 troubleshoot (v10.28.39)
echo   工作目录：%CD%
echo ============================================================
echo.

echo [1/6] Python 解释器...
where python >nul 2>&1 && (echo   OK - python 可执行 & python --version) || (
    where py >nul 2>&1 && (echo   OK - py launcher 可用 & py -3 --version) || (
        echo   FAIL - Python 不在 PATH，请安装 3.8+ 并勾选 Add to PATH
    )
)
echo.

echo [2/6] 关键依赖（pymysql / openpyxl）...
python -c "import pymysql; print('   OK - pymysql', pymysql.__version__)" 2>nul || echo   FAIL - pymysql 未装，请执行：python -m pip install pymysql
python -c "import openpyxl; print('   OK - openpyxl', openpyxl.__version__)" 2>nul || echo   FAIL - openpyxl 未装（不强制需要，但 Excel 导出需要）
echo.

echo [3/6] 端口 8173 占用情况...
netstat -ano -p TCP | findstr ":8173" | findstr LISTENING
if errorlevel 1 (
    echo   FAIL - 8173 端口空闲，说明服务没在监听！
    echo          解决：双击 start.bat 重新启动，或先双击 fix_and_sync.bat
) else (
    echo   OK - 见上方的 PID
    echo   提示：若 PID 不是 python.exe / pythonw.exe，说明是别的程序占着
)
echo.

echo [4/6] 服务存活探测（/api/health）...
curl -s -m 3 http://127.0.0.1:8173/api/health
if errorlevel 1 (
    echo   FAIL - 探测不到健康端点，说明服务没起或端口被别的程序占着
) else (
    echo.
    echo   OK - 服务在跑
)
echo.

echo [5/6] 状态文件 out\_serve_status.json...
if exist "out\_serve_status.json" (
    type "out\_serve_status.json"
) else (
    echo   (状态文件不存在，正常情况是服务还没启动过)
)
echo.

echo [6/6] 关键日志最后 20 行（out\serve_boot.log / out\launch.log）...
echo   --- out\serve_boot.log ---
if exist "out\serve_boot.log" (
    powershell -NoProfile -Command "Get-Content 'out\serve_boot.log' -Tail 20"
) else (
    echo   (无)
)
echo.
echo   --- out\launch.log ---
if exist "out\launch.log" (
    powershell -NoProfile -Command "Get-Content 'out\launch.log' -Tail 20"
) else (
    echo   (无)
)
echo.

echo ============================================================
echo   建议
echo ============================================================
echo 1. 若 1/2/3 任意 FAIL，先修对应项目（装 Python / 装依赖 / 关占用进程）
echo 2. 若 4 FAIL 但 3 OK - 端口被别的程序占着，taskkill /F /PID ^<PID^>
echo 3. 若 3 FAIL - 服务没起，双击 start.bat 启动，盯着窗口里的错误
echo 4. 若以上都 OK 但浏览器仍拒绝 - 强刷一次（Ctrl+Shift+R），或换浏览器试试
echo.
pause
