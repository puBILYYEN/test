# Hermes Agent 斷網 Sandbox（Ubuntu 版）

把 **Hermes Agent**（AI 代理人）和 **本地模型（ORNITH 1.5，用 Ollama 跑）** 一起包進 Docker，
讓它們**沒有任何對外的網路出口**：不能經由 NAT 出去、不能查外部 DNS、不能用 IPv6、也不能拿主機當跳板。

```
                    主機（Ubuntu）
  ┌───────────────────────────────────────────────────────┐
  │  防火牆（第 3 級）：172.30.0.0/24 → 外面  ✗ 丟掉        │
  │                    172.30.0.0/24 → 主機  ✗ 丟掉        │
  │                                                         │
  │   ┌──────── ai-internal（internal: true，無 NAT）────┐   │
  │   │                                                  │   │
  │   │   hermes（AI 代理人）  ──►  llm（Ollama + 模型）  │   │
  │   │   /opt/data  /workspace       模型 volume        │   │
  │   └──────────────────────────────────────────────────┘   │
  └───────────────────────────────────────────────────────┘
```

## 已實測的結果

這份設定用**真正的** `nousresearch/hermes-agent` 和 `ollama/ollama` 映像檔測試過，`scripts/verify.sh` 16 項全部通過。測試過程中發現三件事：

1. **只靠 `internal: true` 不夠。** 容器還是連得到主機本身（172.30.0.1）。實測在主機開一個網頁服務，容器可以直接連上。如果你的主機有跑 proxy 或 VPN 工具，Hermes 就能透過它把資料送出去。所以**第 3 級防火牆一定要裝**。
2. **Ollama 一啟動就會主動連 `ollama.com`。** 它會去抓雲端模型清單和推薦模型。這個 sandbox 擋住了，另外也設了 `OLLAMA_NO_CLOUD=1` 從源頭關掉。
3. **Hermes 官方的 `docker-compose.yml` 用的是 `network_mode: host`。** 這代表容器直接使用主機的網路，完全沒有隔離。所以這裡沒有直接用官方的設定。

另外也測試了「故意把設定弄錯」的情況：把網路改成有 NAT 的普通網路，防火牆照樣把往外的封包擋下來。

---

## 前置準備

1. **安裝官方版 Docker Engine**（`docker-ce`），**不要用 snap 版**：
   照 https://docs.docker.com/engine/install/ubuntu/ 的步驟安裝。
2. 確認版本和防火牆後端：
   ```bash
   docker compose version
   docker info | grep "Firewall Backend"     # 要看到 iptables
   ```
3. 如果有 NVIDIA 顯示卡，想用 GPU 跑模型：安裝 `nvidia-container-toolkit`，再把 `docker-compose.yml` 裡 GPU 那段取消註解。

---

## 第 1 步：取得檔案、設定使用者 ID

```bash
git clone <你的 repo 網址>      # 已經 clone 過的話用 git pull
cd test/hermes-sandbox

cp .env.example .env
id -u    # 查你的 UID
id -g    # 查你的 GID
nano .env    # 把 HERMES_UID / HERMES_GID 改成上面查到的數字（通常都是 1000）
```

## 第 2 步：趁還有網路，先下載映像檔

```bash
docker compose --profile cli pull
```

> 下載映像檔是 Docker 服務本身在做，不是容器在連網，所以不會影響 sandbox。

## 第 3 步：放入模型（二選一）

**A. 模型在 Ollama 官方庫上**（可以 `ollama pull` 的）

```bash
./scripts/pull-model-online.sh <模型名稱>
```

這是**唯一會連網的步驟**。它會開一個臨時容器，只掛模型資料夾，下載完就刪掉。

**B. 你手上是 `.gguf` 檔**

```bash
cp /你放模型的路徑/ORNITH-1.5.gguf models-gguf/
```

**接下來兩種方法都要做：建立 Hermes 要用的模型（加大 context）**

```bash
cp models-gguf/Modelfile.example models-gguf/Modelfile
nano models-gguf/Modelfile
#   B：把 FROM 那行改成你的 .gguf 檔名
#   A：把 FROM 那行改成 FROM <模型名稱>

docker compose up -d
docker compose exec llm ollama create ornith -f /gguf/Modelfile
docker compose exec llm ollama list      # 應該看到 ornith
```

> Hermes 需要至少 64K 的 context，Ollama 預設只有 2K 到 4K，所以要用 Modelfile 加大。

## 第 4 步：設定 Hermes 使用 sandbox 裡的模型

```bash
docker compose run --rm hermes config set model.provider custom
docker compose run --rm hermes config set model.base_url http://llm:11434/v1
docker compose run --rm hermes config set model.default ornith
docker compose run --rm hermes config set model.api_key ollama
docker compose run --rm hermes config set security.allow_lazy_installs false
```

- `base_url` 用 `llm`（容器名稱），**不是** `localhost`。
- `api_key` 隨便填一個字就好，Ollama 不會檢查。
- `allow_lazy_installs false`：不讓 Hermes 自己去網路下載套件。
- **不要**設定 `fallback_providers`（本地模型失敗時改用雲端），那就是把資料送出去。

