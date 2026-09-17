import os
import re
from datetime import datetime

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(_DATA_DIR, exist_ok=True)
AUDIT_LOG_PATH = os.path.join(_DATA_DIR, "it_ops_audit.md")

# action、target 分開檢查：組合式判斷（動詞 + 名詞可能分別落在 action 或 target 欄位），
# 例如 action="刪除"、target="HR 部門員工資料庫" 也要能判斷為高風險。
HIGH_RISK_ACTION_VERBS = [
    r"刪除", r"delete", r"drop", r"清空", r"truncate",
    r"重置", r"reset", r"格式化", r"format", r"重啟", r"restart",
    r"停用", r"disable", r"停止", r"停機", r"shutdown",
]

HIGH_RISK_TARGET_NOUNS = [
    r"資料庫", r"database", r"\bdb\b",
    r"密碼", r"password",
    r"使用者", r"帳號", r"帳戶", r"\buser\b", r"account",
    r"硬碟", r"磁碟", r"disk", r"drive",
    r"服務", r"伺服器", r"server", r"service", r"正式環境", r"production", r"\bprod\b",
]

# 少數單一片語本身就足以判定高風險，不需要動詞 + 名詞都出現
HIGH_RISK_COMBINED_PATTERNS = [
    r"rm\s+-rf", r"drop\s+database", r"delete\s+database", r"truncate\s+table",
    r"reset.*password", r"delete\s+user", r"format\s+(disk|drive|c:)",
]


def _is_high_risk(action: str, target: str) -> bool:
    combined = f"{action} {target}".lower()
    if any(re.search(pattern, combined) for pattern in HIGH_RISK_COMBINED_PATTERNS):
        return True
    has_verb = any(re.search(verb, action.lower()) for verb in HIGH_RISK_ACTION_VERBS)
    has_noun = any(re.search(noun, combined) for noun in HIGH_RISK_TARGET_NOUNS)
    return has_verb and has_noun


def _log(action: str, target: str, decision: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"- [{now}] action=`{action}` target=`{target}` → **{decision}**\n"

    if os.path.exists(AUDIT_LOG_PATH):
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            existing = f.read()
    else:
        existing = "# IT Ops 操作稽核紀錄\n\n"

    with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
        f.write(existing + entry)


async def execute_it_operation(action: str, target: str) -> str:
    """
    模擬執行一項 IT 維運操作，執行前先經過 guardrail policy check。
    刪除資料庫、重置密碼、刪除帳號、重啟正式環境服務等高風險操作會被攔截，不會真的「執行」。
    """
    if _is_high_risk(action, target):
        _log(action, target, "已攔截")
        return (
            f"🚫 已被 Guardrail 攔截：「{action}」對「{target}」屬於高風險操作，"
            f"未取得二次授權前不會執行，已記錄稽核紀錄。請改走正式變更審核流程（Change Request）。"
        )

    _log(action, target, "已模擬執行")
    return f"✅ 已模擬執行：「{action}」對「{target}」，操作已記錄於稽核紀錄。"
