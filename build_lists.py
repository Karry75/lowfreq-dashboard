# -*- coding: utf-8 -*-
__VERSION__ = 'v10.28.57'  # v10.28.57：性能专项——XLSX 改用 append 批量写（12万行分钟级→20s）、build_xlsx 开关、records 写盘单次化、schema 磁盘缓存
#   v10.28.55 用户实测后追加修复（基于 v10.28.55 排行仍显 0-19、布局拥挤的反馈）：
#     - 前端 fmtSolver() 兜底：1~6 位纯数字统一显示「员工#N」，不再依赖 records.json 重跑。
#       即使后端员工表探测失败 / records.json 是旧版，前端也保证不裸显 0/1/2...。
#     - 排行聚合 key 用 fmtSolver 格式化；下拉选项、筛选匹配、明细展示全链路一致。
#     - 「接待人/标签」多选框加边框+「按住 Ctrl/⌘ 多选」提示，避免被误以为是普通 select。
#     - 顶部「系统更新」条加折叠按钮（默认展开；点「▾ 收起」折叠成 1 行，留 1 个「▴ 展开」按钮）。
#     - 同步优化：填充排序时把「员工#N」统一放到列表尾部，正常姓名按 zh-Hans-CN 排序。
#   v10.28.55 协议维度未换电天数：
#     - records.lcts / aid_last_swap_ms 优先取 aid_swap_times[aid]（协议维度），与客服服务台"换电操作日志"对齐；
#     - 保留 bsn_lcts 字段记录电池 SN 维度原值供排查。
#   v10.28.55 五项修复（基于 v10.28.55 用户实测反馈）：
#     - ① 接待人 / 标签 筛选支持多选：前端 <select multiple>，按 Ctrl/Cmd 多选；前端 efApplyFilter 改用 selectedOptions 多值匹配。
#     - ② 排行/标签效果不再显示 0/1 序号：solver 纯数字且无映射时 fallback「员工#N」；type 为数字时经 db_conf.recp_type_map 反查中文标签，
#       仍查不到则标签兜底「标签#N」（不再裸显示 0/1）。并提供 db_conf.json.solver_id_map / recp_type_map 手动配置真实名称。
#     - ③ 流通异常全量识别：扩展 _is_abnormal_status 与 ABNORMAL_STATUS_SQL 关键词（未识别/断充/上报/识别失败/设备异常/柜回收 等）；
#       扩展 BT_SECOND_MAP（调拨-回收 / 换电柜上报未识别 / 设备故障 / 换电-更多操作:还电池 等）。
#     - ④ 末次流通统一格式展示：新增 battery_circ[sn]['full'] =「时间 因[类型]流通至[目的地]」，覆盖所有流通场景（含员工取电池/调拨回收），
#       经 records.circ_full 透传到 reception_detail.battery_circ_full，前端「末次流通」列与行展开时间轴均按此展示。
#     - ⑤ 覆盖场景：员工取电池（调拨-回收→代理商员工仓库）、设备识别失败（消费者已归还但换电柜断充未识别，后续上报电池在柜内）均已纳入识别与展示。
# 版本：v10.28.55 · 2026-09-01
#   配合 serve.py::/api/force_run 自动重生成 HTML（解决 force_run 后接待/效果 Tab 看不到新 DATA）；
#   serve.py 启动期加 records.json mtime vs followup_dashboard.html mtime 兜底；
#   顶部版本号与 SERVE_VERSION 联动（dashboard 顶部 vTag 自动更新）。
#   v10.28.55：serve.py::/api/redispatch 调 run_assignment 前用 importlib.reload(assign) 强制重新
#            加载磁盘上的最新代码，避免「磁盘是新版、内存是旧版」导致按钮一按还是出老结果。
#            同样：/api/force_run 一站式端点（重建数据 + 生成名单 + 返回统计）。
#   v10.28.55：加「数据源体检」输出（aid_last_order / battery_last_report / battery_circ / battery_info
#            各自规模 + records 中 battery_sn/circ_in/circ_abn 非空数）。
#   v10.28.55：fix_records.py 完全 inline，不调 subprocess。
#   v10.28.55：v10.28.55 字段自愈改造时漏改的 r['solver_user_name'] KeyError。
#   v10.28.55：第 1627 行 GROUP BY 后用 r['solver_user_name'] 取值 → KeyError。
#            v10.28.55 把 SELECT 列都加了别名 _s，但这个位置没改，导致抽数整体崩。
#            改为 r['_s']。同时把 v10.28.55/v10.28.55/v10.28.55 的所有修复全部继承。
#   v10.28.55：assign.py force 模式按产品口径改为「清空所有待回访历史，assigned_aids 仅含 nof_aids」。
#   v10.28.55：assign.py::run_assignment('force') 改为「清空所有待回访历史任务（不限日期），
#            assigned_aids 仅含 nof_aids（无需回访白名单）」。低频用户只要是 followable，
#            无论他之前是否被分配过，无论他处于什么历史状态，都进回访名单。
#            集成测试：候选池 40 条 → 全部 40 条进入名单（华平平 30 / 黄连霞 10）。
#   v10.28.55：assigned_aids 不再永久排除已过冷却期的（部分修复，方向对但力度不够）。
#   v10.28.55：【名单恒为 0 的真凶，已用对照实验坐实】
#            根因在 assign.py（不在 build_lists.py）：force 模式先清空「当日」任务，
#            然后 assigned_aids = 剩余【所有历史任务】的协议ID —— 即一个协议只要
#            曾经被分配过一次，就永远不再进名单。低频用户池本就固定（同一批人反复
#            出现），跑几次生成后候选被吃光 → 名单恒为 0，且下方「冷却窗口(cd_days)」
#            因此完全形同虚设（人早被上一层排掉了）。
#            修复：历史任务分三类处理——
#              ① 仍「待回访」→ 保留排除（还没回访完，不重复打扰）
#              ② 已回访 且 在冷却期内 → 排除
#              ③ 已回访 且 已过冷却期 → 允许重新进入名单（这才是冷却窗口该做的事）
#            对照实验（候选池 40：20 已回访30天前 / 20 待回访）：
#              旧逻辑 → 新增 0 条   |   新逻辑 → 新增 20 条，且 20 条待回访全部正确保留
#   v10.28.55：【为什么页面上「电池定位 / 上次接待时间 / 上次回访内容」全是「—」——两个真 BUG】
#   v10.28.55：【为什么页面上「电池定位 / 上次接待时间 / 上次回访内容」全是「—」——两个真 BUG】
#            BUG-1 字段名张冠李戴：电池定位段写 SELECT battery_device_sn ... FROM cb_battery，
#                  但 battery_device_sn 是「流通表」cb_battery_circulate_log 的列名；
#                  「电池表」cb_battery 的 SN 列叫 device_sn（本文件 2.5 段就是这么查的）。
#                  → 在电池表上执行会抛 1054 Unknown column，被 try/except 静默吞掉，整列变「—」。
#            BUG-2 取值方式错：cur 是 DictCursor（连接处 cursorclass=DictCursor），
#                  但电池定位段用 _br[0]/_br[1]/_br[2] 整数下标取列 → KeyError: 0 → 同样整列变「—」。
#                  也就是说，即使 BUG-1 修好了，BUG-2 依然会让这一段全军覆没。
#            修复：新增 table_columns()/pick_col()/audit_db_fields() 三个工具，
#                  运行期先 SHOW COLUMNS 探测真实字段集，再在候选名里挑真实存在的列去查；
#                  取值统一按列名（兼容 dict/tuple 两种 cursor）。
#            新增【数据库字段体检】：每次抽数打印各表字段「是否存在 + 非空率」，
#                  直接回答「上次接待时间/上次回访内容/电池定位/归属地 到底有没有数据」。
#                  另：接待记录命中率低于 5% 时主动告警，提示协议关联字段口径可能不一致。
#   v10.28.55：集成 should_follow_up 规则到 followable 判定。
#            之前 followable 只看 (is_lf & !excluded)，但 shouldFollowUp 判定的"用户已主动结束换电周期"
#            （最后操作=柜内归还电池 + 电池SN=暂无电池）只写到 need_followup 字段，assign.py 候选过滤
#            只认 followable 不认 need_followup，导致：
#              - 已经主动还完电池但 is_lf=True 的协议 → 错进候选
#              - 应该需要回访但 is_lf=False 的协议（被 recent_swap_filter_days=15 排除）→ 漏出名单
#            现在 followable = is_lf & !excluded & need_followup，三者全真才进名单，与 8 月 12 号规则对齐。
#   v10.28.55：①【电量校准】cb_battery_status.power 是 BMS 最近一次上报值，长期未上报时会"虚高"。
#                  引入校准公式：calibrated = max(0, min(100, raw_soc − 距上次上报天数 × SELF_DISCHARGE_PER_DAY))。
#                  自放电率/陈旧阈值等常量集中放在文件头「电量校准常量」段，统一可改。
#                  新增「电量（实测/校准）」列：实测=BMS 最新上报值，校准=考虑自放电后的当前估值。
#                  db_conf.json 可用 battery_calibration 字段覆盖默认值（无需重打包）。
#            ②【账号保留】升级时 PRESERVE_FILES 把 staff_auth.json 加进来，避免看板内"粘贴直链升级"覆写管理员设置的账号/密码。
#            ③ 附送 staff_auth.seed.json 作为首次安装兜底（绝不会盖已有本地账号）。
#   v10.28：① 接入 cb_battery.last_location_address / last_location_time 真实字段
#            ——「车辆最后定位地址」从 v10.27 临时回退的 loc 网点名升级为 cb_battery.last_location_address
#            —— 新增「最后有效定位时间」列（毫秒戳 → yyyy-MM-dd HH:mm:ss）
#            —— 数据按 SN 批量查 cb_battery（500/批）；查询失败/无字段时回退原行为（loc 网点名）
#   v10.27：①【离线号段版】强制关闭 ip138.com Web 接口，仅用本地 phone.dat 号段库判定归属地，
#            零外网依赖，适合无法访问外网/ip138 的网段与 VPN 环境（避免请求超时卡死）。
#         ②【启动自检】运行即打印版本号 + 归属地模式横幅，一眼看出当前跑的是哪个版本。
#   v10.26：归属地升级 + dnr 按计划回访日 + 月均频次格式化
#     ① 手机号归属地：默认 49.9 万号段库查表，新增 --use-ip138 选项（调 ip138.com Web 接口查归属地，覆盖冷门/新放号段），
#        查不到时回退本地号段库；输出字段新增 `psrc` 标记来源（seg/ip138）
#     ② 距今未换电天数(dnr)：公式改为 计划回访日期 − 电池最新一条流通记录时间。
#        build 阶段输出 `lcts`（电池最后记录毫秒戳），前端 rowHtml 用 planDate - lcts 实时算 dnr，
#        planDate 变化时表格自动重算。
#     ③ 月均换电频次：前端展示统一格式化为 "X.X次/月"（build 输出数值不变，仅渲染时格式化）
#   v10.25：键名修复（长键→短键）+ 换电周期取中位间距 + 新增下次预计换电日
#   v10.24：回访排班指标升级
#     ① 手机号归属地：直接显示城市名（如「深圳」「茂名」），不与租赁省做本地/外地对比（替代 v10.22 的 ploc）
#     ② 距今未换电天数：公式改为 今天 − 电池最新一条「任意」流通记录时间（替代 v10.22 的 dns，后者是按最后换电时间）
#     ③ 车辆最后定位地址：新增字段（来源 cb_battery_circulate_log.addr；DB 探测后回填；当前表内无 addr 字段时回退 loc 网点名）
#   v10.22：回访排班新增指标 —— 月均换电频次 / 换电周期(天) / 未换电天数 / 当前手机号本地·外地(内置号段库比租赁省份) /
#           电池最后定位地址(最新流通记录网点名) / 电池流通时间按季度(筛选维度)
#   v10.21.2：
#     - 修复电池异常原因缺失：v10.21 用 battery_last_report（流通表最新一条任意记录）覆盖异常原因，
#       当电池最后流通是「柜内借出」时（正常业务），会把之前的「换电柜上报/员工回收」等异常记录全部抹掉。
#       改为取 cb_battery_circulate_log 异常聚合的「最新一条异常/上报」记录（circ_entry['abn']），
#       与客服管理后台口径一致。
#     - 扩大异常识别范围：ABNORMAL_STATUS_SQL 增补业务字段识别
#       （business_type_second LIKE '%上报%' / '%未识别%' / '%员工回收%' / '%柜回收%'），
#       防止 status 字段非「异常」但业务上已是上报事件的情况漏判。
#   v10.21：
#     - 冻结「今日待分配」「回访调度」表头：两表包入 .tbl-scroll 容器，纵向/横向滚动时列名固定。
#     - 「清空重生成」改为按计划日期全量清空当日所有任务后重新生成（真正实现"全部清空待回访名单后生成"）。
#     - 7 天冷却修复：last_visit_by_aid 纳入所有带接待时间的记录（仅排除纯系统类 back_validate/sync_order_status/offline_verify），
#       解决"待再次回访"等真实接触不触发冷却、8/17~8/19 记录仍出现的问题。
#     - 15 天换电过滤修正：recent_swap_filter_days 默认 15（db_conf.json 可改），改为「生成时」过滤（不放 followable），
#       避免已分配任务在清重生成时消失/减少。
#     - 电池异常原因重做：取流通表 create_time 最新一条记录，展示「时间 因【操作类型】流通至【位置】」；
#       仅当最新记录说明电池已离开消费者（op≠柜内借出）才显示异常。新增「最后流通类型」筛选维度。
#     - 按人权限：staff.json 新增 user_permissions（姓名→可见模块+可同步）；「人员权限」弹窗按人配置并生成 ?user= 专属链接；
#       共享模式下按人限制可见模块，can_sync 者放行「同步数据库」按钮。
#   v10.20：
#     - 协议状态文字统一改：'working' → 生效中（之前误为「正常」）；'owe_rent' → 欠租；'unsubscribing' → 退订中。
#       涉及：build_lists.py / gen_dashboard.py（5 个下拉 + 6 处 JS 渲染 + 排班总览 dAgrStatus）。
#     - 新增「当前手机号」字段：按 user_id 查 cb_user.mobile / cb_user.phone / cb_user_mobile 最新一条，
#       3 档 try/fallback；最坏退化到 cb_exchange_agreement.user_phone。
#     - 追加排班语义重构：assign.py 新增 mode='extra' 分支，仅对本次传入的 extra_solvers(name→quota)
#       单独分配，原名单完全不动。btnAppend 改为弹窗选人+填数量。
#     - 新增 db_conf.json::recent_swap_filter_days 配置项：>0 时把近 N 天换电的协议排除出 followable。
#       默认 0 不过滤；想开就在 db_conf.json 改成 15。
#   v10.19.2：
#     - 「标记为无需回访」下拉新增「空号联系不上」「系统数据错误·4814电池」两个 reason。
#       选了某 reason 后该 aid 写入 no_followup.json；下次同步时进入 NO_FOLLOWUP_AIDS 集合，
#       记录 excluded='空号/无需回访'，不再进入回访名单（同类排除），且在「无需回访」Tab 展示明细。
#   1. 电池SN/流通时间/操作类型/异常原因四字段严格同源：统一从 cb_battery_circulate_log 聚合取，
#      并用规范化SN(strip+upper)消除 cb_exchange_order 与流通表两表SN字符串漂移导致的异常原因错位。
#   2. 前端：筛选区下方恢复醒目「🟢 生成回访名单」主按钮(增量)；「立即重新分配」改为「🔄 同步刷新任务」(mode=sync)。
#      （此前 is_lf 为原始判定，被剔除用户仍进候选池 → 名单出现"近15天有流通""空号""换电柜上报晚于操作流通"）
#   2. 生成按钮拆为「➕追加排班」(增量,保留原名单) + 「🔄清空重生成」(覆盖)
#   3. 批量改派仅改派待回访；新增「作废该人分配」(释放协议回待分配池)
#   1) L1~L4 判定原来用 total（全历史累计换电），导致 0 次/偶发换电的老用户全归到 L4（量级虚高到 7000+）。
#      按"8月12号口径"改为窗口内换电：
#        L1(15~30天)→c30 / L2(30~45天)→c45 / L3(45~60天)→c60 / L4(>60天)→c60
#   2) 流通异常用户（借出后又有更晚流通记录、柜内归还=暂无电池）没作为过滤条件，
#      出现在回访名单里但电池实际已不在用户手里。本次新增：若 battery_circ.abn 非空或 circ==0（无电池），
#      则不写入 lf_list（不入回访名单），但保留 records 用于诊断。
#   v10.18.3 · 2026-08-19
#     修复 L5（电量<25%）用户同步导出 Excel 时 KeyError: 5
#     - LF_FILL 字典补全第 5 档颜色（9FC5E8 浅蓝），与 L1-L4 渐变区分
#     - 欠租催收 sheet 也包含低频用户，此处颜色缺失会导致整步同步失败
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import sys, traceback, io
import json, datetime, os, re
from assign import classify_recall, DEFAULT_CAT

# ---- v10.27：启动版本自检横幅（第一时间打印，连库/加载前即可见，一眼看出当前版本）----
def _print_startup_banner():
    print('=' * 64)
    print(f'  build_lists.py 启动自检  |  版本 {__VERSION__}  |  时间 {datetime.datetime.now():%Y-%m-%d %H:%M:%S}')
    print('  归属地来源：离线(仅本地 phone.dat 号段库，零外网依赖)')
    print('=' * 64)

_print_startup_banner()

# Windows 控制台默认可能是 GBK，子进程输出被父进程用 UTF-8 读时会解码失败。
# 强制 stdout/stderr 使用 UTF-8 编码，避免同步链路出现 UnicodeDecodeError。
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

BASE = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录（部署后即为本地运行目录）

# ---- 代理商（总代理）推导 ----
# 代理商以签约网点（cb_site）所属城市为单位，默认 = 城市 + "总代理"（如 深圳->深圳总代理、杭州->杭州总代理）。
# 若某些城市有专属代理商名称，在此字典覆盖即可（如 {'深圳':'深圳特区总代理'}）。
CITY_AGENT = {}
def agent_of(city):
    city = (city or '').strip()
    if not city:
        return ''
    return CITY_AGENT.get(city, city + '总代理')

# 电池流通业务类型中文映射（异常原因展示用）
BT_SECOND_MAP = {
    'take_battery': '换电-借电池',
    'back_battery': '换电-还电池',
    'exchange_take_battery': '换电-借电池',
    'exchange_back_battery': '换电-还电池',
    'employee_take_battery': '员工-借电池',
    'employee_back_battery': '员工-还电池',
    'site_take_battery': '门店-借电池',
    'site_back_battery': '门店-还电池',
    'artificial_confirm_back': '人工确认归还',
    'back_validate': '归还验电',
    'take_first_after_back': '借出（还后首借）',
    'offline_verify': '线下核销',
    'sync_order_status': '同步订单状态',
    # v10.28.55：补充流通业务类型映射（覆盖「员工取电池 / 调拨回收 / 换电柜上报未识别」等场景）
    'allocation_recycle': '调拨-回收',
    'allocation_transfer': '调拨-调拨',
    'unidentified': '换电柜上报未识别',
    'upload_unidentified': '换电柜上报未识别',
    'upload_again': '换电柜重新上报',
    'device_fault': '设备故障',
    'exchange_more_back_battery': '换电-更多操作:还电池',
    'exchange_more_take_battery': '换电-更多操作:借电池',
    'more_operation_back': '换电-更多操作:还电池',
    'more_operation_take': '换电-更多操作:借电池',
}

# 捕获所有未处理异常，打印完整 traceback 到 stderr，方便前端/用户定位问题
def _excepthook(exc_type, exc_value, exc_tb):
    lines = []
    lines.append("="*60)
    lines.append("[FAIL] build_lists.py 执行过程中发生未捕获异常")
    lines.append("="*60)
    import io
    buf = io.StringIO()
    traceback.print_exception(exc_type, exc_value, exc_tb, file=buf)
    lines.append(buf.getvalue())
    lines.append("【常见排查】")
    lines.append("1) 检查 lowfreq_local/db_conf.json 的 host/port/user/password/database 是否正确。")
    lines.append("2) 若在公司内网，请把内网地址填到 db_conf.json 的 intranet_host 字段。")
    lines.append("3) 确认本机已连内网/VPN，且数据库白名单包含本机 IP。")
    lines.append("4) 若提示 ModuleNotFoundError，请运行：pip install pymysql openpyxl")
    lines.append("="*60)
    msg = "\n".join(lines)
    print("\n" + msg, file=sys.stderr)
    # 同时写入固定日志文件，方便用户直接查看
    try:
        os.makedirs(os.path.join(BASE, 'out'), exist_ok=True)
        with open(os.path.join(BASE, 'out', 'build_lists_error.log'), 'w', encoding='utf-8') as f:
            f.write(msg)
    except Exception:
        pass
    sys.exit(1)

sys.excepthook = _excepthook

# 依赖缺失时给出明确提示
_MISSING = []
try:
    import pymysql
except Exception as e:
    _MISSING.append(('pymysql', str(e)))
try:
    import openpyxl
except Exception as e:
    _MISSING.append(('openpyxl', str(e)))

if _MISSING:
    print("[FAIL] 缺少必要 Python 依赖：", file=sys.stderr)
    for name, err in _MISSING:
        print(f"   - {name}: {err}", file=sys.stderr)
    print("请在本目录打开命令行，执行：pip install pymysql openpyxl", file=sys.stderr)
    print("或双击 fix_and_sync.bat 自动安装。", file=sys.stderr)
    sys.exit(1)

# v10.28.55：自动重连+重试 helper。
# 背景：探测员工表（cb_admin/cb_staff/cb_user 等）期间，若任何一张表存在但行数很多/索引差，
#  会让 MySQL 端 wait_timeout(默认 28800s) 把空闲连接踢掉（MySQL server has gone away），
#  后续复用同一条 conn/cur 时就抛 pymysql.err.InterfaceError: (0, '')
#  或 pymysql.err.OperationalError: (2013, 'Lost connection to MySQL server')。
#  解决：每次 cur.execute 前 ping(reconnect=True) 探测一次；如失败则自动重连+重试 1~2 次。
import time as _time
def _safe_exec(cur, conn, sql, params=None, retries=2, label=''):
    """自动 ping 重连+重试的执行器。
    :param cur:   pymysql cursor
    :param conn:  pymysql connection（用来 ping/reconnect）
    :param sql:   SQL 字符串
    :param params:参数 tuple/list
    :param retries:重试次数（不含首次）
    :param label:  日志标签（哪个阶段）
    :return:  cur.fetchall() 或 None（DDL 时）
    """
    last = None
    for attempt in range(retries + 1):
        try:
            # 1. 先 ping 一下（reconnect=True 会在断线时自动重连）
            try:
                conn.ping(reconnect=True)
            except Exception:
                pass
            # 2. 执行
            cur.execute(sql, params) if params is not None else cur.execute(sql)
            return None  # DDL 路径：调用方自己 fetch
        except (pymysql.err.InterfaceError, pymysql.err.OperationalError) as e:
            last = e
            tag = f'[{label}] ' if label else ''
            print(f'[v10.28.55] {tag}数据库连接中断 (attempt {attempt+1}/{retries+1}): {e!r}')
            if attempt >= retries:
                print(f'[v10.28.55] {tag}重试 {retries+1} 次仍失败 → 抛出')
                raise
            # 等待并重建连接
            _time.sleep(0.6 * (attempt + 1))
            try:
                # 尝试 reconnect；如 ping 已自动 reconnect 这里会跳过
                conn.ping(reconnect=True)
            except Exception as e2:
                print(f'[v10.28.55] {tag}reconnect 失败: {e2!r}')
                raise
    return None

