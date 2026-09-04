import os
from datetime import datetime
import zoneinfo

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8728753257:AAGcB2aPpp8C3CN9KxjwJkLz9wWqqg4MLmo")

# Database Path
DB_FILE = os.path.join(os.path.dirname(__file__), "cats.db")

# Timezone (По умолчанию московское время / UTC+3)
TIMEZONE_NAME = os.getenv("BOT_TIMEZONE", "Europe/Moscow")

def get_current_time():
    """Возвращает текущее время с учетом часового пояса"""
    try:
        tz = zoneinfo.ZoneInfo(TIMEZONE_NAME)
        return datetime.now(tz)
    except Exception:
        return datetime.now().astimezone()

def format_time(dt: datetime) -> str:
    """Форматирует время в удобный вид: ЧЧ:ММ (ДД.ММ.ГГГГ)"""
    return dt.strftime("%H:%M (%d.%m.%Y)")
