#!/usr/bin/env bash
# =============================================================================
# 一鍵檢查 sandbox 有沒有包好
# 用法（在 hermes-sandbox 資料夾裡）：./scripts/verify.sh
# 需要先執行過：docker compose up -d
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

NET=hermes-sandbox_ai-internal
FAIL=0

echo "========== [A] Docker 網路設定 =========="
internal=$(docker network inspect "$NET" --format '{{.Internal}}' 2>/dev/null || echo "missing")
if [[ "$internal" == "true" ]]; then
  echo "  ✅ PASS  $NET 是 internal 網路（沒有 NAT 出口）"
else
  echo "  ❌ FAIL  $NET 的 internal = $internal（請先 docker compose up -d，並確認 internal: true）"
  FAIL=1
fi

for c in $(docker ps -q); do
  mode=$(docker inspect "$c" --format '{{.HostConfig.NetworkMode}}')
  name=$(docker inspect "$c" --format '{{.Name}}')
  if [[ "$mode" == "host" ]]; then
    echo "  ⚠️  注意  容器 ${name#/} 使用 network_mode: host（它完全沒被隔離）"
  fi
done

echo
echo "========== [B] 主機防火牆（第 3 級）=========="
if sudo -n true 2>/dev/null; then
  sudo ./scripts/firewall.sh status
  if ! sudo iptables -C DOCKER-USER -s 172.30.0.0/24 ! -d 172.30.0.0/24 \
        -m comment --comment hermes-sandbox -j DROP 2>/dev/null; then
    echo "  ❌ FAIL  DOCKER-USER 規則沒有套用，請執行：sudo ./scripts/firewall.sh apply"
    FAIL=1
  fi
else
  echo "  （略過：需要 sudo。可以先執行 sudo -v 再跑一次這個腳本）"
fi

echo
echo "========== [C] 模型伺服器容器（llm）往外連 =========="
if docker compose exec -T llm getent hosts example.com >/dev/null 2>&1; then
  echo "  ❌ FAIL  llm 容器查得到 example.com"; FAIL=1
else
  echo "  ✅ PASS  llm 容器查不到 example.com"
fi
if docker compose exec -T llm timeout 5 bash -c '</dev/tcp/1.1.1.1/443' >/dev/null 2>&1; then
  echo "  ❌ FAIL  llm 容器連得到 1.1.1.1:443"; FAIL=1
else
  echo "  ✅ PASS  llm 容器連不到 1.1.1.1:443"
fi

echo
echo "========== [D] Hermes 容器往外連（完整測試）=========="
docker compose run --rm -T \
  -v "$PWD/scripts/egress_test.py:/opt/egress_test.py:ro" \
  hermes python3 /opt/egress_test.py || FAIL=1

echo
if [[ $FAIL -eq 0 ]]; then
  echo "🎉 全部通過：sandbox 沒有對外出口，Hermes 連得到模型。"
else
  echo "❌ 有項目失敗，請不要放敏感資料進去，先把失敗的項目修好。"
fi
exit $FAIL
