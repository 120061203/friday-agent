# Agent Demo App 實作指南

> 目標：建立一個可視化 Claude Agent 決策過程的 demo app，看到 thinking、tool use、multi-agent 協作的完整流程。

---

## 專案結構

```
agent-demo/
├── main.py              # FastAPI server，SSE 串流決策 log
├── orchestrator.py      # 主 agent loop，解析 tool_use block
├── tools/
│   ├── __init__.py
│   ├── web_search.py
│   ├── calculator.py
│   └── file_read.py
├── agents/
│   ├── __init__.py
│   ├── researcher.py    # sub-agent：搜尋 + 摘要
│   ├── coder.py         # sub-agent：生成 + 執行程式碼
│   └── critic.py        # sub-agent：審查 + 回饋
└── frontend/
    └── index.html       # 串流顯示決策 log 的 UI
```

---

## 建議開發順序

1. Orchestrator loop（純 print，不需前端）
2. 加 SSE，把事件推出去
3. 前端 thinking panel
4. Tool 呼叫卡片
5. 加第一個 sub-agent
6. Agent graph 視覺化

---

## ① Claude API — 拿到 streaming blocks

```python
# orchestrator.py
import anthropic

client = anthropic.Anthropic()  # 自動讀取 ANTHROPIC_API_KEY 環境變數

tools = [
    {
        "name": "web_search",
        "description": "搜尋網路資訊",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "calculator",
        "description": "執行數學計算",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"]
        }
    },
    {
        "name": "call_agent",
        "description": "呼叫專門的 sub-agent 處理特定任務",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["researcher", "coder", "critic"]
                },
                "task": {"type": "string"}
            },
            "required": ["agent_name", "task"]
        }
    }
]

# 回傳的 block 類型：
# - thinking  → 內部推理（需開啟 extended thinking）
# - tool_use  → agent 決定呼叫哪個 tool
# - text      → 最終回答
```

**Block 類型說明：**

| Block 類型 | 說明 | 顯示在哪 |
|---|---|---|
| `thinking` | Agent 的內部推理過程 | Thinking panel |
| `tool_use` | 決定呼叫哪個工具、帶什麼參數 | Tool call 卡片 |
| `text` | 最終回覆文字 | 答案區 |

---

## ② Orchestrator Loop — Agent 核心邏輯

```python
# orchestrator.py
import asyncio
from typing import Callable

async def run_agent(
    task: str,
    emit: Callable,
    system_prompt: str = "你是一個有用的 AI 助理。",
    agent_name: str = "orchestrator"
):
    messages = [{"role": "user", "content": task}]

    while True:
        response_blocks = []
        tool_uses = []

        # 一次 API 呼叫，串流收集所有 blocks
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            thinking={"type": "enabled", "budget_tokens": 2000},
            tools=tools,
            messages=messages
        ) as stream:
            for block in stream:
                if block.type == "content_block_start":
                    cb = block.content_block

                    if cb.type == "thinking":
                        await emit("thinking", {
                            "agent": agent_name,
                            "text": cb.thinking
                        })

                    elif cb.type == "tool_use":
                        await emit("tool_call", {
                            "agent": agent_name,
                            "name": cb.name,
                            "input": cb.input,
                            "tool_use_id": cb.id
                        })
                        tool_uses.append(cb)

                    response_blocks.append(cb)

        # 執行所有 tool calls
        tool_results = []
        for tool_use in tool_uses:
            result = await dispatch_tool(tool_use.name, tool_use.input, emit, agent_name)
            await emit("tool_result", {
                "agent": agent_name,
                "name": tool_use.name,
                "result": result,
                "tool_use_id": tool_use.id
            })
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": str(result)
            })

        # 沒有 tool_use → agent 認為任務完成，跳出迴圈
        if not tool_uses:
            final_text = next(
                (b.text for b in response_blocks if hasattr(b, "text")), ""
            )
            return final_text

        # 把結果塞回 messages，繼續下一輪
        messages.append({"role": "assistant", "content": response_blocks})
        messages.append({"role": "user", "content": tool_results})
```

**關鍵：`while True` 迴圈**

