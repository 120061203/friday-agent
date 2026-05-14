# Friday Agent — 美好生活 AI 助理

一個以 Claude API 實作的個人生活推薦系統，可視化 Agent 決策過程，即時展示 thinking、tool use、multi-agent 協作的完整流程。

![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.136-green) ![Python](https://img.shields.io/badge/Python-3.11+-yellow)

---

## 功能

- **週末行程規劃** — 週五下班到週日的完整活動安排
- **餐廳推薦** — 根據個人口味推薦附近餐廳
- **便當計畫** — 一週便當料理與採購清單
- **各城市活動** — 台北、台中、高雄、東京、倫敦近期活動
- **電影推薦** — 根據喜好推薦當週上映電影
- **Extended Thinking 視覺化** — 即時顯示 Claude 的內部推理過程
- **profile.md 記憶庫** — 儲存個人偏好，每次查詢自動帶入

---

## 專案結構

```
friday-agent/
├── main.py              # FastAPI server，SSE 串流 + profile API
├── orchestrator.py      # Agent 核心：決策迴圈、tool dispatch、multi-agent
├── profile.md           # 使用者偏好記憶庫（可直接編輯）
├── tools/
│   ├── web_search.py    # DuckDuckGo 真實搜尋
│   ├── calculator.py    # 數學計算
│   ├── current_time.py  # 取得目前時間
│   ├── file_read.py     # 讀取本地檔案
│   └── profile_manager.py  # 讀寫 profile.md
├── agents/
│   ├── event_planner.py # 週末活動規劃 agent
│   ├── food_advisor.py  # 餐廳推薦 + 便當計畫 agent
│   ├── local_scout.py   # 在地活動 + 電影查詢 agent
│   ├── researcher.py    # 資訊研究 agent
│   ├── coder.py         # 程式碼 agent
│   └── critic.py        # 審查 agent
└── frontend/
    └── index.html       # 視覺化 UI，含快捷按鈕與 Markdown 渲染
```

---

## 快速開始

### 1. 安裝依賴

```bash
python3 -m venv venv
source venv/bin/activate
pip install anthropic fastapi uvicorn python-dotenv duckduckgo-search
```

### 2. 設定 API Key

```bash
cp .env.example .env
# 編輯 .env，填入你的 ANTHROPIC_API_KEY
```

### 3. 啟動伺服器

```bash
uvicorn main:app --reload --port 8000
```

### 4. 開啟瀏覽器

```
http://localhost:8000
```

---

## Agent 決策邏輯

> 核心位置：`orchestrator.py:60` `run_agent()`

每次收到任務，Agent 進入 `while True` 迴圈持續與 Claude 對話，直到任務完成：

```
使用者輸入任務
      ↓
  run_agent() 載入 profile.md + 當前時間，組成 system prompt
      ↓
  呼叫 Claude API（orchestrator.py:72）
      ↓
  get_final_message() 取得完整回應（orchestrator.py:91）
      ↓
  回應裡有 tool_use block？
  ├─ 有 → dispatch_tool() 執行對應 tool → 結果塞回 messages → 繼續下一輪
  └─ 沒有 → 回傳最終文字，結束迴圈
```

**關鍵函式對照表：**

| 函式 | 位置 | 說明 |
|---|---|---|
| `run_agent()` | `orchestrator.py:60` | Agent 主迴圈，遞迴支援 sub-agent |
| `build_system_prompt()` | `orchestrator.py:56` | 載入 profile + 時間組成 system prompt |
| `dispatch_tool()` | `orchestrator.py:118` | 根據 tool name 分派到對應實作 |
| `tool_call_agent()` | `orchestrator.py:131` | 啟動 sub-agent，遞迴呼叫 run_agent |

---

## Tool Use

> 核心位置：`orchestrator.py:9` tools 清單定義，`orchestrator.py:118` dispatch

共 5 個 tools，由 Claude 自主決定何時呼叫：

| Tool | 說明 | 實作位置 |
|---|---|---|
| `web_search` | DuckDuckGo 真實搜尋，查活動、餐廳、電影 | `tools/web_search.py` |
| `get_current_time` | 取得目前日期時間，確保推薦的是未來活動 | `tools/current_time.py` |
| `update_profile` | 更新 profile.md 中的歷史記錄欄位 | `tools/profile_manager.py` |
| `calculator` | 安全數學計算，支援 math 模組 | `tools/calculator.py` |
| `call_agent` | 呼叫專門的 sub-agent 處理複雜子任務 | `orchestrator.py:131` |

**執行流程：**

```
Claude 回應包含 tool_use block
    ↓ orchestrator.py:93 偵測並收集
dispatch_tool() 根據 name 路由
    ↓
實際執行（web_search / get_current_time / ...）
    ↓
emit("tool_result") 推送到前端顯示
    ↓
結果以 tool_result message 塞回對話
    ↓
Claude 根據結果繼續決策
```

前端 **Tool Calls 面板** 會即時顯示每次呼叫的工具名稱、輸入參數與回傳結果。

---

## Multi-agent

> 核心位置：`orchestrator.py:131` `tool_call_agent()`

當 orchestrator 判斷任務需要專門處理時，透過 `call_agent` tool 呼叫對應的 sub-agent。每個 sub-agent 都有**自己獨立的 agent loop**，能自主使用 tools。

**架構：**

```
Orchestrator（friday）
    ↓ 呼叫 call_agent tool
tool_call_agent() — orchestrator.py:131
    ↓ 帶入對應 system prompt + profile context
Sub-agent（event_planner / food_advisor / local_scout）
    ↓ 有自己的 while True 迴圈
    ↓ 可自主呼叫 web_search、get_current_time 等 tools
    ↓ 完成後回傳結果給 orchestrator
Orchestrator 根據結果繼續判斷
```

**Sub-agent 對照表：**

| Agent | System Prompt 位置 | 職責 |
|---|---|---|
| `event_planner` | `agents/event_planner.py` | 規劃週末活動行程 |
| `food_advisor` | `agents/food_advisor.py` | 餐廳推薦 + 便當計畫 |
| `local_scout` | `agents/local_scout.py` | 查詢在地活動與電影 |
| `researcher` | `agents/researcher.py` | 搜尋整理資訊 |
| `coder` | `agents/coder.py` | 撰寫解釋程式碼 |
| `critic` | `agents/critic.py` | 審查回饋 |

**怎麼觀察 multi-agent 運作：**
丟一個複合任務（例如「規劃台中週末行程，順便安排下週便當」），前端 **Agents 面板**會看到 `活動規劃` 和 `飲食顧問` 依序 active（橘色）→ done（綠色）。

**目前限制：**
- Sub-agent 為依序執行，非並行
- 只支援 orchestrator → sub-agent 單向，sub-agent 之間不互通

---

## SSE 事件一覽

| 事件 | 說明 |
|---|---|
| `thinking` | Claude 內部推理過程 |
| `tool_call` | 呼叫工具，帶工具名稱與輸入參數 |
| `tool_result` | 工具回傳結果 |
| `agent_start` | Sub-agent 開始執行 |
| `agent_done` | Sub-agent 完成 |
| `done` | Orchestrator 完成，帶最終回答 |
| `error` | 發生錯誤 |

---

## 延伸方向

- 串接真實搜尋 API（Tavily、Brave Search）
- 加入 tool 執行時間計時
- Sub-agent 並行執行（asyncio.gather）
- 用 D3.js 畫動態 agent graph
- 支援多輪對話歷史
- 把 sub-agent 拆成獨立 FastAPI service，模擬分散式架構
