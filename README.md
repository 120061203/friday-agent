# Friday Agent — Claude AI 決策視覺化 Demo

一個可視化 Claude Agent 決策過程的 demo app，即時展示 thinking、tool use、multi-agent 協作的完整流程。

![Agent 決策視覺化](https://img.shields.io/badge/Claude-Sonnet_4.5-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.136-green) ![Python](https://img.shields.io/badge/Python-3.11+-yellow)

---

## 功能

- **Extended Thinking 視覺化** — 即時顯示 Claude 的內部推理過程
- **Tool Call 追蹤** — 看到每個工具的輸入與回傳結果
- **Multi-agent 協作** — Orchestrator 動態呼叫 researcher、coder、critic
- **SSE 串流** — 所有事件即時推送到前端，無需輪詢

---

## 專案結構

```
friday-agent/
├── main.py              # FastAPI server，SSE 串流決策 log
├── orchestrator.py      # 主 agent loop，解析 tool_use block
├── tools/
│   ├── web_search.py    # DuckDuckGo 真實搜尋
│   ├── calculator.py    # 數學計算
│   ├── current_time.py  # 取得目前時間
│   └── file_read.py     # 讀取本地檔案
├── agents/
│   ├── researcher.py    # 研究員：搜尋 + 摘要
│   ├── coder.py         # 工程師：生成 + 解釋程式碼
│   └── critic.py        # 審查員：找問題 + 回饋
└── frontend/
    └── index.html       # 串流顯示決策 log 的 UI
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

或直接設定環境變數：

```bash
export ANTHROPIC_API_KEY=sk-ant-...
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

## 可用 Tools

| Tool | 說明 |
|---|---|
| `web_search` | 使用 DuckDuckGo 搜尋真實網路資訊 |
| `calculator` | 執行數學計算，支援 math 模組函數 |
| `get_current_time` | 取得目前日期時間，可指定時區 |
| `file_read` | 讀取工作目錄內的本地檔案 |
| `call_agent` | 呼叫專門的 sub-agent（researcher / coder / critic） |

## Sub-agents

| Agent | 職責 |
|---|---|
| `researcher` | 搜尋並整理資訊，輸出有條理的摘要 |
| `coder` | 撰寫並解釋程式碼 |
| `critic` | 審查內容，找出問題並提供改進建議 |

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

## Agent Loop 運作原理

```
使用者輸入任務
      ↓
  呼叫 Claude API
      ↓
  收到 tool_use？
  ├─ 是 → 執行 tool → 結果塞回 messages → 繼續下一輪
  └─ 否 → 回傳最終文字，結束
```

---

## 延伸方向

- 串接真實搜尋 API（Tavily、Brave Search）
- 加入 tool 執行時間計時
- 用 D3.js 畫動態 agent graph
- 支援多輪對話歷史
- 把 sub-agent 拆成獨立 FastAPI service，模擬分散式架構
