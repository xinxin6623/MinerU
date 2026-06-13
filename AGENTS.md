# minerU · Agent 操作守则

> **上来先读这份，再看 [`INDEX.md`](./INDEX.md) 找模块和导航。**

## 这是什么项目

MinerU——实用的文档解析工具：把 PDF / 图片 / DOCX / PPTX / XLSX 转成 Markdown 和 JSON。本目录是上游开源仓库 clone，主代码在 `mineru/` 包内。

## 上手三步

1. 读 [`INDEX.md`](./INDEX.md)，看项目结构和子模块导航。
2. 找到目标模块目录，**先读它的本地文档**（如 `<module>/README.md` 或 `<module>/AGENTS.md` 若存在）。
3. 看根目录或模块里有没有脚本入口、配置文件、环境变量样例（本项目根目录有 `pyproject.toml` / `mineru.template.json` / `mkdocs.yml`）。

## 改动前的硬规则

- **不要随手改 `.env` / 凭证 / `settings.json`**：敏感配置由项目所有者维护。
- **不要主动删除文件**：废弃 / 旧版本 / 半成品请移动到 `archive/` 或 `不加载/` 这类约定目录，不要 `rm`。
- **不要重命名公共接口、路由、对外 API 字段**：除非明确授权，这些是契约。
- **改动前确认是否有依赖你正在改的代码的其他模块**：先 `grep` 引用再下手。
- **本仓库按"本地 fork"对待（2026-06-13 起，项目所有者指令，替代旧的"不改内核"规则）**：`mineru/` 内核**可以直接改**。优先级：本机跑通 > 发挥 M4 硬件性能 > 与上游兼容。不考虑发 PR 回上游、不为上游同步留余地（将来若要同步，rebase 时再处理冲突）。内核改动必须经 git commit 留痕（推自己的仓库），不要留无版本管理的散改。

## 本机运行约定（M4 / macOS / 国内网络）

- **Python 环境**：用 uv venv（Python 3.12），位于本仓库根的 `.venv/`。激活 `source .venv/bin/activate`，或直接调 `.venv/bin/mineru`。
- **必须的三个环境变量**（pipeline / hybrid 后端都要）：
  ```bash
  export MINERU_MODEL_SOURCE=modelscope
  export HF_HUB_OFFLINE=1
  export TRANSFORMERS_OFFLINE=1
  ```
  原因：mineru 的 pipeline 后端在 `model_init` 里用 `transformers` 加载公式识别模型（unimernet），即使权重已经从 modelscope 下完，transformers / huggingface_hub 仍会去 `huggingface.co` HEAD 验证缓存——国内 SSL 直连会 `[SSL: UNEXPECTED_EOF_WHILE_READING]` 失败，整个 task 报 "Server disconnected"。两个 OFFLINE 标志阻止任何外联，`MODEL_SOURCE` 让 mineru 内部从 modelscope 拿。
- **配置文件路径**：`~/mineru.json`（不是仓库内的 `mineru.template.json`）。首次运行 `mineru-models-download` 时自动生成。
- **模型缓存路径**：`~/.cache/modelscope/hub/models/OpenDataLab/PDF-Extract-Kit-1.0/`（pipeline 后端用的 ~7 GB 权重）。
- **后端选择**：默认的 `hybrid-auto-engine` 需 VLM 权重，未下载前会失败。`-b pipeline` 是最稳的回退路径，纯 CV 流水线（layout + MFR + table + OCR），M4 上 ~10 页/分钟。
- **LibreOffice**：未安装。仅处理 PDF/图片不需要；处理 `.docx/.pptx/.xlsx` 才装（`brew install --cask libreoffice`）。

### 后端选择矩阵（本机实测，2026-06）

| 后端 | 引擎 | 速度 | 现状 |
|---|---|---|---|
| `vlm-auto-engine` | **mlx-engine**（M4 GPU/ANE，纯 VLM） | ~6.5 秒/页 | ✅ **唯一可用，主后端**。MinerU2.5-Pro-1.2B |
| `pipeline` | PaddleOCR + 公式/表/Layout 模型 | — | ❌ transformers 5 下两处断（MFR import + layout v2），**已放弃修复** |
| `hybrid-auto-engine` | mlx VLM + pipeline layout | — | ❌ 同上，layout v2 断，**已放弃修复** |

### transformers 5 兼容陷阱（重要，2026-06-13 更新：pipeline/hybrid 判死刑）

