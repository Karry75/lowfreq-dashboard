# 低频用户 · 欠租催收智能回访看板（lowfreq-dashboard）

> 面向换电 / 两轮出行行业的**低频用户识别 + 欠租催收 + 智能回访排班**一体化数据分析与可视化工具。
> 支持从 MySQL 同步业务数据，自动构建用户画像、低频档位、归属地、促成漏斗，并生成可按接待人/标签筛选、按日/周/月统计的运营看板，以及可直接下发的回访排班名单。

> 📊 **在线可视化看板（GitHub Pages）**：[https://karry75.github.io/lowfreq-dashboard/](https://karry75.github.io/lowfreq-dashboard/) —— 进入后点「▶ 打开看板 Live Demo」即可查看完整脱敏运营看板。

---

## ✨ 功能特性

- **一键数据同步**：`build_lists.py` 连接业务库，自动探测表结构（字段自愈）、计算低频档位、押金/欠租状态、归属地（数据自带 → 离线字典 → 在线 API 三级兜底）。
- **运营看板**：`gen_dashboard.py` 生成**自包含单文件 HTML**（无需服务器即可双击打开），含：
  - 接待人促成排行、促成时间分布、标签促成效果
  - 按日 / 周 / 月统计切换
  - 手机号归属地呈现（在线兜底，断网也能显示）
  - 搜索联系人 → 直接呈现其相关数据
- **智能回访排班**：`assign.py` 基于最新接待记录自动推断回访状态，生成 Excel 回访名单 + JSON 排班（含配额、冷却期、派单历史）。
- **本地服务**：`serve.py` 提供 `0.0.0.0:8173` HTTP 服务，支持同网段访问、gzip 压缩、列式编码（2600 行看板仅 ~730KB）。
- **离线演示**：`mock_db.py` + `run_with_mock.py` 可在**无数据库**情况下跑通整条流水线，便于本地调试。

## 📁 目录结构

```
lowfreq-dashboard/
├── serve.py                 # 本地 HTTP 服务（0.0.0.0:8173）
├── build_lists.py           # 数据同步 + 用户画像 + 低频识别主流程
├── gen_dashboard.py         # 看板 HTML 生成（列式编码，自包含）
├── assign.py                # 回访排班名单生成
├── phone_fallback.py        # 手机号归属地离线字典 + 查询
├── env.py / mock_db.py      # 环境配置 / 离线 Mock 数据源
├── sync_intranet.py / sync_local.py
├── *.bat / start.sh         # Windows / Linux 启动与运维脚本
├── db_conf.example.json     # 数据库配置样例（请复制为 db_conf.json 填写）
├── staff_auth.example.json  # 员工/权限样例
├── desensitize_data.py      # 隐私脱敏工具（PII -> 匿名）
├── phone.dat                # 号段归属地数据
├── requirements.txt
├── out/                     # 生成的产物（含脱敏示例数据，可直接演示）
│   ├── records.json         # 脱敏后的数据集（2600 条协议，结构/分布真实）
│   ├── followup_dashboard.html  # 看板（双击即看，无需服务）
│   ├── assignments.json     # 回访排班
│   ├── dispatch_history.json# 派单历史
│   ├── effect_summary.json  # 促成效果汇总
│   └── ...
├── docs/                    # 口径说明 / 部署手册 / 版本复盘
├── LICENSE
└── CHANGELOG.md
```

## 🚀 快速开始

### 方式 A：零配置看演示
直接双击 `out/followup_dashboard.html`，看板立即呈现**脱敏示例数据**（含真实业务分布，已隐去消费者隐私）。

### 方式 B：连你自己的真实库
```bash
pip install -r requirements.txt
cp db_conf.example.json db_conf.json      # 填入你的 MySQL 连接信息
cp staff_auth.example.json staff_auth.json
python build_lists.py                     # 同步数据 -> out/records.json
python gen_dashboard.py                   # 生成看板
python serve.py                           # 启动服务，浏览器访问 http://127.0.0.1:8173
```
> Windows 用户可直接双击 `start.bat`（自动完成上述步骤并打开浏览器）。

### 方式 C：无数据库本地调试
```bash
python run_with_mock.py                   # 用内置 Mock 数据跑通整条流水线
```

## 🔒 隐私与合规

本项目对**消费者隐私零容忍**：

- 仓库内 `out/` 数据均经过 `desensitize_data.py` 处理：手机号 → `186****1001` 掩码；员工/接待人姓名 → `员工#NN` 匿名；街道/社区 → 清空（仅保留省/市/区用于聚合）。
- **数据库账号、密码、token 等凭证从不入库**（见 `.gitignore`），仅提供 `*.example.json` 占位。
- 脱敏是**确定性的**：同一真实值始终映射到同一脱敏值，跨文件关联不断裂，确保分析结果可复现。
- 本地连真实库时，请在 `db_conf.json`（已被 git 忽略）中填写，**不要提交到任何公开仓库**。

重新生成脱敏数据：
```bash
python desensitize_data.py out/
```

## 🛠 技术栈

Python 3.11 · pymysql · openpyxl · 原生 HTML/CSS/JS（无前端框架，零构建）· 列式编码 + gzip 传输优化。

## 📄 许可

[MIT License](LICENSE) —— 可自由用于学习、二次开发与商业项目。
