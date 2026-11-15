#!/usr/bin/env bash
# =============================================================================
# 第 3 級防護：主機防火牆（雙保險）
#
# 就算 docker-compose.yml 哪天被改錯（例如拿掉 internal: true），
# 這兩條規則還是會擋住 sandbox 網段的封包：
#   1. DOCKER-USER：從 172.30.0.0/24 要「轉送」到網段外的封包 → 丟掉
#      （擋住經由 NAT 出去的路）
#   2. INPUT：從 172.30.0.0/24 要「進入主機本身」的封包 → 丟掉
#      （擋住容器連主機上的服務，例如主機上的 proxy、DNS、SSH 再轉出去）
#
# 用法：
#   sudo ./scripts/firewall.sh apply    # 加上規則（重複執行也不會重複加）
#   sudo ./scripts/firewall.sh remove   # 移除規則
#   sudo ./scripts/firewall.sh status   # 查看規則和擋下的封包數
# =============================================================================
set -euo pipefail

SUBNET="${SANDBOX_SUBNET:-172.30.0.0/24}"
ACTION="${1:-status}"

if [[ $EUID -ne 0 ]]; then
  echo "請用 sudo 執行：sudo $0 $ACTION" >&2
  exit 1
fi

if ! iptables -n -L DOCKER-USER >/dev/null 2>&1; then
  echo "找不到 DOCKER-USER chain。請先確認 Docker 已經啟動（sudo systemctl start docker）。" >&2
  echo "如果你的 Docker 設定成 nftables 防火牆後端，這個腳本不適用。" >&2
  exit 1
fi

FWD_RULE=(DOCKER-USER -s "$SUBNET" ! -d "$SUBNET" -m comment --comment hermes-sandbox -j DROP)
IN_RULE=(INPUT -s "$SUBNET" -m comment --comment hermes-sandbox -j DROP)

add_rule() {
  # -C 檢查規則是否已存在；不存在才用 -I 插到最前面
  if ! iptables -C "$@" 2>/dev/null; then
    iptables -I "$@"
  fi
}

del_rule() {
  while iptables -C "$@" 2>/dev/null; do
    iptables -D "$@"
  done
}

case "$ACTION" in
  apply)
    add_rule "${FWD_RULE[@]}"
    add_rule "${IN_RULE[@]}"
    echo "✅ 已套用：$SUBNET 的對外封包和連主機的封包都會被丟掉"
    ;;
  remove)
    del_rule "${FWD_RULE[@]}"
    del_rule "${IN_RULE[@]}"
    echo "已移除 hermes-sandbox 防火牆規則"
    ;;
  status)
    echo "== DOCKER-USER（pkts 欄位 = 擋下的封包數）=="
    iptables -n -v -L DOCKER-USER | grep -E "pkts|hermes-sandbox" || true
    echo
    echo "== INPUT =="
    iptables -n -v -L INPUT | grep -E "pkts|hermes-sandbox" || true
    echo
    echo "== NAT 表裡有沒有 $SUBNET 的 MASQUERADE（應該要沒有）=="
    if iptables -t nat -S POSTROUTING | grep -F "${SUBNET%/*}"; then
      echo "⚠️  發現 NAT 規則！sandbox 網路可能不是 internal，請檢查 docker-compose.yml"
    else
      echo "✅ 沒有，NAT 出口不存在"
    fi
    ;;
  *)
    echo "用法：sudo $0 {apply|remove|status}" >&2
    exit 1
    ;;
esac
