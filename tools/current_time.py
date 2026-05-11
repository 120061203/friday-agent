from datetime import datetime
import zoneinfo


async def get_current_time(timezone: str = "Asia/Taipei") -> str:
    """取得目前的日期與時間。"""
    try:
        tz = zoneinfo.ZoneInfo(timezone)
    except Exception:
        tz = zoneinfo.ZoneInfo("Asia/Taipei")

    now = datetime.now(tz)
    return now.strftime(f"%Y-%m-%d %H:%M:%S ({timezone})")
