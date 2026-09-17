import os
import re


def _tokenize(text: str) -> set:
    return set(re.findall(r"[\w一-鿿]+", text.lower()))


def search_markdown_dir(dir_path: str, query: str, label: str) -> str:
    """
    在指定目錄下的 .md 檔案中，以關鍵字重疊比對搜尋與 query 最相關的文件，
    回傳內容並附上來源檔名。以此取代真正的向量檢索，作為簡化版 RAG 實作。
    """
    if not os.path.isdir(dir_path):
        return f"{label} 尚未建立任何文件。"

    query_tokens = _tokenize(query)
    if not query_tokens:
        return "查詢內容為空，無法搜尋。"

    scored = []
    for filename in sorted(os.listdir(dir_path)):
        if not filename.endswith(".md"):
            continue
        path = os.path.join(dir_path, filename)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        overlap = len(query_tokens & _tokenize(content))
        if overlap > 0:
            scored.append((overlap, filename, content))

    if not scored:
        return f"{label} 中找不到與「{query}」相關的內容。"

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, filename, content = scored[0]
    return f"（來源：{filename}，關鍵字命中 {best_score} 個）\n\n{content}"
