#!/usr/bin/env bash
# =============================================================================
# 唯一一個「會連網」的步驟：從 Ollama 官方下載模型
#
# 這時候開的是一個臨時容器，只掛載模型 volume，沒有掛你的任何資料，
# 下載完立刻刪除。之後真正使用的 llm 容器是斷網的。
#
# 如果你的 ORNITH 1.5 是 .gguf 檔案，就不需要這個腳本，請看 README「第 3 步 B」。
#
# 用法：./scripts/pull-model-online.sh <模型名稱>
#   例如：./scripts/pull-model-online.sh qwen3:8b
# =============================================================================
set -euo pipefail

MODEL="${1:-}"
if [[ -z "$MODEL" ]]; then
  echo "用法：$0 <Ollama 模型名稱>" >&2
  exit 1
fi

VOL=hermes-ollama-data
NAME=hermes-model-download

docker volume create "$VOL" >/dev/null
docker rm -f "$NAME" >/dev/null 2>&1 || true

# 臨時容器：用 Docker 預設網路（有網路），只掛模型 volume
docker run -d --rm --name "$NAME" -v "$VOL":/root/.ollama ollama/ollama:latest >/dev/null
trap 'docker stop "$NAME" >/dev/null 2>&1 || true' EXIT

echo "等待 Ollama 啟動..."
for _ in $(seq 1 30); do
  docker exec "$NAME" ollama list >/dev/null 2>&1 && break
  sleep 1
done

docker exec "$NAME" ollama pull "$MODEL"
echo "✅ 下載完成：$MODEL（存在 volume $VOL，臨時容器會自動刪除）"
