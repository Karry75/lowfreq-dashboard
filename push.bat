@echo off
chcp 65001 >nul
title 推送 lowfreq-dashboard 到 GitHub
echo ============================================
echo   lowfreq-dashboard 一键推送到 GitHub
echo   目标: git@github.com:Karry75/lowfreq-dashboard.git
echo ============================================
echo.
echo [1/1] 正在推送 main 分支 ...
cd /d "%~dp0"
git push -u origin main
if %errorlevel%==0 (
  echo.
  echo ✅ 推送成功！仓库地址: https://github.com/Karry75/lowfreq-dashboard
) else (
  echo.
  echo ❌ 推送失败，常见原因与解决：
  echo.
  echo   1) GitHub 上还没添加本机 SSH 公钥
  echo      - 测试: 打开 Git Bash 运行  ssh -T git@github.com
  echo      - 解决: 把 ~/.ssh/id_ed25519_github.pub 内容
  echo              粘贴到 https://github.com/settings/ssh/new
  echo.
  echo   2) 仓库 Karry75/lowfreq-dashboard 还没创建
  echo      - 解决: 打开 https://github.com/new
  echo              名填 lowfreq-dashboard，选 Public，不要勾 README
  echo.
  echo   3) 公钥已加但 agent 没加载私钥
  echo      - 运行: ssh-add ~/.ssh/id_ed25519_github
)
echo.
pause
