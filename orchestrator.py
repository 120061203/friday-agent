import asyncio
from typing import Callable
import anthropic
from tools.web_search import web_search as _web_search
from tools.current_time import get_current_time as _get_current_time

client = anthropic.Anthropic()

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
        "name": "get_current_time",
        "description": "取得目前的日期與時間",
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "時區，例如 Asia/Taipei、UTC、America/New_York，預設為 Asia/Taipei"
                }
            },
            "required": []
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

        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            thinking={"type": "enabled", "budget_tokens": 2000},
            tools=tools,
            messages=messages
        ) as stream:
            # 串流期間只發 thinking 事件（input 還不完整）
            for block in stream:
                if block.type == "content_block_start":
                    cb = block.content_block
                    if cb.type == "thinking":
                        await emit("thinking", {
                            "agent": agent_name,
                            "text": cb.thinking
                        })

            # 串流結束後取完整 blocks（input 已完整解析）
            final_message = stream.get_final_message()
            for cb in final_message.content:
                if cb.type == "tool_use":
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


async def dispatch_tool(name: str, input: dict, emit, agent_name: str):
    if name == "web_search":
        return await tool_web_search(input["query"])

    elif name == "get_current_time":
        return await _get_current_time(input.get("timezone", "Asia/Taipei"))

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
    return await _web_search(query)


async def tool_calculator(expression: str) -> str:
    try:
        # 只允許安全的數學運算
        allowed_names = {"__builtins__": {}}
        import math
        allowed_names.update({k: getattr(math, k) for k in dir(math) if not k.startswith("_")})
        result = eval(expression, allowed_names)
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