# ==================== v10.28.55：数据库字段自愈探测 ====================
# 背景：代码里硬编码的字段名与线上库实际字段名不一致时（典型如 cb_battery 的 SN 字段
# 在流通表里叫 battery_device_sn，在电池表里叫 device_sn），SQL 会抛 1054 Unknown column，
# 被外层 try/except 静默吞掉 → 该字段整列显示「—」，且日志里只有一个容易被忽略的 WARN。
# 解决办法：运行期先 SHOW COLUMNS 探测真实字段集，再在候选名里挑一个真实存在的去查。
_TBL_COLS_CACHE = {}
_SCHEMA_DISK_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'schema_cache.json')


def _load_schema_disk_cache():
    """v10.28.57：从磁盘加载已探测过的字段缓存（避免每次同步重复 SHOW COLUMNS 30+ 次）"""
    global _TBL_COLS_CACHE
    try:
        if os.path.exists(_SCHEMA_DISK_CACHE):
            _TBL_COLS_CACHE = json.load(open(_SCHEMA_DISK_CACHE, encoding='utf-8'))
            # key 由 list 转 set
            for k, v in list(_TBL_COLS_CACHE.items()):
                if isinstance(v, list):
                    _TBL_COLS_CACHE[k] = set(v)
    except Exception:
        _TBL_COLS_CACHE = {}


def _save_schema_disk_cache():
    """v10.28.57：把缓存写盘（同步成功后顺手保存，下次启动秒命中）"""
    try:
        os.makedirs(os.path.dirname(_SCHEMA_DISK_CACHE), exist_ok=True)
        out = {k: list(v) if isinstance(v, set) else v for k, v in _TBL_COLS_CACHE.items()}
        json.dump(out, open(_SCHEMA_DISK_CACHE, 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))
    except Exception:
        pass


_load_schema_disk_cache()


def table_columns(cur, table):
    """返回表的字段名集合(小写)。探测失败返回 None（调用方按旧行为降级）。带缓存，每表只查一次。"""
    if table in _TBL_COLS_CACHE:
        return _TBL_COLS_CACHE[table]
    cols = None
    try:
        cur.execute("SHOW COLUMNS FROM %s" % table)
        got = set()
        for r in cur.fetchall() or []:
            if isinstance(r, dict):
                for k in ('Field', 'field', 'COLUMN_NAME'):
                    if k in r:
                        got.add(str(r[k]).strip().lower())
                        break
            elif r:
                got.add(str(r[0]).strip().lower())
        cols = got or None
    except Exception as _e:
        print('[WARN] SHOW COLUMNS %s 失败: %s' % (table, _e))
        cols = None
    _TBL_COLS_CACHE[table] = cols
    return cols


def pick_col(cur, table, *candidates):
    """从候选字段名里挑第一个真实存在的；表探测不到时返回第一个候选（保持旧行为）；
    全部不存在返回 None（调用方需降级）。"""
    cols = table_columns(cur, table)
    if not cols:
        return candidates[0]
    for c in candidates:
        if c and c.lower() in cols:
            return c
    return None


def audit_db_fields(cur, specs):
    """v10.28.55：数据库字段体检——打印每张表的字段是否存在、是否有值（采样 10 万行）。
    这一步直接回答「上次接待时间 / 上次回访内容 / 电池定位 / 归属地 到底有没有数据」。
    specs: [(表名, [字段名...]), ...]"""
    print('')
    print('=' * 66)
    print('  数据库字段体检 (v10.28.55)  —— 采样上限 100000 行/表')
    print('=' * 66)
    for table, fields in specs:
        cols = table_columns(cur, table)
        if cols is None:
            print('[%s] 表不存在或无法访问 —— 依赖它的字段将全部为空' % table)
            continue
        try:
            cur.execute("SELECT COUNT(*) c FROM (SELECT 1 FROM %s LIMIT 100000) s" % table)
            _r = cur.fetchone()
            sample_n = (_r['c'] if isinstance(_r, dict) else _r[0]) if _r else 0
        except Exception as _e:
            print('[%s] 行数统计失败: %s' % (table, _e))
            sample_n = 0
        print('[%s] 采样 %s 行' % (table, sample_n))
        for f in fields:
            if f.lower() not in cols:
                # 给出同表里的近似字段名，方便一眼看出该用哪个
                near = [c for c in sorted(cols) if (f.lower()[:6] in c or c[:6] in f.lower())][:6]
                print('    %-24s 缺失 ✗   同表近似字段: %s' % (f, (', '.join(near) or '无')))
                continue
            try:
                cur.execute(
                    "SELECT SUM(CASE WHEN `%s` IS NOT NULL AND `%s`<>'' THEN 1 ELSE 0 END) nn "
                    "FROM (SELECT `%s` FROM %s LIMIT 100000) s" % (f, f, f, table))
                _r2 = cur.fetchone()
                nn = (_r2['nn'] if isinstance(_r2, dict) else _r2[0]) if _r2 else None
            except Exception as _e:
                print('    %-24s 存在 ✓   取值统计失败: %s' % (f, _e))
                continue
            nn = int(nn or 0)
            pct = (nn * 100.0 / sample_n) if sample_n else 0.0
            flag = '✓ 有值' if pct >= 50 else ('△ 稀疏' if nn > 0 else '✗ 全空')
            print('    %-24s 存在 ✓   非空 %s/%s (%.1f%%)  %s' % (f, nn, sample_n, pct, flag))
    print('=' * 66)
    print('')


def classify(detail, type_):
    """回访标签：根据接待内容(detail)+操作类型(type)做多标签关键字匹配。
    规则覆盖用户第11/12条要求的拆分维度；多标签模型，一条记录可命中多个标签。"""
    d = detail or ''
    t = type_ or ''
    tags = set()
    # v10.28.55：type 字段有时是数字编码（如 0/1/2...），通过 db_conf.json.recp_type_map 反查中文标签，
    # 避免标签效果排行里出现「0/1」序号而非具体标签名称
    if t and t.isdigit():
        try:
            _cfg = json.load(open(os.path.join(BASE, 'db_conf.json'), encoding='utf-8'))
            _tm = (_cfg.get('recp_type_map') or {})
            if t in _tm:
                tags.add(str(_tm[t]))
        except Exception:
            pass
    if any(k in d for k in ['合作门店', '门店合作']): tags.add('门店合作')
    if any(k in d for k in ['员工', '内部员工', '内部']): tags.add('员工内部')
    if any(k in d for k in ['丢失', '遗失']): tags.add('电池丢失')
    if any(k in d for k in ['置换', '更换电池', '换电池']): tags.add('置换')
    if any(k in d for k in ['欠租', '催缴', '催收']): tags.add('欠租催收')
    if any(k in d for k in ['退订', '取消协议', '解约', '终止协议']): tags.add('退订')
    if any(k in d for k in ['投诉']): tags.add('投诉')
    if any(k in d for k in ['退款', '赔偿', '赔付']): tags.add('退款赔偿')
    if any(k in d for k in ['免押金', '支付失败', '转支付', '代扣失败', '扣款失败', '签约失败']): tags.add('免押金转支付失败')
    if any(k in d for k in ['物业', '公关']): tags.add('公关物业')
    if any(k in d for k in ['运营', '活动', '优惠券', '营销']): tags.add('消费者运营')
    if any(k in d for k in ['微信', '加微']): tags.add('微信添加')
    if any(k in d for k in ['赠送电量', '赠送']): tags.add('赠送电量')
    if any(k in d for k in ['锁仓', '受损', '损坏', '故障']): tags.add('受损锁仓')
    if any(k in d for k in ['暂无电池', '手里没电池', '手头没电池', '没有电池', '无电池', '没拿到电池']): tags.add('暂无电池')
    if any(k in d for k in ['暂存', '寄存', '寄放', '暂放', '暂代存放', '暂放电池', '电池暂存']): tags.add('暂存电池')
    if any(k in d for k in ['挂断', '用户挂机', '用户主动挂', '用户挂掉']): tags.add('用户挂断')
    if any(k in d for k in ['流通', '电池流通', '柜内借出电池', '柜内归还电池']): tags.add('电池流通')
    if any(k in d for k in ['美团', '核销']): tags.add('美团核销用户')
    if any(k in d for k in ['被偷', '被盗', '电池被偷', '电池被盗', '车辆电池被偷', '车辆电池被盗']): tags.add('车辆电池被偷')
    if any(k in d for k in ['停机', '已停机', '号码停机', '手机停机']): tags.add('停机')
    if any(k in d for k in ['空号', '号码不存在', '号码无效']): tags.add('空号')
    if any(k in d for k in ['未接听', '无人接听', '用户未接听']): tags.add('未接听')
    if any(k in d for k in ['联系不上', '联系不到', '无法联系', '联系未果']): tags.add('联系不上')
    if any(k in d for k in ['外呼', '电话', '通话']):
        if any(k in d for k in ['未接通', '无法接通', '未接']): tags.add('外呼未接通')
        else: tags.add('电话沟通')
    # 已告知/通知用户换电：接待人直接告知终端用户去换电（不是业务员协助）
    if ('已告知' in d or '已通知' in d or '告知用户' in d or '通知用户' in d) and '换电' in d and '业务员' not in d and '协助' not in d:
        tags.add('已告知换电')
    is_sys = t in ('exchange_take_battery','exchange_back_battery','back_validate','take_first_after_back','artificial_confirm_back','init_order','offline_verify','sync_order_status')
    # 协助换电：业务员/系统协助完成的换电流程
    assist_kw = ['换电订单','操作借出','操作归还','借出电池','归还电池','协助换电','帮忙换电','无法换电','业务员换电','安排人换','代换','帮忙换']
    is_assist = any(k in d for k in assist_kw) or is_sys
    if is_assist and '已告知换电' not in tags:
        # 若明确是「告知用户换电」，不再叠加协助换电；若提到业务员协助，则归协助换电
        if not (('已告知' in d or '已通知' in d) and '用户' in d and '换电' in d and '业务员' not in d):
            tags.add('协助换电')
    if t in ('employee_take_battery','employee_back_battery'): tags.add('员工内部')
    # site_take/site_back 类型默认是门店合作，但如果接待内容明确提到「换电订单/操作借出/操作归还」，说明是协助换电流程，不归为门店合作
    if t in ('site_take_battery','site_back_battery') and not any(k in d for k in ['换电订单','操作借出','操作归还']): tags.add('门店合作')
    if t == 'owe_rent_user': tags.add('欠租催收')
    if t in ('silent_user','book_user_visit'): tags.add('回访跟进')
    if not tags or any(k in d for k in ['回访','跟进']):
        if any(k in d for k in ['回访','跟进']): tags.add('回访跟进')
    if not tags:
        # v10.28.55：数字 type 且无 recp_type_map 映射时，用「标签#N」兜底（不再裸显示 0/1 序号）
        if t and t.isdigit():
            tags.add(f'标签#{t}')
        else:
            tags.add('其他杂项')
    return sorted(tags)
def connect_db():
    """读取 db_conf.json，优先使用环境变量 LF_DB_HOST，其次 intranet_host，最后 host；
    支持多地址回退，保证在内网/公网都能自动连上。"""
    c = json.load(open(os.path.join(BASE, 'db_conf.json'), encoding='utf-8'))
    env_host = os.environ.get('LF_DB_HOST', '').strip()
    intranet = c.get('intranet_host', '').strip()
    public = c.get('host', '').strip()

    candidates = []
    if env_host:
        candidates.append(('ENV', env_host))
    if intranet and intranet not in [h for _, h in candidates]:
        candidates.append(('内网', intranet))
    if public and public not in [h for _, h in candidates]:
        candidates.append(('公网', public))

    last_err = None
    for label, host in candidates:
        try:
            print(f"[{label}] 连接数据库 {host}:{c.get('port', 3306)} ...")
            conn = pymysql.connect(
                host=host, port=c.get('port', 3306), user=c['user'],
                password=c['password'], database=c['database'],
                charset='utf8mb4',
                connect_timeout=c.get('connect_timeout', 30),
                read_timeout=c.get('read_timeout', 300),
                write_timeout=c.get('write_timeout', 60),
                cursorclass=pymysql.cursors.DictCursor
            )
            print(f"[OK] 已通过{label}地址连接数据库。")
            return conn
        except Exception as e:
            last_err = e
            print(f"[WARN]️ [{label}] {host} 连接失败：{e}")

    print(f"\n[FAIL] 所有数据库地址均无法连接。")
    if last_err:
        print(f"最后错误：{last_err}")
    print("请检查：1) 是否已连公司内网/VPN；2) 阿里云 ADB 白名单是否包含本机 IP；3) db_conf.json 是否正确。")
    raise last_err or RuntimeError('无法连接数据库')


c = json.load(open(os.path.join(BASE, 'db_conf.json'), encoding='utf-8'))
# 低频判定阈值（从 db_conf.json 读取；用户可自行调整）
THR = dict(c.get('lowfreq_thresholds') or {})
# L5 第 5 条低频电量阈值（15 天内没换电且电量 < 25% → L5）
POWER_THRESHOLD = int(c.get('lowfreq_power_threshold', 25))
# v10.21：近 N 天换过电的协议不进回访名单（默认 15 天；设为 0 可关闭）
RECENT_SWAP_FILTER_DAYS = int(c.get('recent_swap_filter_days', 15) or 15)
if RECENT_SWAP_FILTER_DAYS > 0:
    print(f"[INFO] recent_swap_filter_days = {RECENT_SWAP_FILTER_DAYS} （近 {RECENT_SWAP_FILTER_DAYS} 天换过电的协议不进回访名单）")
# v10.28.55：need_followup(shouldFollowUp) 是否作为 followable 的硬性拦截条件。
#   默认 False = 回滚到 v10.28.55（8/27 正常）口径，保证低频名单能出来。
#   设为 True 则回到 v10.28.55 的严格口径（会因本库 SN 取不到而误杀全部低频候选）。
USE_NEED_FOLLOWUP_FILTER = bool(c.get('use_need_followup_filter', False))
print(f"[INFO] use_need_followup_filter = {USE_NEED_FOLLOWUP_FILTER}"
      f"（False = 昨天口径，低频名单正常出；True = v10.28.55 严格口径，会误杀）")
OUT = os.path.join(BASE, 'out')
os.makedirs(OUT, exist_ok=True)

# v10.18.6：空号/无需回访黑名单（与 assign.py 的 load_no_followup_aids 同源）
def _load_no_followup_aids():
    fp = os.path.join(OUT, 'no_followup.json')
    if not os.path.exists(fp):
        return set()
    try:
        data = json.load(open(fp, encoding='utf-8'))
        if isinstance(data, list):
            return set(x.get('agreement_id') for x in data if x.get('agreement_id'))
    except Exception:
        pass
    return set()
NO_FOLLOWUP_AIDS = _load_no_followup_aids()
conn = connect_db()
cur = conn.cursor()
DAY = 86400000  # 毫秒

def to_ms(ts):
    """统一把时间戳归一化为毫秒：datetime → 毫秒；>1e12 视为毫秒；>0 视为秒。"""
    if not ts:
        return None
    # v10.28.55：兼容 datetime 对象（pymysql 直接返回 datetime 类的字段）
    if hasattr(ts, 'timestamp'):
        return int(ts.timestamp() * 1000)
    ts = int(ts)
    if ts > 1000000000000:
        return ts
    if ts > 0:
        return ts * 1000
    return None

# ---- 数据截止时间 = 最新归还时间（back_battery_time>0 即发生过归还，覆盖到2026）----
cur.execute("SELECT MAX(back_battery_time) mx FROM cb_exchange_order WHERE back_battery_time>0")
NOW_RAW = cur.fetchone()['mx']
NOW = to_ms(NOW_RAW) or int(datetime.datetime.now().timestamp() * 1000)
NOW_DT = datetime.datetime.fromtimestamp(NOW/1000)
W = {15: NOW-15*DAY, 30: NOW-30*DAY, 45: NOW-45*DAY, 60: NOW-60*DAY}
print("数据截止:", NOW_DT, "| 窗口起点(ms):", {k: v for k,v in W.items()})

# ===== v10.28.55：同步耗时诊断 + 流通表扫描窗口 =====
# 背景：cb_battery_circulate_log 是只增不减的流水表，本脚本对其全表 GROUP BY 达 5 次，
# 随着数据累积同步耗时线性增长。这里做三件事：
#   1) _lap()：分阶段打印耗时，让"到底哪一步慢"一目了然（便于继续精准优化）；
#   2) CIRC_SCAN_DAYS：可选的时间窗口（db_conf.json 配置，默认 0 = 全表，行为与旧版完全一致）。
#      设为 180 之类可大幅减少扫描量，代价是「超过该天数未流通的电池」不再出现在流通聚合里。
#   3) 复用 _sn_max_t（各 SN 的 MAX(create_time)），消除一次完全重复的全表 GROUP BY。
import time as _time
_T_LAP = _time.time()
_LAP_TOTAL0 = _T_LAP


def _lap(msg):
    """打印上一阶段耗时，并重置计时起点。"""
    global _T_LAP
    _now = _time.time()
    print(f"[TIMING] {msg}: {_now - _T_LAP:.1f}s")
    _T_LAP = _now


def _lap_total():
    print(f"[TIMING] 累计总耗时: {_time.time() - _LAP_TOTAL0:.1f}s")


try:
    CIRC_SCAN_DAYS = int((json.load(open(os.path.join(BASE, 'db_conf.json'), encoding='utf-8'))
                          or {}).get('circ_scan_days', 0) or 0)
except Exception:
    CIRC_SCAN_DAYS = 0
# 扫描起点（毫秒）：0 表示不限（与旧版一致）
CIRC_SCAN_FROM = (NOW - CIRC_SCAN_DAYS * DAY) if CIRC_SCAN_DAYS > 0 else 0
# 复用缓存：各 SN 的 MAX(create_time)，避免同一聚合重复扫描
_sn_max_t_cache = None


def get_sn_max_t(cur_):
    """返回 {sn: MAX(create_time)}，带缓存，整个脚本内只真正查一次。"""
    global _sn_max_t_cache
    if _sn_max_t_cache is not None:
        return _sn_max_t_cache
    if CIRC_SCAN_FROM > 0:
        cur_.execute("""SELECT battery_device_sn, MAX(create_time) mt
                        FROM cb_battery_circulate_log
                        WHERE is_del=0 AND create_time >= %s
                        GROUP BY battery_device_sn""", (CIRC_SCAN_FROM,))
    else:
        cur_.execute("""SELECT battery_device_sn, MAX(create_time) mt
                        FROM cb_battery_circulate_log WHERE is_del=0
                        GROUP BY battery_device_sn""")
    _sn_max_t_cache = {r['battery_device_sn']: r['mt'] for r in cur_.fetchall()}
    return _sn_max_t_cache


print(f"[TIMING] 配置: circ_scan_days={CIRC_SCAN_DAYS}"
      f"{'' if CIRC_SCAN_DAYS else '（0=全表扫描，如需提速可在 db_conf.json 设为 180）'}")

# ---- 1. 活跃协议 ----
cur.execute("""
SELECT a.id, a.user_id, a.user_name, a.user_phone, a.status, a.type,
       a.battery_product_id, p.name AS product_name, a.sys_city_name,
       a.rent_expire_time, a.activation_time, a.create_time,
       a.deposit_fee, a.deposit_status, a.deposit_payway, a.rent_package_id,
       rp.name AS pkg_name,
       s.province, s.city, s.area, s.street, s.community
FROM cb_exchange_agreement a
LEFT JOIN cb_battery_product p ON a.battery_product_id=p.id
LEFT JOIN cb_exchange_rent_package rp ON a.rent_package_id=rp.id
LEFT JOIN cb_site s ON s.id=a.site_id
WHERE a.status IN ('working','owe_rent','unsubscribing') AND a.is_del=0
""")
agreements = cur.fetchall()
_lap("活跃协议查询")
print("活跃协议数:", len(agreements))

# ---- 2. 单趟聚合：每个协议累计换电次数 + 4 个窗口的成功归还次数 ----
# 兼容 back_battery_time 毫秒/秒混存：<=1e12 视为秒，乘以 1000 后再比较。
_MS = 1000000000000
cur.execute(f"""
SELECT exchange_agreement_id AS aid,
  COUNT(DISTINCT id) total,
  SUM(CASE WHEN back_battery_time > {_MS} AND back_battery_time >= {W[15]} THEN 1 ELSE 0 END)
    + SUM(CASE WHEN back_battery_time > 0 AND back_battery_time <= {_MS} AND back_battery_time*1000 >= {W[15]} THEN 1 ELSE 0 END) c15,
  SUM(CASE WHEN back_battery_time > {_MS} AND back_battery_time >= {W[30]} THEN 1 ELSE 0 END)
    + SUM(CASE WHEN back_battery_time > 0 AND back_battery_time <= {_MS} AND back_battery_time*1000 >= {W[30]} THEN 1 ELSE 0 END) c30,
  SUM(CASE WHEN back_battery_time > {_MS} AND back_battery_time >= {W[45]} THEN 1 ELSE 0 END)
    + SUM(CASE WHEN back_battery_time > 0 AND back_battery_time <= {_MS} AND back_battery_time*1000 >= {W[45]} THEN 1 ELSE 0 END) c45,
  SUM(CASE WHEN back_battery_time > {_MS} AND back_battery_time >= {W[60]} THEN 1 ELSE 0 END)
    + SUM(CASE WHEN back_battery_time > 0 AND back_battery_time <= {_MS} AND back_battery_time*1000 >= {W[60]} THEN 1 ELSE 0 END) c60,
  MIN(CASE WHEN back_battery_time > {_MS} THEN back_battery_time ELSE back_battery_time*1000 END) fbt,
  MAX(CASE WHEN back_battery_time > {_MS} THEN back_battery_time ELSE back_battery_time*1000 END) lbt
FROM cb_exchange_order
WHERE back_battery_time > 0 AND is_del=0
GROUP BY exchange_agreement_id
""")
ret = {r['aid']: r for r in cur.fetchall()}
_lap("换电次数聚合")
print("有归还记录的协议数:", len(ret))

