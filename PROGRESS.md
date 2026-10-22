# Progress

## 2026-10-19

### 部署到 Cloudflare Containers

- 原因：專案是 Python/FastAPI（uvicorn + asyncio Queue 做 SSE 串流），無法直接以純 Cloudflare Workers（JS/TS、V8 isolate、無本地檔案系統）部署，改用 Cloudflare **Containers**（跑既有 Dockerfile，由 Worker 當前端路由）。
- 新增檔案：
  - `src/index.ts`：Worker 入口，`FridayAgentContainer`（Durable Object）包住 container，轉發 HTTP 請求到 container 內 port 8000，並在啟動時輪詢 `/health` 確認就緒。
  - `wrangler.jsonc`：Containers + Durable Object binding 設定（`scheduling_policy: durable_object`，`exports` 宣告 DO class）。無任何寫死的環境變數值——`ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`、`RATE_LIMIT_PER_MINUTE`、`AGENT_MAX_ROUNDS`、`LITELLM_BASE_URL`、`LITELLM_API_KEY`、`LITELLM_MODEL`、`BRAVE_API_KEY` 全部一律用 `npx wrangler secret put <NAME>` 設定（即使非敏感的也一樣，統一走 secret，不進 git）。
  - `package.json` / `tsconfig.json`：wrangler + TypeScript 開發依賴。
- `main.py` 新增 `/health` endpoint，供 Worker 啟動 container 後輪詢用。
- `.dockerignore` / `.gitignore` 排除 Worker 相關檔案（`node_modules`、`.wrangler`、`src/`、`wrangler.jsonc` 等不進 Python image；`node_modules`、`.wrangler`、`worker-configuration.d.ts` 不進 git）。
- 本機已驗證：`npx wrangler types`、`npx tsc --noEmit`、`docker build` 皆通過；實際跑 container 確認 `/health` 與前端頁面正常回應。
- 已 commit + push 到 `origin/main`（`ec0fd6b`）。
- **待辦（使用者自行執行）**：
  1. 確認 Cloudflare 帳號已升級 Workers Paid 方案（Containers 需要）。
  2. 跑 `npx wrangler login` + 8 個 `npx wrangler secret put <NAME>` 設定所有環境變數。
  3. 回 Cloudflare dashboard「建立和部署」精靈按部署（專案名稱需為 `friday-agent`，組建命令留空，部署命令維持 `npx wrangler deploy`）。
- 討論但未採用：Anthropic Workload Identity Federation（OIDC）取代 `ANTHROPIC_API_KEY`。結論：Cloudflare Workers/Containers 沒有原生身分簽發服務（不像 GitHub Actions、AWS ECS/EKS/Lambda 有平台級 OIDC token 發行機制），要接 WIF 得自己架一套 IdP，等於把長期密鑰換個地方存，不划算。AWS ECS 若想用 OIDC 則可行，走 STS `GetWebIdentityToken`（帳號層級的 outbound web identity federation）。

### 修正：AGENT_MAX_ROUNDS 太小時浪費最後一輪思考

- 問題：`orchestrator.py` 的 `run_agent` 迴圈，若模型在最後一輪仍選擇呼叫工具，迴圈結束只回傳先前輪次累積的文字（甚至是空字串／「已達最大執行輪次，任務未完成」），等於白燒 token。
- 修法：最後一輪呼叫 LLM 時不提供 `tools`（`tools=[]`），並在訊息中明確告知「已達最後一輪，請直接根據目前資訊整理最終答案，不要再呼叫工具」，逼模型就地收斂、產出完整回答。
- 已用 `AGENT_MAX_ROUNDS=2` 搭配需要查資料的任務本機測試驗證：第一輪搜尋、第二輪（最後一輪）成功直接整理出完整三間餐廳推薦，而非被截斷。
- 已 commit（`7827dd0`）並 push。

## 2026-10-21 ~ 10-22

