#!/usr/bin/env bash
# 在服务器上跑：生成 24 位强密码 → bcrypt 哈希 → 写入 mineru-middlewares.yml
# 部署位置：/opt/mineru/gen-basic-auth.sh
# 运行：sudo bash /opt/mineru/gen-basic-auth.sh
#
# ⚠️ 密码只在终端显示一次，立刻存进密码管理器。脚本不写日志、不留明文。
# 重跑会覆盖旧哈希，旧密码立即失效。

set -euo pipefail

USER="${MINERU_BASIC_AUTH_USER:-mineru}"
MW_FILE="/etc/dokploy/traefik/dynamic/mineru-middlewares.yml"

# 1. 确保 htpasswd 可用
if ! command -v htpasswd >/dev/null 2>&1; then
  echo "[*] installing apache2-utils for htpasswd..."
  sudo apt-get update -qq
  sudo apt-get install -y apache2-utils >/dev/null
fi

# 2. 生成 24 位 URL-safe 密码（去掉容易混淆的 = + /）
PASSWORD=$(openssl rand -base64 32 | tr -d '=+/' | head -c 24)

# 3. bcrypt 哈希
HASH=$(htpasswd -nbB "$USER" "$PASSWORD")

# 4. 写入 dynamic 文件（覆盖整个文件，含 ratelimit 配置一起）
sudo tee "$MW_FILE" >/dev/null <<EOF
http:
  middlewares:
    mineru-auth:
      basicAuth:
        users:
          - "$HASH"
        realm: "MinerU"
        removeHeader: true

    mineru-ratelimit:
      rateLimit:
        average: 100
        burst: 50
        period: 1m
        sourceCriterion:
          ipStrategy:
            depth: 1
EOF
sudo chmod 600 "$MW_FILE"
sudo chown root:root "$MW_FILE"

# 5. 显示凭证（仅此一次）
cat <<EOF

==========================================================
  Basic Auth credentials — SAVE THESE NOW (shown once)
==========================================================
  Username: $USER
  Password: $PASSWORD

  URLs (after DNS propagates):
    https://mineru-ui.alphaxbot.xyz
    https://mineru-api.alphaxbot.xyz/docs
==========================================================

Traefik will pick up the new auth file within ~5 seconds.
Verify with:
  curl -I https://mineru-ui.alphaxbot.xyz             # expect 401
  curl -I -u $USER:<password> https://mineru-ui.alphaxbot.xyz   # expect 200
EOF
