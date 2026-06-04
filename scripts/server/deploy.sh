#!/usr/bin/env bash
# 一键部署：把 scripts/server/ 下的所有文件 scp 到 huoshan-server01 对应位置，
# 部署 socat 桥接 stack、生成 basic-auth 凭证、让 Traefik 自动加载路由。
#
# 前置：
#   1. *.alphaxbot.xyz DNS 已解析（用 dig +short mineru-ui.alphaxbot.xyz @8.8.8.8 验证）
#   2. Mac 端 mineru-api / gradio / reverse-tunnel 都跑着
#   3. ssh volcano 别名能登

set -euo pipefail

cd "$(dirname "$0")"
SERVER=volcano

echo "[1/5] 上传文件到服务器 /tmp..."
scp mineru-bridge-stack.yml mineru-middlewares.yml mineru.yml gen-basic-auth.sh \
    "$SERVER:/tmp/"

echo "[2/5] 放置到目标路径..."
ssh "$SERVER" 'sudo mkdir -p /opt/mineru && \
  sudo mv /tmp/mineru-bridge-stack.yml /opt/mineru/ && \
  sudo mv /tmp/gen-basic-auth.sh /opt/mineru/ && \
  sudo chmod 700 /opt/mineru/gen-basic-auth.sh && \
  sudo mv /tmp/mineru-middlewares.yml /etc/dokploy/traefik/dynamic/ && \
  sudo mv /tmp/mineru.yml /etc/dokploy/traefik/dynamic/'

echo "[3/5] 部署 socat 桥接 stack..."
ssh "$SERVER" 'sudo docker stack deploy -c /opt/mineru/mineru-bridge-stack.yml mineru'

echo "[4/5] 等桥接 service 就绪..."
ssh "$SERVER" '
  for i in 1 2 3 4 5 6 7 8 9 10; do
    state=$(sudo docker service ls --filter name=mineru_ --format "{{.Replicas}}" | tr "\n" " ")
    echo "  $state"
    if echo "$state" | grep -qE "1/1.*1/1"; then break; fi
    sleep 2
  done
'

echo "[5/5] 生成 basic-auth 凭证..."
ssh -t "$SERVER" 'sudo bash /opt/mineru/gen-basic-auth.sh'

cat <<'EOF'

==========================================================
  部署完成。等 60s 让 Let's Encrypt 签证书，然后：
    curl -I https://mineru-ui.alphaxbot.xyz   # 期望 401
    curl -I -u mineru:<密码> https://mineru-ui.alphaxbot.xyz   # 期望 200
==========================================================
EOF
