#!/bin/zsh
# 本机起 MinerU pipeline 专用 FastAPI 服务（前台），端口 7862。
#
# 为什么单独一个服务 + 单独的 .venv-pipeline：
#   mlx-vlm 把主 venv 的 transformers 顶到 5.x，而 pipeline 后端依赖 transformers 4.x
#   的 find_pruneable_heads_and_indices 等符号，在 5.x 下 ImportError 加载即崩。
#   .venv-pipeline 用 mineru[pipeline]（锁 transformers<5），与主 venv 的 mlx 路径隔离。
#
# 分工：7861(.venv,mlx)跑 vlm-auto-engine 处理图文混排；7862(本服务,pipeline)
#   处理纯文本 PDF —— pipeline 无串行锁、吃 MINERU_VIRTUAL_VRAM_SIZE 做 GPU batch、
#   可真并发，纯文本 ~6s/页（vs vlm 25-30s/页）。apdd choose_backend() 决定发哪个端口。
set -e
cd /Users/macmini/Documents/minerU
export MINERU_MODEL_SOURCE=modelscope
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
# 统一内存 32GB → batch_ratio=16，让 pipeline 的 layout/MFR/OCR 一次过更多图，吃满 GPU
export MINERU_VIRTUAL_VRAM_SIZE=32
# 代理 DNS 污染防护：避免 Mineru 内部 httpx 调本进程被 Clash/Surge 拦
export NO_PROXY="localhost,127.0.0.1,::1"
export no_proxy="localhost,127.0.0.1,::1"
# 注意：本变量在 macOS 上【不生效】。fast_api.py:223 对 macOS 无条件 max=1
#   （上游为 mlx 串行锁设的一刀切，误伤无锁的 pipeline）。pipeline 在 Mac 上实际仍
#   单并发。主要收益是单文件提速（纯文本 ~6×：52s vs vlm 320s），并发是另一回事，
#   不为它改 mineru/ 内核（守 CLAUDE.md 硬规则）。保留此行仅为语义留痕 + 非 Mac 可用。
export MINERU_API_MAX_CONCURRENT_REQUESTS=2
# pipeline 无 VLM，不需要 --enable-vlm-preload；pipeline 后端不消费 server_url，
# 无需 --allow-public-http-client。
exec ./.venv-pipeline/bin/mineru-api --host 0.0.0.0 --port 7862
