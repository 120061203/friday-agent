import asyncio
from datetime import datetime
from ddgs import DDGS

RETRY_COUNT = 2
RETRY_DELAY_SECONDS = 1.5


async def web_search(query: str, max_results: int = 5) -> str:
    """使用 DuckDuckGo 進行真實網路搜尋，不需要 API key。
    搜尋端點偶爾會在短時間內收到多次請求後逾時/限流，失敗時重試幾次再放棄。
    """
    def _search():
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    last_error = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            results = await asyncio.get_event_loop().run_in_executor(None, _search)
            if not results:
                return f"找不到關於「{query}」的搜尋結果。"

            today = datetime.now().strftime("%Y-%m-%d")
            lines = [f"（今天日期：{today}，請忽略已過期的活動資訊）\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}\n   {r['body']}\n   來源：{r['href']}")
            return "\n\n".join(lines)

        except Exception as e:
            last_error = e
            if attempt < RETRY_COUNT:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    return f"搜尋失敗（已重試 {RETRY_COUNT} 次）：{last_error}"
