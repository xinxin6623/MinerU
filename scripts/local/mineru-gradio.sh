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
# 同 mineru-api.sh：mps 显存探测缺失的兜底（gradio 若自拉 api 时也生效）
export MINERU_VIRTUAL_VRAM_SIZE=16

# 等 mineru-api 就绪（vlm-preload 需要几秒到十几秒）。最多等 180s。
# launchd 并行启动 api / gradio 时避免 gradio 早死 KeepAlive 反复重启。
echo "waiting for mineru-api on :7861 ..."
for i in $(seq 1 180); do
  if curl -sf --max-time 1 http://localhost:7861/docs >/dev/null 2>&1; then
    echo "mineru-api ready after ${i}s"
    break
  fi
  sleep 1
done

exec ./.venv/bin/mineru-gradio --server-name 0.0.0.0 --server-port 7860 --api-url http://localhost:7861
