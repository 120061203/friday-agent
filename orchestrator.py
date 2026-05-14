import asyncio
import math
from typing import Callable
import anthropic
from tools.web_search import web_search as _web_search
from tools.current_time import get_current_time as _get_current_time
from tools.profile_manager import read_profile, update_profile as _update_profile
from agents.event_planner import event_planner_prompt
from agents.food_advisor import food_advisor_prompt
from agents.local_scout import local_scout_prompt
from agents.researcher import researcher_prompt
from agents.coder import coder_prompt
from agents.critic import critic_prompt

client = anthropic.Anthropic()

FRIDAY_SYSTEM_PROMPT = """你是 Friday，一個專為享受美好生活設計的 AI 個人助理。

你了解使用者的偏好（記錄在下方 profile），能夠：
- 推薦台北、台中、高雄、日本、英國的熱門活動與展覽
- 推薦附近符合口味的餐廳
- 規劃週五下班後到週日晚的完整行程
- 安排一週便當料理
- 查詢最新電影與在地活動

回覆請使用 Markdown 格式，讓內容清晰易讀。
遇到需要查詢最新資訊的任務，優先使用 web_search。
遇到複雜的規劃任務，呼叫對應的專門 agent。

---

## 使用者偏好
{profile}

---

## 今天是
{current_time}
"""

tools = [
    {
        "name": "web_search",
        "description": "搜尋網路上的最新資訊，包含活動、餐廳、電影等",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
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
                    "description": "時區，例如 Asia/Taipei，預設為 Asia/Taipei"
                }
            },
            "required": []
        }
    },
    {
        "name": "update_profile",
        "description": "更新使用者偏好檔案中的特定欄位，例如記錄歷史查詢",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "欄位名稱，例如「上次查詢活動」"},
                "value": {"type": "string", "description": "新的值"}
            },
            "required": ["key", "value"]
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
                    "enum": ["event_planner", "food_advisor", "local_scout", "researcher", "coder", "critic"]
                },
                "task": {"type": "string", "description": "交給 sub-agent 的完整任務描述，包含相關 context"}
            },
            "required": ["agent_name", "task"]
        }
    }
]

AGENT_PROMPTS = {
    "event_planner": event_planner_prompt,
    "food_advisor": food_advisor_prompt,
    "local_scout": local_scout_prompt,
    "researcher": researcher_prompt,
    "coder": coder_prompt,
    "critic": critic_prompt,
}


async def build_system_prompt() -> str:
    profile = await read_profile()
    current_time = await _get_current_time("Asia/Taipei")
    return FRIDAY_SYSTEM_PROMPT.format(profile=profile, current_time=current_time)


async def run_agent(
    task: str,
    emit: Callable,
    system_prompt: str | None = None,
    agent_name: str = "orchestrator"
):
    if system_prompt is None:
        system_prompt = await build_system_prompt()

    messages = [{"role": "user", "content": task}]
    accumulated_text = []  # 跨輪次累積所有文字
    MAX_ROUNDS = 10

    for _round in range(MAX_ROUNDS):
        response_blocks = []
        tool_uses = []

        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=8096,
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

        # 這一輪有 text block 就累積起來（即使同時有 tool_use）
        round_text = next((b.text for b in response_blocks if hasattr(b, "text")), "")
        if round_text:
            accumulated_text.append(round_text)

        tool_results = []
        last_agent_result = None
        for tool_use in tool_uses:
            result = await dispatch_tool(tool_use.name, tool_use.input, emit, agent_name, system_prompt)
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
            # 記錄 sub-agent 回傳的完整內容
            if tool_use.name == "call_agent":
                last_agent_result = str(result)

        if not tool_uses:
            # 合併所有累積的文字
            all_text = "\n\n".join(accumulated_text).strip()
            if not all_text and tool_results:
                all_text = tool_results[-1]["content"]
            return all_text

        # 如果這輪只有 call_agent，直接回傳 sub-agent 的完整結果
        if last_agent_result and all(t.name == "call_agent" or t.name == "update_profile" for t in tool_uses):
            return last_agent_result

        messages.append({"role": "assistant", "content": response_blocks})
        messages.append({"role": "user", "content": tool_results})

    # 超過最大輪次，回傳已累積的內容或錯誤訊息
    return "\n\n".join(accumulated_text).strip() or "（已達最大執行輪次，任務未完成）"


async def dispatch_tool(name: str, input: dict, emit, agent_name: str, parent_system_prompt: str):
    if name == "web_search":
        return await _web_search(input["query"])

    elif name == "get_current_time":
        return await _get_current_time(input.get("timezone", "Asia/Taipei"))

    elif name == "update_profile":
        return await _update_profile(input["key"], input["value"])

    elif name == "calculator":
        try:
            allowed = {"__builtins__": {}}
            allowed.update({k: getattr(math, k) for k in dir(math) if not k.startswith("_")})
            return str(eval(input["expression"], allowed))
        except Exception as e:
            return f"計算錯誤：{e}"

    elif name == "call_agent":
        return await tool_call_agent(
            input["agent_name"],
            input["task"],
            emit,
            parent_system_prompt
        )

    return f"未知的 tool: {name}"


async def tool_call_agent(agent_name: str, task: str, emit, parent_system_prompt: str) -> str:
    prompt_or_fn = AGENT_PROMPTS.get(agent_name)
    base_prompt = prompt_or_fn() if callable(prompt_or_fn) else prompt_or_fn

    if base_prompt:
        # 在 agent prompt 後面附加 profile context
        profile_section = "\n---\n" + "\n".join(
            line for line in parent_system_prompt.split("\n")
            if "使用者偏好" in line or line.startswith("- ") or line.startswith("## ")
        )
        system_prompt = base_prompt + profile_section
    else:
        system_prompt = "你是 Friday Agent 的助理。"

    await emit("agent_start", {"name": agent_name, "task": task})

    result = await run_agent(
        task=task,
        emit=emit,
        system_prompt=system_prompt,
        agent_name=agent_name
    )

    await emit("agent_done", {"name": agent_name, "result": result})
    return result
