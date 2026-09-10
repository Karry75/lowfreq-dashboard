@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title 部署自检 v10.28.40

echo ============================================================
echo   部署自检 v10.28.40
echo ============================================================
echo.

cd /d "%~dp0"

echo [STEP 1] 检查核心文件版本号
echo ------------------------------------------------------------
for %%F in (build_lists.py gen_dashboard.py fix_records.py serve.py auto_update.py) do (
    if exist "%%F" (
        set "v="
        for /f "tokens=2 delims='" %%V in ('findstr /R /C:"__VERSION__ = '" "%%F" 2^>nul') do set "v=%%V"
        if not defined v (
            for /f "tokens=2 delims='" %%V in ('findstr /R /C:"SERVE_VERSION = '" "%%F" 2^>nul') do set "v=%%V"
        )
        if not defined v (
            for /f "tokens=2 delims='" %%V in ('findstr /R /C:"'version': '" "%%F" 2^>nul') do set "v=%%V"
        )
        if not defined v ( set "v=[未带版本号]" )
        echo   %%F  ^:  !v!
    ) else (
        echo   %%F  ^:  [未找到]
    )
)
echo.

echo [STEP 2] 关键代码特征检查（33 项）
echo ------------------------------------------------------------
set PASS=0
set FAIL=0

REM 1) calibrate_soc 定义在前（电池数据回填的根）
findstr /C:"def calibrate_soc" build_lists.py >nul 2>&1 && (
    findstr /C:"_cal = calibrate_soc" build_lists.py >nul 2>&1 && (
        echo   [OK]  电池校准函数定义在前（fix for v10.28.30^)
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] 电池校准函数定义在后！会导致 NameError，电池字段全空
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 未找到 calibrate_soc 函数
    set /a FAIL+=1 >nul
)

REM 2) to_ms datetime 兼容
findstr /C:"hasattr(ts, 'timestamp')" build_lists.py >nul 2>&1 && (
    echo   [OK]  to_ms datetime 兼容
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] to_ms datetime 兼容缺失
    set /a FAIL+=1 >nul
)

REM 3) cb_battery 电气字段兜底
findstr /C:"v10.28.30" build_lists.py >nul 2>&1 && (
    findstr /C:"_b_pow = pick_col(cur, 'cb_battery', 'power'" build_lists.py >nul 2>&1 && (
        echo   [OK]  cb_battery 电气字段兜底
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] cb_battery 兜底代码存在但电气字段不完整
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] cb_battery 电气字段兜底缺失
    set /a FAIL+=1 >nul
)

REM 4) _circ_from_log 流通表来源标记
findstr /C:"_circ_from_log" build_lists.py >nul 2>&1 && (
    echo   [OK]  流通表来源标记（修复 0 名单）
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 流通表来源标记缺失
    set /a FAIL+=1 >nul
)

REM 5) 昨日口径开关
findstr /C:"use_need_followup_filter" build_lists.py >nul 2>&1 && (
    echo   [OK]  低频名单正常出（昨日口径）
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 低频名单过滤开关缺失
    set /a FAIL+=1 >nul
)

REM 6) 低频用户数据分析 7 筛选 HTML
findstr /C:"id=\"aProduct\"" gen_dashboard.py >nul 2>&1 && (
    echo   [OK]  低频用户数据分析 7 维度筛选
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 低频用户数据分析 7 维度筛选缺失
    set /a FAIL+=1 >nul
)

REM 7) 导出全部开关
findstr /C:"__EXPORT_ALL__" gen_dashboard.py >nul 2>&1 && (
    echo   [OK]  导出全部开关（双模式导出）
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 导出全部开关缺失
    set /a FAIL+=1 >nul
)

REM 8) 电池最后定位 lla 回退
findstr /C:"r.lla||r.cloc||r.bloc" gen_dashboard.py >nul 2>&1 && (
    echo   [OK]  电池最后定位 lla 回退
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 电池最后定位 lla 回退缺失
    set /a FAIL+=1 >nul
)

REM 9) vTag 自动同步版本号
findstr /C:"__VTAG__" gen_dashboard.py >nul 2>&1 && (
    echo   [OK]  顶部版本标签自动同步
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 顶部版本标签未做自动同步
    set /a FAIL+=1 >nul
)

