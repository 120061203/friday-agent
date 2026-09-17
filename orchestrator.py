import asyncio
import math
import os
from contextlib import asynccontextmanager
from typing import Callable
import anthropic
from tools.web_search import web_search as _web_search
from tools.current_time import get_current_time as _get_current_time
from tools.profile_manager import read_profile, update_profile as _update_profile
from tools.bento_manager import read_bento_history as _read_bento_history, save_bento_plan as _save_bento_plan
from tools.it_ops_guardrail import execute_it_operation as _execute_it_operation
from tools.it_knowledge_base import search_runbook as _search_runbook
from tools.it_ticket_router import classify_ticket as _classify_ticket
from agents.event_planner import event_planner_prompt
from agents.food_advisor import food_advisor_prompt
from agents.local_scout import local_scout_prompt
from agents.researcher import researcher_prompt
from agents.coder import coder_prompt
from agents.critic import critic_prompt
from agents.it_ops_advisor import it_ops_advisor_prompt

MODEL_NAME = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

# LiteLLM base url 為主要路徑（可用來統一計費/路由多個 model provider）；
# 沒設 LITELLM_BASE_URL 時完全退回原本只打官方 Anthropic API 的行為。
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "").strip()
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "").strip()
LITELLM_MODEL = os.getenv("LITELLM_MODEL", MODEL_NAME)

litellm_client = (
    anthropic.AsyncAnthropic(base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY)
    if LITELLM_BASE_URL else None
)
anthropic_client = anthropic.AsyncAnthropic()  # 官方 API，讀 ANTHROPIC_API_KEY 環境變數


@asynccontextmanager
async def messages_stream(**kwargs):
    """
    優先透過 LiteLLM 呼叫；只有在建立連線這一步就失敗（尚未讀到任何回應內容，
    例如 LiteLLM 整個掛掉、連不上、或回傳非 2xx）時，才 fallback 回官方 Anthropic key。
    一旦已經開始收串流，後續錯誤直接往上拋，不重打一次，避免內容重複。
    """
    if litellm_client is not None:
        manager = litellm_client.messages.stream(**{**kwargs, "model": LITELLM_MODEL})
        try:
            stream = await manager.__aenter__()
        except Exception as e:
            print(f"[orchestrator] LiteLLM（{LITELLM_BASE_URL}）連線失敗，改用官方 Anthropic API key：{e}")
        else:
            try:
                yield stream
            finally:
                await manager.__aexit__(None, None, None)
            return

    async with anthropic_client.messages.stream(**{**kwargs, "model": MODEL_NAME}) as stream:
        yield stream

