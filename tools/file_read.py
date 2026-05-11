import os


async def file_read(path: str) -> str:
    """讀取本地檔案內容。僅允許讀取當前工作目錄下的檔案。"""
    # 安全限制：只允許讀取當前目錄內的檔案
    base_dir = os.path.abspath(".")
    target = os.path.abspath(path)

    if not target.startswith(base_dir):
        return f"拒絕存取：不允許讀取工作目錄以外的檔案 ({path})"

    if not os.path.exists(target):
        return f"檔案不存在：{path}"

    if not os.path.isfile(target):
        return f"路徑不是檔案：{path}"

    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 10000:
            content = content[:10000] + "\n... (內容過長，已截斷)"
        return content
    except Exception as e:
        return f"讀取錯誤：{e}"