REM 10) records._meta 版本元数据
findstr /C:"build_lists_version" build_lists.py >nul 2>&1 && (
    echo   [OK]  records._meta 写入版本号
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] records._meta 缺失（build_lists.py 是 v10.28.32 或更旧）
    set /a FAIL+=1 >nul
)

REM 11) 导出按钮在筛选条内
findstr /C:"v10.28.37" gen_dashboard.py >nul 2>&1 && (
    findstr /C:"btnAnalysisCsv" gen_dashboard.py >nul 2>&1 && (
        echo   [OK]  导出按钮已挪到筛选条内（v10.28.34+^)
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] gen_dashboard 标记了 v10.28.37 但找不到导出按钮代码
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] gen_dashboard 仍是 v10.28.33 旧版（导出按钮埋在表格下面）
    set /a FAIL+=1 >nul
)

REM 12) v10.28.35 登录凭证持久化
findstr /C:"ensure_auth_file" serve.py >nul 2>&1 && (
    findstr /C:"staff_auth.seed.json" auto_update.py >nul 2>&1 && (
        findstr /C:"reset_admin_default" serve.py >nul 2>&1 && (
            echo   [OK]  登录凭证持久化已落地（ensure_auth_file + 种子保留 + 找回默认密码^)
            set /a PASS+=1 >nul
        ) || (
            echo   [FAIL] 找回默认密码接口缺失（serve.py 无 reset_admin_default^)
            set /a FAIL+=1 >nul
        )
    ) || (
        echo   [FAIL] auto_update.py 未保留 staff_auth.seed.json
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] serve.py 缺少 ensure_auth_file（升级会清空账号密码^)
    set /a FAIL+=1 >nul
)

REM 13) v10.28.36 新增：Excel 导出服务端端点
findstr /C:"_api_export_analysis_xlsx" serve.py >nul 2>&1 && (
    echo   [OK]  Excel 导出服务端端点 _api_export_analysis_xlsx
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 服务端缺失 Excel 导出端点（serve.py 无 _api_export_analysis_xlsx^)
    set /a FAIL+=1 >nul
)

REM 14) v10.28.36 新增：Excel 导出按钮（前端）
findstr /C:"btnAnalysisXlsx" gen_dashboard.py >nul 2>&1 && (
    echo   [OK]  低频用户数据分析 Excel 导出按钮（筛选/全部）
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 前端缺少 Excel 导出按钮（btnAnalysisXlsx^)
    set /a FAIL+=1 >nul
)

REM 15) v10.28.36 新增 + v10.28.38 改进：open_firewall.bat（双击自动提权放行）
if exist "open_firewall.bat" (
    echo   [OK]  open_firewall.bat 存在（双击即可自动提权放行端口，无需右键管理员）
    set /a PASS+=1 >nul
) else (
    echo   [FAIL] 缺少 open_firewall.bat（同事可能打不开局域网链接）
    set /a FAIL+=1 >nul
)

REM 16) v10.28.36 改进：防火墙规则 profile=any（公共/来宾网络也生效）
findstr /C:"profile=any" serve.py >nul 2>&1 && (
    echo   [OK]  防火墙规则 profile=any（不限于专用网络）
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 防火墙规则未加 profile=any（连公共网络时可能不生效）
    set /a FAIL+=1 >nul
)

REM 17) v10.28.36 改进：lan_info 返回 firewall_ok 自检
findstr /C:"firewall_ok" serve.py >nul 2>&1 && (
    echo   [OK]  生成链接时自检防火墙状态（firewall_ok^)
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] lan_info 未返回 firewall_ok（无法提示同事打不开的原因）
    set /a FAIL+=1 >nul
)

REM 18) v10.28.37 新增：打开即用离线兜底（有 records.json 即开，无需连库）
findstr /C:"v10.28.37：离线兜底" serve.py >nul 2>&1 && (
    echo   [OK]  打开即用离线兜底（本地有 records.json 即生成看板，断网也能开）
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 缺少离线兜底（out 被清空且连不上库时会一直停在「首次同步」）
    set /a FAIL+=1 >nul
)

REM 19) v10.28.37 新增：DATA 注入转义 </script>（防数据破坏 HTML 结构）
findstr /C:"replace('</script>'" gen_dashboard.py >nul 2>&1 && (
    echo   [OK]  DATA 注入转义 </script>（字段含该串也不会破坏页面）
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] DATA 注入未转义 </script>（某字段含该串会切断 HTML 导致白屏）
    set /a FAIL+=1 >nul
)