**症状**：① hybrid / pipeline 报 `'PPDocLayoutV2Config' object has no attribute 'reading_order_config'`（layout v2 配置类在 transformers 5 下 sub_configs 初始化顺序不兼容）；② pipeline 公式模型 unimernet 报 `ImportError: cannot import name 'find_pruneable_heads_and_indices'`（transformers 5 移除了该函数，服务日志有实锤 traceback）。

**根因**：`pyproject.toml` 原本锁 `transformers>=4.57.3,<5.0.0`，但 `mlx-vlm>=0.3.3` 强制要 `transformers>=5`，装 `[mlx]` extra 时 uv 自动把 transformers 升到 5.9。pipeline 的 MFR 和 layout v2 都用 transformers 4 的 API。注意 pipeline 的 layout 也走 `pp_doclayout_v2`（`model_init.py`），不存在"pipeline 用旧版 layout 所以没事"——早期"pipeline 实测可用"的记录是 transformers 4 时代的，已失效。

**决策（2026-06-13，项目所有者拍板）**：**放弃修复 pipeline / hybrid**（含 reading_order_config 路径）。主后端 = `vlm-auto-engine`（mlx，不碰任何断点代码，质量和速度都不差于 pipeline）。不降级 transformers（mlx-vlm 装不上）、不找旧 mlx-vlm（不支持 MinerU2.5 模型）、不另建 transformers<5 的 venv（维护成本不值）。

### get_vram() 不认 MPS → batch_ratio 永远是 1（重要，2026-06-13 发现）

**症状**：pipeline / hybrid 后端在 Apple Silicon 上"感觉不走 GPU"，速度上不去，活动监视器里 CPU 忙 GPU 闲。日志里可见 `GPU Memory: 1 GB, Batch Ratio: 1`。

**根因**：`mineru/utils/model_utils.py::get_vram()` 写了 cuda/npu/gcu/musa/mlu/sdaa 六种设备分支，**唯独漏了 mps**，探测不到落兜底 1GB。32GB 的 M4 被当 1GB 机器，`pipeline_analyze.py` / `hybrid_analyze.py` 里 batch_ratio 落到最小档 1（MFR 批量 16、OCR det 批量 8，本应是 128 / 64）。次因：MPS 不支持的算子静默回落 CPU，所以 CPU 显得忙。

**修复（2026-06-13，内核直改）**：`mineru/utils/model_utils.py::get_vram()` 已加 mps 分支，用 `torch.mps.recommended_max_memory()`（Metal 驱动报告的工作集上限，约 75% RAM，32GB M4 ≈ 21-24GB → batch_ratio=8）。`MINERU_VIRTUAL_VRAM_SIZE` 环境变量仍是第一优先级，可显式覆盖（`scripts/local/mineru-api.sh` / `mineru-gradio.sh` 里固化了 16，效果同自动探测档位）。注：batch_ratio 只影响 pipeline/hybrid，这两个后端已放弃，此修复属于"顺手修对 + 防将来"。

### Mac 上 API 并发数可调（2026-06-13，内核直改）

`mineru/cli/fast_api.py` 原本在 Mac 上硬编码并发=1。已改为默认仍 1、但尊重 `MINERU_API_MAX_CONCURRENT_REQUESTS` 环境变量。mlx predictor 自带串行执行锁（`vlm_analyze.py::_maybe_enable_serial_execution`），GPU 推理永远单路；调高并发的收益是多请求的 CPU 段（PDF 渲染 / 后处理）与 GPU 推理重叠，多文档吞吐场景可试 2-3，单文档无收益。代价是峰值内存增加，调高前看内存余量。

### 引擎自动选择逻辑

`mineru/utils/engine_utils.py::_select_mac_engine()`：
- 能 `from mlx_vlm import load` + macOS 13.5+ Apple Silicon → 返回 `'mlx'`
- 否则 → fallback `'transformers'`（torch + MPS，慢 3 倍）

确认走的是 mlx：日志里看 `Using mlx-engine as the inference engine for VLM.`。CPU 占用低（<5%）+ RSS 暴涨到 3 GB+ 也是 mlx 在跑的特征（模型常驻统一内存）。

## 本机算力服务部署（2026-06-04 起）

Mac mini 作为**算力机**对外暴露 MinerU 服务，本机 / 局域网 MacBook / 火山云服务器（经反向 SSH 隧道）三方共享，**服务器零计算开销**。该套配置从已弃用的 docling-serve 部署移植过来。

