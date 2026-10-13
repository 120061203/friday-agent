import asyncio
import os
import re
from datetime import datetime
import httpx
from ddgs import DDGS

_HTML_TAG_RE = re.compile(r"<[^>]+>")

RETRY_COUNT = 2
RETRY_DELAY_SECONDS = 1.5
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def _format_results(query: str, results: list[dict]) -> str:
    if not results:
        return f"找不到關於「{query}」的搜尋結果。"
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"（今天日期：{today}，請忽略已過期的活動資訊）\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r['body']}\n   來源：{r['href']}")
    return "\n\n".join(lines)


async def _brave_search(query: str, max_results: int, api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            BRAVE_SEARCH_URL,
            params={"q": query, "count": max_results},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        )
        resp.raise_for_status()
        data = resp.json()

    web_results = data.get("web", {}).get("results", [])
    return [
        {
            "title": _HTML_TAG_RE.sub("", r.get("title", "")),
            "body": _HTML_TAG_RE.sub("", r.get("description", "")),
            "href": r.get("url", ""),
        }
        for r in web_results[:max_results]
    ]


def _ddgs_search(query: str, max_results: int) -> list[dict]:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


async def web_search(query: str, max_results: int = 5) -> str:
    """搜尋網路最新資訊。設定 BRAVE_API_KEY 時優先用 Brave Search API，
    沒設定則退回 ddgs（DuckDuckGo 等聚合引擎，不需要 API key）。
    搜尋端點偶爾會逾時/限流，失敗時重試幾次再放棄。
    """
    brave_api_key = os.getenv("BRAVE_API_KEY", "").strip()

    last_error = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            if brave_api_key:
                results = await _brave_search(query, max_results, brave_api_key)
            else:
                results = await asyncio.get_event_loop().run_in_executor(
                    None, _ddgs_search, query, max_results
                )
            return _format_results(query, results)

        except Exception as e:
            last_error = e
            if attempt < RETRY_COUNT:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    return f"搜尋失敗（已重試 {RETRY_COUNT} 次）：{last_error}"