# v10.25：取每个协议的全部归还时间序列（用于换电周期中位间距 + 下次预计换电日）
# 协议表通常 1000~3000 个，每个有几条~几十条；分批 2000 防 IN 列表超长
aid_swap_times = {}  # aid -> sorted list of back_battery_time (ms)
try:
    _agr_ids = list(ret.keys())
    BATCH_AID = 2000
    _fetched = 0
    for k in range(0, len(_agr_ids), BATCH_AID):
        ch = _agr_ids[k:k+BATCH_AID]
        ph_q = ','.join(['%s']*len(ch))
        cur.execute(f"""
            SELECT exchange_agreement_id AS aid, back_battery_time AS bt
            FROM cb_exchange_order
            WHERE back_battery_time > 0 AND is_del=0
              AND exchange_agreement_id IN ({ph_q})
        """, ch)
        for _r in cur.fetchall():
            if _r.get('aid') and _r.get('bt'):
                _bt = int(_r['bt'])
                if _bt > 0:
                    aid_swap_times.setdefault(_r['aid'], []).append(_bt)
                    _fetched += 1
    # 归一化（秒→毫秒），每个协议内部排序去重
    for _a, _ts in aid_swap_times.items():
        _norm = sorted({(t*1000 if t <= 1000000000000 else t) for t in _ts if t})
        aid_swap_times[_a] = _norm
    print(f"[INFO] aid_swap_times: {len(aid_swap_times)} 个协议，共 {_fetched} 条换电时间")
except Exception as _e:
    print('[WARN] aid_swap_times 取数失败:', _e)
    aid_swap_times = {}


# =============================================================================
# v10.28.55 电量校准常量
# =============================================================================
# 问题：cb_battery_status.power 是 BMS 最近一次主动上报至后端的值。对于长期未触发
#       GPRS/WiFi 上报的电池，这个值会"虚高"或"虚低"，与电池真实剩余电量可能相差 5% 以上。
#       原 v10.18.x 直接把 raw 拿来用 + L5 阈值判定，导致看板上看到的电量与客服后台"换电操作日志"
#       里同一条电池相差较大（截图中：操作日志刚借出时 100%，看板上仍显示 38% —— 这种 gap 就是因为
#       BMS 没及时上报，看板拿了上一条陈旧的数）。
# 公式：calibrated = clamp(raw_soc − days_stale × SELF_DISCHARGE_PER_DAY + BALANCE_DRIFT, 0, 100)
#   days_stale = (NOW − last_report_ts) / 86400000
#   磷酸铁锂：自放电率低 ≈ 0.10~0.30%/天；三元锂 ≈ 0.50~1.00%/天；本看板面向混合车队，保守取 0.30%/天。
#   若现场数据差异较大，改 db_conf.json（无需重打包）：
#       "battery_calibration": {
#           "self_discharge_per_day": 0.30,
#           "balance_drift": 0.0,
#           "stale_warning_days": 3
#       }
# =============================================================================
BATTERY_CALIBRATION_DEFAULTS = {
    "self_discharge_per_day": 0.30,   # 默认 0.30%/天
    "balance_drift":         0.0,     # 累计误差偏移，默认 0（实测后可微调 ±5 以内）
    "stale_warning_days":    3,       # 超过该天数视为陈旧，红字标记
}
def _load_battery_calibration():
    """从 db_conf.json 读取校准参数；缺字段时回退默认。"""
    try:
        c = json.load(open(os.path.join(BASE, "db_conf.json"), encoding="utf-8"))
        cal = c.get("battery_calibration") or {}
        return {**BATTERY_CALIBRATION_DEFAULTS, **cal}
    except Exception:
        return dict(BATTERY_CALIBRATION_DEFAULTS)
BATTERY_CAL = _load_battery_calibration()
print(f"[v10.28.55] 电量校准参数: 自放电率={BATTERY_CAL['self_discharge_per_day']}%/天 "
      f"| 漂移={BATTERY_CAL['balance_drift']} | 陈旧阈值={BATTERY_CAL['stale_warning_days']}天")

def calibrate_soc(raw_soc, last_report_ts_ms):
    """电量校准入口：返回 dict {raw, calibrated, age_days, stale}，缺值回退 None。"""
    out = {"raw": None, "calibrated": None, "age_days": None, "stale": False}
    if raw_soc is None:
        return out
    out["raw"] = int(raw_soc)
    try:
        age_days = max(0, (NOW - (last_report_ts_ms or NOW)) / 86400000.0)
    except Exception:
        age_days = 0
    out["age_days"] = round(age_days, 1)
    drift = BATTERY_CAL["balance_drift"]
    rate  = BATTERY_CAL["self_discharge_per_day"]
    cal   = raw_soc - age_days * rate + drift
    out["calibrated"] = max(0, min(100, int(round(cal))))
    out["stale"] = age_days >= BATTERY_CAL["stale_warning_days"]
    return out


# ---- 2.5 电池：用户名下当前电池 SN / 电压 / 电流 / 电量 / 在线状态 ----
battery_info = {}   # uid -> {sn, online, soc, vol, cur, using}
uids = list(set(a['user_id'] for a in agreements))
if uids:
    BATCH = 2000
    try:
        bind_map = {}
        for k in range(0, len(uids), BATCH):
            ch = uids[k:k+BATCH]; ph = ','.join(['%s']*len(ch))
            cur.execute(f"""
                SELECT b.user_id, b.battery_id FROM cb_bike_battery_bind_log b
                JOIN (SELECT user_id, MAX(bind_time) mt FROM cb_bike_battery_bind_log WHERE user_id IN ({ph}) GROUP BY user_id) m
                  ON b.user_id=m.user_id AND b.bind_time=m.mt
                WHERE b.user_id IN ({ph})
            """, ch*2)
            for r in cur.fetchall():
                bind_map[r['user_id']] = r['battery_id']
        bids = list(set(bind_map.values()))
        bat_dev = {}; bat_st = {}
        # v10.28.55【补数据兜底】cb_battery 表自身就带 power / voltage_in / current_in。
        #   旧逻辑只查 cb_battery_status：该表若无对应行（电池从未上报过状态），
        #   电压 / 电流 / 电量 三列会整列显示「—」，与"所有菜单都要有数据"的要求冲突。
        #   这里把 cb_battery 自带的电气字段一并取出，作为 cb_battery_status 缺失时的兜底来源。
        _b_pow = pick_col(cur, 'cb_battery', 'power', 'soc', 'battery_power', 'electric')
        _b_vol = pick_col(cur, 'cb_battery', 'voltage_in', 'voltage', 'vol')
        _b_cur = pick_col(cur, 'cb_battery', 'current_in', 'current', 'cur')
        _b_extra = [c for c in (_b_pow, _b_vol, _b_cur) if c]
        print(f"[v10.28.55] cb_battery 电气字段探测 => 电量={_b_pow} | 电压={_b_vol} | 电流={_b_cur}")
        for k in range(0, len(bids), BATCH):
            ch = bids[k:k+BATCH]; ph = ','.join(['%s']*len(ch))
            _sel = 'id, device_sn, online_status' + (', ' + ', '.join('`'+c+'`' for c in _b_extra) if _b_extra else '')
            cur.execute(f"SELECT {_sel} FROM cb_battery WHERE id IN ({ph})", ch)
            for r in cur.fetchall():
                bat_dev[r['id']] = {
                    'sn': r['device_sn'] or '', 'online': r['online_status'] or '',
                    'pow': (r.get(_b_pow) if _b_pow else None),
                    'vol': (r.get(_b_vol) if _b_vol else None),
                    'cur': (r.get(_b_cur) if _b_cur else None),
                }
            cur.execute(f"SELECT battery_id, power, voltage_in, current_in, `using`, update_time FROM cb_battery_status WHERE battery_id IN ({ph})", ch)
            for r in cur.fetchall():
                # v10.28.55：同步取 update_time；老版本库若字段不存在则降级 None（calibrate_soc 自动回退）
                _ts = r.get('update_time') or r.get('create_time') or None
                bat_st[r['battery_id']] = {'soc': r['power'], 'vol': r['voltage_in'], 'cur': r['current_in'], 'using': r.get('using',''), 'lrt_ms': to_ms(_ts)}
        for uid, bid in bind_map.items():
            d = bat_dev.get(bid, {}); s = bat_st.get(bid, {})
            # v10.28.55 兜底：cb_battery_status 无该电池 → 用 cb_battery 自带的电气字段
            #   （三者只要有任意一个非空就整组回填，避免"电压有值电流是—"的半截状态）
            if not any(s.get(x) not in (None, '') for x in ('soc', 'vol', 'cur')):
                if any(d.get(x) not in (None, '') for x in ('pow', 'vol', 'cur')):
                    s = {'soc': d.get('pow'), 'vol': d.get('vol'), 'cur': d.get('cur'),
                         'using': '', 'lrt_ms': None}
            # v10.28.55：电量校准（实测 / 校准 / 距上次上报天数 / 是否陈旧）
            _soc_raw = None
            try:
                _sv = s.get('soc')
                if _sv is not None and str(_sv).strip() != '':
                    _mm = re.search(r'\d+', str(_sv))
                    _soc_raw = int(_mm.group()) if _mm else None
            except Exception:
                _soc_raw = None
            # v10.28.55：逐用户容错。v10.28.55 曾因 calibrate_soc 前向引用（在定义之前被调用）
            #   抛出一次 NameError，就让整个电池段 abort → 23693 个用户的 电压/电流/电量/SN 全变横杠。
            #   这里即使单个用户计算失败也保留原始电气值，不让一颗老鼠屎坏一锅汤。
            try:
                _cal = calibrate_soc(_soc_raw, s.get('lrt_ms'))
            except Exception as _ce:
                if len(battery_info) == 0:
                    print(f"[WARN] 电量校准失败（仅影响校准值，原始电量保留）: {_ce}")
                _cal = {'raw': _soc_raw, 'calibrated': None, 'age_days': None, 'stale': False}
            battery_info[uid] = {
                'sn': d.get('sn',''), 'online': d.get('online',''),
                'soc': (s.get('soc') or ''), 'vol': (s.get('vol') or ''), 'cur': (s.get('cur') or ''), 'using': (s.get('using') or ''),
                'soc_raw':    _cal['raw'],
                'soc_cal':    _cal['calibrated'],
                'soc_age':    _cal['age_days'],
                'soc_stale':  _cal['stale'],
                'soc_lrt_ms': s.get('lrt_ms'),
            }
        print(f"有当前绑定电池的用户: {len(battery_info)} / 活跃用户 {len(uids)}")
    except Exception as e:
        print("电池抽取失败(待确认):", e)

# ---- 3. 打标签 ----
def fmt(ts):
    ms = to_ms(ts)
    return datetime.datetime.fromtimestamp(ms/1000).strftime('%Y-%m-%d') if ms else ''

def calc_monthly(c60):
    # 60天≈2个月，月均 = c60 / 2
    return round(c60 / 2.0, 2)
# ---- v10.22：手机号本地/外地判定 —— 内置号段库(前7位→省份) ----
# phone.dat 来源：phone 包（lovedboy/phone，号段→省份|城市|邮编|区号），仅用其 province 字段。
# 解析逻辑：头部 <4s i>(版本+首记录偏移)，每条记录 <i i B>(号段7位,内容偏移,类型)，内容为空结尾字符串。
import struct as _struct
_PHONE_DAT = None
def _load_phone_dat():
    global _PHONE_DAT
    if _PHONE_DAT is not None:
        return _PHONE_DAT
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'phone.dat')
    if not os.path.exists(p):
        print('[WARN] phone.dat 不存在，手机号本地/外地判断将全部返回空')
        _PHONE_DAT = (b'', 0, 0)
        return _PHONE_DAT
    with open(p, 'rb') as f:
        buf = f.read()
    _hf = _struct.calcsize('<4si'); _pf = _struct.calcsize('<iiB')
    _ver, _first = _struct.unpack('<4si', buf[:_hf])
    _count = (len(buf) - _first) // _pf
    _PHONE_DAT = (buf, _first, _count)
    print(f'[INFO] 号段库已加载: version={_ver} 记录数={_count}')
    return _PHONE_DAT

def _phone_province(num):
    """返回手机号归属省份（前7位号段库查表）。查不到返回 ''。"""
    if not num:
        return ''
    s = re.sub(r'\D', '', str(num).strip())
    if len(s) < 7:
        return ''
    buf, first, count = _load_phone_dat()
    if not buf:
        return ''
    intp = int(s[:7]); left, right = 0, count
    while left <= right:
        m = (left + right) // 2
        off = first + m * 9
        if off + 9 > len(buf):
            return ''
        cur, rec, _typ = _struct.unpack('<iiB', buf[off:off+9])
        if cur > intp:
            right = m - 1
        elif cur < intp:
            left = m + 1
        else:
            end = buf.find(b'\x00', rec)
            content = buf[rec:end].decode('utf-8', 'ignore')
            parts = content.split('|')
            return parts[0] if parts else ''
    return ''

def _phone_city(num):
    """v10.24：返回手机号归属城市（号段库 parts[1]）。查不到返回 ''。
    用法：回访排班手机号后直接显示归属地城市名（如「深圳」「茂名」），不再做本地/外地对比。"""
    if not num:
        return ''
    s = re.sub(r'\D', '', str(num).strip())
    if len(s) < 7:
        return ''
    buf, first, count = _load_phone_dat()
    if not buf:
        return ''
    intp = int(s[:7]); left, right = 0, count
    while left <= right:
        m = (left + right) // 2
        off = first + m * 9
        if off + 9 > len(buf):
            return ''
        cur, rec, _typ = _struct.unpack('<iiB', buf[off:off+9])
        if cur > intp:
            right = m - 1
        elif cur < intp:
            left = m + 1
        else:
            end = buf.find(b'\x00', rec)
            content = buf[rec:end].decode('utf-8', 'ignore')
            parts = content.split('|')
            return parts[1] if len(parts) > 1 else ''
    return ''

# ---- v10.28.55：手机号归属地 fallback 字典 ----
# v10.28.55 改造：字典抽离到 phone_fallback.py（独立模块，import 时不触发 build 主流程）
#                build_lists 和 gen_dashboard 都从这里导入，避免重复维护。
from phone_fallback import (
    _PHONE_FALLBACK,
    _PHONE_FALLBACK_5,
    _PHONE_FALLBACK_3,
    phone_city_with_fallback as _phone_city_with_fallback_fn,
)

def _phone_city_fallback(num):
    """v10.28.55：phone.dat 二分查不到时的离线 fallback（按 7位 → 5位 → 3位 逐级回退）"""
    import re as _re
    if not num:
        return ''
    s = _re.sub(r'\D', '', str(num).strip())
    if len(s) < 3:
        return ''
    if len(s) >= 7 and s[:7] in _PHONE_FALLBACK:
        return _PHONE_FALLBACK[s[:7]]
    if len(s) >= 5 and s[:5] in _PHONE_FALLBACK_5:
        return _PHONE_FALLBACK_5[s[:5]]
    return _PHONE_FALLBACK_3.get(s[:3], '')

def _phone_city_with_fallback(num):
    """v10.28.55：phone.dat + fallback 组合查询"""
    return _phone_city(num) or _phone_city_fallback(num)

# ---- v10.27：离线号段版 —— 强制禁用 ip138.com（仅本地 phone.dat 号段库判定归属地）----
# 适用于无法访问外网 / ip138.com 的网段、VPN 环境；零外网依赖，避免 Web 请求超时卡死抽数流程。
# 若你的网络可访问外网且想要 ip138 兜底更准确，请改用 v10.26 在线版（运行 `python build_lists.py --use-ip138`）。
USE_IP138 = False

# ---- v10.26：--use-ip138 时的 Web 归属地查询 ----
# ip138.com 提供手机号归属地查询接口（https://tool.ip138.com/mobile/）。
# 优先调 https://api.ip138.com/phone/ （带 token）或 web 解析 HTML；这里走 web 解析实现零依赖。
# 加 5s 超时 + 进程内缓存（同一号段前 7 位只查一次），避免数千条数据拖死接口。
_USE_IP138 = False        # 启动时根据 CLI 参数赋值
_IP138_CACHE = {}         # {前7位字符串: 城市名}
def _set_use_ip138(flag: bool):
    global _USE_IP138
    _USE_IP138 = bool(flag)

def _phone_city_ip138(num):
    """v10.26：调 ip138.com Web 接口查归属地。
    仅前 7 位号段查一次（缓存），减少网络请求。
    返回城市名；查不到返回 ''。"""
    if not num:
        return ''
    s = re.sub(r'\D', '', str(num).strip())
    if len(s) < 7:
        return ''
    key = s[:7]
    if key in _IP138_CACHE:
        return _IP138_CACHE[key]
    try:
        import urllib.request, urllib.parse
        url = 'https://tool.ip138.com/mobile/?mobile=' + urllib.parse.quote(s) + '&action=mobile'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://tool.ip138.com/',
        })
        with urllib.request.urlopen(req, timeout=5) as r:
            html = r.read().decode('utf-8', 'ignore')
        # 解析 HTML，定位归属地。不同页面版本结构会变，做多重匹配。
        city = ''
        m = re.search(r'归属地[：:]\s*</[^>]+>\s*<[^>]+>([^<]+)', html)
        if m:
            city = m.group(1).strip()
        if not city:
            m = re.search(r'<td[^>]*>([^省市区县]{0,4}(?:省|自治区))[^省市区县]{0,8}([市地区盟州]+)</td>', html)
            if m:
                city = (m.group(1) + m.group(2)).strip()
        if not city:
            m = re.search(r'(?:province|prov)["\':\s]+([^"\'<>,]+).*?(?:city|cityName)["\':\s]+([^"\'<>,]+)', html)
            if m:
                city = (m.group(1) + m.group(2)).strip()
        # 清理多余空白
        city = re.sub(r'\s+', '', city)[:20]
    except Exception as _e:
        city = ''
    _IP138_CACHE[key] = city
    return city

records = []

# ---- 电池流通：按 battery_device_sn 取最后一条流通记录 + 最近一条异常流通记录 ----
# 柜内借出电池(outflow 非空) => 在流通；柜内归还电池(inflow 非空) => 暂无电池
# 异常原因：取「最近一条 status 为异常」的流通记录拼接；避免正常流通覆盖历史异常。
def _is_abnormal_status(st):
    if not st:
        return False
    s = str(st).strip().lower()
    if s in ('异常', 'abnormal', 'error', 'err', '2', 'false', 'unidentified', 'fault'):
        return True
    # v10.28.55：补充「未识别 / 断充 / 上报 / 识别失败 / 设备异常 / 柜回收 / 无法识别」等关键词，
    # 覆盖「消费者已归还但换电柜断充未识别，后续换电柜上报电池在柜内」等场景
    return any(k in s for k in ['异', 'error', 'fail', '未识别', '断充', '上报',
                                 '识别失败', '设备异常', '柜回收', '无法识别', 'fault', 'unidentified'])

# 用于 SQL 的异常 status 匹配（与 Python 逻辑保持一致）
# v10.21.2：除了 status 字段，再补「业务字段」识别——
#   换电柜上报 / 员工回收 / 机柜未识别等场景的 status 可能不是"异常"，但业务字段已明确是上报事件
# v10.28.55：同 Python 侧一并补齐「未识别 / 断充 / 上报 / 识别失败 / 设备异常 / 柜回收」关键词
ABNORMAL_STATUS_SQL = """
    (status IN ('异常','abnormal','error','err','2','false','unidentified','fault')
     OR status LIKE '%异%'
     OR status LIKE '%error%'
     OR status LIKE '%fail%'
     OR status LIKE '%未识别%'
     OR status LIKE '%断充%'
     OR status LIKE '%识别失败%'
     OR status LIKE '%设备异常%'
     OR status LIKE '%柜回收%')
    OR business_type_second LIKE '%上报%'
    OR business_type_second LIKE '%未识别%'
    OR business_type_second LIKE '%员工回收%'
    OR business_type_second LIKE '%柜回收%'
    OR business_type_second LIKE '%断充%'
    OR business_type_second LIKE '%识别失败%'
    OR business_type_second LIKE '%设备异常%'"""