REM 20) v10.28.37 新增：records.json 损坏兜底（不再整脚本崩溃）
findstr /C:"使用空数据兜底" gen_dashboard.py >nul 2>&1 && (
    echo   [OK]  records.json 读取失败兜底（损坏也不崩，打开不卡死）
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 缺少 records.json 损坏兜底（文件坏会整脚本崩溃，看板打不开）
    set /a FAIL+=1 >nul
)

REM 21) v10.28.37 新增：前端全局 onerror 兜底（出错显示红条而非白屏）
findstr /C:"页面渲染出错（可尝试刷新或重新同步一次）" gen_dashboard.py >nul 2>&1 && (
    echo   [OK]  前端全局错误兜底（渲染异常显示提示而非白屏卡死）
    set /a PASS+=1 >nul
) || (
    echo   [FAIL] 缺少前端全局错误兜底（一旦报错只能白屏）
    set /a FAIL+=1 >nul
)

REM 22) v10.28.38 新增：防火墙 self-elevating（双击 open_firewall.bat 自动提权放行，无需右键管理员）
findstr /C:"_try_elevate_firewall" serve.py >nul 2>&1 && (
    findstr /C:"Start-Process -FilePath" open_firewall.bat >nul 2>&1 && (
        echo   [OK]  防火墙双击自动提权放行（serve 启动自动请求 UAC，无需手动右键管理员）
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] open_firewall.bat 未改造为 self-elevating（双击不会自动提权）
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] serve.py 缺少 _try_elevate_firewall（启动不会自动请求放行防火墙）
    set /a FAIL+=1 >nul
)

REM 23) v10.28.39 新增：detached 模式不再卡死（_pause_for_user + isatty 判断）
findstr /C:"_pause_for_user" serve.py >nul 2>&1 && (
    findstr /C:"stdin.isatty" serve.py >nul 2>&1 && (
        echo   [OK]  服务启动失败不再静默退出（_pause_for_user + isatty 兼容 detached 模式）
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] serve.py 有 _pause_for_user 但未做 isatty 判断（仍可能卡死）
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 缺少 _pause_for_user（detached 模式下 input() 卡死导致端口永远不监听）
    set /a FAIL+=1 >nul
)

REM 24) v10.28.39 新增：_write_serve_status（外部可探测服务是否真的活）
findstr /C:"_write_serve_status" serve.py >nul 2>&1 && (
    findstr /C:"SERVE_STATUS_FILE" serve.py >nul 2>&1 && (
        echo   [OK]  健康状态文件 out/_serve_status.json（外部脚本可探测服务真活假活）
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] serve.py 有 _write_serve_status 但未定义 SERVE_STATUS_FILE
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 缺少 _write_serve_status（无法外部判断服务真活假活）
    set /a FAIL+=1 >nul
)

REM 25) v10.28.39 新增：/api/health 最小存活端点
findstr /C:"api/health" serve.py >nul 2>&1 && (
    findstr /C:"\"ok\": True" serve.py >nul 2>&1 && (
        echo   [OK]  /api/health 存活端点（最小 GET，start.py 用它判断"是不是我们的服务"）
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] serve.py 有 /api/health 但 ok 字段不规范
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 缺少 /api/health 端点（端口被别的程序占着也会被误判为"服务起来"）
    set /a FAIL+=1 >nul
)

REM 26) v10.28.39 新增：kill_port_occupants（启动前自动清残留 pythonw.exe）
findstr /C:"kill_port_occupants" start.py >nul 2>&1 && (
    findstr /C:"taskkill" start.bat >nul 2>&1 && (
        echo   [OK]  启动前自动清理端口残留（kill_port_occupants + start.bat taskkill）
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] start.py 有 kill_port_occupants 但 start.bat 没 taskkill
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 缺少端口残留清理（旧 pythonw.exe 占着 8173 会让新 serve 起不来）
    set /a FAIL+=1 >nul
)

REM 27) v10.28.39 新增：troubleshoot.bat（一键自检）
if exist "troubleshoot.bat" (
    echo   [OK]  troubleshoot.bat 一键自检（端口/Python/日志全诊断）
    set /a PASS+=1 >nul
) else (
    echo   [FAIL] 缺少 troubleshoot.bat（出问题时用户无从下手）
    set /a FAIL+=1 >nul
)