### 端口分配（固定，不要动态）

| 端口 | 服务 | 绑定 |
|---|---|---|
| `7860` | mineru-gradio（Web UI） | `0.0.0.0` |
| `7861` | mineru-api（FastAPI / Swagger 在 `/docs`） | `0.0.0.0` |

Gradio 启动时用 `--api-url http://localhost:7861` 复用已起的 mineru-api，**不要让 gradio 再自己拉起一个** —— 否则会有两个 mineru-api 实例占内存。

### 三段访问入口

```
本机   http://localhost:7860 / :7861
局域网 http://192.168.1.89:7860 / :7861
服务器 http://localhost:7860 / :7861（经反向 SSH 隧道至 huoshan-server01）
```

### 启动脚本（位于 `scripts/local/`）

| 脚本 | 作用 |
|---|---|
| `mineru-api.sh` | 起 FastAPI 服务（依赖 mlx VLM 预热） |
| `mineru-gradio.sh` | 起 Gradio UI，连本机 7861 |
| `reverse-tunnel.sh` | autossh `-R 7860 -R 7861` → `huoshan-server01` |

三个脚本里都固化了：
- `MINERU_MODEL_SOURCE=modelscope` + `HF_HUB_OFFLINE=1` + `TRANSFORMERS_OFFLINE=1`（防 SSL EOF）
- `NO_PROXY=localhost,127.0.0.1,::1`（防本机 Clash/Surge 代理拦截 httpx 调本进程→503 空响应）
- `mineru-api.sh` 额外带 `--allow-public-http-client`（见下方"gradio server_url 默认值踩坑"）

### gradio server_url 默认值踩坑（重要）

**症状**：api 绑 `0.0.0.0` + gradio 任意选 `vlm-auto-engine` / `pipeline` 提交任务 → `400 公开的 API 默认禁用 *-http-client 后端和 server_url。请重新绑定到 127.0.0.1，或者如果您了解 SSRF 风险，请使用 --allow-public-http-client 参数启动。`

**根因**：`mineru/cli/gradio_app.py:1789` 把 `server_url` Textbox 的初始值固化为 `http://localhost:30000`，并在 `gradio_app.py:995` 不论用户选哪个后端都把 `server_url=url` 塞进 form_data。api 的 SSRF 守卫（`mineru/cli/public_http_client_policy.py:34-37`）见到非空 `server_url` 就拒。属于上游 gradio_app 的小毛病——server_url 应只在 http-client 后端激活时才传。

**绕开**：`mineru-api.sh` 启动时加 `--allow-public-http-client` 放行。本套部署是 LAN + 反向 SSH 隧道到 `huoshan-server01`（可控），不是真"公开"，SSRF 风险可接受。

**别尝试的修复**：① 把 api 改回绑 127.0.0.1 → LAN / 反向隧道都用不了；② 改 gradio_app.py → 动 `mineru/` 内核，违反"不直接改上游"硬规则，等官方修。

### macOS App Firewall 放行（一次性）

本机系统防火墙启用时，**必须放行 mineru venv 的 python**，否则 LAN 访问报 "Connection reset by peer"（本机 loopback 不受影响）：

```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /Users/macmini/Documents/minerU/.venv/bin/python3
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp /Users/macmini/Documents/minerU/.venv/bin/python3
```

> 注意：放行清单按**二进制绝对路径**记，重建 venv 或迁移仓库目录后需要重做。

### 持久化（LaunchDaemon + TCC 必备，2026-06-04 起）

三个服务现在由 **system-level LaunchDaemon** 拉起（开机自动跑、不依赖用户登录、崩了自愈）。plist 在 `scripts/local/launchd/`，安装/卸载脚本同目录。

| Label | plist | 日志（root 写、macmini 可读） |
|---|---|---|
| `xyz.alphaxbot.mineru-api` | `xyz.alphaxbot.mineru-api.plist` | `/var/log/mineru-api.{out,err}.log` |
| `xyz.alphaxbot.mineru-gradio` | `xyz.alphaxbot.mineru-gradio.plist` | `/var/log/mineru-gradio.{out,err}.log` |
| `xyz.alphaxbot.mineru-tunnel` | `xyz.alphaxbot.mineru-tunnel.plist` | `/var/log/mineru-tunnel.{out,err}.log` |

