import os
import re

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_RUNBOOK_DIR = os.path.join(_DATA_DIR, "runbooks")


def _tokenize(text: str) -> set:
    return set(re.findall(r"[\w一-鿿]+", text.lower()))


async def search_runbook(query: str) -> str:
    """
    在本地 runbook 知識庫中搜尋與 query 最相關的文件，回傳內容並附上來源檔名。
    以關鍵字重疊比對取代真正的向量檢索，作為簡化版 RAG 實作。
    """
    if not os.path.isdir(_RUNBOOK_DIR):
        return "知識庫尚未建立任何 runbook 文件。"

    query_tokens = _tokenize(query)
    if not query_tokens:
        return "查詢內容為空，無法搜尋。"

    scored = []
    for filename in sorted(os.listdir(_RUNBOOK_DIR)):
        if not filename.endswith(".md"):
            continue
        path = os.path.join(_RUNBOOK_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        overlap = len(query_tokens & _tokenize(content))
        if overlap > 0:
            scored.append((overlap, filename, content))

    if not scored:
        return f"知識庫中找不到與「{query}」相關的 runbook，建議轉交人工客服。"

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, filename, content = scored[0]
    return f"（來源：{filename}，關鍵字命中 {best_score} 個）\n\n{content}"
