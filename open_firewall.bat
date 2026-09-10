@echo off
chcp 65001 >nul
title 放行防火墙（同网络同事才能访问本机看板）
setlocal EnableDelayedExpansion

REM ==========================================================
REM  低频看板 · Windows 防火墙放行（self-elevating 版）
REM  双击本文件即可：若当前不是管理员，会自动请求一次 UAC
REM  提权后放行端口；规则长期保留，之后双击 start.bat 即可。
REM ==========================================================

REM ----- 管理员自检：非管理员则提权重跑自身（无需右键"以管理员身份运行"）-----
NET SESSION >nul 2>&1
if %errorlevel% neq 0 (
  echo 需要管理员权限以放行防火墙（仅此一次，规则会长期保留）...
  echo 即将弹出 Windows 用户账户控制（UAC），请点「是」。
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

REM ----- 以下为管理员权限下执行（用 %~dp0 定位端口文件，忽略当前目录）-----
set PORT=8173
if exist "%~dp0out\_serve_port.txt" (
  set /p PORT=< "%~dp0out\_serve_port.txt"
)

echo ============================================================
echo   低频看板 · Windows 防火墙放行（同网络同事才能访问）
echo ============================================================
echo.
echo 将为低频看板放行 TCP 入站端口 %PORT%（规则名 lowfreq_local_in）。
echo.

netsh advfirewall firewall delete rule name=lowfreq_local_in >nul 2>&1
netsh advfirewall firewall add rule name=lowfreq_local_in dir=in action=allow protocol=TCP localport=%PORT% profile=any

if %errorlevel%==0 (
  echo [OK] 已放行 TCP %PORT% 入站，同网络同事现在可访问 http://你的局域网IP:%PORT%
  echo.
  echo 查看你的局域网 IP：打开看板，页面顶部「同事访问」处即为完整链接，复制发给同事即可。
) else (
  echo [失败] 返回码 %errorlevel%
  echo 请确认 UAC 弹窗点了「是」；或手动在管理员命令行执行：
  echo   netsh advfirewall firewall add rule name=lowfreq_local_in dir=in action=allow protocol=TCP localport=%PORT% profile=any
)
echo.
pause