**安装**：`sudo bash scripts/local/launchd/install.sh`（脚本会杀当前 nohup → cp plist → 创建日志文件 → bootstrap）
**卸载**：`sudo bash scripts/local/launchd/uninstall.sh`
**手动重启某个**：`sudo launchctl kickstart -k system/xyz.alphaxbot.mineru-api`（也可用 osascript with admin privileges 触发 GUI 密码框，避免终端 sudo）

#### TCC 完全磁盘访问（FDA）必加（**严重坑**）

LaunchDaemon 由系统 launchd（root）启动，子进程**没有用户登录会话的 TCC 上下文**，访问 `~/Documents/`、`~/Desktop/`、`~/Downloads/` 等受保护目录会被 **deny**（POSIX 报 `Operation not permitted` 或 `can't open input file`），即使 plist 已 `UserName=macmini`。

必须给 **两个二进制**手动加完全磁盘访问（系统设置 → 隐私与安全性 → 完全磁盘访问 → 点 `+` → `Cmd+Shift+G` 输路径）：

| 二进制 | 为什么要加 |
|---|---|
| `/bin/zsh` | plist shebang 是 zsh，它要 open() `~/Documents/minerU/scripts/local/*.sh` |
| `/Users/macmini/.local/bin/python3.12` | venv python，启动时要 read `~/Documents/minerU/.venv/pyvenv.cfg` |

**FDA 不会向子进程继承**——zsh 有 FDA 不代表它启动的 python 也有。必须各自分别授权。

**重建 venv 后必须重新加 FDA**：用 `uv` 重装 python，路径还是 `/Users/macmini/.local/bin/python3.12`，但二进制 inode 变了，TCC 看作"另一个二进制"，FDA 失效。届时日志会再报 `PermissionError`，按上面再加一次。

#### 应急回退（LaunchDaemon 出问题时手动起）

如果 launchd 全死、TCC 错乱、想纯手工跑：

```bash
cd /Users/macmini/Documents/minerU
nohup bash scripts/local/mineru-api.sh    > /tmp/mineru-api.log 2>&1 & disown
nohup bash scripts/local/mineru-gradio.sh > /tmp/mineru-gradio.log 2>&1 & disown
nohup bash scripts/local/reverse-tunnel.sh > /tmp/mineru-tunnel.log 2>&1 & disown
```

公网入口几十秒后回来。关 shell 就丢，仅作应急用，**不要常驻**。

### 公网入口（服务器 Traefik + basic-auth，2026-06-04 起）

把 Mac mini 的 7860/7861 通过 huoshan-server01 的 Traefik 暴露到公网域名上，加 basic-auth。Mac 不直连公网，所有外部流量必经 Traefik。

**架构链路**：

```
浏览器 → https://mineru-{ui,api}.alphaxbot.xyz
       → 火山云 Traefik (TLS 终结 + ratelimit + basic-auth)
       → dokploy-network overlay → mineru_bridge-{ui,api}  (socat 容器)
       → 172.18.0.1:7860/7861  (docker_gwbridge host 端)
       → 反向 SSH 隧道  (autossh，autossh PID 在 Mac /tmp/mineru-tunnel.log)
       → Mac mini localhost:7860/7861  (mineru-gradio / mineru-api)
```

**关键端点**：

| 公网 URL | 后端 | basic-auth |
|---|---|---|
| `https://mineru-ui.alphaxbot.xyz` | Gradio 7860 | mineru / 仅本地密码管理器 |
| `https://mineru-api.alphaxbot.xyz/docs` | FastAPI 7861 | 同上 |

**部署文件**（仓库内是模板，服务器上是落地副本）：

| 仓库路径 | 服务器路径 | 用途 |
|---|---|---|
| `scripts/server/mineru-bridge-stack.yml` | `/opt/mineru/` | socat swarm stack（dokploy-network overlay） |
| `scripts/server/mineru-middlewares.yml` | `/etc/dokploy/traefik/dynamic/` | basic-auth + rate-limit（含哈希，权限 600） |
| `scripts/server/mineru.yml` | `/etc/dokploy/traefik/dynamic/` | 两个子域路由 + LE 证书 |
| `scripts/server/gen-basic-auth.sh` | `/opt/mineru/` | 生成强密码 + bcrypt + 写 middlewares |
| `scripts/server/deploy.sh` | — | 一键 scp + stack deploy + 生成 auth |

