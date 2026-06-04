#!/bin/zsh
# 反向 SSH 隧道：把本机 7860 (Gradio) + 7861 (FastAPI) 暴露到 huoshan-server01
#
# 绑定目标：服务器 docker_gwbridge 网桥 host 端 IP（172.18.0.1）
#   - docker_gwbridge 是 swarm overlay 容器的默认网关（不是 docker0）
#   - 仅对 swarm 容器可见，公网 IP / eth0 上不监听
#   - 此 IP 由 docker swarm init 时分配，dokploy 装好后固定
#   - 需要服务器 sshd 配 `GatewayPorts clientspecified`（已配于 01-harden.conf）
#
# autossh 自愈，断了自动重连
set -e
exec /Users/macmini/.local/bin/autossh -M 0 -N \
  -o "ServerAliveInterval=30" \
  -o "ServerAliveCountMax=3" \
  -o "ExitOnForwardFailure=yes" \
  -R 172.18.0.1:7860:localhost:7860 \
  -R 172.18.0.1:7861:localhost:7861 \
  huoshan-server01