```
呼叫 Claude API
    ↓
收到 tool_use block？
    ├─ 是 → 執行 tool → 塞回 messages → 繼續下一輪
    └─ 否 → 回傳最終文字，結束
```

---

## ③ Tool 執行層

```python
# orchestrator.py（續）
async def dispatch_tool(name: str, input: dict, emit, agent_name: str):
    if name == "web_search":
        return await tool_web_search(input["query"])

    elif name == "calculator":
        return await tool_calculator(input["expression"])

    elif name == "call_agent":
        return await tool_call_agent(
            input["agent_name"],
            input["task"],
            emit
        )

    return f"未知的 tool: {name}"


async def tool_web_search(query: str) -> str:
    # 實際可串接 Tavily、Brave Search 等 API
    # 這裡先 mock
    return f"搜尋結果：關於「{query}」的資訊..."


async def tool_calculator(expression: str) -> str:
    try:
        result = eval(expression)  # 正式環境請用 safer eval
        return str(result)
    except Exception as e:
        return f"計算錯誤：{e}"


async def tool_call_agent(agent_name: str, task: str, emit) -> str:
    system_prompts = {
        "researcher": "你是研究員，專門搜尋並整理資訊，給出有條理的摘要。",
        "coder": "你是工程師，專門撰寫並解釋程式碼。",
        "critic": "你是審查員，專門找出問題與改進空間，提供建設性回饋。"
    }

    await emit("agent_start", {"name": agent_name, "task": task})

    result = await run_agent(
        task=task,
        emit=emit,
        system_prompt=system_prompts.get(agent_name, "你是 AI 助理。"),
        agent_name=agent_name
    )

    await emit("agent_done", {"name": agent_name, "result": result})
    return result
```

---

## ④ FastAPI SSE — 把事件推到前端

```python
# main.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json, asyncio

from orchestrator import run_agent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


class RunRequest(BaseModel):
    task: str


@app.post("/run")
async def run(body: RunRequest):
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event_type: str, data: dict):
        await queue.put({"type": event_type, "data": data})

    async def agent_task():
        try:
            result = await run_agent(body.task, emit)
            await queue.put({"type": "done", "data": {"result": result}})
        except Exception as e:
            await queue.put({"type": "error", "data": {"message": str(e)}})
        finally:
            await queue.put(None)  # 結束信號

    asyncio.create_task(agent_task())

    async def stream():
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
```

---