**凭证铁律**：basic-auth 密码**只在 gen-basic-auth.sh 输出时显示一次**，立刻进密码管理器。`mineru-middlewares.yml` 服务器副本里是 bcrypt 哈希（不可逆），但仓库内是占位符版本，不含真实密码——**永远不要把服务器上那份 commit 进仓库**。重跑 gen-basic-auth.sh 会覆盖哈希，旧密码立即失效。

**basic-auth 升级触发条件**（满足任一即升 Authelia / IP 白名单）：
- 用户数 > 3（共享密码已不合理）
- access log 出现明显字典扫描
- 需要给"非完全信任的人"用（外部协作者、客户 demo）

#### 踩坑（部署时撞了不止一次）

1. **swarm overlay 容器的 host-gateway ≠ docker0**：socat 容器跑在 dokploy-network overlay 上，默认路由走 `docker_gwbridge`（172.18.0.1），不是 `docker0`（172.17.0.1）。Docker `extra_hosts: host-gateway` 别名在 swarm 模式下会错误地解析为 docker0 IP，导致 socat → host 不通。**修复**：mineru-bridge-stack.yml 里 hardcode `TCP:172.18.0.1:7860`，不依赖 host-gateway 别名。

2. **反向 SSH 隧道默认绑 host 127.0.0.1**：Docker 容器从 docker_gwbridge 视角看不到 host loopback。**修复**：服务器 sshd `01-harden.conf` 加 `GatewayPorts clientspecified`（reload 不杀会话），Mac 端 `reverse-tunnel.sh` 改 `-R 172.18.0.1:7860:localhost:7860`。绑 172.18.0.1 仅对 swarm 容器可见，不暴露公网 eth0。

3. **ufw 默认 INPUT DROP 把 docker_gwbridge 入站拦了**：socat 容器到 172.18.0.1:7860 timeout。**修复**：`sudo ufw allow in on docker_gwbridge to any port 7860 proto tcp`（只对这块网卡放行，公网不放）。已加规则 #7 #8 #15 #16。

4. **DNS 加 `*` 通配符记录时，主机记录字段只填一个英文星号**——不要填 `*.alphaxbot.xyz`、不要带空格、不要带点。火山引擎 DNS 控制台填错会"看似保存"但实际 NS 收不到。验证用 `dig +short mineru-ui.alphaxbot.xyz @vip1.volcengine-dns.com`（直接问火山权威 NS）。

#### 故障排查命令

```bash
# Mac 端
pgrep -fla "autossh.*172.18.0.1"                           # 反向隧道在不在
lsof -iTCP:7860 -sTCP:LISTEN                               # gradio 在不在
tail -f /tmp/mineru-tunnel.log                              # 隧道日志

# 服务器侧
ssh volcano 'ss -tlnp | grep -E ":(7860|7861)\s"'          # 隧道有没有绑上 172.18.0.1
ssh volcano 'sudo docker service ls --filter name=mineru_' # socat 桥接服务存活
ssh volcano 'sudo docker exec dokploy-traefik wget -qS --timeout=5 http://mineru_bridge-ui:7860/ -O /dev/null 2>&1 | head -3'  # Traefik→桥接通

# 外部验证
curl -I https://mineru-ui.alphaxbot.xyz                                     # 期望 401
curl -I -u mineru:<密码> https://mineru-ui.alphaxbot.xyz                    # 期望 200
```

### 替代 docling-serve 的历史背景

之前 docling-serve 部署在 `~/Documents/docling/`（已删），那套撞坑：① Apple Silicon MPS float64 不兼容，强制 CPU 后慢；② docling-core SSRF 防护下 URL 模式被代理 DNS 污染拦死；③ docling-serve 自身吃 1.9GB，加模型 4GB。**MinerU 用 mlx-engine 直跑 GPU（Apple Silicon ANE），同等任务速度数量级提升**，所以替换。具体决策细节见 `~/baidu/Archives/2026-06-02-docling-mac-local-serve-deploy.md`。

## 文档维护节奏（三份文档的分工与更新时机）

三份文档**不是平权的**。它们的更新频率和触发条件不一样，按错节奏会污染 signal：

- **AGENTS.md（活文档）**：**随时更新**。工作中发现新的项目惯例、踩坑、约束、决策，立刻加进来。这是"项目实时手册"——agent 的护栏会越来越厚，下一个 agent 来就少踩一次坑。边干边写，不要等收尾，否则会忘。
- **INDEX.md（结构快照）**：**阶段性更新**。只在顶层目录 / 子模块结构变化（新增 / 重命名 / 删除 / 归档）时同步。不要每改一个文件就动。
- **CHANGELOG.md（演绎记录）**：**阶段性更新**。每个任务 / 功能 / 修复**告一段落时**追加一条，不是每个 edit 一条。按文件顶部强标签格式写。**只记摘要 + Why + 详细记录指针**，不贴 diff。

