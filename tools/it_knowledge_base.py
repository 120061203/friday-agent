import os

from tools.markdown_search import search_markdown_dir

# 故意放在 data/ 之外：部署環境常會把 data/ 掛成 persistent volume 讓
# profile.md/bento_history.md 跨部署保留，volume 會蓋掉映像檔裡同路徑的內容，
# runbooks/ 若放在 data/ 底下就會在有掛 volume 的環境裡永遠讀不到。
_RUNBOOK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runbooks")


async def search_runbook(query: str) -> str:
    """在本地 runbook 知識庫中搜尋與 query 最相關的問題排除文件。"""
    return search_markdown_dir(_RUNBOOK_DIR, query, "Runbook 知識庫")
