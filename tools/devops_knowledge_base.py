import os

from tools.markdown_search import search_markdown_dir

_REFERENCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "skills", "devops-skill", "references"
)


async def search_devops_reference(query: str) -> str:
    """在 devops-skill 知識庫中搜尋與 query 最相關的基礎設施參考文件。"""
    return search_markdown_dir(_REFERENCE_DIR, query, "DevOps 知識庫")