### Agent 必须主动提醒用户同步 INDEX/CHANGELOG 的节点

- **任务阶段性收尾**：一个功能 / 修复 / 重构告一段落、即将切到下一个话题前
- **上下文长度即将触发压缩**：感觉对话已经很长、再几轮可能被压缩，趁记忆还在赶紧落
- **用户明确说**"沉淀一下""做个 checkpoint""收尾"

提醒话术示例：
> 这一段告一段落了。要不要现在把 INDEX/CHANGELOG 同步一下？这一阶段的改动清单：...

**为什么强调"主动提醒"**：用户干活时不会自己想起"该更 INDEX 了"，等切下个话题或下轮对话就忘了。Agent 当观察员，在节点上抬手提示，是这套文档体系能维持下去的关键。

### 详细改版记录的位置

根目录 `CHANGELOG.md` 只是**索引**，详细改版记录写在该模块自己目录下（如 `<module>/CHANGELOG.md` 或 commit message 里），根 CHANGELOG 用"详见 `<path>`"指过去。

## 子项目嵌套（如本项目下存在子项目）

**判定**：子目录里若也有 `AGENTS.md + INDEX.md + CHANGELOG.md` 三件套，它就是一个**子项目**（通常由 `/project-init` 在该子目录下跑出来）。本仓库的 `projects/` 目前是周边子项目集合（暂未都自带三件套），未来若某个子项目自带三件套即适用本节规则。

**更新边界**：

| 操作类型 | 子项目三件套 | 父项目 INDEX | 父项目 CHANGELOG |
|---|---|---|---|
| 单一子项目内的开发 / 改动 | ✅ 按节奏更新 | ❌ 不动 | ❌ **绝不记录** |
| 子项目结构变化（新增 / 重命名 / 归档） | ✅ | ✅ 摘要行 | ❌ 不记录 |
| 横跨多个子项目的同时操作 | ✅ 各记一条 | 视情况 | ✅ 多 `scope:` 一条 |

- **父项目 INDEX.md** → 给每个子项目一行**摘要**（名称 + 一句话定位），不展开
- **父项目 CHANGELOG.md** → **不记录任何单一子项目操作**，只记录**横跨多个子项目的同时操作**
- **父项目 AGENTS.md** → 父级通用守则；子项目特有约束写进**子项目自己的 AGENTS**

**为什么这么切**：父 CHANGELOG 若收所有子项目流水会被噪音淹没失去检索价值。让子项目自己的 CHANGELOG 承担细粒度记录，父级 CHANGELOG 自然成为"项目级里程碑视图"。

## 目录命名约定

子目录推荐用这些通用名（按项目实际需要选用）：

| 子目录 | 用途 |
|---|---|
| `scripts/` | 可执行脚本 |
| `src/` 或 `lib/` | 主代码（本项目用 `mineru/` 作为 Python 包名） |
| `tests/` | 测试 |
| `docs/` | 详细文档 |
| `assets/` | 静态素材 |
| `templates/` | 模板文件 |
| `archive/` 或 `不加载/` | 归档区，不参与构建 |

## 语言规则

- 解释性内容、架构决策、注意事项 → **中文**
- 代码、变量名、函数名、目录名 → 英文
- 与项目所有者对话 → **中文**（除非对方用英文）

## 不要做的事

- ❌ 删除文件（应该 `mv` 到归档目录）
- ❌ 把 INDEX / CHANGELOG 当 AGENTS 用（每轮都改），或把 AGENTS 当 CHANGELOG 用（攒着到收尾才写）——三份文档节奏不同，见上方"文档维护节奏"
- ❌ 阶段性收尾或上下文快压缩时**不**主动提醒用户同步 INDEX/CHANGELOG
- ❌ 在 `CHANGELOG.md` 里贴大段 diff / 长解释（只记一句话，详情进各自模块）
- ❌ **单一子项目操作时往父项目 CHANGELOG 写条目**（父 CHANGELOG 只接收跨多个子项目的同时操作）
- ❌ 自动提交 secrets / 凭证
- ❌ 替用户做 `git push --force` / 任何不可逆操作（必须先问）