FRIDAY_SYSTEM_PROMPT = """你是 Friday，一個專為享受美好生活設計的 AI 個人助理。

你了解使用者的偏好（記錄在下方 profile），能夠：
- 推薦台北、台中、高雄、日本、英國的熱門活動與展覽
- 推薦附近符合口味的餐廳
- 規劃週五下班後到週日晚的完整行程
- 安排一週便當料理
- 查詢最新電影與在地活動
- 協助 IT 維運：高風險操作審核攔截、內部支援知識庫問答、工單分類與優先級判定

回覆與思考過程請全程使用繁體中文。
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
        "name": "save_bento_plan",
        "description": "儲存本週便當計畫到 bento_history.md",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan": {"type": "string", "description": "完整的便當計畫內容（Markdown 格式）"}
            },
            "required": ["plan"]
        }
    },
    {
        "name": "read_bento_history",
        "description": "讀取過去的便當計畫記錄",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
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
        "name": "execute_it_operation",
        "description": "模擬執行一項 IT 維運操作（重啟服務、重置密碼、刪除帳號、資料庫操作等）。執行前會先經過 Guardrail policy check，高風險操作會被攔截並記錄稽核紀錄。",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "要執行的操作，例如「重置密碼」「重啟服務」「刪除資料庫」"},
                "target": {"type": "string", "description": "操作對象，例如帳號名稱、服務名稱、資料庫名稱"}
            },
            "required": ["action", "target"]
        }
    },
    {
        "name": "search_runbook",
        "description": "在內部 IT 支援知識庫（runbook）中搜尋問題排除步驟，例如 VPN 異常、系統當機、帳號鎖定。",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "要查詢的問題描述"}},
            "required": ["query"]
        }
    },
    {
        "name": "classify_ticket",
        "description": "模擬 ITSM 工單分類：依標題與內容判斷應分派的團隊與優先級（P1/P2/P3）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "工單標題"},
                "content": {"type": "string", "description": "工單內容"}
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "call_agent",
        "description": "呼叫專門的 sub-agent 處理特定任務，並取得該 agent 產出的完整結果。單次、簡單的查詢請直接呼叫 web_search，不需要透過 sub-agent。",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": ["event_planner", "food_advisor", "local_scout", "researcher", "coder", "critic", "it_ops_advisor"],
                    "description": (
                        "依任務性質選擇對應的 sub-agent：\n"
                        "- event_planner：規劃週五下班後到週日晚的完整活動行程（需整合多天、多活動）\n"
                        "- food_advisor：餐廳推薦，或一週便當料理規劃（含採購清單）\n"
                        "- local_scout：查詢單一城市近期的活動、展覽、電影、市集（不需跨天整合行程）\n"
                        "- researcher：一般性資訊蒐集與摘要，不屬於上述生活場景類任務\n"
                        "- coder：撰寫或解釋程式碼\n"
                        "- critic：審查既有內容（程式碼、文章、計畫）並提出具體改進建議\n"
                        "- it_ops_advisor：IT 維運操作（需 Guardrail 審核）、內部支援知識庫問答、ITSM 工單分類"
                    )
                },
                "task": {"type": "string", "description": "交給 sub-agent 的完整任務描述，包含相關 context"}
            },
            "required": ["agent_name", "task"]
        }
    }
]

# 每個 agent 只能存取自己職責範圍內的 tools，避免可選項過多降低 tool 選擇準確度，
# 也讓 sub-agent 之間無法再透過 call_agent 互相呼叫（無防護遞迴風險）。
AGENT_TOOLS = {
    "orchestrator": ["web_search", "get_current_time", "update_profile", "save_bento_plan", "read_bento_history", "calculator", "call_agent"],
    "event_planner": ["web_search", "get_current_time"],
    "food_advisor": ["web_search", "get_current_time", "read_bento_history", "save_bento_plan"],
    "local_scout": ["web_search", "get_current_time"],
    "researcher": ["web_search"],
    "coder": ["calculator"],
    "critic": [],
    "it_ops_advisor": ["execute_it_operation", "search_runbook", "classify_ticket"],
}

AGENT_PROMPTS = {
    "event_planner": event_planner_prompt,
    "food_advisor": food_advisor_prompt,
    "local_scout": local_scout_prompt,
    "researcher": researcher_prompt,
    "coder": coder_prompt,
    "critic": critic_prompt,
    "it_ops_advisor": it_ops_advisor_prompt,
}


def tools_for_agent(agent_name: str) -> list:
    allowed = AGENT_TOOLS.get(agent_name, [t["name"] for t in tools])
    return [t for t in tools if t["name"] in allowed]


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
    MAX_ROUNDS = int(os.getenv("AGENT_MAX_ROUNDS", "10"))
    agent_tools = tools_for_agent(agent_name)

    for _round in range(MAX_ROUNDS):
        response_blocks = []
        tool_uses = []

        async with messages_stream(
            max_tokens=8096,
            system=system_prompt,
            thinking={"type": "adaptive", "display": "summarized"},
            tools=agent_tools,
            messages=messages
        ) as stream:
            async for event in stream:
                etype = getattr(event, "type", None)
                if etype == "content_block_start":
                    cb = event.content_block
                    if getattr(cb, "type", None) == "thinking":
                        await emit("thinking_start", {"agent": agent_name})
                elif etype == "content_block_delta":
                    delta = event.delta
                    if getattr(delta, "type", None) == "thinking_delta":
                        await emit("thinking_delta", {
                            "agent": agent_name,
                            "text": getattr(delta, "thinking", "")
                        })

            final_message = await stream.get_final_message()
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

    elif name == "save_bento_plan":
        plan = input.get("plan", "").strip()
        if not plan:
            return "錯誤：save_bento_plan 需要傳入 plan 參數（完整便當計畫的 Markdown 內容）"
        return await _save_bento_plan(plan)

    elif name == "read_bento_history":
        return await _read_bento_history()

    elif name == "calculator":
        try:
            allowed = {"__builtins__": {}}
            allowed.update({k: getattr(math, k) for k in dir(math) if not k.startswith("_")})
            return str(eval(input["expression"], allowed))
        except Exception as e:
            return f"計算錯誤：{e}"

    elif name == "execute_it_operation":
        return await _execute_it_operation(input["action"], input["target"])

    elif name == "search_runbook":
        return await _search_runbook(input["query"])

    elif name == "classify_ticket":
        return await _classify_ticket(input["title"], input["content"])

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
