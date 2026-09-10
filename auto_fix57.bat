@echo off
chcp 65001 >nul
setlocal ENABLEDELAYEDEXPANSION
title v10.28.57 性能专项升级包 - 双击运行

cd /d %~dp0

set "DL=https://ae71ffa2092522eec.sh7.agentos-app.net/lowfreq_local_v10.28.57_FINAL.zip"
set "ZIP=%TEMP%\lowfreq_v10.28.57.zip"

echo.
echo ==============================================================
echo   低频用户回访看板 v10.28.57 升级（性能专项）
echo   看板 28.8MB -> 2.15MB，启动/同步/生成名单全面提速
echo ==============================================================
echo.

rem === 1. 备份关键配置 ===
echo [1/6] 备份当前配置...
if not exist "_backup" mkdir _backup
if exist "db_conf.json"        copy /Y "db_conf.json"        "_backup\db_conf.json.bak" >nul
if exist "staff_auth.json"     copy /Y "staff_auth.json"     "_backup\staff_auth.json.bak" >nul
if exist "out\assignments.json" copy /Y "out\assignments.json" "_backup\assignments.json.bak" >nul
if exist "out\records.json"    copy /Y "out\records.json"    "_backup\records.json.bak" >nul
echo       已备份到 _backup\
echo.

rem === 2. 结束旧进程 ===
echo [2/6] 结束旧进程（python.exe / pythonw.exe）...
taskkill /F /IM python.exe   >nul 2>&1
taskkill /F /IM pythonw.exe  >nul 2>&1
echo       完成
echo.

rem === 3. 下载升级包 ===
echo [3/6] 下载 v10.28.57 完整包...
if exist "%ZIP%" del /F /Q "%ZIP%" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue';" ^
  "try{ [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
  "Invoke-WebRequest -Uri '%DL%' -OutFile '%ZIP%' -UseBasicParsing -TimeoutSec 300;" ^
  "Write-Host '       下载成功' }catch{ Write-Host '       下载失败:' $_.Exception.Message; exit 3 }"
if errorlevel 3 goto :DLFAIL
if not exist "%ZIP%" goto :DLFAIL
echo.

rem === 4. 解压到 _new ===
echo [4/6] 解压...
if exist "_new" rmdir /S /Q "_new" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try{ Expand-Archive -Path '%ZIP%' -DestinationPath '_new' -Force; Write-Host '       解压成功' }" ^
  "catch{ Write-Host '       解压失败:' $_.Exception.Message; exit 4 }"
if errorlevel 4 goto :FAIL
if not exist "_new\serve.py" goto :FAIL
echo.

rem === 5. 覆盖（保留本机配置与数据）===
echo [5/6] 覆盖文件（保留 db_conf.json / staff_auth.json / out 数据）...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$skip = @('db_conf.json','staff_auth.json','records.json','assignments.json','回访名单.xlsx','dispatch_history.json');" ^
  "$src='_new'; $dst='.';" ^
  "Get-ChildItem -Path $src -Recurse -File | ForEach-Object {" ^
  "  $rel = $_.FullName.Substring((Resolve-Path $src).Path.Length + 1);" ^
  "  if ($skip -contains $_.Name) { return }" ^
  "  $t = Join-Path $dst $rel;" ^
  "  $d = Split-Path $t -Parent;" ^
  "  if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }" ^
  "  Copy-Item $_.FullName -Destination $t -Force" ^
  "};" ^
  "Write-Host '       覆盖完成'"
echo.

rem === 6. 校验版本号 ===
echo [6/6] 校验版本号...
findstr /C:"v10.28.57" serve.py        >nul && echo       serve.py       OK || echo       serve.py       版本异常
findstr /C:"v10.28.57" build_lists.py  >nul && echo       build_lists.py OK || echo       build_lists.py 版本异常
findstr /C:"v10.28.57" gen_dashboard.py >nul && echo      gen_dashboard.py OK || echo     gen_dashboard.py 版本异常
echo.
echo ==============================================================
echo   升级完成！接下来会自动启动 start.bat
echo   启动后请点一次「同步」，让新版本重新生成看板（列式编码）
echo   页面右上角版本号应为 v10.28.57（不是就按 Ctrl+F5 强刷）
echo ==============================================================
echo.
pause
if exist "start.bat" start "" "start.bat"
goto :EOF

:DLFAIL
echo.
echo [下载失败] 可能原因：本机无外网 / 公司网络拦截
echo 解决办法：在浏览器打开下面的链接手动下载，解压覆盖到本目录：
echo   https://ae71ffa2092522eec.sh7.agentos-app.net/
echo.
pause
goto :EOF

:FAIL
echo.
echo [升级失败] 解压或覆盖出错，原目录未受影响。
echo 可手动下载完整包解压覆盖：
echo   https://ae71ffa2092522eec.sh7.agentos-app.net/
echo.
pause
goto :EOF
