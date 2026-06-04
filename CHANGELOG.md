# minerU · CHANGELOG

> 每次动了什么记一条。详细记录写在各自模块目录下，根目录 CHANGELOG 是**强标签化的检索索引**。
>
> **如本项目下有子项目**（子目录里也有 AGENTS/INDEX/CHANGELOG 三件套）：本 CHANGELOG **只记录跨多个子项目的同时操作**；单一子项目操作记在该子项目自己的 CHANGELOG 里。详见 AGENTS.md "子项目嵌套" 段。

## 格式规范（严格）

```
## YYYY-MM-DD #<type> scope:<name> [#<extra-tag>...] - <一句话主题>

- Why: <一句话动机，不复述 what>
- 详见: <path 或 commit hash>
```

**硬约束**：
- 日期必须 ISO 格式 `YYYY-MM-DD`
- 类型标签必须以 `#` 开头，从下面字典选一个为主标签
- 作用域必须 `scope:<name>` 形式，name 用 kebab-case；多模块改动用多个 `scope:`
- Why 一行不超过 80 字符
- **不贴 diff、不复述 what**——那些进 commit 或模块自己的文档

## 类型标签字典

| 标签 | 含义 |
|---|---|
| `#feat` | 新功能 |
| `#fix` | bug 修复 |
| `#refactor` | 重构（无行为变化） |
| `#perf` | 性能优化 |
| `#docs` | 文档变更 |
| `#test` | 测试相关 |
| `#chore` | 构建/依赖/工具链/初始化 |
| `#archive` | 归档/弃用 |
| `#breaking` | 破坏性变更（叠加） |
| `#deprecated` | 标记弃用（叠加） |
| `#wip` | 进行中（叠加） |

## 检索示例

```bash
grep -E "^## .* #feat .* scope:auth" CHANGELOG.md   # auth 模块新功能
grep "#breaking" CHANGELOG.md                        # 所有破坏性变更
grep "^## 2026-05" CHANGELOG.md                      # 2026 年 5 月所有动作
```

---

## 2026-06-04 #feat scope:deploy - LaunchDaemon 持久化（Mac 重启自启 + 崩溃自愈）

- Why: 三服务原本 nohup 跑、关 shell 即丢；改 LaunchDaemon 后 Mac mini 无人值守也撑得住；过程中踩了 TCC 拦 ~/Documents/ 的坑，沉淀到 AGENTS
- 详见: AGENTS.md "持久化（LaunchDaemon + TCC 必备）"段 + scripts/local/launchd/{*.plist,install.sh,uninstall.sh}

## 2026-06-04 #feat scope:deploy scope:server - 公网入口 Traefik + basic-auth（mineru-ui/api.alphaxbot.xyz）

- Why: 把 Mac mini 算力通过 huoshan-server01 反向代理到公网域名，强密码 + HTTPS + ratelimit 拦自动扫描；服务器零算力开销
- 详见: AGENTS.md "公网入口（服务器 Traefik + basic-auth）"段 + scripts/server/{mineru-bridge-stack.yml,mineru.yml,mineru-middlewares.yml,gen-basic-auth.sh,deploy.sh}

## 2026-06-04 #fix scope:deploy - mineru-api 加 `--allow-public-http-client` 绕过 SSRF 守卫

- Why: gradio 不论选哪个后端都把 `server_url` 默认值塞进 form_data，api 绑 0.0.0.0 时被 SSRF 守卫拒 400；LAN+反向隧道部署可控，放行可接受
- 详见: AGENTS.md "gradio server_url 默认值踩坑" + scripts/local/mineru-api.sh

## 2026-06-04 #feat scope:deploy - 本机算力服务三段部署（替代 docling-serve）

- Why: 用户需要 Mac mini 当算力机，本机/LAN/火山云服务器三方调用；docling-serve 因 MPS float64 不兼容 + 代理 DNS 污染 SSRF 拦截不可用，MinerU 走 mlx 直跑 GPU 更顺
- 详见: AGENTS.md "本机算力服务部署"段 + scripts/local/{mineru-api,mineru-gradio,reverse-tunnel}.sh + ~/baidu/Archives/2026-06-02-docling-mac-local-serve-deploy.md

## 2026-06-01 #chore scope:bootstrap - 本机环境跑通 pipeline 后端 + demo 全样本

- Why: 验证 M4/macOS/国内网络下从零到能解析 PDF 的最短路径，并把踩坑沉淀进 AGENTS
- 详见: AGENTS.md "本机运行约定"段；产物 /tmp/mineru-out/{demo1,demo2,demo3,small_ocr}/auto/

## 2026-06-01 #chore scope:init - 项目初始化

- Why: 新项目需要 agent 入口、人类导航、演绎记录三件套，便于 agent 协作和未来 LLM 检索
- 详见: AGENTS.md / INDEX.md / 本文件

<!-- 新条目加在这里上方，保持最新在最上 -->