### 用 CC Switch 切換 sandbox 裡的 Hermes

CC Switch 預設會改主機上的 `~/.hermes/config.yaml`，但 sandbox 裡的 Hermes 讀的是 `hermes-sandbox/hermes-data/config.yaml`。所以要讓 CC Switch 改對地方：

1. 打開 CC Switch → **設定（Settings）** → **App 設定** → **Hermes** 的「設定目錄（Config directory）」
2. 填入 `hermes-data` 資料夾的**完整路徑**，例如 `/home/你的帳號/test/hermes-sandbox/hermes-data`
3. 之後在 CC Switch 按「Enable」切換，下次執行 `docker compose run --rm hermes` 就會生效

要注意的是：
- 在 sandbox 裡，**只有本地模型（`http://llm:11434/v1`）連得到**。切換到雲端供應商（Kimi、SiliconFlow 等）會連線失敗，這代表 sandbox 有效，不是 CC Switch 壞了。
- CC Switch 的 MCP / Skills 同步到 Hermes 時，也會寫進這個 `config.yaml`。需要網路的 MCP 在 sandbox 裡一樣連不出去。
- CC Switch 切換 **Claude Code** 的部分不受影響。Claude Code 在 sandbox 外面，照常使用。

## 第 5 步：裝防火牆（第 3 級，必做）

```bash
# 先套用一次
sudo ./scripts/firewall.sh apply

# 設定成開機和 Docker 重新啟動時自動套用
sudo cp scripts/firewall.sh /usr/local/sbin/hermes-sandbox-firewall.sh
sudo cp scripts/hermes-sandbox-firewall.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hermes-sandbox-firewall.service
```

## 第 6 步：驗證（每次改設定後都要跑）

```bash
sudo -v                # 先輸入一次密碼，讓腳本可以檢查防火牆
./scripts/verify.sh
```

最後看到 `🎉 全部通過` 才可以放敏感資料進去。

## 第 7 步：開始使用

```bash
docker compose up -d                 # 啟動模型伺服器（開機後會自動啟動）
docker compose run --rm hermes       # 開啟 Hermes 對話
```

- 要給 Hermes 處理的檔案放在 `workspace/`，在容器裡對應 `/workspace`。
- Hermes 的設定、記憶、對話紀錄放在 `hermes-data/`。

---

## ⚠️ 不能做的事（會破壞 sandbox）

| 不要做 | 原因 |
|---|---|
| 在 `docker-compose.yml` 加 `network_mode: host` | 容器會直接用主機的網路，隔離全部失效 |
| 把 `internal: true` 拿掉 | Docker 會建立 NAT 出口 |
| 掛載 `/var/run/docker.sock` | 容器可以自己開一個有網路的新容器 |
| 把 Hermes 的 `terminal.backend` 改成 `docker` | 這個功能需要 docker.sock（目前是 `local`，指令就在 sandbox 容器裡執行） |
| 掛載 `~` 或 `~/.ssh`、`~/.hermes` | 會把主機上的金鑰和舊的 API key 交給代理人 |
| 設定 Telegram/Discord 等 gateway | 那些功能本來就需要連外，對話內容會經過它們的伺服器 |
| 在主機的 Ollama 或 proxy 開 `0.0.0.0` | 第 3 級防火牆有擋，但不要依賴單一保護 |

## 正常會發生的事

- Hermes 的網頁搜尋、瀏覽器、`hermes update` 都會失敗。**這代表 sandbox 有效。** 可以用 `docker compose run --rm hermes tools` 把用不到的網路工具關掉，減少錯誤訊息。
- 執行指令時可能出現 `install out of sync (pnpm ...)` 的警告，這是官方映像檔本身的訊息，不影響使用。
- **更新 Hermes 的方法**：`docker compose --profile cli pull`，然後**再跑一次 `verify.sh`**。

## 疑難排解

- **模型輸出一段 JSON，而不是真的執行工具**：通常是模型的 tool-call 格式沒被 Ollama 正確解析，換一個有支援 tools 的模型版本，或者跟我說錯誤內容。
- **`hermes-data` 權限錯誤**：確認 `.env` 裡的 UID/GID 跟 `id -u`、`id -g` 一樣。
- **Hermes 容器啟動失敗**：把錯誤訊息貼給我。可以先暫時把 `cap_drop` / `cap_add` 兩行註解掉，確認是不是權限設定造成的。
- **`firewall.sh` 說找不到 DOCKER-USER**：先 `sudo systemctl start docker`。

## 完全移除

```bash
docker compose down
sudo systemctl disable --now hermes-sandbox-firewall.service
sudo rm /etc/systemd/system/hermes-sandbox-firewall.service /usr/local/sbin/hermes-sandbox-firewall.sh
docker volume rm hermes-ollama-data      # 會刪除下載的模型
```

## 提醒

- 幫你操作的 AI（例如在 Antigravity 裡執行的 Claude Code）是在 **sandbox 外面**執行的。它要執行 `sudo` 或刪除檔案時，請先看清楚再同意。
- Windows 版之後另外處理（Docker Desktop 的網路架構不一樣，第 3 級防火牆要換成別的做法）。
