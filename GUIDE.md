# MinerU 小白指南

MinerU —— 把 PDF / 图片 / Office 文档转成 Markdown 和 JSON 的工具。

## 快速访问（已部署服务）

本机 Mac mini 已跑着两个服务，开机自启：

| 服务 | 地址 |
|---|---|
| Gradio Web UI | http://localhost:7860 |
| FastAPI / Swagger 文档 | http://localhost:7861/docs |

局域网访问：`http://192.168.1.89:7860`

> 服务由 LaunchDaemon 托管，如需重启：
> ```bash
> sudo launchctl kickstart -k system/xyz.alphaxbot.mineru-gradio
> sudo launchctl kickstart -k system/xyz.alphaxbot.mineru-api
> ```

---

## 手动启动（开发调试用）

### 环境准备

```bash
cd /Users/macmini/Documents/minerU
source .venv/bin/activate

export MINERU_MODEL_SOURCE=modelscope
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export NO_PROXY="localhost,127.0.0.1,::1"
```

### 方式一：单独起 Gradio UI（自动拉起本地 API）

```bash
./.venv/bin/mineru-gradio \
  --server-name 0.0.0.0 \
  --server-port 7860 \
  --enable-vlm-preload true
```

- Gradio 会自动在后台起一个 `mineru-api`
- `--enable-vlm-preload` 让 VLM 模型预加载，启动较慢但后续快
- 启动时 Gradia 会等 API 就绪，最多等 180 秒

### 方式二：Gradio UI + 已有 API（推荐调试用）

先确保 API 在跑（已部署的话已经在跑）：

```bash
# 停掉 gradio 避免端口冲突
pkill -f "mineru-gradio"

# 单独起 API（如果没在跑）
./.venv/bin/mineru-api --host 0.0.0.0 --port 7861 --enable-vlm-preload true --allow-public-http-client
```

再起 Gradio UI 连接到已有 API：

```bash
./.venv/bin/mineru-gradio \
  --server-name 0.0.0.0 \
  --server-port 7860 \
  --api-url http://localhost:7861
```

---

## Web UI 参数说明

| 参数 | 作用 |
|---|---|
| `--server-name` | 监听地址，`0.0.0.0` 表示局域网可访问 |
| `--server-port` | Gradio Web UI 端口 |
| `--api-url` | 指向 mineru-api 的地址，不填则自动拉起 |
| `--enable-vlm-preload` | 启动时预加载 VLM 模型（启动慢、后续快） |
| `--enable-api` | 开启 Gradio API 接口供程序调用 |
| `--max-convert-pages` | 单次任务最大转换页数 |
| `--latex-delimiters-type` | LaTeX 公式定界符风格：`a`($) / `b`($$) / `all` |

---

## API 调用（程序用）

Swagger 文档在 http://localhost:7861/docs，可直接在页面调试。

### Python 调用示例

```python
import httpx

resp = httpx.post(
    "http://localhost:7861/api/parse",
    files={"file": open("document.pdf", "rb")},
    data={"backend": "vlm-auto-engine", "language": "auto"},
    timeout=300,
)
result = resp.json()
print(result["markdown"])
```

### 可用后端

| 后端 | 说明 |
|---|---|
| `pipeline` | 纯 CV 流水线（PaddleOCR + 公式/表格/Layout 模型），最稳，M4 ~10 页/分钟 |
| `vlm-auto-engine` | 纯 VLM（mlx-engine，M4 GPU/ANE），推荐，速度快 |
| `hybrid-auto-engine` | VLM + pipeline layout，**当前不稳定**，transformers 5 兼容问题 |

---

## 本地示例文件

```bash
# 看有哪些示例
ls demo/

# 跑示例脚本
python demo/demo.py
```

---

## 常见问题

**Q: 提交任务后报 "公开的 API 默认禁用"**
A: API 启动时需加 `--allow-public-http-client` 参数。本机已加，无需手动处理。

**Q: hybrid-auto-engine 报错 `PPDocLayoutV2Config has no attribute reading_order_config`**
A: transformers 5 和 pipeline layout 配置不兼容。用 `vlm-auto-engine` 或 `pipeline` 后端即可。

**Q: 局域网访问报 "Connection reset by peer"**
A: 系统防火墙未放行 venv python。按 AGENTS.md 说明操作：
```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /Users/macmini/Documents/minerU/.venv/bin/python3
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp /Users/macmini/Documents/minerU/.venv/bin/python3
```