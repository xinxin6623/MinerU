#!/usr/bin/env bash
# 把三个 plist 安装到 /Library/LaunchDaemons/ 并 bootstrap。
# 安装后系统重启即自动启动 mineru-api / mineru-gradio / 反向隧道。
#
# 用法：
#   sudo bash scripts/local/launchd/install.sh
#
# 安装前会停掉当前手动 nohup 跑的进程（避免端口冲突）。
# 卸载：sudo bash scripts/local/launchd/uninstall.sh

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "需要 sudo 跑（plist 装到系统 LaunchDaemons）" >&2
  exit 1
fi

cd "$(dirname "$0")"
DAEMONS=(
  xyz.alphaxbot.mineru-api
  xyz.alphaxbot.mineru-gradio
  xyz.alphaxbot.mineru-tunnel
)

echo "[1/4] 停掉当前手动跑的进程（避免端口冲突）..."
pkill -f "mineru-api --host" 2>/dev/null || true
pkill -f "mineru-gradio --server-name" 2>/dev/null || true
pkill -f "autossh.*huoshan-server01" 2>/dev/null || true
sleep 2

echo "[2/4] 复制 plist 到 /Library/LaunchDaemons/ 并设权限..."
for d in "${DAEMONS[@]}"; do
  install -o root -g wheel -m 644 "$d.plist" "/Library/LaunchDaemons/$d.plist"
  echo "  installed $d.plist"
done

echo "[3/4] 创建日志文件并赋权 macmini..."
touch /var/log/mineru-api.{out,err}.log /var/log/mineru-gradio.{out,err}.log /var/log/mineru-tunnel.{out,err}.log
chown macmini:staff /var/log/mineru-*.log

echo "[4/4] launchctl bootstrap..."
for d in "${DAEMONS[@]}"; do
  # 若已 loaded 先 bootout 再 bootstrap（幂等）
  launchctl bootout system "/Library/LaunchDaemons/$d.plist" 2>/dev/null || true
  launchctl bootstrap system "/Library/LaunchDaemons/$d.plist"
  echo "  bootstrapped $d"
done

echo
echo "=========================================="
echo "  完成。看状态："
echo "    launchctl print system/xyz.alphaxbot.mineru-api  | head -20"
echo "    tail -f /var/log/mineru-api.err.log"
echo "  端口检查："
echo "    lsof -iTCP:7860 -sTCP:LISTEN"
echo "    lsof -iTCP:7861 -sTCP:LISTEN"
echo "  反向隧道："
echo "    ssh volcano 'ss -tlnp | grep -E \":(7860|7861)\\s\"'"
echo "=========================================="
