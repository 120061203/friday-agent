import re

_RULES = [
    (r"vpn|網路|連線|wifi|dns", "Network Team", "P2"),
    (r"密碼|帳號|帳戶|active directory|\bad\b|登入|鎖定", "Identity & Access Team", "P2"),
    (r"當機|crash|down|無法開機|藍屏|服務中斷", "Infrastructure Team", "P1"),
    (r"軟體|application|安裝|授權|license", "Application Support Team", "P3"),
]

_URGENT_HINT = r"全球|多人|大量|所有人|production|正式環境|緊急"


async def classify_ticket(title: str, content: str) -> str:
    """
    依標題與內容的關鍵字，模擬 ITSM 工單分類：判斷應分派的團隊與優先級（P1/P2/P3）。
    """
    text = f"{title} {content}".lower()

    team = "General IT Support"
    priority = "P3"
    for pattern, matched_team, matched_priority in _RULES:
        if re.search(pattern, text):
            team = matched_team
            priority = matched_priority
            break

    if re.search(_URGENT_HINT, text):
        priority = "P1"

    return (
        "**工單分類結果**\n"
        f"- 標題：{title}\n"
        f"- 分派團隊：{team}\n"
        f"- 優先級：{priority}\n"
        "- 判斷依據：關鍵字比對（模擬 ITSM 分類引擎，正式環境應接 ServiceNow / Jira Service Management API）"
    )