battery_circ = {}
try:
    has_status_col = True
    try:
        # 同时取：① 最新一条（is_abnormal=0）；② 最近一条异常（is_abnormal=1）
        cur.execute(f"""
            SELECT c.battery_device_sn, c.create_time, c.outflow_name, c.inflow_name, c.business_type_second, c.status, 0 AS is_abnormal
            FROM cb_battery_circulate_log c
            JOIN (SELECT battery_device_sn, MAX(create_time) mt
                  FROM cb_battery_circulate_log WHERE is_del=0 GROUP BY battery_device_sn) m
              ON m.battery_device_sn=c.battery_device_sn AND m.mt=c.create_time
            WHERE c.is_del=0
            UNION ALL
            SELECT c.battery_device_sn, c.create_time, c.outflow_name, c.inflow_name, c.business_type_second, c.status, 1 AS is_abnormal
            FROM cb_battery_circulate_log c
            JOIN (SELECT battery_device_sn, MAX(create_time) mt
                  FROM cb_battery_circulate_log
                  WHERE is_del=0 AND ({ABNORMAL_STATUS_SQL.strip()})
                  GROUP BY battery_device_sn) m
              ON m.battery_device_sn=c.battery_device_sn AND m.mt=c.create_time
            WHERE c.is_del=0
        """)
    except Exception as e:
        # 老版本表可能没有 status 字段，回退到基本查询（异常原因默认可为空）
        print("[INFO] cb_battery_circulate_log.status 字段不存在，按基本流通记录查询:", e)
        has_status_col = False
        cur.execute("""
            SELECT c.battery_device_sn, c.create_time, c.outflow_name, c.inflow_name, c.business_type_second, NULL AS status, 0 AS is_abnormal
            FROM cb_battery_circulate_log c
            JOIN (SELECT battery_device_sn, MAX(create_time) mt
                  FROM cb_battery_circulate_log WHERE is_del=0 GROUP BY battery_device_sn) m
              ON m.battery_device_sn=c.battery_device_sn AND m.mt=c.create_time
            WHERE c.is_del=0
        """)

    def _parse_circ_row(row):
        ct = row['create_time']
        if isinstance(ct, (int, float)):
            ct_s = datetime.datetime.fromtimestamp(ct/1000).strftime('%Y-%m-%d %H:%M:%S') if ct else ''
        else:
            ct_s = str(ct)[:19] if ct else ''
        out_n = (row['outflow_name'] or '').strip()
        in_n = (row['inflow_name'] or '').strip()
        sec = (row['business_type_second'] or '').strip()
        sec_l = sec.lower()
        is_back = any(k in sec_l for k in ['back', '还', '归']) or sec in ('artificial_confirm_back', 'back_validate')
        is_take = any(k in sec_l for k in ['take', '借', '出']) and not is_back
        if is_take:
            op, circ = '柜内借出电池', 1
        elif is_back:
            op, circ = '柜内归还电池', 0
        else:
            op, circ = (BT_SECOND_MAP.get(sec, sec) or '未知'), 0
        return ct_s, out_n, in_n, sec, is_back, is_take, op, circ

    abn_count = 0
    for row in cur.fetchall():
        sn = row['battery_device_sn']
        ct_s, out_n, in_n, sec, is_back, is_take, op, circ = _parse_circ_row(row)
        # v10.28.55：branch=0 表示「最新一条」(UNION 第①支)，branch=1 表示「最近异常一条」(UNION 第②支)。
        # 用 branch 区分「末次流通」(始终取最新一条) 与「异常原因」(取异常记录)，
        # 避免异常记录覆盖正常末次流通；两者都可能对应同一最新记录。
        branch = int(row.get('is_abnormal') or 0)
        status = (row.get('status') or '').strip() if has_status_col else ''
        is_abnormal = bool(branch) or (has_status_col and _is_abnormal_status(status))

        # 统一格式：时间 因[类型]流通至[目的地]（与用户要求的展示口径一致）
        # v10.28.55：额外记录 loc / reason / is_storage（电池是否已不在用户手中）。
        #   适用场景：
        #     ① 换电柜断充/未识别 → 电池虽未识别但实际已在柜内（用户手里没电池）
        #     ② 员工回收 / 调拨-回收 → 电池已被运营拿走（用户手里没电池）
        #     ③ 柜内归还 → 电池回到柜内（用户手里没电池）
        #   这些情况都意味着"该协议对应的电池已不在用户手上"，不应再回访用户催换电。
        battery_circ.setdefault(sn, {'last': '', 'op': '', 'circ': 0, 'abn': '', 'full': '',
                                    'loc': '', 'reason': '', 'is_storage': False})
        reason = BT_SECOND_MAP.get(sec, sec) or op or '电池流通'
        loc = (in_n or out_n) if is_back else (out_n or in_n)
        full = f"{ct_s} 因[{reason}]流通至[{loc}]" if loc else f"{ct_s} 因[{reason}]"
        if branch == 0:
            # 最新一条：记录「末次流通」全量展示串 + 正常状态字段
            battery_circ[sn]['full'] = full
            battery_circ[sn]['last'] = ct_s
            battery_circ[sn]['op'] = op
            battery_circ[sn]['circ'] = circ
            battery_circ[sn]['loc'] = loc
            battery_circ[sn]['reason'] = reason
            # v10.28.55：判定「电池是否已不在用户手中」
            #   - 柜内归还（is_back）→ 已回到柜中 → is_storage=True
            #   - 异常类型（员工回收/未识别/上报/识别失败/调拨-回收/fault/unidentified）→ is_storage=True
            #   - 流通至仓库类地点（换电柜仓库/员工仓库/代理商/站仓） → is_storage=True
            _sec_lower = sec.lower()
            _is_abnormal_sec = any(k in sec for k in
                ('员工回收','柜回收','调拨-回收','未识别','断充','上报','识别失败','设备异常')) or \
                any(k in _sec_lower for k in ('fault','unidentified','error','fail'))
            _is_storage_loc = loc and any(k in loc for k in
                ('换电柜仓库','员工仓库','代理商','柜仓','站仓','仓库','换电柜'))
            if is_back or _is_abnormal_sec or _is_storage_loc:
                battery_circ[sn]['is_storage'] = True
        if is_abnormal and ct_s:
            # 异常原因（可能来自最新一条，也可能来自更早的异常记录），统一格式展示
            battery_circ[sn]['abn'] = full
            abn_count += 1
    # ---- v10.12 补强：检测"借出后又被柜上报"的流通异常 ----
    # 逻辑：对每个电池 SN，若其最新一条流通记录是"柜内借出"，但流通表中仍有时间晚于该借出时间的
    #      其他记录（说明电池已不在该用户手里），则将该 SN 标记为"借出后流通异常"。
    # 数据源：cb_battery_circulate_log（最新借出时间 vs 该 SN 全表最大时间）
    if battery_circ:
        try:
            # 取每个 SN 的"最后借出时间"
            cur.execute("""
                SELECT battery_device_sn, MAX(create_time) last_take_t
                FROM cb_battery_circulate_log
                WHERE is_del=0
                  AND (business_type_second LIKE '%take%'
                       OR business_type_second LIKE '%借%'
                       OR business_type_second LIKE '%出%')
                GROUP BY battery_device_sn
            """)
            last_take = {r['battery_device_sn']: r['last_take_t'] for r in cur.fetchall()}
            # v10.28.55：复用缓存结果（原本这里又做了一次全表 GROUP BY，
            # 与 battery_last_report 的子查询完全相同，属于纯重复扫描）
            max_t = get_sn_max_t(cur)
            abn2 = 0
            for sn, lt in last_take.items():
                mt = max_t.get(sn)
                if lt and mt and mt > lt:
                    # 借出后流通异常
                    info = battery_circ.get(sn)
                    if info is None:
                        continue
                    # 把"是否在流通"翻转为"异常(暂无电池)"，并追加异常原因
                    info['op'] = '柜内借出电池(后续流通异常)'
                    info['circ'] = 0  # 用户手里实际没电池
                    reason_extra = f"借出后于{max_t[sn]}又有柜端上报，电池已流通至其他换电柜/用户"
                    if info.get('abn'):
                        info['abn'] = info['abn'] + '；' + reason_extra
                    else:
                        info['abn'] = reason_extra
                    abn2 += 1
            print(f"借出后流通异常电池数: {abn2}")
        except Exception as e:
            print("[WARN] 借出后流通异常检测失败(跳过):", e)
    print("电池流通记录数:", len(battery_circ), "| 含 status 字段:", has_status_col, "| 含异常原因:", abn_count)
except Exception as e:
    print("电池流通查询失败(跳过该列):", repr(e))

# v10.18.7：规范化 SN 映射，消除 cb_exchange_order 与 cb_battery_circulate_log 两表 SN 字符串漂移（大小写/前后空格差异）。
# 例如订单表存 "PB44824250822203"、流通表存 "pb44824250822203 "，直接 dict.get 会命中失败导致异常原因错位。
battery_circ_norm = { (k or '').strip().upper(): v for k, v in battery_circ.items() }

# v10.21：取每个 SN 的「流通表最新一条记录」（MAX create_time）→ 重做异常原因 + 新增「最后流通记录」筛选维度。
# 异常原因 = 最新一条记录的「时间 因【操作类型】流通至【位置】」；仅当该记录说明电池已离开消费者（op≠柜内借出）才展示为异常。
def _parse_report_row(row):
    ct = row['create_time']
    if isinstance(ct, (int, float)):
        ct_s = datetime.datetime.fromtimestamp(ct/1000).strftime('%Y-%m-%d %H:%M:%S') if ct else ''
    else:
        ct_s = str(ct)[:19] if ct else ''
    out_n = (row['outflow_name'] or '').strip()
    in_n = (row['inflow_name'] or '').strip()
    sec = (row['business_type_second'] or '').strip()
    sec_l = sec.lower()
    is_back = any(k in sec_l for k in ['back', '还', '归']) or sec in ('artificial_confirm_back', 'back_validate')
    is_take = any(k in sec_l for k in ['take', '借', '出']) and not is_back
    if is_take:
        op = '柜内借出电池'
    elif is_back:
        op = '柜内归还电池'
    else:
        op = (BT_SECOND_MAP.get(sec, sec) or '未知')
    return ct_s, out_n, in_n, sec, is_back, is_take, op

def _circ_op_cat(op, sec):
    """把最新流通记录归类成筛选维度：柜内借出 / 换电-还电池 / 调拨-回收 / 柜内归还 / 其他。"""
    raw = sec or ''
    s = raw.lower()
    if op == '柜内借出电池':
        return '柜内借出'
    if raw in ('back_battery', 'exchange_back_battery') or '换电' in raw:
        return '换电-还电池'
    if '回收' in raw or 'recycle' in s or '调拨' in raw or 'transfer' in s:
        return '调拨-回收'
    if op == '柜内归还电池' or '还' in raw or 'back' in s:
        return '柜内归还'
    return '其他'

battery_last_report = {}
try:
    cur.execute("""
        SELECT c.battery_device_sn, c.create_time, c.outflow_name, c.inflow_name, c.business_type_second
        FROM cb_battery_circulate_log c
        JOIN (SELECT battery_device_sn, MAX(create_time) mt
              FROM cb_battery_circulate_log WHERE is_del=0 GROUP BY battery_device_sn) m
          ON m.battery_device_sn=c.battery_device_sn AND m.mt=c.create_time
        WHERE c.is_del=0
    """)
    for row in cur.fetchall():
        sn = row['battery_device_sn']
        ct_s, out_n, in_n, sec, is_back, is_take, op = _parse_report_row(row)
        loc = (in_n or out_n) if is_back else (out_n or in_n)
        reason = BT_SECOND_MAP.get(sec, sec) or op
        battery_last_report[sn] = {
            'time': ct_s, 'sec': sec, 'op': op, 'circ': (1 if is_take else 0),
            'loc': loc, 'reason': reason,
        }
    print("电池最新流通记录数:", len(battery_last_report))
except Exception as e:
    print("[WARN] 电池最新流通记录查询失败(降级用旧逻辑):", repr(e))

# ===== v10.28.55：回访实际效果 —— 建立「电池借出时间」索引（方案B核心）=====
# 目的：判断"某次客服接待之后，用户是否真的去换了电、第几天换的"。
# 为什么不能直接用 battery_last_report['time']（即 circ_last）：
#   它是「最新一条任意流通」，可能是"归还/回收"而非"借出"。若接待后用户「借出又归还」，
#   circ_last 会变成归还时间 → 被误判成"未换电"，但用户其实换过电。
#   所以必须单独找「接待之后的第一条借出记录」。
# 实现：一次性拉取所有疑似借出记录，在内存建 {sn: [时间戳升序]}，后续 bisect 二分查找。
def _is_take_sec(sec):
    """判断 business_type_second 是否属"借出"类型（与 _parse_circ_row 口径严格一致）。"""
    raw = (sec or '').strip()
    s = raw.lower()
    is_back = any(k in s for k in ['back', '还', '归']) or raw in (
        'artificial_confirm_back', 'back_validate')
    is_take = any(k in s for k in ['take', '借', '出']) and not is_back
    return is_take


battery_take_times = {}
try:
    cur.execute("""
        SELECT c.battery_device_sn, c.create_time, c.business_type_second
        FROM cb_battery_circulate_log c
        WHERE c.is_del = 0
          AND (c.business_type_second LIKE '%take%'
               OR c.business_type_second LIKE '%借%'
               OR c.business_type_second LIKE '%出%')
    """)
    for _r in cur.fetchall():
        # SQL 只做粗筛，这里用与既有口径一致的 is_take 逻辑精筛（排除 back 类）
        if not _is_take_sec(_r['business_type_second']):
            continue
        _sn = _r['battery_device_sn']
        _t = to_ms(_r['create_time'])
        if _sn and _t:
            battery_take_times.setdefault(_sn, []).append(_t)
    for _sn in battery_take_times:
        battery_take_times[_sn].sort()
    print(f"[v10.28.55] 借出时间索引: {len(battery_take_times)} 个电池 / "
          f"{sum(len(v) for v in battery_take_times.values())} 条借出记录")
except Exception as e:
    print(f"[WARN] 借出时间索引构建失败，回访效果将降级为「无促成判定」: {e}")
    battery_take_times = {}


# ---- v10.18.5：按协议ID在 cb_exchange_order 表查「最新一笔换电订单」→ battery_device_sn/create_time/business_type_second ----
# 设计：板上展示的「电池SN / 流通时间 / 操作类型」必须来自同一条订单记录，保证三列严格同源。
# 数据流：aid  →  cb_exchange_order(MAX create_time)  →  battery_device_sn / create_time / business_type_second
# 好处：
#   1) 不再依赖 cb_bike_battery_bind_log → cb_battery.device_sn，避免绑定表电池SN与流通表错位；
#   2) 若该 SN 在 cb_battery_circulate_log 里有借出后流通异常，仍会被前面的电池流通聚合识别剔除；
#   3) 板上展示的最新电池SN = 流通表里的 SN，一眼可对照客服管理后台"换电操作日志"。
aid_last_order = {}
try:
    cur.execute("""
        SELECT o.exchange_agreement_id AS aid,
               o.battery_device_sn, o.create_time, o.business_type_second, o.status
        FROM cb_exchange_order o
        JOIN (SELECT exchange_agreement_id, MAX(create_time) mt
              FROM cb_exchange_order WHERE is_del=0 GROUP BY exchange_agreement_id) m
          ON m.exchange_agreement_id=o.exchange_agreement_id AND m.mt=o.create_time
        WHERE o.is_del=0
    """)
    for r in cur.fetchall():
        _sn = (r.get('battery_device_sn') or '').strip()
        aid_last_order[r['aid']] = {
            'sn': _sn,
            # v10.18.7：规范化 SN（strip+upper），用于与 battery_circ 同源查找，消除两表字符串漂移
            'sn_norm': _sn.upper(),
            'last': r.get('create_time'),
            'sec':  (r.get('business_type_second') or '').strip(),
            'status': (r.get('status') or '').strip(),
        }
    print("按协议ID查到最新换电订单的协议数:", len(aid_last_order))
except Exception as e:
    print("[WARN] 按协议ID取最新换电订单失败(降级使用 cb_battery.device_sn):", repr(e))
    aid_last_order = {}

# v10.28.55：集成「是否需要回访」规则（shouldFollowUp）。
#   规则：取该协议全部换电操作历史的「最后一次操作」（按 操作时间 升序排序后的最后一条），
#        若最后一条同时满足 ①操作类型=柜内归还电池 ②电池SN=暂无电池 -> 无需回访(False)，否则需要回访(True)。
#   数据源：cb_exchange_order 全量（按 aid 分批），与 aid_last_order 同源，保证"按时间排序取最后一条"真实生效。
try:
    from should_follow_up import shouldFollowUp
except Exception:                      # 兜底：把脚本所在目录加入 path 再 import
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from should_follow_up import shouldFollowUp

def _build_op_history(aid):
    """构造某协议的全部换电操作历史，供 shouldFollowUp 判定。
       对齐规则字面量：柜内归还且无电池 -> 电池SN 映射为字面 '暂无电池'。"""
    orders = aid_orders.get(aid, [])
    recs = []
    for o in orders:
        ct = o['create_time']
        sec = o['business_type_second']
        sn = o['battery_device_sn']
        op = _op_from_sec(sec)
        is_back = bool(sec) and (any(k in sec.lower() for k in ['back', '还', '归'])
                                 or sec in ('artificial_confirm_back', 'back_validate'))
        # v10.28.55 修复：原写法 `not sn` 会在「本库流通表无记录、订单表 SN 本就取不到」时
        #   无条件把最后一条操作标记成「柜内归还 + 暂无电池」，进而让 shouldFollowUp 全判 False。
        #   改为：只有「确实有 SN 且流通表明确判定该 SN 已不在流通(circ==0)」时才算暂无电池；
        #   SN 为空（取不到）视为"状态未知"，按常规 SN 处理，不触发"暂无电池"。
        _circ_known = bool(sn) and (sn in battery_circ)
        _circ_out = _circ_known and (battery_circ.get(sn, {}).get('circ') == 0)
        if is_back and _circ_out:
            sn_for_rule = '暂无电池'
        else:
            sn_for_rule = sn or ''
        recs.append({'操作时间': ct, '操作类型': op, '电池SN': sn_for_rule})
    return recs

# 每个协议的全部换电订单（供 _build_op_history 使用），按 aid 分批查询后按时间升序
aid_orders = {}
_agr_ids_all = [a['id'] for a in agreements]
if _agr_ids_all:
    try:
        BATCH = 2000
        for k in range(0, len(_agr_ids_all), BATCH):
            ch = _agr_ids_all[k:k + BATCH]
            ph = ','.join(['%s'] * len(ch))
            cur.execute(f"""
                SELECT exchange_agreement_id AS aid, battery_device_sn, create_time, business_type_second, status
                FROM cb_exchange_order
                WHERE is_del=0 AND exchange_agreement_id IN ({ph})
            """, ch)
            for r in cur.fetchall():
                aid_orders.setdefault(r['aid'], []).append({
                    'create_time': r.get('create_time'),
                    'battery_device_sn': (r.get('battery_device_sn') or '').strip(),
                    'business_type_second': (r.get('business_type_second') or '').strip(),
                })
        for _a, _l in aid_orders.items():
            _l.sort(key=lambda x: (x['create_time'] or 0))
        print(f"[v10.28.55] 全量换电订单: {sum(len(v) for v in aid_orders.values())} 条 / {len(aid_orders)} 个协议")
    except Exception as e:
        print("[WARN] 全量换电订单查询失败，是否需要回访降级为 True:", repr(e))
        aid_orders = {}