## ⑤ 前端 — 接收 SSE 並分類顯示

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <title>Agent Demo</title>
  <style>
    body { font-family: system-ui; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
    #input-area { display: flex; gap: 8px; margin-bottom: 1.5rem; }
    #task-input { flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 15px; }
    button { padding: 8px 16px; background: #5b4fbe; color: white; border: none; border-radius: 8px; cursor: pointer; }

    .panel { border: 1px solid #eee; border-radius: 10px; padding: 1rem; margin-bottom: 1rem; }
    .panel h3 { margin: 0 0 8px; font-size: 13px; color: #888; text-transform: uppercase; letter-spacing: .05em; }

    .thinking-block { background: #f5f3ff; border-left: 3px solid #7c6fcd; padding: 8px 12px; border-radius: 4px; margin-bottom: 8px; font-size: 13px; color: #444; white-space: pre-wrap; }
    .tool-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; font-size: 13px; }
    .tool-card .tool-name { font-weight: 600; color: #0f766e; margin-bottom: 4px; }
    .tool-card .tool-input { color: #666; margin-bottom: 4px; }
    .tool-card .tool-result { color: #16a34a; border-top: 1px solid #f0fdf4; padding-top: 6px; margin-top: 6px; }

    .agent-node { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; margin: 4px; background: #f3f4f6; border: 1px solid #e5e7eb; }
    .agent-node.active { background: #fef3c7; border-color: #f59e0b; color: #92400e; }
    .agent-node.done { background: #d1fae5; border-color: #10b981; color: #065f46; }
  </style>
</head>
<body>

<h2>Agent 決策視覺化</h2>

<div id="input-area">
  <input id="task-input" placeholder="輸入任務，例如：查詢台灣 AI 新創公司並整理摘要" />
  <button onclick="runAgent()">執行</button>
</div>

<!-- Agent 狀態 -->
<div class="panel">
  <h3>Agents</h3>
  <div id="agent-graph">
    <span class="agent-node" id="node-orchestrator">orchestrator</span>
    <span class="agent-node" id="node-researcher">researcher</span>
    <span class="agent-node" id="node-coder">coder</span>
    <span class="agent-node" id="node-critic">critic</span>
  </div>
</div>

<!-- 推理過程 -->
<div class="panel">
  <h3>Thinking</h3>
  <div id="thinking-panel"></div>
</div>

<!-- Tool 呼叫 -->
<div class="panel">
  <h3>Tool Calls</h3>
  <div id="tool-panel"></div>
</div>

<!-- 最終答案 -->
<div class="panel">
  <h3>最終回答</h3>
  <div id="result-panel" style="white-space: pre-wrap; font-size: 15px;"></div>
</div>

<script>
const toolCards = {};  // tool_use_id → DOM element

function runAgent() {
  const task = document.getElementById('task-input').value.trim();
  if (!task) return;

  // 清空面板
  ['thinking-panel', 'tool-panel', 'result-panel'].forEach(id => {
    document.getElementById(id).innerHTML = '';
  });
  document.querySelectorAll('.agent-node').forEach(n => {
    n.className = 'agent-node';
  });

  fetch('/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task })
  }).then(res => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    function read() {
      reader.read().then(({ done, value }) => {
        if (done) return;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop();  // 保留未完成的行

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const { type, data } = JSON.parse(line.slice(6));
            handleEvent(type, data);
          }
        }
        read();
      });
    }
    read();
  });
}

function handleEvent(type, data) {
  if (type === 'thinking') {
    const div = document.createElement('div');
    div.className = 'thinking-block';
    div.textContent = `[${data.agent}] ${data.text}`;
    document.getElementById('thinking-panel').appendChild(div);
  }

  else if (type === 'tool_call') {
    const card = document.createElement('div');
    card.className = 'tool-card';
    card.innerHTML = `
      <div class="tool-name">${data.name}</div>
      <div class="tool-input">輸入：${JSON.stringify(data.input)}</div>
    `;
    toolCards[data.tool_use_id] = card;
    document.getElementById('tool-panel').appendChild(card);
  }

  else if (type === 'tool_result') {
    const card = toolCards[data.tool_use_id];
    if (card) {
      const resultDiv = document.createElement('div');
      resultDiv.className = 'tool-result';
      resultDiv.textContent = `結果：${data.result}`;
      card.appendChild(resultDiv);
    }
  }

  else if (type === 'agent_start') {
    const node = document.getElementById(`node-${data.name}`);
    if (node) node.className = 'agent-node active';
  }

  else if (type === 'agent_done') {
    const node = document.getElementById(`node-${data.name}`);
    if (node) node.className = 'agent-node done';
  }

  else if (type === 'done') {
    document.getElementById('result-panel').textContent = data.result;
  }
}
</script>
</body>
</html>
```

---

## 啟動方式

```bash
# 安裝依賴
pip install anthropic fastapi uvicorn

# 設定 API key
export ANTHROPIC_API_KEY=sk-ant-...

# 啟動伺服器
uvicorn main:app --reload --port 8000

# 開瀏覽器
open http://localhost:8000
```

---

## 事件類型一覽

| 事件 | 資料欄位 | 說明 |
|---|---|---|
| `thinking` | `agent`, `text` | Agent 內部推理 |
| `tool_call` | `agent`, `name`, `input`, `tool_use_id` | 呼叫工具 |
| `tool_result` | `agent`, `name`, `result`, `tool_use_id` | 工具回傳值 |
| `agent_start` | `name`, `task` | Sub-agent 開始執行 |
| `agent_done` | `name`, `result` | Sub-agent 完成 |
| `done` | `result` | Orchestrator 完成 |
| `error` | `message` | 發生錯誤 |

---

## 延伸方向

- 串接真實搜尋 API（Tavily、Brave Search）
- 加入 tool 執行時間計時
- 用 D3.js 畫動態 agent graph
- 加入對話歷史，支援多輪任務
- 把 sub-agent 拆成獨立 FastAPI service，模擬分散式架構
