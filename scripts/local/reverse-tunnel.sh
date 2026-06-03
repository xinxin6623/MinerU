#!/bin/zsh
# 反向 SSH 隧道：把本机 7860 (Gradio) + 7861 (FastAPI) 暴露到 huoshan-server01 同名端口
# autossh 自愈，断了自动重连
set -e
exec /Users/macmini/.local/bin/autossh -M 0 -N \
  -o "ServerAliveInterval=30" \
  -o "ServerAliveCountMax=3" \
  -o "ExitOnForwardFailure=yes" \
  -R 7860:localhost:7860 \
  -R 7861:localhost:7861 \
  huoshan-server01
