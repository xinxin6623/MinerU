#!/usr/bin/env bash
# 卸载三个 LaunchDaemon：bootout + 删 plist。
# 卸载后 Mac 重启不会再自动跑 mineru，三个服务也立刻停。
#
# 用法：sudo bash scripts/local/launchd/uninstall.sh

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "需要 sudo 跑" >&2
  exit 1
fi

DAEMONS=(
  xyz.alphaxbot.mineru-api
  xyz.alphaxbot.mineru-gradio
  xyz.alphaxbot.mineru-tunnel
)

for d in "${DAEMONS[@]}"; do
  PLIST="/Library/LaunchDaemons/$d.plist"
  if [ -f "$PLIST" ]; then
    launchctl bootout system "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "removed $d"
  else
    echo "skip $d (not installed)"
  fi
done

echo "卸载完成。日志文件 /var/log/mineru-*.log 保留，如需清理手动 rm。"
