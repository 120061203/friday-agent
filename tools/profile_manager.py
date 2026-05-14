import os
import re
from datetime import datetime

PROFILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "profile.md")


DEFAULT_PROFILE = """# Friday Agent — 使用者偏好檔案

## 基本資訊
- 常駐城市：台北
- 時區：Asia/Taipei

## 飲食偏好
- 喜歡：日式料理、台式家常菜
- 不吃：（未設定）
- 過敏：無

## 活動偏好
- 喜歡：展覽、電影、市集

## 週末習慣
- 週五下班時間：約 18:00
- 偏好行程密度：適中
- 餐廳預算：NT$300-800 / 人

## 歷史記錄
- 上次查詢活動：
- 上次便當計畫：
- 上次餐廳推薦：
"""


async def read_profile() -> str:
    """讀取使用者偏好檔案 profile.md，不存在時自動建立預設檔案。"""
    if not os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            f.write(DEFAULT_PROFILE)
        return DEFAULT_PROFILE
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return f.read()


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
