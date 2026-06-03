#!/bin/zsh
# 本机起 MinerU Gradio Web UI（前台）。launchd plist 会调它。
# 暴露在 0.0.0.0:7860。
# 注意：本脚本会让 gradio **自己拉起一个本地 mineru-api**（如果未指定 --api-url）；
# 如果想让 gradio 复用 mineru-api.sh 起的那个，把 --api-url 改成 http://localhost:7861
set -e
cd /Users/macmini/Documents/minerU
export MINERU_MODEL_SOURCE=modelscope
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export NO_PROXY="localhost,127.0.0.1,::1"
export no_proxy="localhost,127.0.0.1,::1"
exec ./.venv/bin/mineru-gradio --server-name 0.0.0.0 --server-port 7860 --api-url http://localhost:7861
