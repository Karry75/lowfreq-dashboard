#!/usr/bin/env bash
# v10.28.52 macOS / Linux 启动脚本（等价于 start.bat）
set -e
cd "$(dirname "$0")"

# 探测 python
PY=""
for cand in python3.11 python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "[ERROR] 未找到 python3，请先安装 Python 3.10+"
  exit 1
fi
echo "[start.sh] 使用 Python: $($PY --version)"

# 探测依赖
$PY -c "import pymysql" 2>/dev/null || {
  echo "[start.sh] 缺少 pymysql，尝试自动安装…"
  $PY -m pip install --user pymysql openpyxl requests || true
}

# 优先尝试 start.py（无头自动），fallback 到 run_serve.bat 等价 shell
if [ -f "start.py" ]; then
  echo "[start.sh] 启动 start.py…"
  exec $PY start.py
else
  echo "[start.sh] 启动 serve.py…"
  exec $PY serve.py
fi
