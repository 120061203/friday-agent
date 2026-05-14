import os
from datetime import datetime

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(_DATA_DIR, exist_ok=True)
BENTO_PATH = os.path.join(_DATA_DIR, "bento_history.md")


async def read_bento_history() -> str:
    """讀取便當歷史記錄。"""
    if not os.path.exists(BENTO_PATH):
        return "（尚無便當記錄）"
    with open(BENTO_PATH, "r", encoding="utf-8") as f:
        return f.read()


async def save_bento_plan(plan: str) -> str:
    """儲存本週便當計畫到 bento_history.md。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    week = datetime.now().strftime("%Y 第 %W 週")

    entry = f"\n## {week}（記錄於 {now}）\n\n{plan}\n\n---"

    if os.path.exists(BENTO_PATH):
        with open(BENTO_PATH, "r", encoding="utf-8") as f:
            existing = f.read()
    else:
        existing = "# 便當計畫歷史記錄\n"

    with open(BENTO_PATH, "w", encoding="utf-8") as f:
        f.write(existing + entry)

    return f"已儲存本週便當計畫（{week}）"