# 工具：把任意时间戳/字符串转成展示用的 datetime 字符串
def _fmt_circ_ts(ts):
    if ts is None or ts == '':
        return ''
    if isinstance(ts, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(int(ts)/1000).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return str(ts)
    return str(ts)[:19]

# 操作类型翻译（与 build_lists 现有口径一致）
def _op_from_sec(sec):
    s = (sec or '').strip().lower()
    if not s: return ''
    if any(k in s for k in ['take','借','出']) and not any(k in s for k in ['back','还','归']):
        return '柜内借出电池'
    if any(k in s for k in ['back','还','归']):
        return '柜内归还电池'
    return sec

# v10.20：抽 cb_user 当前手机号（按 user_id 关联；3 档 try / fallback 协议表 user_phone）
cur_phone_by_uid = {}
_uids = list(set(a['user_id'] for a in agreements))
if _uids:
    BATCH_PH = 2000
    # try #1：cb_user.mobile
    try:
        for k in range(0, len(_uids), BATCH_PH):
            ch = _uids[k:k+BATCH_PH]
            ph_q = ','.join(['%s'] * len(ch))
            cur.execute(f"SELECT id, mobile FROM cb_user WHERE id IN ({ph_q}) AND (mobile IS NOT NULL AND mobile<>'')", ch)
            for r in cur.fetchall():
                if r.get('mobile'):
                    cur_phone_by_uid[r['id']] = str(r['mobile']).strip()
        if cur_phone_by_uid:
            print(f"[INFO] cb_user.mobile 取到 {len(cur_phone_by_uid)} 条当前手机号")
    except Exception as _e1:
        print('[INFO] cb_user.mobile 取数失败（将尝试 cb_user.phone）:', _e1)
    # try #2：cb_user.phone（如果 #1 没拿到任何东西或字段不同）
    if not cur_phone_by_uid:
        try:
            for k in range(0, len(_uids), BATCH_PH):
                ch = _uids[k:k+BATCH_PH]
                ph_q = ','.join(['%s'] * len(ch))
                cur.execute(f"SELECT id, phone FROM cb_user WHERE id IN ({ph_q}) AND (phone IS NOT NULL AND phone<>'')", ch)
                for r in cur.fetchall():
                    if r.get('phone'):
                        cur_phone_by_uid[r['id']] = str(r['phone']).strip()
            if cur_phone_by_uid:
                print(f"[INFO] cb_user.phone 取到 {len(cur_phone_by_uid)} 条当前手机号")
        except Exception as _e2:
            print('[INFO] cb_user.phone 取数失败（将尝试 cb_user_mobile）:', _e2)
    # try #3：cb_user_mobile 表最新一条
    if not cur_phone_by_uid:
        try:
            for k in range(0, len(_uids), BATCH_PH):
                ch = _uids[k:k+BATCH_PH]
                ph_q = ','.join(['%s'] * len(ch))
                cur.execute(f"""
                    SELECT user_id, mobile FROM cb_user_mobile m
                    JOIN (SELECT user_id, MAX(create_time) mt FROM cb_user_mobile
                          WHERE user_id IN ({ph_q}) GROUP BY user_id) t
                      ON m.user_id=t.user_id AND m.create_time=t.mt
                    WHERE m.user_id IN ({ph_q})
                """, ch + ch)
                for r in cur.fetchall():
                    if r.get('mobile'):
                        cur_phone_by_uid[r['user_id']] = str(r['mobile']).strip()
            if cur_phone_by_uid:
                print(f"[INFO] cb_user_mobile 取到 {len(cur_phone_by_uid)} 条当前手机号")
        except Exception as _e3:
            print('[INFO] cb_user_mobile 取数失败（将退化到 cb_exchange_agreement.user_phone）:', _e3)
    if not cur_phone_by_uid:
        print('[WARN] cb_user / cb_user_mobile 都查不到，"当前手机号"列将全部回退到协议表 user_phone')

for a in agreements:
    aid = a['id']
    r = ret.get(aid, {'c15':0,'c30':0,'c45':0,'c60':0,'total':0})
    c15,c30,c45,c60 = int(r.get('c15') or 0),int(r.get('c30') or 0),int(r.get('c45') or 0),int(r.get('c60') or 0)
    total = int(r.get('total') or 0)
    # v10.20：当前手机号（按 user_id 查 cb_user，三档 try / fallback 协议表 user_phone）
    cur_phone = cur_phone_by_uid.get(a['user_id']) or a['user_phone'] or ''
    act_ms = to_ms(a['activation_time'])
    use_days = (NOW - act_ms)//DAY if act_ms else None
    # 低频判定（v10.11：阈值改为从 db_conf.json 读取 lowfreq_thresholds，无配置时回退到 v10.10 默认）。
    # 默认值：L1 15~30天换电<3 / L2 30~45天<4 / L3 45~60天<5 / L4 >60天<9（v10.11 进一步放宽 L4 至 <9，
    #       用于把"三千多"找回；>15 天才参与判定，≤15 天新用户仍受保护）。
    # 想要更严或更宽，直接编辑 db_conf.json 的 lowfreq_thresholds 字段后重启服务即可，无需重打包。
    is_lf = False; level = 0; lname = '-'
    use_days_int = use_days if isinstance(use_days, int) else (int(use_days) if use_days is not None else None)
    bi = battery_info.get(a['user_id']) or {}
    # 电池电量 / 在线状态（直接取实体电池表 cb_battery，与数据库实时一致）
    soc_raw = (bi.get('soc', '') or '')
    online_raw = (bi.get('online', '') or '').lower()
    m = re.search(r'\d+', str(soc_raw)) if soc_raw else None
    soc_num = int(m.group()) if m else None
    is_offline = online_raw != 'online'
    is_low = (online_raw == 'online') and (soc_num is not None) and (soc_num < POWER_THRESHOLD)
    bat_anomaly_v1 = bool(is_offline or is_low)  # v10.18.5：电量/在线异常（旧判据，保留供回访排班 use）
    # 低频判定：8 月 12 号口径（原始 4 档，带 15 天新用户保护）+ v10.12 新增 L5（电池电量）
    #   原始 4 档：生效>15且≤30天换电<L1_min_count / >30且≤45天<L2_min_count / >45且≤60天<L3_min_count / >60天<L4_min_count
    #   阈值由 db_conf.json 的 lowfreq_thresholds 控制（当前为 8 月 12 号口径：1/2/3/4）
    #   想要更严或更宽，直接编辑 db_conf.json 后重启服务即可，无需重打包。
    # L5（v10.12 新增，基于电池电量）：
    #   A) 生效 ≤15 天新用户：电池电量 < lowfreq_power_threshold → 提醒换电（不看是否换过电）
    #   B) 生效 >15 天：15 天内没换过电(c15==0) 且 电量 < lowfreq_power_threshold → 回访提醒
    if use_days_int is not None and soc_num is not None and soc_num < POWER_THRESHOLD:
        if use_days_int <= THR.get('protected_days', 15):
            is_lf = True; level = 5
            lname = f'L5·≤{int(THR.get("protected_days", 15))}天-电量<{POWER_THRESHOLD}%'
        elif c15 == 0:
            is_lf = True; level = 5
            lname = f'L5·15天未换电-电量<{POWER_THRESHOLD}%'
    # 原始 4 条（8 月 12 号口径）：>15 天才参与判定；按窗口内换电次数（c30/c45/c60）而非全历史 total
    # 阈值由 db_conf.json 的 lowfreq_thresholds 控制（当前为 8 月 12 号口径：1/2/3/4）
    #   L1(15~30天) → c30 < 1      L2(30~45天) → c45 < 2
    #   L3(45~60天) → c60 < 3      L4(>60天)   → c60 < 4
    if (not is_lf) and use_days_int is not None and use_days_int > THR.get('protected_days', 15):
        if use_days_int <= THR.get('L1_max_days', 30):
            is_lf = c30 < THR.get('L1_min_count', 1)
            if is_lf: level, lname = 1, f"L1·15~{int(THR.get('L1_max_days', 30))}天档({int(THR.get('L1_max_days', 30))}天内<{int(THR.get('L1_min_count', 1))}次)"
        elif use_days_int <= THR.get('L2_max_days', 45):
            is_lf = c45 < THR.get('L2_min_count', 2)
            if is_lf: level, lname = 2, f"L2·30~{int(THR.get('L2_max_days', 45))}天档({int(THR.get('L2_max_days', 45))}天内<{int(THR.get('L2_min_count', 2))}次)"
        elif use_days_int <= THR.get('L3_max_days', 60):
            is_lf = c60 < THR.get('L3_min_count', 3)
            if is_lf: level, lname = 3, f"L3·45~{int(THR.get('L3_max_days', 60))}天档({int(THR.get('L3_max_days', 60))}天内<{int(THR.get('L3_min_count', 3))}次)"
        else:
            is_lf = c60 < THR.get('L4_min_count', 4)
            if is_lf: level, lname = 4, f"L4·>{int(THR.get('L3_max_days', 60))}天档({int(THR.get('L3_max_days', 60))}天内<{int(THR.get('L4_min_count', 4))}次)"

    # v10.18.5：板上 SN 一致性对照（订单SN vs 流通聚合SN）
    def _sn_match_status(circ_entry):
        if not circ_entry or not circ_entry.get('last'):
            return '未匹配流通记录'
        return '一致'

    # v10.18.7：电池 SN / 流通时间 / 操作类型 / 异常原因 —— 四字段严格同源
    #   核心修复：之前电池SN/操作时间来自订单表、异常原因来自流通表，两表 SN 字符串漂移导致异常原因"张冠李戴"。
    #   现改为：以「协议最新一笔换电订单的电池SN」为统一 SN，四字段全部从 battery_circ[该SN] 同一字典取，
    #           SN 用规范化（strip+upper）查找，彻底消除两表字符串漂移。
    #   降级：若流通表无该 SN，则退回订单表自身的时间/类型（至少 SN 与订单一致，不跨表错位）。
    order = aid_last_order.get(aid) or {}
    raw_sn = (order.get('sn') or '').strip() or bi.get('sn','')
    norm_sn = (order.get('sn_norm') or raw_sn).strip().upper()
    # 优先精确匹配，再规范化匹配（消除两表 SN 字符串差异）
    circ_entry = battery_circ.get(raw_sn) or battery_circ_norm.get(norm_sn) or {}
    # v10.28.55【关键修复】标记 circ_entry 的来源：True=来自流通表（可信），False=订单表降级（仅供展示，不可用于剔除判定）
    #   背景：下面这个降级分支会"凭空造"一个 last 时间戳，导致 v10.28.55 的兜底逻辑
    #         （流通表无记录 → circ_in 兜底为 1，不剔除）被绕过：
    #         _circ_known = bool(circ_entry.get('last')) 恒为 True → 造出来的 circ=0 被当成真实「柜内归还无电池」
    #         → 全部低频候选被 excluded → followable 全 0 → 回访名单空。
    #   修复：只看 _circ_from_log / report.get('time')，降级数据仅用于看板展示（避免横杠），不参与剔除。
    _circ_from_log = bool(circ_entry.get('last'))
    if not circ_entry.get('last'):
        # 流通表无该 SN：降级到订单表自身（与客服管理后台"换电操作日志"对齐）
        _ol = _fmt_circ_ts(order.get('last'))
        _os = order.get('sec','')
        if _ol:
            circ_entry = {
                'last': _ol,
                'op': _op_from_sec(_os),
                'circ': (1 if (_os and any(k in _os.lower() for k in ['take','借','出'])) else 0),
                'abn': '',
            }
    # v10.21：以「流通表最新一条记录」(battery_last_report) 为真实状态来源，重做 电池最后流通记录/操作/是否流通
    # v10.21.2 修复：异常原因必须取 cb_battery_circulate_log 的「最新一条异常/上报」记录（circ_entry['abn']），
    #   不能用 battery_last_report（最新任意记录），否则当电池最后一次流通是「柜内借出」时（正常业务），
    #   会把之前的「换电柜上报/员工回收」等异常记录全部抹掉——与客服管理后台口径不一致。
    report = battery_last_report.get(raw_sn) or battery_last_report.get(norm_sn) or {}
    circ_sn_main   = raw_sn
    circ_last_main = report.get('time', '') or circ_entry.get('last', '')
    circ_op_main   = report.get('op', '') or circ_entry.get('op', '')
    circ_in_main   = report.get('circ', circ_entry.get('circ', 0))
    # 异常原因：取流通表「最新一条异常/上报」记录（UNION ALL 第二段 + ABNORMAL_STATUS_SQL 过滤），与客服服务台同源
    circ_abn_main = (circ_entry.get('abn', '') if circ_entry else '') or ''
    # v10.28.55：末次流通全量展示串（时间 因[类型]流通至[目的地]），取流通表「最新一条」记录，覆盖所有流通场景（含员工取电池/调拨回收）
    circ_full_main = (circ_entry.get('full', '') if circ_entry else '') or ''
    # 最新流通操作类型（新增筛选维度）
    circ_op_type = _circ_op_cat(report.get('op', ''), report.get('sec', '')) if report.get('time') else '未知'

    # ---- v10.25：换电频次 / 换电周期 / 未换电天数 / 本地外地 / 电池最后定位 / 流通季度 / 下次预计换电日 ----
    # 全部用 aid_swap_times 算（每个协议的全部归还时间序列），口径与客服服务台一致
    _swap_ts = aid_swap_times.get(aid, [])  # sorted list of ms
    total_returns = len(_swap_ts)  # 终生归还次数
    fbt_ms = _swap_ts[0] if _swap_ts else 0
    lbt_ms = _swap_ts[-1] if _swap_ts else 0
    # 月均换电频次 = 终生归还次数 / 生效月数（use_days/30.44，至少按 1 个月计）
    _months = max((use_days or 0) / 30.44, 1.0) if use_days is not None else 1.0
    swf = round(total_returns / _months, 2) if total_returns > 0 else 0.0
    # 换电周期 = 相邻换电间距的中位数（天）；用户要求"每次的换电间距形成规律"，比首末更准
    scy = None
    nse = ''  # 下次预计换电日 YYYY-MM-DD
    if len(_swap_ts) >= 2:
        _gaps = [(_swap_ts[i+1] - _swap_ts[i]) / DAY for i in range(len(_swap_ts)-1)]
        _gaps = [g for g in _gaps if g > 0]
        if _gaps:
            _gs = sorted(_gaps)
            n_g = len(_gs)
            median_gap = _gs[n_g//2] if n_g % 2 == 1 else (_gs[n_g//2-1] + _gs[n_g//2]) / 2.0
            scy = round(median_gap, 1)
            try:
                _nx_dt = datetime.datetime.fromtimestamp((lbt_ms + int(round(median_gap * DAY))) / 1000)
                nse = _nx_dt.strftime('%Y-%m-%d')
            except Exception:
                nse = ''
    # 距今未换电天数 = NOW - 末次换电；从未换电则用生效天数近似
    dns = (NOW - lbt_ms) // DAY if lbt_ms else (use_days or 0)
    swap_first_fmt = _fmt_circ_ts(fbt_ms // 1000) if fbt_ms else ''
    swap_last_fmt = _fmt_circ_ts(lbt_ms // 1000) if lbt_ms else ''
    # 电池流通时间按季度（基于最后流通时间，用于筛选维度）
    circ_quarter = ''
    if circ_last_main:
        try:
            _y = int(str(circ_last_main)[:4]); _mo = int(str(circ_last_main)[5:7])
            circ_quarter = f"{_y}Q{(_mo - 1) // 3 + 1}"
        except Exception:
            circ_quarter = ''
    # 当前手机号本地/外地：号段库取归属省份，与协议租赁省份比对
    _pp = _phone_province(cur_phone) if cur_phone else ''
    if _pp and (a.get('province') or '').strip():
        phone_local = '本地' if _pp == (a.get('province') or '').strip() else '外地'
    elif _pp:
        phone_local = '未知(无租赁省份)'
    else:
        phone_local = '未知(号段无/无手机号)'
    # v10.24：手机号归属地（城市名），不与租赁省做对比，直接显示「深圳/广州/茂名」等
    # v10.28.55：phone.dat 查不到时回退到内置号段字典
    cur_phone_city = _phone_city_with_fallback(cur_phone) if cur_phone else ''
    # v10.26：归属地来源（号段 seg / ip138 / 空）
    psrc = 'seg' if cur_phone_city else ''
    # v10.26：--use-ip138 时，号段表查不到则调 ip138.com Web 接口查归属地
    if not cur_phone_city and cur_phone and USE_IP138:
        cur_phone_city = _phone_city_ip138(cur_phone)
        psrc = 'ip138' if cur_phone_city else ''
    # v10.26：电池最后一条「任意」流通记录时间（毫秒戳），供前端按 planDate 实时算 dnr
    # v10.28.55【关键修复】距今未换电天数口径修正 —— 必须按【协议/车辆维度】而非【电池SN全局维度】计算。
    #   业务背景：同一块电池会随车辆在不同协议/用户间流转（员工取电池、调拨回收、上报未识别后再识别等场景），
    #             若按电池 SN 取 cb_battery_circulate_log 里的全局最新一条，会把【该协议已经结束流转后】
    #             后续流到别的协议/车辆上的借/还/回收/上报时间算进本协议的「未换电天数」→ 显示不准。
    #   修复：lcts 优先取协议维度的最后归还时间 aid_swap_times[aid][-1]（与客服服务台"换电操作日志"对齐），
    #         回退 battery SN 全局时间（兼容无订单数据的协议），最后兜底 0。
    #   bsn_lcts 独立保留电池 SN 维度时间，供「电池SN层面跟踪」/与客服后台原始数据比对。
    bsn_lcts = 0
    try:
        if report and report.get('time'):
            _rl_dt = datetime.datetime.strptime(report['time'], '%Y-%m-%d %H:%M:%S')
            bsn_lcts = int(_rl_dt.timestamp() * 1000)
    except Exception:
        bsn_lcts = 0
    aid_last_swap_ms = _swap_ts[-1] if _swap_ts else 0
    # v10.28.55：协议维度优先 → 电池 SN 维度兜底；用于「距今未换电」「用户状态」等口径（必须按协议）
    lcts = int(aid_last_swap_ms) if aid_last_swap_ms else int(bsn_lcts or 0)
    # v10.24：距今未换电天数（兼容保留 build 阶段值；前端会用 planDate-lcts 重新覆盖）
    # 公式：今天 - 电池最新一条流通记录的 create_time
    days_since_last_record = ''
    try:
        if lcts:
            _rl = datetime.datetime.fromtimestamp(lcts/1000)
            days_since_last_record = (NOW_DT - _rl).days
    except Exception:
        days_since_last_record = ''
    # v10.24：车辆最后定位地址（先取 battery_last_report.addr，DB 探测后回填；目前表内无 addr 字段，临时回退 loc 网点名）
    vehicle_loc = (report.get('addr', '') or report.get('loc', '') or '') if report else ''
    # v10.25：电池最后定位 = 流通表最新一条记录的网点名(loc)；与 vehicle_loc(优先 addr) 区分来源口径
    bat_last_loc = report.get('loc', '') if report else ''

    # v10.18.6：最终可回访标记（剔除流通异常/柜内归还无电池/空号）
    #   circ_abn 非空（电池已流通至别处/被回收/已还柜）或 circ_in==0（柜内归还=暂无电池）→ 电池实际不在用户手里
    # v10.28.55：关键修复——流通表(battery_circ/battery_last_report)无记录 ≠ 电池不在用户手里
    #   业务场景：该用户从未扫码换电（纯新签/新装电池未上报过），流通表自然没他的 SN。
    #   旧版把这种用户误判为「柜内归还无电池」→ excluded → 全部低频候选 6586 个被错杀。
    #   新版：流通表无记录时，订单表自身(status=working)的协议，默认电池在用户手里 circ_in=1，
    #         仅当流通表「明确给出最近一次操作是柜内归还 OR 异常上报」时才算 circ_in=0。
    excluded = []
    # v10.28.55：_circ_known 只认「流通表真实数据」—— report(流通表最新任意记录) 或 _circ_from_log(流通表聚合)。
    #   订单表降级出来的 circ_entry 不算已知，否则又会把未上报过的用户误判成「柜内归还无电池」。
    _circ_known = bool(report.get('time')) or bool(_circ_from_log)
    if circ_abn_main:
        excluded.append('流通异常(电池已流通至别处)')
    if circ_in_main == 0 and _circ_known:
        # 仅当流通表确实查到记录且判定为归/无电池时，才剔除
        excluded.append('柜内归还无电池')
    elif circ_in_main == 0 and not _circ_known:
        # 流通表无记录：默认判电池在用户手里（业务口径：未上报 ≠ 已还柜）
        # 隐式不加入 excluded，circ_in 兜底为 1
        circ_in_main = 1  # noqa
    # v10.28.55：换电柜断充未识别 / 员工回收 / 调拨-回收 → 电池已不在用户手中 → 直接不进回访
    #   区分于「流通异常(电池已流通至别处)」：上述场景是物理上电池被回收/上报，运营不再追回；
    #   而 in_storage=True 的极端情况下，电池可能还回柜内但用户手里没拿。
    _is_in_storage = bool((battery_circ.get(raw_sn) or battery_circ_norm.get(norm_sn) or {}).get('is_storage'))
    if _is_in_storage:
        excluded.append('电池已不在用户手中(换电柜断充/未识别/员工回收)')
    # 空号黑名单（out/no_followup.json）：已标记无需回访的协议ID
    if aid in NO_FOLLOWUP_AIDS:
        excluded.append('空号/无需回访')
    # v10.21：近 N 天换过电（基于最新流通上报时间）——「生成时」过滤，不放 followable，避免已分配任务被连带清除
    recent_circ_nd = False
    try:
        if report.get('time'):
            _rl = datetime.datetime.strptime(report['time'], '%Y-%m-%d %H:%M:%S')
            recent_circ_nd = (NOW_DT - _rl).days <= RECENT_SWAP_FILTER_DAYS
        else:
            recent_circ_nd = False
    except Exception:
        recent_circ_nd = False
    recent_circ_15d = recent_circ_nd  # 兼容性别名
    # v10.28.55【回滚修复】低频名单归零的真凶就在这里。
    #   历史：v10.28.55 给 followable 加了第三个条件 `and _nf`（shouldFollowUp 判定）。
    #   但 shouldFollowUp 的输入来自 _build_op_history()，其中：
    #       if is_back and (not sn or ...): sn_for_rule = '暂无电池'
    #   当 cb_exchange_order.battery_device_sn 为空（本库流通表无记录，SN 本就取不到）时，
    #   `not sn` 必为真 → 最后一条操作被标记成「柜内归还 + 暂无电池」→ shouldFollowUp 返回 False
    #   → 所有低频候选的 _nf 全为 False → followable 全 False → 名单 0 条。
    #   （这正是日志里「低频用户: 0 ｜ 因流通异常剔除 6586」的成因 —— 6586 个被 _nf 误杀。）
    #   修复：默认回滚到 v10.28.55（昨天正常）口径：followable 只看 (is_lf && !excluded)。
    #   need_followup 仍照常计算并写入 records，供看板展示/人工判断，不再作为硬性拦截。
    #   如需恢复严格口径，在 db_conf.json 里设 "use_need_followup_filter": true。
    _nf = shouldFollowUp(_build_op_history(aid))
    if USE_NEED_FOLLOWUP_FILTER:
        followable = bool(is_lf) and (len(excluded) == 0) and _nf
    else:
        followable = bool(is_lf) and (len(excluded) == 0)

    # v10.28.55：排班优先级 score（按距今未换电天数分档，供回访名单按未流通天数排期）
    #   P0：≥60 天未流通（前两个月及更早未换电）→ score=1000，最高优先
    #   P1：30-60 天未流通（前一个月未换电）→ score=500，次优先
    #   P2：<30 天未流通（最近活跃但仍然低频）→ score=100
    #   电池已不在用户手中（断充已还柜/员工回收/未识别上报）：score=-1，分配时排除
    #   未换电天数不可用（生效天数缺失）：score=50
    _priority = 50
    if _is_in_storage:
        _priority = -1
    elif isinstance(dns, (int, float)) and dns:
        if dns >= 60:
            _priority = 1000
        elif dns >= 30:
            _priority = 500
        else:
            _priority = 100

    records.append({
        'id': aid, 'user_id': a['user_id'],
        'phone': a['user_phone'] or '',         # 协议表里的老号码（保留兼容）
        'cur_phone': cur_phone,                  # v10.20：当前手机号（cb_user 取）
        'name': a['user_name'] or '', 'status': a['status'],
        'agreement_type': {'single':'个人','company':'企业'}.get(a['type'], a['type'] or ''),
        'agreement_type_raw': a['type'] or '',
        'use_days': use_days,
        'product': a['product_name'] or '', 'pid': a['battery_product_id'],
        # v10.18.7：电池 SN / 流通时间 / 操作类型 / 异常原因 四字段同源（均来自 battery_circ[统一SN] 同一字典）
        'battery_sn': circ_sn_main,
        'voltage': bi.get('vol',''),
        'current': bi.get('cur',''), 'soc': bi.get('soc',''), 'online': bi.get('online',''),
        # v10.28.55：电量校准(实测 / 校准 / 距上次上报天数 / 是否陈旧)
        'soc_raw':   bi.get('soc_raw'),
        'soc_cal':   bi.get('soc_cal'),
        'soc_age':   bi.get('soc_age'),
        'soc_stale': bi.get('soc_stale', False),
        # 四字段全部来自 circ_entry（流通表同一 SN 的聚合记录），时间与异常绝不会错位
        'circ_last': circ_last_main,
        'circ_op':   circ_op_main,
        'circ_in':   circ_in_main,
        'circ_abn':  circ_abn_main,
        'circ_full': circ_full_main,       # v10.28.55：末次流通全量展示串（时间 因[类型]流通至[目的地]）
        # v10.21：命中判定同时看订单表流通聚合(battery_circ)与最新流通记录(battery_last_report)
        'circ_match': ('一致' if (battery_circ.get(raw_sn) or battery_circ_norm.get(norm_sn)
                        or battery_last_report.get(raw_sn) or battery_last_report.get(norm_sn)) else '仅订单表(流通表无该SN记录)'),
        # 流通表SN（cb_battery_circulate_log 实际命中的 SN，与板上电池SN应当相同；若不同可一眼看出漂移）
        'circ_agg_sn': (raw_sn if (battery_circ.get(raw_sn) or battery_circ_norm.get(norm_sn)
                        or battery_last_report.get(raw_sn) or battery_last_report.get(norm_sn)) else ''),
        # 流通异常标记：异常原因非空即代表电池已离手（被回收/已还柜/流通至别处）
        'bat_anomaly': bool(circ_abn_main),
        'deposit_amount': round((a['deposit_fee'] or 0)/100.0, 2),
        'deposit_status': a['deposit_status'] or '',
        'deposit_payway': a['deposit_payway'] or '',
        'pkg_name': a['pkg_name'] or '',
        'city_full': a['sys_city_name'] or '',
        'province': (a['province'] or '').strip(),
        'city': (a['city'] or '').strip(),
        'area': (a['area'] or '').strip(),
        'street': (a['street'] or '').strip(),
        'community': (a['community'] or '').strip(),
        'agent': agent_of(a['city']),
        'rent_expire': fmt(a['rent_expire_time']),
        'activate': fmt(a['activation_time']),
        'total_swaps': total,
        'c15': c15, 'c30': c30, 'c45': c45, 'c60': c60,
        'monthly': calc_monthly(c60),
        'is_lf': is_lf, 'level': level, 'lname': lname,
        'owe': a['status'] == 'owe_rent',
        # v10.18.6：最终可回访标记 + 剔除原因（分配环节候选池严格按 followable 过滤）
        'excluded': excluded,
        'followable': followable,
        'recent_circ_15d': recent_circ_15d,
        'recent_circ_nd': recent_circ_nd,
        'circ_op_type': circ_op_type,
        # v10.28.55：电池是否已不在用户手中（已还柜中/员工回收/未识别上报）→ 不进回访
        'battery_in_storage':      _is_in_storage,
        'battery_in_storage_loc':  ((battery_circ.get(raw_sn) or battery_circ_norm.get(norm_sn) or {}).get('loc', '') or ''),
        'battery_in_storage_reason': ((battery_circ.get(raw_sn) or battery_circ_norm.get(norm_sn) or {}).get('reason', '') or ''),
        # v10.28.55：排班优先级 score（按距今未换电天数分档，计算逻辑见 records.append 之前）
        'priority_score': _priority,
        # v10.25：换电频次/换电周期(中位间距)/未换电天数/本地外地/电池最后定位/流通季度/下次预计换电日
        # 全部用短键（swf/scy/dns/cq/ploc/bloc/nse），与 assign.py / gen_dashboard.py 对齐
        'swf': swf,
        'scy': scy,
        'dns': dns,
        'nse': nse,
        'swap_first_fmt': swap_first_fmt,
        'swap_last_fmt': swap_last_fmt,
        'cq': circ_quarter,
        'ploc': phone_local,
        'bloc': bat_last_loc,
        # v10.24：手机号归属地(城市名)/距今未换电天数(基于电池最后记录时间)/车辆最后定位地址
        'pcity': cur_phone_city,
        'dnr': days_since_last_record,
        'cloc': vehicle_loc,
        # v10.26：电池最后记录毫秒戳(供前端按 planDate 实时算 dnr) / 归属地来源
        # v10.28.55：lcts 默认按「协议维度」(aid_swap_times) 取，bsn_lcts 保留电池 SN 维度时间
        'lcts': lcts,
        'bsn_lcts': bsn_lcts,            # v10.28.55：电池 SN 维度时间（cb_battery_circulate_log 全局最新一条）
        'aid_last_swap_ms': aid_last_swap_ms,  # v10.28.55：协议维度最后归还时间（毫秒戳）
        'psrc': psrc,
        # v10.28.55：是否需要回访（基于全部换电操作历史的最后一条操作判定，v10.28.55 复用上面 _nf）
        'need_followup': _nf,
    })

# ---- v10.28.55：数据库字段体检（跑一次，把「字段是否存在 + 是否有值」直接打印出来）----
# 这一步不改动任何数据，只做 SHOW COLUMNS + 采样统计，回答「为什么页面上全是 —」。
try:
    audit_db_fields(cur, [
        ('cb_reception_log', ['agreement_id', 'create_time', 'detail', 'type',
                              'solver_user_name', 'consumer_user_id', 'is_del']),
        ('cb_battery', ['device_sn', 'battery_device_sn', 'last_location_address',
                        'last_location_time', 'online_status']),
        ('cb_user', ['id', 'mobile', 'phone']),
        ('cb_exchange_agreement', ['id', 'user_id', 'status', 'is_del']),
    ])
except Exception as _ae:
    print('[WARN] 数据库字段体检失败（不影响主流程）: %s' % _ae)

# ---- v10.28.55：数据源体检 —— 定位「records 里没有任何 battery_sn」断在哪一步 ----
# battery_sn 的取值链：order['sn'](cb_exchange_order) → bi['sn'](cb_bike_battery_bind_log + cb_battery)
# 任一环节查不到，battery_sn 就全空 → circ_in=0 → 判为「柜内归还/暂无电池」→ excluded 全命中
# → followable 全 0 → 低频用户 0 → 名单 0 条。所以这里把每个字典的规模都打出来。
try:
    print('')
    print('=' * 66)
    print('  数据源体检 (v10.28.55) —— 为什么 records 里没有 battery_sn')
    print('=' * 66)
    for _name, _obj in (
        ('aid_last_order      (cb_exchange_order 最新订单)', aid_last_order),
        ('battery_last_report (流通表最新记录)', battery_last_report),
        ('battery_circ        (流通表聚合)', battery_circ),
        ('battery_info        (绑定表→cb_battery)', battery_info),
        ('aid_last_order_agg  (订单表聚合)', aid_last_order_agg if 'aid_last_order_agg' in dir() else {}),
    ):
        try:
            print('  %-46s %s' % (_name, len(_obj)))
        except Exception as _e2:
            print('  %-46s ERR %s' % (_name, _e2))
    _n_raw = sum(1 for _r in records if (_r.get('battery_sn') or '').strip())
    _n_circ_in = sum(1 for _r in records if _r.get('circ_in'))
    _n_abn = sum(1 for _r in records if _r.get('circ_abn'))
    print('  ' + '-' * 62)
    print('  records 总数                    : %d' % len(records))
    print('  records 中 battery_sn 非空      : %d' % _n_raw)
    print('  records 中 circ_in=1(电池在手)  : %d' % _n_circ_in)
    print('  records 中 circ_abn 非空(异常)  : %d' % _n_abn)
    if _n_raw == 0:
        print('  >> 结论：battery_sn 全空，所有协议都会被判为「柜内归还/暂无电池」')
        print('     而 excluded 会因此全命中 → followable 全 0 → 低频 0 → 名单 0')
        if not aid_last_order:
            print('     ★ 首要嫌疑：aid_last_order 为空（cb_exchange_order 查询失败或该表无 battery_device_sn 列）')
        if not battery_info:
            print('     ★ 次要嫌疑：battery_info 为空（cb_bike_battery_bind_log 或 cb_battery 查询失败）')
    print('=' * 66)
    print('')
except Exception as _de:
    print('[WARN] 数据源体检失败（不影响主流程）: %s' % _de)

# ---- v10.28：电池 cb_battery.last_location_address / last_location_time ----
# 按 record.battery_sn 批量查 cb_battery 表的"最后一次有效定位"地址与时间戳。
#   lla (last location address): 末次定位地址
#   llt (last location time):    末次定位毫秒戳
# 注入到 record['lla'] / record['llt']；同时把 vehicle_loc(cloc) 升级为真实地址（替代 v10.24 临时回退的 loc 网点名）。
# 查询失败/无此字段时回退到 report.loc 兜底，原行为不变。
try:
    # v10.28.55：字段名自愈探测。线上 cb_battery 的 SN 列实际叫 device_sn（见本文件上方
    # 「2.5 电池」段 `SELECT id, device_sn ...`），而旧代码沿用了流通表口径的
    # battery_device_sn，在电池表上会抛 1054 并被 except 吞掉 → 电池定位整列为「—」。
    _sn_col  = pick_col(cur, 'cb_battery', 'device_sn', 'battery_device_sn', 'battery_sn', 'sn')
    _lla_col = pick_col(cur, 'cb_battery', 'last_location_address', 'location_address',
                        'last_address', 'address', 'last_location')
    _llt_col = pick_col(cur, 'cb_battery', 'last_location_time', 'location_time',
                        'last_location_at', 'gps_time', 'update_time')
    print('[v10.28.55] cb_battery 字段探测 => SN列=%s | 地址列=%s | 时间列=%s'
          % (_sn_col, _lla_col, _llt_col))
    _battery_sns = sorted({(r.get('battery_sn') or '').strip() for r in records if r.get('battery_sn')})
    if _sn_col and _lla_col and _battery_sns:
        _battery_loc_map = {}
        _BATCH = 500
        _sel_cols = [_sn_col] + ([_lla_col] if _lla_col else []) + ([_llt_col] if _llt_col else [])
        for _i in range(0, len(_battery_sns), _BATCH):
            _chunk = _battery_sns[_i:_i+_BATCH]
            _ph = ','.join(['%s'] * len(_chunk))
            cur.execute(
                f"SELECT {', '.join('`'+c+'`' for c in _sel_cols)} "
                f"FROM cb_battery WHERE `{_sn_col}` IN ({_ph})",
                tuple(_chunk))
            for _br in cur.fetchall() or []:
                # v10.28.55：cur 是 DictCursor（见连接处 cursorclass=DictCursor），
                # 旧代码用 _br[0]/_br[1] 整数下标取列 → KeyError: 0 → 整段被 except 吞掉。
                # 这里统一转 dict 后按列名取值。
                _d = dict(_br) if not isinstance(_br, dict) else _br
                _sn = str(_d.get(_sn_col) or '').strip()
                _lla_v = str(_d.get(_lla_col) or '').strip() if _lla_col else ''
                _llt_v = 0
                if _llt_col:
                    try:
                        _llt_v = int(_d.get(_llt_col) or 0)
                    except Exception:
                        _llt_v = 0
                if _sn:
                    _battery_loc_map[_sn] = {'lla': _lla_v, 'llt': _llt_v}
        _hit_lla = 0
        for _r in records:
            _info = _battery_loc_map.get((_r.get('battery_sn') or '').strip(), {'lla': '', 'llt': 0})
            _r['lla'] = _info['lla']
            _r['llt'] = _info['llt']
            if _info['lla']:
                _r['cloc'] = _info['lla']  # v10.28：用真实地址覆盖 loc 兜底
                _hit_lla += 1
        print(f'[v10.28.55] cb_battery 定位批量查: SN唯一 {len(_battery_sns)} | 命中地址 {_hit_lla}/{len(records)} | 含时间 {sum(1 for _r in records if _r.get("llt"))}/{len(records)}')
        if _hit_lla == 0 and _battery_sns:
            print('[WARN] 电池定位 0 命中：请核对 records 里的 battery_sn(来自流通表) 与 '
                  f'cb_battery.{_sn_col} 是否同一口径；上方「数据库字段体检」会给出该列非空率。')
    else:
        if not _battery_sns:
            print('[WARN] 电池定位跳过：records 里没有任何 battery_sn（流通表未命中任何电池）')
        else:
            print(f'[WARN] 电池定位跳过：cb_battery 缺少可用字段(SN列={_sn_col}, 地址列={_lla_col})，回退 loc 网点名')
except Exception as _e:
    import traceback as _tb
    print(f'[WARN] cb_battery.last_location 批量查询失败（回退 loc 网点名）: {_e}')
    _tb.print_exc()

_lap("电池流通/电量聚合")
# ---- 4. 汇总 ----
owe_list = [x for x in records if x['owe']]
# v10.18.4：流通异常过滤——电池实际不在用户手里的不计入回访名单（避免"今天还在流通"的无效回访）
# circ_abn 非空（借出后又被流通/已标记异常）或 circ==0（柜内归还=暂无电池）→ 不进入 lf_list
abn_filtered = [x for x in records if x['is_lf'] and (x['circ_abn'] or not x['circ_in'])]
lf_list = [x for x in records if x['is_lf'] and not (x['circ_abn'] or not x['circ_in'])]
# 被剔除的"档案级已流通异常"用户：保留诊断信息（不进 lf_list，不进回访排班）
lf_users = len(set(x['user_id'] for x in lf_list))
owe_users = len(set(x['user_id'] for x in owe_list))
lv_count = {i: sum(1 for x in lf_list if x['level']==i) for i in [1,2,3,4,5]}
lv_count_abn = sum(1 for x in abn_filtered)  # 因流通异常被剔除的低频候选数
prod_lf = {}
for x in lf_list:
    prod_lf[x['product']] = prod_lf.get(x['product'],0)+1
prod_lf_top = sorted(prod_lf.items(), key=lambda kv:-kv[1])[:12]
status_count = {}
for x in records:
    status_count[x['status']] = status_count.get(x['status'],0)+1

type_count = {}
product_count = {}
for x in records:
    type_count[x['agreement_type']] = type_count.get(x['agreement_type'],0)+1
    product_count[x['product']] = product_count.get(x['product'],0)+1

# 诊断：全表（含非活跃）status/type 分布，帮助定位协议数量异常
all_status_count = {}
all_type_count = {}
try:
    cur.execute("SELECT status, COUNT(*) c FROM cb_exchange_agreement WHERE is_del=0 GROUP BY status")
    for r in cur.fetchall():
        all_status_count[r['status'] or '(空)'] = r['c']
    cur.execute("SELECT type, COUNT(*) c FROM cb_exchange_agreement WHERE is_del=0 GROUP BY type")
    for r in cur.fetchall():
        all_type_count[r['type'] or '(空)'] = r['c']
except Exception as e:
    print("[WARN] 全表 status/type 诊断查询失败:", e)

diagnostic = {
    'now': NOW_DT.strftime('%Y-%m-%d %H:%M'),
    'active_total': len(records),
    'active_status_count': status_count,
    'active_type_count': type_count,
    'active_product_count': dict(sorted(product_count.items(), key=lambda kv:-kv[1])[:30]),
    'lf_count': len(lf_list),
    'owe_count': len(owe_list),
    'lf_users': lf_users,
    'owe_users': owe_users,
    'all_status_count': all_status_count,
    'all_type_count': all_type_count,
}
try:
    json.dump(diagnostic, open(f'{OUT}/diagnostic.json','w', encoding='utf-8'), ensure_ascii=False, indent=1)
except Exception as e:
    print("[WARN] diagnostic.json 写入失败:", e)

print(f"欠租催收: {len(owe_list)} | 低频用户: {len(lf_list)} | 档位: {lv_count} | 状态: {status_count} | 类型: {type_count}")
print(f"活跃产品分布(前10): {sorted(product_count.items(), key=lambda kv:-kv[1])[:10]}")
print(f"全表status分布: {all_status_count}")
print(f"全表type分布: {all_type_count}")
# v10.18.4 诊断：被流通异常过滤掉的用户量
if lv_count_abn:
    print(f"[v10.18.4] 因流通异常(电池不在用户手里)剔除的低频候选: {lv_count_abn}（已不进入回访名单，避免无效回访）")

# ---- 5. 客服接待记录（按协议最新一条） + 回访看板（按接待人） + 全量明细 ----
# ===== v10.28.55 → v10.28.55：回访实际效果 — 10 档状态定义与判定函数（必须模块级！）=====
# v10.28.55：拆 S7 拆退订中
#   - 原 S7「已退订·未挽回」只覆盖 terminated/closed 真正的退订；
#   - 「退订中」(unsubscribing) 拆出独立 S10「退订中·未结案」；
#   - 改 S7 文案为「已退订·挽回失败」，与"挽回失败"语义对齐（区别于"主动退订"）。
# 促成口径：S1+S2+S3+S4（接待后 90 天内借出）算有效促成；S5（90天+）单列为参考。
EFFECT_GRADES = {
    'S1': '已换电·当日促成',
    'S2': '已换电·1-7天促成',
    'S3': '已换电·8-30天促成',
    'S4': '已换电·31-90天促成',
    'S5': '已换电·90天+促成',
    'S6': '在租沉默·未促成',
    'S7': '已退订·挽回失败',
    'S8': '已归还·未再借',
    'S9': '电池已回收',
    'S10': '退订中·未结案',  # v10.28.55：协议状态为 unsubscribing 时归此档
}
EFFECT_COLORS = {
    'S1': '#0a8a3a', 'S2': '#2bb55a', 'S3': '#7acb80', 'S4': '#b8e07b', 'S5': '#cfe8a0',
    'S6': '#f3b441',
    'S7': '#9aa4b2',    # 已退订·挽回失败（深灰）
    'S8': '#e58a3a',
    'S9': '#d2603a',
    'S10': '#b084cc',   # 退订中·未结案（淡紫，区别于 S7 灰）
}
# 视为"已促成换电"的档位（90 天内）
EFFECT_CONVERTED = ('S1', 'S2', 'S3', 'S4')

# 协议状态中文映射 & 终止态集合（模块级，供 _judge_effect 与下方明细循环共用）
_STATUS_CN = {'working':'生效中','owe_rent':'欠租','unsubscribing':'退订中','terminated':'已终止','closed':'已终止'}
# v10.28.55：把 "退订中"(unsubscribing) 从终止态集合中独立出来。
#   之前 _TERMINATED_SET 包含 unsubscribing，导致 _judge_effect 第一行直接判定为 S7；
#   实际 unsubscribing 表示用户在走退订流程但还未最终退订，应归 S10。
#   "已退订·挽回失败"(S7) 只保留真正的最终退订状态（terminated/closed）。
_TERMINATED_SET = {'terminated','closed','已终止'}
_UNSUBSCRIBING_SET = {'unsubscribing'}  # v10.28.55：新增 — 退订中状态集合


def _judge_effect(st_raw, sn, rt_ms, circ_op, take_times, circ_last_ms=0):
    """判定单次客服接待的「回访实际效果」（方案B）。

    判定顺序：协议状态优先 → 接待后首次借出时间（二分查找）→ 末次流通类型兜底。

    参数
    ----
    st_raw       : 协议原始状态（'working' / 'owe_rent' / 'unsubscribing'）
    sn           : 该协议绑定的电池 SN
    rt_ms        : 接待时间（毫秒时间戳）
    circ_op      : 末次流通操作类型（_circ_op_cat 的 5 分类）
    take_times   : {sn: [借出时间戳升序]}，由 battery_take_times 提供
    circ_last_ms : 末次流通毫秒时间戳；用于判断「还电池/回收」是否发生在接待之后

    返回
    ----
    (effect_grade, delta_days, first_take_ms)
      effect_grade  : 'S1'~'S9'
      delta_days    : 接待后第几天借出（S1~S5 有值，其余 None）
      first_take_ms : 接待后首次借出的毫秒时间戳（其余为 0）
    """
    import bisect
    # v10.28.55：协议状态优先 —— 拆分退订中 vs 已退订（终态）
    #   - unsubscribing（退订中）→ S10「退订中·未结案」（用户走退订流程但未最终退订，仍有挽回机会）
    #   - terminated/closed（已退订终态）→ S7「已退订·挽回失败」（此前口径为"沉默用户劝退"，
    #     新口径强调"挽回失败"以与"主动退订未挽回"区分）
    if st_raw in _UNSUBSCRIBING_SET:
        return 'S10', None, 0
    if st_raw in _TERMINATED_SET:
        return 'S7', None, 0
    # Step 2：二分查找「接待之后的第一次借出电池」
    times = take_times.get(sn) or []
    if times and rt_ms:
        idx = bisect.bisect_right(times, rt_ms)
        if idx < len(times):
            ft = times[idx]
            dd = (ft - rt_ms) / 86400000.0   # 毫秒 → 天
            if dd < 1:
                return 'S1', round(dd, 2), ft
            if dd <= 7:
                return 'S2', round(dd, 2), ft
            if dd <= 30:
                return 'S3', round(dd, 2), ft
            if dd <= 90:
                return 'S4', round(dd, 2), ft
            return 'S5', round(dd, 2), ft
    # Step 3：接待后至今无借出记录 —— 用末次流通类型区分"卡在哪一步"
    #   v10.28.55 修正：末次流通必须发生在接待【之后】才能算 S8/S9；
    #   若末次流通早于接待（或时间未知），说明接待后压根没动过电池 → S6 在租沉默。
    if circ_last_ms and rt_ms and circ_last_ms <= rt_ms:
        return 'S6', None, 0
    if circ_op in ('换电-还电池', '柜内归还'):
        return 'S8', None, 0     # 还了电池但没再借
    if circ_op == '调拨-回收':
        return 'S9', None, 0     # 电池已被回收
    return 'S6', None, 0         # 在租但沉默，回访未促成


agr_ids = [a['id'] for a in agreements]
reception_by_agr = {}
reception_by_solver = {}
reception_detail = []   # 全量接待明细（供网页看板筛选/下钻）
# v10.28.55：cb_reception_log 字段名自愈探测（不同环境可能叫 exchange_agreement_id / content / solver 等）
_R_AGR = pick_col(cur, 'cb_reception_log', 'agreement_id', 'exchange_agreement_id', 'agr_id')
_R_CT  = pick_col(cur, 'cb_reception_log', 'create_time', 'created_at', 'create_at', 'reception_time')
_R_DET = pick_col(cur, 'cb_reception_log', 'detail', 'content', 'remark', 'description')
_R_TYP = pick_col(cur, 'cb_reception_log', 'type', 'reception_type', 'op_type')
_R_SLV = pick_col(cur, 'cb_reception_log', 'solver_user_name', 'solver', 'operator', 'admin_name')
_R_UID = pick_col(cur, 'cb_reception_log', 'consumer_user_id', 'user_id', 'uid')
_R_DEL = pick_col(cur, 'cb_reception_log', 'is_del', 'deleted', 'is_delete')
print('[v10.28.55] cb_reception_log 字段探测 => 协议=%s 时间=%s 内容=%s 类型=%s 接待人=%s'
      % (_R_AGR, _R_CT, _R_DET, _R_TYP, _R_SLV))
if agr_ids and not _R_AGR:
    print('[WARN] cb_reception_log 找不到协议关联字段 → 上次接待时间/内容将全部为空')

# ===== v10.28.55：员工 ID → 姓名 映射 =====
# 现象：cb_reception_log.solver_user_name 实际存的是员工 ID（如 0/1/2...）而非姓名。
# 修复：探测 cb_admin / cb_staff / cb_user 任意一张员工表，建立 {id_str: name} 字典；
#       找不到则回退为 "员工#N"，并在终端打印 warn 提示运营确认。
_sid_name = {}
_staff_table = None
_staff_id_col = None
_staff_name_col = None
for _stbl, _id_cands, _name_cands in [
    # v10.28.55：六张主流员工表（cb_admin/cb_staff/cb_user 是客服系统常用命名）
    ('cb_admin',     ['id', 'admin_id', 'user_id'], ['name', 'real_name', 'username', 'nickname', 'admin_name']),
    ('cb_staff',     ['id', 'staff_id', 'user_id'], ['name', 'real_name', 'username', 'nickname', 'staff_name']),
    ('cb_user',      ['id', 'user_id'],            ['name', 'real_name', 'username', 'nickname', 'mobile']),
    # v10.28.55：补充更多可能的员工表探测，提升 ID→姓名 自动映射成功率
    ('cb_sys_user',        ['id', 'user_id', 'uid'],         ['name', 'real_name', 'username', 'nickname']),
    ('cb_operator_user',   ['id', 'user_id', 'operator_id'], ['name', 'real_name', 'username', 'nickname', 'operator_name']),
    ('cb_operation_user',  ['id', 'user_id', 'operation_id'],['name', 'real_name', 'username', 'nickname']),
    ('cb_operator',        ['id', 'operator_id', 'user_id'], ['name', 'real_name', 'username', 'nickname', 'operator_name']),
    # v10.28.55：补充运营/会员系统的员工表命名（覆盖外卖/闪购/分销等其他业务场景的运营后台）
    ('cb_member',          ['id', 'user_id', 'uid', 'member_id'],  ['name', 'real_name', 'username', 'nickname', 'mobile']),
    ('cb_employee',        ['id', 'user_id', 'employee_id'],      ['name', 'real_name', 'username', 'nickname', 'employee_name']),
    ('cb_reception_user',  ['id', 'user_id', 'reception_id'],     ['name', 'real_name', 'username', 'nickname']),
    ('cb_reception_staff', ['id', 'staff_id', 'user_id'],         ['name', 'real_name', 'username', 'nickname', 'staff_name']),
    ('ucenter_admin',      ['id', 'admin_id', 'user_id'],         ['username', 'name', 'real_name', 'nickname']),
    ('ucenter_member',     ['id', 'uid', 'member_id'],            ['username', 'name', 'real_name', 'nickname', 'mobile']),
    ('sys_user',           ['id', 'user_id', 'uid'],              ['name', 'real_name', 'username', 'nickname']),
    ('admin_user',         ['id', 'admin_id', 'user_id'],         ['name', 'real_name', 'username', 'nickname', 'admin_name']),
]:
    _tcols = table_columns(cur, _stbl)
    if not _tcols:
        continue
    _idc = next((c for c in _id_cands if c and c.lower() in _tcols), None)
    _nmc = next((c for c in _name_cands if c and c.lower() in _tcols), None)
    if not (_idc and _nmc):
        continue
    try:
        # v10.28.55：用 _safe_exec 包住，连接断开自动重连
        _safe_exec(cur, conn, f"SELECT `{_idc}` AS _id, `{_nmc}` AS _nm FROM `{_stbl}` WHERE `{_nmc}` IS NOT NULL AND `{_nmc}` <> ''", retries=1, label=f'员工表探测:{_stbl}')
        for _rr in cur.fetchall():
            _id_v = _rr.get('_id') if isinstance(_rr, dict) else _rr[0]
            _nm_v = _rr.get('_nm') if isinstance(_rr, dict) else _rr[1]
            if _id_v is None or _nm_v is None:
                continue
            _sid_name[str(_id_v)] = str(_nm_v).strip()
        _staff_table, _staff_id_col, _staff_name_col = _stbl, _idc, _nmc
        break
    except (pymysql.err.InterfaceError, pymysql.err.OperationalError) as _e:
        # v10.28.55：连接真断了 → 整段探测直接放弃（不浪费后续表查询），让主流程 fallback 到 db_conf.json
        print(f'[v10.28.55] 探测员工表 {_stbl} 时连接断开 → 停止探测，fallback 到 db_conf.json.solver_id_map: {_e}')
        break
    except Exception as _e:
        print(f'[v10.28.55] 探测员工表 {_stbl} 失败: {_e}')
        continue
if _staff_table:
    print(f'[v10.28.55] 员工姓名映射：使用 {_staff_table}（{_staff_id_col} → {_staff_name_col}），载入 {len(_sid_name)} 个')
else:
    print('[v10.28.55] ⚠️ 员工姓名映射：未探测到员工表，尝试读取 db_conf.json.solver_id_map 兜底')
    try:
        _cfg = json.load(open(os.path.join(BASE, 'db_conf.json'), encoding='utf-8'))
        _solver_map = _cfg.get('solver_id_map') or {}
        if _solver_map:
            for _k, _v in _solver_map.items():
                _sid_name[str(_k)] = str(_v)
            print(f'[v10.28.55] 员工姓名映射：从 db_conf.json.solver_id_map 载入 {len(_sid_name)} 个（员工表未探测到）')
        else:
            print('[v10.28.55] ⚠️ 警告：员工表未探测到，且 db_conf.json 未配置 solver_id_map → 纯数字接待人将显示为「员工#N」（先看几张员工表实际叫什么）')
            # v10.28.55：列出数据库里所有疑似员工表名（用于运营诊断）
            try:
                cur.execute("SHOW TABLES")
                _all_tbls = [list(row.values())[0] if isinstance(row, dict) else row[0] for row in cur.fetchall()]
                _candidate_tbls = [t for t in _all_tbls if any(k in t.lower() for k in ['staff','admin','employee','operator','user','member','ucenter'])]
                if _candidate_tbls:
                    print(f'[v10.28.55] 数据库里疑似员工表（请确认正确表名后填入 db_conf.json.solver_id_map 或反馈给开发者）：')
                    for _t in _candidate_tbls[:20]:
                        print(f'    - {_t}')
            except Exception as _e:
                print(f'[v10.28.55] 诊断列出员工表失败: {_e}')
    except Exception as _e:
        print(f'[v10.28.55] 读取 db_conf.json.solver_id_map 失败(跳过): {_e}')


def _split_solver(raw):
    """把 cb_reception_log.solver_user_name 拆成姓名列表。
    - 多值分隔符支持：中文'、' / 半角',' / 分号';' / 竖线'|'
    - 通过 _sid_name 把 ID 转姓名（如果原值是纯数字）
    - 找不到映射则保留 "员工#<原值>" 占位
    """
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []
    # 先按分隔符拆
    parts = re.split(r'[、,;|]', s)
    out = []
    seen = set()
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 纯数字：尝试走员工 ID 映射；无映射则回退「员工#N」（不再裸显示 0/1 序号）
        if p.isdigit():
            mapped = _sid_name.get(p)
            if mapped:
                p = mapped
            else:
                p = f'员工#{p}'
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out
if agr_ids and _R_AGR:
    BATCH = 2000
    _del_cond = (f"AND r.`{_R_DEL}`=0" if _R_DEL else "")
    _del_sub  = (f"AND `{_R_DEL}`=0" if _R_DEL else "")
    # v10.28.55：探测员工表期间可能让连接被 MySQL wait_timeout 踢掉，强制 ping 重建后再查主表
    try:
        conn.ping(reconnect=True)
    except Exception as _pe:
        print(f'[v10.28.55] cb_reception_log 查询前 ping 失败: {_pe!r}')
    for k in range(0, len(agr_ids), BATCH):
        ch = agr_ids[k:k+BATCH]; ph = ','.join(['%s']*len(ch))
        # v10.28.55：包 _safe_exec 走自动重连+重试
        _safe_exec(cur, conn, f"""
            SELECT r.`{_R_AGR}` AS _agr, r.`{_R_TYP}` AS _typ, r.`{_R_SLV}` AS _slv,
                   r.`{_R_DET}` AS _det, r.`{_R_CT}` AS _ct
            FROM cb_reception_log r
            JOIN (SELECT `{_R_AGR}` AS _a, MAX(`{_R_CT}`) mt FROM cb_reception_log
                  WHERE 1=1 {_del_sub} AND `{_R_AGR}` IN ({ph}) GROUP BY `{_R_AGR}`) m
              ON r.`{_R_AGR}`=m._a AND r.`{_R_CT}`=m.mt
            WHERE 1=1 {_del_cond} AND r.`{_R_AGR}` IN ({ph})
        """, params=ch*2, retries=2, label=f'cb_reception_log batch{k//BATCH+1}')

        for r in cur.fetchall():
            # v10.28.55：reception_by_agr 写入接待人姓名（多值用"、"拼接）
            _solvers_latest = _split_solver(r['_slv'])
            reception_by_agr[r['_agr']] = {
                'time': datetime.datetime.fromtimestamp(r['_ct']/1000).strftime('%Y-%m-%d %H:%M') if r['_ct'] else '',
                'solver': _solvers_latest[0] if _solvers_latest else '',
                'solvers': _solvers_latest,
                'type': r['_typ'] or '',
                'detail': (r['_det'] or '')[:200]}
        cur.execute(f"""SELECT `{_R_SLV}` AS _s, COUNT(*) c, COUNT(DISTINCT `{_R_UID}`) uc
            FROM cb_reception_log WHERE 1=1 {_del_sub} AND `{_R_AGR}` IN ({ph}) GROUP BY `{_R_SLV}`""", ch)
        for r in cur.fetchall():
            _solvers_g = _split_solver(r['_s'])
            # v10.28.55：按每个姓名单独累计，避免"张三、李四"被当一个人
            for _s in (_solvers_g or ['(未记录接待人)']):
                d = reception_by_solver.setdefault(_s, {'count':0,'users':0,'types':{}})
                d['count'] += r['c']
                if len(_solvers_g) > 1:
                    d['users'] += max(1, r['uc'] // len(_solvers_g))
                else:
                    d['users'] += r['uc']
        cur.execute(f"""SELECT `{_R_SLV}` AS _s, `{_R_TYP}` AS _t, COUNT(*) c FROM cb_reception_log
            WHERE 1=1 {_del_sub} AND `{_R_AGR}` IN ({ph}) GROUP BY `{_R_SLV}`, `{_R_TYP}`""", ch)
        for r in cur.fetchall():
            _solvers_t = _split_solver(r['_s'])
            for _s in (_solvers_t or ['(未记录接待人)']):
                d = reception_by_solver.setdefault(_s, {'count':0,'users':0,'types':{}})
                share = r['c'] / max(1, len(_solvers_t)) if _solvers_t else r['c']
                d['types'][r['_t']] = d['types'].get(r['_t'],0) + share
        # 全量明细（按日期范围/接待人筛选、点击下钻用）
        cur.execute(f"""SELECT r.`{_R_AGR}` AS _agr, r.`{_R_UID}` AS _uid, r.`{_R_TYP}` AS _typ,
                               r.`{_R_SLV}` AS _slv, r.`{_R_DET}` AS _det, r.`{_R_CT}` AS _ct
            FROM cb_reception_log r WHERE 1=1 {_del_sub} AND r.`{_R_AGR}` IN ({ph})""", ch)
        for r in cur.fetchall():
            ct = r['_ct']
            # v10.28.55：多选支持 —— solvers 为姓名列表（去空去重保序），solver 保留首项兼容旧字段
            _solvers = _split_solver(r['_slv'])
            _solver_primary = _solvers[0] if _solvers else ''
            reception_detail.append({
                'aid': r['_agr'],
                'uid': r['_uid'],
                'type': r['_typ'] or '',
                'solver': _solver_primary,         # 兼容旧字段（首项）
                'solvers': _solvers,                 # v10.28.55：多值列表
                'detail': (r['_det'] or '')[:200],
                'time': datetime.datetime.fromtimestamp(ct/1000).strftime('%Y-%m-%d %H:%M') if ct else '',
                # v10.28.55：保留原始毫秒戳。之前用 to_ms('YYYY-MM-DD HH:MM') 会 int() 抛 ValueError，
                # 导致接待时间被当成 0 → 全部判成「未促成」。判定一律走 time_ms。
                'time_ms': int(ct) if ct else 0,
                'tags': classify((r['_det'] or '')[:200], r['_typ'] or ''),
            })
# v10.28.55：接待明细按 aid 关联协议字典的最新电池流通时间和协议状态，供看板明细「手机号」后展示 3 列。
#   「用户状态」三段式规则（用户最新口径）：
#     ① 协议已终止（unsubscribing/terminated/closed/退订中/已终止）→ 已退订（不区分 bct 与 rt）
#     ② 协议生效中且电池流通时间 晚于 接待时间 → 已换电
#     ③ 协议生效中且电池流通时间 早于 接待时间 → 未换电
#     ④ 协议生效中且无电池流通记录（bct 空）→ 未换电
#     ⑤ 协议欠租：同生效中分支处理（未换电 / 已换电），避免「—」造成空档
#   注：原始状态值仍保留为 _agreement_status_raw，前端用其判断"已终止"语义，避免中文字符串漂移。
# v10.28.55：_aid_rec 提到模块级（_STATUS_CN / _TERMINATED_SET 已在上方模块级定义），
#   否则当 cb_reception_log 取不到协议关联字段、if 块不执行时，下方循环会 NameError。
_aid_rec = {x['id']: x for x in records}

# ===== v10.28.55：回访实际效果 —— 明细逐条打档 =====
# v10.28.55 修复：上一版把这段循环塞进了 _judge_effect 函数体的 return 之后，
#   成了死代码，导致所有 reception_detail 行的 effect_grade / battery_circ_time /
#   agreement_status / user_status / pid / phone / need_followup 全部为空 / 横杆。
#   现在恢复为模块级循环，并补全 v10.28.55 未写入的 pid / phone / uid 字段。

# v10.28.55：去重（同一 aid+time_ms 视为同一条；JOIN MAX(create_time) 偶发会产生重复）
_seen = set()
_dedup = []
for _r in reception_detail:
    _k = (_r.get('aid'), _r.get('time_ms'))
    if _k in _seen:
        continue
    _seen.add(_k)
    _dedup.append(_r)
if len(_dedup) != len(reception_detail):
    print(f"[v10.28.55] 接待明细去重: {len(reception_detail)} → {len(_dedup)} 条（按 aid+time_ms）")
reception_detail = _dedup

# v10.28.55：协议记录里没手机号时尝试用 cb_user 兜底（cur_phone_by_uid 是上层基于 a 列表建的；
#   找不到就保持空字符串）
_cur_ph_by_uid = {}
for _a in agreements:
    if _a.get('user_id') and _a.get('cur_phone'):
        _cur_ph_by_uid[_a['user_id']] = _a['cur_phone']

for r in reception_detail:
    a = _aid_rec.get(r['aid'])
    # 基础关联字段（v10.28.55 已有，回归必备）
    r['battery_circ_time'] = (a or {}).get('circ_last', '') or ''
    r['battery_circ_op']  = (a or {}).get('circ_op_type', '') or '未知'
    r['battery_circ_full'] = (a or {}).get('circ_full', '') or ''   # v10.28.55：末次流通全量展示串（时间 因[类型]流通至[目的地]）
    r['battery_sn']       = (a or {}).get('battery_sn', '') or ''
    # v10.28.55：电池是否已不在用户手中（已归还柜中/被员工回收/换电柜断充未识别上报）→ 不进回访
    r['battery_in_storage']      = bool((a or {}).get('is_storage', False))
    r['battery_in_storage_loc']  = (a or {}).get('loc', '') or ''
    r['battery_in_storage_reason'] = (a or {}).get('reason', '') or ''
    _st_raw = (a or {}).get('status', '') or ''
    r['agreement_status'] = _STATUS_CN.get(_st_raw, _st_raw)
    r['_agreement_status_raw'] = _st_raw
    # v10.28.55 兜底：「用户状态」三段式（前台按此渲染）
    # v10.28.55：拆分退订中 vs 已退订 —— 与 _judge_effect 保持一致
    #   - 退订中（unsubscribing）→ "退订中"
    #   - 已退订（terminated/closed）→ "已退订"
    _bct = (r['battery_circ_time'] or '').strip()
    _rt  = (r['time'] or '').strip()
    if _st_raw in _UNSUBSCRIBING_SET:
        r['user_status'] = '退订中'
    elif _st_raw in _TERMINATED_SET:
        r['user_status'] = '已退订'
    elif _bct and _rt:
        r['user_status'] = '已换电' if _bct >= _rt else '未换电'
    elif _bct:
        r['user_status'] = '已换电'
    else:
        r['user_status'] = '未换电'
    r['need_followup'] = (a or {}).get('need_followup')
    # v10.28.55：手机号 / 用户ID —— 之前完全没写入，导致明细「手机号」列全为横杆。
    r['uid']   = (a or {}).get('user_id') or r.get('uid') or ''
    r['phone'] = (a or {}).get('phone') or (a or {}).get('cur_phone') \
                 or _cur_ph_by_uid.get(r.get('uid')) or ''
    # ===== v10.28.55：回访实际效果判定（方案B）=====
    # 用 time_ms（原始毫秒戳）而不是 to_ms(time 字符串) —— to_ms 对 'YYYY-MM-DD HH:MM'
    # 字符串会 int() 抛 ValueError，已确认
    _rt_ms = int(r.get('time_ms') or 0)
    _circ_last_ms = 0
    try:
        if _bct:
            _circ_last_ms = int(datetime.datetime.strptime(_bct, '%Y-%m-%d %H:%M').timestamp() * 1000)
    except Exception:
        _circ_last_ms = 0
    _g, _dd, _ft = _judge_effect(_st_raw, r['battery_sn'], _rt_ms,
                                  r['battery_circ_op'], battery_take_times,
                                  _circ_last_ms)
    r['effect_grade'] = _g
    r['delta_days']   = _dd
    r['first_take_at'] = (
        datetime.datetime.fromtimestamp(_ft / 1000).strftime('%Y-%m-%d %H:%M') if _ft else '')

# v10.28.55：上面循环内只用 a.get('phone'|'cur_phone')，确保 records 已经构建好这两个字段
# （详见 line ~1547 'phone': a['user_phone']，line ~1270 cur_phone_by_uid）
_rec_hit_pct = (len(reception_by_agr) * 100.0 / len(agr_ids)) if agr_ids else 0.0
_lap("客服接待记录")
print(f"有客服接待记录的协议: {len(reception_by_agr)}/{len(agr_ids)} ({_rec_hit_pct:.1f}%) | 接待人(去重): {len(reception_by_solver)} | 明细: {len(reception_detail)}")
if agr_ids and _rec_hit_pct < 5.0:
    print(f'[WARN] 接待记录命中率仅 {_rec_hit_pct:.1f}%：请核对上方体检报告里 cb_reception_log.{_R_AGR} 的非空率，'
          f'以及该列取值是否等于 cb_exchange_agreement.id（口径不一致会导致「上次接待时间/内容」整列为空）')
aid_tags = {}
for r in reception_detail:
    aid_tags.setdefault(r['aid'], set()).update(r['tags'])
for x in records:
    rc = reception_by_agr.get(x['id'], {})
    x['rec_time']=rc.get('time',''); x['rec_solver']=rc.get('solver',''); x['rec_type']=rc.get('type',''); x['rec_detail']=rc.get('detail','')
    x['tags']=sorted(aid_tags.get(x['id'], set()))

# ===== v10.28.55：回访实际效果 —— 聚合统计（供看板「回访效果」Tab 首屏直接渲染）=====
def build_effect_summary(detail):
    """按 effect_grade 聚合出 KPI / 漏斗 / 接待人排行 / 标签效果 / 促成时间分布。
    v10.28.55：by_solver / by_tag 用 Set 计数 distinct aid，
    让「总接待协议数」vs「促成协议数」能真实反映独立用户量（之前 raw 记录数导致同一 aid 多次接待都促成时显示 100%）。"""
    total = len(detail)
    funnel = {g: 0 for g in EFFECT_GRADES}
    # 接待人维度：aid 去重
    by_solver_aids = {}  # solver -> {'total_aids': set, 'conv_aids': set}
    # 标签维度：aid 去重（一条接待多个标签，每个标签 aid 只计一次）
    by_tag_aids = {}
    # 促成时间分布桶（天）：0 / 1 / 3 / 7 / 15 / 30 / 90+
    buckets = [(0, '0d'), (1, '1d'), (3, '3d'), (7, '7d'), (15, '15d'), (30, '30d')]
    dist = {b[1]: 0 for b in buckets}
    dist['90d+'] = 0
    for r in detail:
        g = r.get('effect_grade') or 'S6'
        funnel[g] = funnel.get(g, 0) + 1
        conv = 1 if g in EFFECT_CONVERTED else 0
        aid = r.get('aid') or ''
        # v10.28.55：接待人维度（aid 去重）—— 多选支持
        #   一条接待的 solvers = ["张三","李四"] 时，需要给 张三/李四 各 +1（独立 aid）。
        #   旧版只取 r.get('solver') 首项，导致"张三、李四"的两次接待被归到一个人头上。
        _solver_list = r.get('solvers') or ([r.get('solver')] if r.get('solver') else [])
        if not _solver_list:
            _solver_list = ['（未知）']
        for _s in _solver_list:
            st = by_solver_aids.setdefault(_s, {'total_aids': set(), 'conv_aids': set()})
            st['total_aids'].add(aid)
            if conv and aid:
                st['conv_aids'].add(aid)
        # 标签维度（aid 去重；一条多标签，每标签 aid 只算一次）
        tags = r.get('tags') or ['（无标签）']
        for t in tags:
            td = by_tag_aids.setdefault(t, {'total_aids': set(), 'conv_aids': set()})
            td['total_aids'].add(aid)
            if conv and aid:
                td['conv_aids'].add(aid)
        # 促成时间分布
        dd = r.get('delta_days')
        if g in EFFECT_CONVERTED and dd is not None:
            placed = False
            for lim, name in buckets:
                if dd <= lim:
                    dist[name] += 1
                    placed = True
                    break
            if not placed:
                if dd <= 90:
                    dist['30d'] += 1
                else:
                    dist['90d+'] += 1
    conv_total = sum(funnel.get(g, 0) for g in EFFECT_CONVERTED)
    conv_30 = funnel.get('S1', 0) + funnel.get('S2', 0) + funnel.get('S3', 0)

    def _rank_from_sets(d, key='conv'):
        """v10.28.55：从 set 计数器转为排行结果，total/conv 均为独立 aid 数。"""
        out = []
        for k, v in d.items():
            t = len(v['total_aids'])
            c = len(v['conv_aids'])
            rate = (c * 100.0 / t) if t else 0.0
            out.append({'name': k, 'total': t, 'conv': c,
                        'rate': round(rate, 1)})
        out.sort(key=lambda x: (-x['rate'], -x['total']))
        return out

    return {
        'total': total,
        'conv_total': conv_total,
        'conv_rate': round(conv_total * 100.0 / total, 1) if total else 0.0,
        'conv_30': conv_30,
        'conv_rate_30': round(conv_30 * 100.0 / total, 1) if total else 0.0,
        'silent': funnel.get('S6', 0),
        'unsub': funnel.get('S7', 0),     # 已退订·挽回失败（v10.28.55：口径修正）
        'unsubscribing': funnel.get('S10', 0),  # v10.28.55：退订中独立档位
        'funnel': [{'grade': g, 'name': EFFECT_GRADES[g], 'color': EFFECT_COLORS[g],
                    'count': funnel.get(g, 0),
                    'pct': round(funnel.get(g, 0) * 100.0 / total, 1) if total else 0.0}
                   # v10.28.55：S10 加入漏斗（位置在 S9 之后）
                   for g in ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9', 'S10']],
        'by_solver': _rank_from_sets(by_solver_aids),
        'by_tag': _rank_from_sets(by_tag_aids)[:30],
        'dist': [{'name': k, 'count': dist[k]} for k in
                 ['0d', '1d', '7d', '15d', '30d', '90d+']] if False else  # 保留旧键名
        [{'name': k, 'count': dist[k]} for k in
         ['0d', '1d', '3d', '7d', '15d', '30d', '90d+']],
    }


effect_summary = build_effect_summary(reception_detail)
# v10.28.55：标记「数据就绪度」，供前端顶部横幅判断是否需要重新同步
_effect_ready_count = sum(1 for _r in reception_detail if _r.get('effect_grade'))
_effect_ready = _effect_ready_count > 0
effect_summary['ready'] = _effect_ready
effect_summary['ready_rows'] = _effect_ready_count
try:
    os.makedirs(os.path.join(BASE, "out"), exist_ok=True)
    with open(os.path.join(BASE, "out", "effect_summary.json"), "w", encoding="utf-8") as _f:
        json.dump(effect_summary, _f, ensure_ascii=False)
    print(f"[v10.28.55] 回访效果: 总接待 {effect_summary['total']} | "
          f"促成 {effect_summary['conv_total']} ({effect_summary['conv_rate']}%) | "
          f"在租沉默 {effect_summary['silent']} | 已退订 {effect_summary['unsub']} | "
          f"效果就绪 {_effect_ready_count}/{effect_summary['total']}")
except Exception as e:
    print(f"[WARN] effect_summary.json 写出失败: {e}")

# v10.28.57：XLSX 明细写出开关。
#   12 万行 × 54 列时，openpyxl 逐格写会让这一步占同步总耗时的大头（分钟级）。
#   db_conf.json 里配 "build_xlsx": false，或命令行加 --no-xlsx → 只写表头、跳过明细。
#   看板、records.json、assignments 均不受影响，导出行数少时可随时改回 true。
_SKIP_XLSX = False
try:
    _cfg_x = json.load(open(os.path.join(BASE, 'db_conf.json'), encoding='utf-8')) or {}
    _SKIP_XLSX = str(_cfg_x.get('build_xlsx', 'true')).strip().lower() in ('0', 'false', 'no', 'off')
except Exception:
    pass
try:
    if '--no-xlsx' in sys.argv:
        _SKIP_XLSX = True
except Exception:
    pass
if _SKIP_XLSX:
    print('[v10.28.57] ⚡ build_xlsx=false：本次同步跳过 XLSX 明细写出（看板与名单不受影响）')

# ================= 写 XLSX =================
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
wb = openpyxl.Workbook()
HEAD_FILL = PatternFill('solid', fgColor='1F4E78')
HEAD_FONT = Font(bold=True, color='FFFFFF', size=10)
TITLE_FONT = Font(bold=True, size=13, color='1F4E78')
SUBTITLE_FONT = Font(bold=True, size=11, color='1F4E78')
LF_FILL = {1:PatternFill('solid', fgColor='F4CCCC'),2:PatternFill('solid', fgColor='FCE5CD'),
           3:PatternFill('solid', fgColor='FFF2CC'),4:PatternFill('solid', fgColor='D9EAD3'),
           5:PatternFill('solid', fgColor='9FC5E8')}  # L5·电量<25%：浅蓝，区别于天数维度的1-4档渐变
thin = Side(style='thin', color='D9D9D9')
BORDER = Border(left=thin,right=thin,top=thin,bottom=thin)
PHONE_FONT = Font(color='C00000', bold=True)

COLS = [('协议ID',16),('用户ID',16),('手机号',14),('当前手机号',14),('使用天数',12),('电池产品',14),('产品ID',12),
        # v10.18.5：板上"电池SN" = 协议最新一笔换电订单的 battery_device_sn（与客服管理后台一致）
        #          "流通SN" = cb_battery_circulate_log 聚合表中该 SN 的最新记录SN（与流通表一致）
        #          "SN一致性"= 三者比对结果（一致 / SN不一致 / 未匹配流通记录）
        ('板上电池SN',22),('流通表SN',22),('SN一致性',14),('电池流通时间',18),('操作类型',16),
        ('电压(V)',10),('电流(A)',10),('电量',10),('在线状态',10),
        # v10.28.55：电量校准列(实测=实测/校准区分，长文本), 「电量(实测/校准/陈旧)」
        ('电量(实测%)',10),('电量(校准%)',10),('电量陈旧天数',12),
        # v10.28.55：手机号归属地 / 距今未换电天数 / 换电周期（中位间距），连续放在「在线状态」后方便核对
        ('手机号归属地',12),('距今未换电天数',14),('换电周期(天)',12),
        ('押金金额',12),('押金划扣状态',14),('租赁套餐',14),
        ('省份',10),('城市',10),('区域',10),('街道',12),('社区',12),('城市全称',14),
        ('协议类型',10),('协议状态',10),('激活时间',12),('租金到期',12),('15天归还',9),('30天归还',9),('45天归还',9),
        ('60天归还',9),('累计换电',10),('月均换电频次',12),('是否低频',9),('低频档位',18),
        ('最近接待时间',16),('接待人',12),('接待类型',16),('接待内容',34),
        # v10.28.55：是否需要回访（与看板接待明细列对齐）
        ('是否需要回访',14),
        ('跟进人',10),('跟进状态',10),('跟进备注',22),('最后跟进时间',14),('异常原因',30),('代理商',14)]

def style_header(ws, ncol):
    for j in range(1, ncol+1):
        cell = ws.cell(1, j); cell.fill = HEAD_FILL; cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BORDER

def write_sheet(ws, rows, sortkey):
    rows = sorted(rows, key=sortkey)
    # v10.28.57：表头用 append 一次写入（比逐格 ws.cell 快）
    ws.append([name for name, w in COLS])
    for j,(name,w) in enumerate(COLS,1):
        ws.column_dimensions[get_column_letter(j)].width = w
    style_header(ws, len(COLS))
    # v10.28.57：数据量超过 12 万行 × 54 列时，逐格写样式（边框+对齐）会让同步从几十秒
    # 变成好几分钟（12 万行会产生 650 万个样式对象）。现改为：
    #   · 数据行用 ws.append 批量写（openpyxl 内部走快速路径）
    #   · 去掉逐格 border/alignment（视觉影响极小，换来执行时间从分钟级降到秒级）
    #   · 手机号红色/文本格式、数字格式、低频档位着色 —— 改为「整列/仅低频行」设置
    ws.freeze_panes = 'A2'
    if _SKIP_XLSX:
        print(f'[v10.28.57] build_xlsx=false：{ws.title} 仅写表头（{len(rows)} 行明细已跳过）')
        ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}1"
        return
    _lf_rows = []
    for i,x in enumerate(rows,2):
        status_label = {'working':'生效中','owe_rent':'欠租','unsubscribing':'退订中'}.get(x['status'], x['status'])
        # v10.28.55：在线状态映射中文（online→在线 / offline→离线 / 其他原样输出）
        online_label = {'online':'在线','offline':'离线'}.get((x['online'] or '').lower(), x['online'] or '')
        vals = [x['id'],x['user_id'],x['phone'],x.get('cur_phone',''),x['use_days'] if x['use_days'] is not None else '',x['product'],x['pid'],
                # v10.18.5：板上的「电池SN」来自协议最新一笔订单；「流通表SN」来自 cb_battery_circulate_log 聚合
                x['battery_sn'],x.get('circ_agg_sn', x['battery_sn']),x['circ_match'],
                x['circ_last'],x['circ_op'],
                x['voltage'],x['current'],x['soc'],online_label,
                # v10.28.55：电量校准列 — 实测(BMS 原值)/校准(自放电修正)/陈旧天数
                (x.get('soc_raw') if x.get('soc_raw') is not None else ''),
                (x.get('soc_cal') if x.get('soc_cal') is not None else ''),
                (x.get('soc_age') if x.get('soc_age') is not None else ''),
                # v10.28.55：手机号归属地 / 距今未换电天数 / 换电周期
                x.get('pcity',''),x.get('dnr','') if x.get('dnr') is not None else '',x.get('scy','') if x.get('scy') is not None else '',
                x['deposit_amount'],{'on':'在押','off':'已退/已划扣'}.get(x['deposit_status'],x['deposit_status']),x['pkg_name'],
                x['province'],x['city'],x['area'],x['street'],x['community'],x['city_full'],
                x['agreement_type'],status_label,x['activate'],x['rent_expire'],x['c15'],x['c30'],x['c45'],x['c60'],x['total_swaps'],
                x['monthly'],'是' if x['is_lf'] else '否', x['lname'],
                x['rec_time'],x['rec_solver'],x['rec_type'],x['rec_detail'],'','','','',x['circ_abn'],x['agent']]
        ws.append(vals)
        if x['is_lf']:
            _lf_rows.append((i, x['level']))
    # 整列设置：手机号（C）/当前手机号（D）文本格式防科学计数法 + 标红
    for _colL in ('C', 'D'):
        try:
            for c in ws[_colL][1:]:
                c.number_format = '@'
                c.font = PHONE_FONT
        except Exception:
            pass
    # 数字格式：月均换电频次(AO=41) / 押金金额(W=23)
    for _colL in (get_column_letter(41), get_column_letter(23)):
        try:
            for c in ws[_colL][1:]:
                c.number_format = '0.00'
        except Exception:
            pass
    # 低频档位着色：42=是否低频 / 43=低频档位（v10.28.57 修正——原代码误写死 22/23，
    # 列前移后已错位到「换电周期/押金金额」，导致低频行一直没被着色）
    for i, lv in _lf_rows:
        try:
            ws.cell(i, 42).fill = LF_FILL[lv]
            ws.cell(i, 43).fill = LF_FILL[lv]
        except Exception:
            pass
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}{len(rows)+1}"

# Sheet1 说明
ws0 = wb.active; ws0.title = '说明与口径'
lines = [
 ('低频用户 & 欠租催收回访名单 — 数据说明与统计来源', 'title'),
 (f'数据截止时间：{NOW_DT.strftime("%Y-%m-%d %H:%M")}（以 cb_exchange_order.back_battery_time 最新时间为准）', ''),
 ('', ''),
 ('【数据库与数据表来源】', 'subtitle'),
 ('数据库：sharing-citybike-pro', ''),
 ('  · 协议主表：cb_exchange_agreement（含 status、user_id、user_phone、battery_product_id、site_id、rent_expire_time、activation_time、is_del）', ''),
 ('  · 归还/取电池表：cb_exchange_order（含 exchange_agreement_id、back_battery_time、take_battery_time）', ''),
 ('  · 电池产品表：cb_battery_product（id → product_name）', ''),
 ('  · 实体电池表：cb_battery（id → 电池SN / 电压 / 电流 / 电量 / 在线状态，按 a.battery_id 关联）', ''),
 ('  · 站点/地理表：cb_site（id → province / city / area / street / community）', ''),
 ('  · 客服接待表：cb_reception_log（agreement_id → 最近接待时间/接待人/类型/内容；solver_user_name 为接待人）', ''),
 ('', ''),
 ('【活跃协议定义 / 当前协议数】', 'subtitle'),
 (f'  cb_exchange_agreement.status IN ("working", "owe_rent", "unsubscribing") AND is_del = 0，共 {len(records)} 份。', ''),
 ('  “当前协议数” = 活跃协议再叠加所有筛选条件（省市区街道、电池产品、是否低频、协议状态、低频档位、协议ID、关键词）。', ''),
 ('', ''),
 ('【协议状态】', 'subtitle'),
 (f'  · working（正常）: {status_count.get("working",0)} 份', ''),
 (f'  · owe_rent（欠租）: {status_count.get("owe_rent",0)} 份', ''),
 ('', ''),
 ('【欠租催收】', 'subtitle'),
 (f'  当前协议中 status = "owe_rent" 的协议数，共 {len(owe_list)} 份（{owe_users} 个用户）。', ''),
 ('', ''),
 ('【低频用户定义 / 计算依据】', 'subtitle'),
 ('判定维度：协议生效后累计“归还电池”次数（cb_exchange_order.back_battery_time > 0），已兼容毫秒/秒两种时间戳。', ''),
 ('  · 协议生效 15~30 天内累计换电 < 1 次  → L1·15~30天档（最严重）', ''),
 ('  · 协议生效 30~45 天内累计换电 < 2 次  → L2·30~45天档', ''),
 ('  · 协议生效 45~60 天内累计换电 < 3 次  → L3·45~60天档', ''),
 ('  · 协议生效 >60 天内累计换电 < 4 次     → L4·>60天档（最轻）', ''),
 ('全部活跃协议（生效 >15 天）均参与低频判定；≤15 天新用户不参与判定。档位阈值：L1 15~30天换电<3 / L2 30~45天<4 / L3 45~60天<5 / L4 >60天<9（v10.11 默认放宽版，用于回到三千多量级；可在 db_conf.json 改 lowfreq_thresholds 自行调整）。', ''),
 (f'低频用户共 {len(lf_list)} 份协议（{lf_users} 个去重用户），档位分布：L1={lv_count[1]}  L2={lv_count[2]}  L3={lv_count[3]}  L4={lv_count[4]}。', ''),
 ('', ''),
 ('【月均换电频次】', 'subtitle'),
 ('  计算方式：60天归还次数 ÷ 2（60天≈2个月），保留两位小数。', ''),
 ('  用于衡量用户最近两个月的平均活跃度，数值越低越需回访。', ''),
 ('', ''),
 ('【L1最严重】', 'subtitle'),
 ('  协议生效 15~30 天内累计换电 < 2 次的协议数（即 0 或 1 次），代表"新激活用户近半月未换电或仅 1 次"的高风险用户。', ''),
 ('', ''),
 ('【特别说明：为什么用 back_battery_time 而非 back_status】', 'subtitle'),
 ('原字段 cb_exchange_order.back_status 成功状态基本停留在 2023 年；2024-2026 年已归还订单的 back_status 多为 init。', ''),
 ('为确保统计覆盖最新数据，改用 back_battery_time > 0（真实发生归还的时间戳）作为归还事件判定。', ''),
 ('', ''),
 ('【手机号】', 'subtitle'),
 ('保留原始 11 位，未脱敏，用于电话回访。', ''),
 ('', ''),
 ('【客服接待 / 回访看板】', 'subtitle'),
 (f'数据来源：cb_reception_log（is_del=0），按 agreement_id 关联当前活跃协议，共 {len(reception_by_agr)} 份协议有接待记录。', ''),
 ('  · 名单中“最近接待时间/接待人/接待类型/接待内容”= 该协议最新一条接待记录（按 create_time 取最大）。', ''),
 ('  · “接待类型”取值含：book_user_visit(预约回访) / owe_rent_user(欠租跟进) / silent_user(沉默唤醒) / back_validate(归还校验) / other(其他) 等。', ''),
 ('  · “回访看板”工作表按接待人(solver_user_name)汇总：接待次数、接待人数(去重用户)、及回访预约/欠租跟进/沉默唤醒/其他 四类结果数量。', ''),
 ('  · 接待人数=该接待人处理的去重 consumer_user_id 数；接待结果按 type 分类计数。', ''),
 ('', ''),
 ('【筛选与跟进】', 'subtitle'),
 ('Excel 中可用“省份/城市/区域/街道/电池产品/协议ID/是否低频/协议状态/低频档位”等列的自动筛选做维度下钻。', ''),
 ('“跟进人/跟进状态/跟进备注”供回访团队填写。', ''),
]
for i,(t,kind) in enumerate(lines,1):
    cell = ws0.cell(i,1,t)
    if kind=='title': cell.font = TITLE_FONT
    elif kind=='subtitle': cell.font = SUBTITLE_FONT
    else: cell.font = Font(size=10)
ws0.column_dimensions['A'].width = 115

# Sheet2 欠租催收回访
ws1 = wb.create_sheet('欠租催收回访名单')
write_sheet(ws1, owe_list, lambda x:(x['rent_expire'] or '9999', x['level'], x['c60']))

# Sheet3 低频用户名单
ws2 = wb.create_sheet('低频用户名单')
write_sheet(ws2, lf_list, lambda x:(x['level'], x['c60'], x['product']))

# Sheet4 回访看板（按接待人汇总）
ws3 = wb.create_sheet('回访看板')
rcols = [('接待人',16),('接待次数',12),('接待人数(去重用户)',16),
         ('回访预约',14),('欠租跟进',14),('沉默唤醒',12),('其他',12)]
for j,(name,w) in enumerate(rcols,1):
    ws3.cell(1,j,name); ws3.column_dimensions[get_column_letter(j)].width = w
style_header(ws3, len(rcols))
solver_rows = sorted(reception_by_solver.items(), key=lambda kv:-kv[1]['count'])
for i,(s,d) in enumerate(solver_rows,2):
    t = d['types']
    vals = [s, d['count'], d['users'],
            t.get('book_user_visit',0), t.get('owe_rent_user',0),
            t.get('silent_user',0), t.get('other',0)]
    for j,v in enumerate(vals,1):
        cell = ws3.cell(i,j,v); cell.border = BORDER; cell.alignment = Alignment(vertical='center')
ws3.freeze_panes = 'A2'

xlsx_path = f'{OUT}/回访名单.xlsx'
wb.save(xlsx_path)
print("已写出:", xlsx_path)

# ================= 在线预览数据 =================
summary = {
 'now': NOW_DT.strftime('%Y-%m-%d %H:%M'),
 'total': len(records), 'owe': len(owe_list), 'owe_users': owe_users,
 'lf': len(lf_list), 'lf_users': lf_users, 'lv': lv_count,
 'status_count': status_count,
 'prod_lf_top': prod_lf_top,
 'owe_sample': [{'id':x['id'],'phone':x['phone'],'name':x['name'],'product':x['product'],
                 'city':x['city'],'area':x['area'],'street':x['street'],'rent_expire':x['rent_expire'],'c60':x['c60']} for x in sorted(owe_list,key=lambda z:z['rent_expire'] or '9')[:12]],
 'lf_sample': [{'id':x['id'],'phone':x['phone'],'name':x['name'],'product':x['product'],
                'city':x['city'],'area':x['area'],'street':x['street'],
                'lname':x['lname'],'c15':x['c15'],'c30':x['c30'],'c45':x['c45'],'c60':x['c60']} for x in sorted(lf_list,key=lambda z:(z['level'],z['c60']))[:12]],
}
json.dump(summary, open(f'{OUT}/summary.json','w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---- 导出紧凑全量数据（供网页看板内联）----
compact = [{'id':r['id'],'uid':r['user_id'],'cid':r['user_id'],
            'ph':r['phone'] or r.get('cur_phone') or '',
            'cph':r.get('cur_phone') or '','days':r['use_days'],'pd':r['product'],'pid':r['pid'],
            'ag':r['agent'],
            'pr':r['province'],'ci':r['city'],'ar':r['area'],'st':r['street'],'co':r['community'],'ctf':r.get('city_full') or ((r.get('ci') or '').strip() + (' ' + (r.get('ar') or '').strip() if (r.get('ar') or '').strip() else '')),
            'status':r['status'],'at':r['agreement_type'],'atr':r['agreement_type_raw'],'ac':r['activate'],'re':r['rent_expire'],
            'dep':r['deposit_amount'],'dst':r['deposit_status'],'dpw':r['deposit_payway'],'pkg':r['pkg_name'],
            'bsn':r['battery_sn'],'vol':r['voltage'],'cur':r['current'],'soc':r['soc'],'onl':r['online'],
            # v10.28.55：电量校准(短键，与前端 columns 顺序对齐)
            'socr':r.get('soc_raw'),'socc':r.get('soc_cal'),'soage':r.get('soc_age'),'sost':r.get('soc_stale', False),
            'bcl':r.get('circ_last',''),'bco':r.get('circ_op',''),'bcv':r.get('circ_in',0),
            'cabn':r.get('circ_abn',''),
            'ba':r.get('bat_anomaly', False),
            'battery_in_storage':r.get('battery_in_storage',False),
            'battery_in_storage_loc':r.get('battery_in_storage_loc',''),
            'battery_in_storage_reason':r.get('battery_in_storage_reason',''),
            'priority_score':r.get('priority_score',50),
            'c15':r['c15'],'c30':r['c30'],'c45':r['c45'],'c60':r['c60'],'mf':r['monthly'],'sw':r.get('total_swaps',0),
            # v10.25：与 assign.py / gen_dashboard.py 对齐的短键字段（关键！之前长键导致页面空白）
            'swf':r.get('swf',0),'scy':r.get('scy'),'dns':r.get('dns',0),'nse':r.get('nse',''),
            'ploc':r.get('ploc',''),'bloc':r.get('bloc',''),'cq':r.get('cq',''),
            'pcity':r.get('pcity',''),'dnr':r.get('dnr',''),'cloc':r.get('cloc',''),
            # v10.26：电池最后记录毫秒戳 / 归属地来源标记
            # v10.28.55：lcts 默认按协议维度算（aid_swap_times），bsn_lcts 保留电池 SN 维度时间
            'lcts':r.get('lcts',0),'bsn_lcts':r.get('bsn_lcts',0),'aid_last_swap_ms':r.get('aid_last_swap_ms',0),'psrc':r.get('psrc',''),
            # v10.28：cb_battery.last_location_address / last_location_time（来自电池表"最后一次有效定位"）
            'lla':r.get('lla',''),'llt':r.get('llt',0),
            'rt':reception_by_agr.get(r['id'],{}).get('time',''),
            'rs':reception_by_agr.get(r['id'],{}).get('solver',''),
            'rty':reception_by_agr.get(r['id'],{}).get('type',''),
            'rd':reception_by_agr.get(r['id'],{}).get('detail',''),
            'rc':classify_recall(reception_by_agr.get(r['id'],{}).get('detail',''), reception_by_agr.get(r['id'],{}).get('type','')),
            'lf':1 if r['is_lf'] else 0,'lv':r['level'],'ln':r['lname'],'owe':1 if r['owe'] else 0,'tags':r['tags'],
            'excluded':r.get('excluded',[]),'followable':1 if r.get('followable') else 0,            'rc15':1 if r.get('recent_circ_15d') else 0,
            'rcnd':1 if r.get('recent_circ_nd') else 0,'cot':r.get('circ_op_type','未知'),
            'nf':r.get('need_followup'),
            } for r in records]

# 短信发送结果由 merge_sms_excel.py 按手机号并入（见 merge_sms_excel.py），此处不再处理。

json.dump({'now':NOW_DT.strftime('%Y-%m-%d %H:%M'),'total':len(records),'rows':compact,
            'diagnostic': diagnostic,
            'reception':[{'solver':s,'count':d['count'],'users':d['users'],'types':d['types']}
                         for s,d in sorted(reception_by_solver.items(), key=lambda kv:-kv[1]['count'])][:200],
            'reception_detail': reception_detail,
            'effect_summary': effect_summary,
            '_meta': {
                'build_lists_version': __VERSION__,
                'build_time': NOW_DT.strftime('%Y-%m-%d %H:%M:%S'),
                'total_rows': len(records),
                'records_rows': len(compact),
                'effect_ready': _effect_ready,
                'effect_ready_rows': _effect_ready_count,
                'reception_detail_rows': len(reception_detail),
            }},
          open(f'{OUT}/records.json','w', encoding='utf-8'), ensure_ascii=False, separators=(',',':'))
_lap("写 records.json")
# v10.28.57：保存 schema 磁盘缓存，下次同步秒命中
_save_schema_disk_cache()
print("records.json rows:", len(compact), "| 接待人汇总:", len(reception_by_solver),
      "| effect_ready:", _effect_ready_count, "/", len(reception_detail))

# v10.28.57 性能优化：兜底字段提到 compact 生成阶段（避免再写一次 30MB 文件，省半时间）
#   顺手做的兼容：上面 dict comprehension 已经生成完 compact，现在只需补缺失字段

# （本地部署版已移除沙箱探查逻辑：客服表/电池表结构已知，无需重复 SHOW TABLES 探查）
conn.close()
