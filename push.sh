#!/bin/bash
# lowfreq-dashboard 一键推送到 GitHub (需先在 GitHub 添加 SSH 公钥)
cd "$(dirname "$0")"
echo "正在推送 main 分支到 git@github.com:Karry75/lowfreq-dashboard.git ..."
ssh-add ~/.ssh/id_ed25519_github 2>/dev/null
git push -u origin main
if [ $? -eq 0 ]; then
  echo "✅ 推送成功！仓库: https://github.com/Karry75/lowfreq-dashboard"
else
  echo "❌ 推送失败，请检查："
  echo "  1) GitHub 是否已添加本机 SSH 公钥 (ssh -T git@github.com 测试)"
  echo "  2) 仓库 Karry75/lowfreq-dashboard 是否已创建 (github.com/new, Public, 不勾 README)"
fi
