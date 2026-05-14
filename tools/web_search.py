import asyncio
from ddgs import DDGS


async def web_search(query: str, max_results: int = 5) -> str:
    """使用 DuckDuckGo 進行真實網路搜尋，不需要 API key。"""
    def _search():
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    try:
        results = await asyncio.get_event_loop().run_in_executor(None, _search)
        if not results:
            return f"找不到關於「{query}」的搜尋結果。"

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}\n   {r['body']}\n   來源：{r['href']}")
        return "\n\n".join(lines)

    except Exception as e:
        return f"搜尋失敗：{e}"