REM 28) v10.28.40 新增：gzip 压缩（解决同事打开链接一直转圈）
findstr /C:"Content-Encoding" serve.py >nul 2>&1 && (
    findstr /C:"gzip" serve.py >nul 2>&1 && (
        echo   [OK]  响应 gzip 压缩（看板 HTML 体积降至约 1/8，同事打开不再转圈）
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] serve.py 引用了 Content-Encoding 但没有 gzip 逻辑
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 缺少 gzip 压缩（大 HTML 原样传输，同事打开会一直转圈）
    set /a FAIL+=1 >nul
)

REM 29) v10.28.40 新增：HTML 内存缓存（避免每请求重读数十 MB）
findstr /C:"_read_dashboard_html" serve.py >nul 2>&1 && (
    findstr /C:"_HTML_CACHE" serve.py >nul 2>&1 && (
        echo   [OK]  看板 HTML 内存缓存（按 mtime 复用，多人访问不再反复读盘）
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] 有 _read_dashboard_html 但缺 _HTML_CACHE
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 缺少 HTML 缓存（每个请求都重读大文件，多人访问变慢）
    set /a FAIL+=1 >nul
)

REM 30) v10.28.40 新增：回访效果判定函数 _judge_effect
findstr /C:"def _judge_effect" build_lists.py >nul 2>&1 && (
    findstr /C:"EFFECT_GRADES" build_lists.py >nul 2>&1 && (
        echo   [OK]  回访效果判定函数 _judge_effect + 9 档状态定义
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] 有 _judge_effect 但缺 EFFECT_GRADES
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 缺少 _judge_effect（回访效果无法判定）
    set /a FAIL+=1 >nul
)

REM 31) v10.28.40 新增：电池借出时间索引（方案B核心）
findstr /C:"battery_take_times" build_lists.py >nul 2>&1 && (
    findstr /C:"_is_take_sec" build_lists.py >nul 2>&1 && (
        echo   [OK]  电池借出时间索引（精确算"接待后第 N 天换电"）
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] 有 battery_take_times 但缺 _is_take_sec 口径函数
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 缺少借出时间索引（回访效果会降级为粗略判定）
    set /a FAIL+=1 >nul
)

REM 32) v10.28.40 新增：effect_summary.json 聚合输出
findstr /C:"build_effect_summary" build_lists.py >nul 2>&1 && (
    findstr /C:"effect_summary.json" build_lists.py >nul 2>&1 && (
        echo   [OK]  回访效果聚合输出 effect_summary.json
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] 有 build_effect_summary 但未写出 json
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 缺少 build_effect_summary（看板拿不到聚合数据）
    set /a FAIL+=1 >nul
)

REM 33) v10.28.40 新增：前端「回访效果」Tab
findstr /C:"data-v=\"effect\"" gen_dashboard.py >nul 2>&1 && (
    findstr /C:"renderEffect" gen_dashboard.py >nul 2>&1 && (
        echo   [OK]  前端「回访效果」Tab（KPI/漏斗/排行/分布/明细下钻）
        set /a PASS+=1 >nul
    ) || (
        echo   [FAIL] 有 Tab 按钮但缺 renderEffect 渲染逻辑
        set /a FAIL+=1 >nul
    )
) || (
    echo   [FAIL] 前端缺少「回访效果」Tab
    set /a FAIL+=1 >nul
)

echo.
echo   通过 PASS=!PASS!  / 失败 FAIL=!FAIL!
echo.

if !FAIL! GTR 0 (
    echo [结论] 部署不完整，请下载最新完整包解压覆盖后再运行。
) else (
    echo [结论] 部署完整！v10.28.40 全部 33 项自检通过。
    echo.
    echo   本次重点（服务起不来/同事打不开 的治本方案）^:
    echo   - serve 启动失败不再静默退出，会把原因写在黑窗口停留 8 秒；
    echo   - 启动前自动 taskkill 残留 pythonw.exe，避免「端口被占 → 127.0.0.1 拒绝连接」；
    echo   - 出错时 troubleshoot.bat 一键自检（Python/端口/日志全列出来）。
    echo   仍打不开时：双击 troubleshoot.bat 把输出发我即可定位。
    echo.
    echo   浏览器若仍看不到新按钮：Ctrl+Shift+R 强刷（清缓存^) 或关掉重开。
)

echo.
echo ============================================================
pause
