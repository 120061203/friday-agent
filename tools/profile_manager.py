import os
import re
from datetime import datetime

PROFILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "profile.md")


async def read_profile() -> str:
    """讀取使用者偏好檔案 profile.md。"""
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "（profile.md 尚未建立）"


async def update_profile(key: str, value: str) -> str:
    """
    更新 profile.md 中特定欄位的值。
    key: 欄位名稱，例如「上次查詢活動」
    value: 新的值
    """
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_line = f"- {key}：{value}（{now}）"
        pattern = rf"(- {re.escape(key)}：).*"

        if re.search(pattern, content):
            updated = re.sub(pattern, new_line, content)
        else:
            updated = content + f"\n{new_line}"

        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            f.write(updated)

        return f"已更新「{key}」"
    except Exception as e:
        return f"更新失敗：{e}"
