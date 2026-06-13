#!/bin/zsh
# 本机起 MinerU FastAPI 服务（前台）。launchd plist 会调它。
# 暴露在 0.0.0.0:7861，本机 / LAN / 反向 SSH 隧道都能用。
set -e
cd /Users/macmini/Documents/minerU
export MINERU_MODEL_SOURCE=modelscope
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
# 代理 DNS 污染防护：避免 Mineru 内部 httpx 调本进程被 Clash/Surge 拦
export NO_PROXY="localhost,127.0.0.1,::1"
export no_proxy="localhost,127.0.0.1,::1"
# get_vram() 没有 mps 分支，Apple Silicon 会按兜底 1GB 算 → batch_ratio=1，GPU 大量空转。
# 用官方环境变量直接声明可用显存（统一内存 32GB，留余量给系统 + mlx VLM 常驻）→ batch_ratio=8。
export MINERU_VIRTUAL_VRAM_SIZE=16
exec ./.venv/bin/mineru-api --host 0.0.0.0 --port 7861 --enable-vlm-preload true --allow-public-http-client
