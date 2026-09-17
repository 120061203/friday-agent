import os

from tools.markdown_search import search_markdown_dir

_RUNBOOK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "runbooks")


async def search_runbook(query: str) -> str:
    """在本地 runbook 知識庫中搜尋與 query 最相關的問題排除文件。"""
    return search_markdown_dir(_RUNBOOK_DIR, query, "Runbook 知識庫")