### 部署到 Coolify（自架於 Tencent VPS）

- 用既有 `Dockerfile` 直接部署，建立了 GitHub App（`friday-agent-coolify`）串接 Coolify 的 Automated installation，webhook endpoint 用 **Custom endpoint**（`https://coolify.xsong.us:4869`）而不是 Instance endpoint，因為 Coolify 的 `Settings > General > URL` 存網域時會自動拔掉非標準 port，但 Coolify 本身是跑在非標準的 `4869` port 上。
- GitHub webhook 來源 IP 已限制為 GitHub 官方公告的 webhook IP 段（`https://api.github.com/meta` 的 `hooks` 欄位），不是對全世界開放 `4869`。
- App 設定：Build Pack 改成 `Dockerfile`（預設是 Railpack）、Ports exposes 設 `8000`、Port mappings 留空（Traefik 代理不需要）。
- 已掛 **Persistent Storage**（Volume Mount，`/app/data`），避免每次重新部署 `data/profile.md` 被打回 `tools/profile_manager.py` 的預設樣板。
- 已加自訂網域 `friday-coolify.xsong.us`（+ `www`），Cloudflare DNS 記錄設成**灰色雲（DNS only）**，因為 Coolify 預設用 HTTP-01 驗證跟 Let's Encrypt 申請憑證，走 Cloudflare 代理（橘色雲）會擋住驗證請求。
- **尚未解決**：網域雖然 DNS matches、app 本身能正常訪問（HTTP 層面路由正常），但瀏覽器顯示的憑證還是 `TRAEFIK DEFAULT CERT`（自簽 fallback），代表 Let's Encrypt 申請還沒成功。查了 `coolify-proxy` container 的 log，近 300 行裡完全沒有 acme/friday-coolify/error/certificate 相關紀錄，懷疑是 Traefik 根本沒有重新載入抓到這個新網域的動態設定，而不是憑證申請本身失敗。下次接續：確認 `docker exec coolify-proxy cat /traefik/dynamic.yaml` 裡有沒有這個網域的路由規則。
- 影響：在憑證問題解決前，`https://friday-coolify.xsong.us` 的瀏覽器端 `navigator.geolocation`（附近餐廳的座標功能）無法使用，因為瀏覽器視其為不安全連線。

### Token 成本優化（參考 `costdownToken.md`，未進 git，純本機參考筆記）

- 背景：使用者反應目前每次執行大約花 $0.1 美金，想知道能不能省。
- 核心問題：`orchestrator.py` 完全沒用到 Prompt Caching，也沒設定 `effort`（adaptive thinking 思考量無上限、模型自行決定想多久，thinking tokens 以 output 價計費，是 input 的 5 倍）。架構上 orchestrator 常常 `call_agent` 委派給 sub-agent（例如 `food_advisor`）、sub-agent 自己又跑好幾輪 `web_search`，每一輪完全相同的 system prompt + tools 都用全價重算。
- 修法（`messages_stream()` 呼叫處）：
  - 加 `cache_control={"type": "ephemeral"}`（top-level，SDK 自動標在最後一個可快取區塊）。
  - 加 `output_config={"effort": AGENT_EFFORT}`，新增環境變數 `AGENT_EFFORT`（預設 `medium`，可選 low/medium/high/xhigh/max），不用改程式碼就能調整。
- 已透過正式在用的 Tencent LiteLLM 路徑實測驗證：多輪 + sub-agent 任務中，第二輪 `cache_read_input_tokens=2340`，確認快取真的命中（0.1 倍價格），且沒有任何錯誤。
- 刻意不動的部分：`max_tokens`（仍是 8096，怕調低後把長回答截斷，跟之前修的「最後一輪」問題衝突）、輸出長度/格式的 prompt 指令（會改變回答風格，屬於行為改動不是純省錢改動，留給使用者自己決定要不要加）。
- 已 commit 並 push。
