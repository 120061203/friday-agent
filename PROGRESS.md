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
- 已 commit（`7827dd0`），尚未 push。
