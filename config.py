import os
from datetime import datetime
import zoneinfo
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Секреты никогда не должны иметь значение по умолчанию в исходниках.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Каталог данных можно смонтировать как постоянный диск в production.
DATA_DIR = os.path.abspath(os.getenv("DATA_DIR", os.path.dirname(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)

# Database Path
DB_FILE = os.path.join(DATA_DIR, "cats.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

def _parse_user_ids(value: str) -> frozenset[int]:
    result = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            try:
                result.add(int(item))
            except ValueError:
                raise RuntimeError("ALLOWED_USER_IDS must be a comma-separated list of Telegram user IDs")
    return frozenset(result)

ALLOWED_USER_IDS = _parse_user_ids(os.getenv("ALLOWED_USER_IDS", ""))
WEBAPP_AUTH_MAX_AGE_SECONDS = int(os.getenv("WEBAPP_AUTH_MAX_AGE_SECONDS", "86400"))

# Timezone (По умолчанию московское время / UTC+3)
TIMEZONE_NAME = os.getenv("BOT_TIMEZONE", "Europe/Moscow")

# Web Server & Mini App Port
WEB_PORT = int(os.getenv("PORT", 8080))

# Mini App URL (если бот развернут на Render или проброшен через ngrok/localtunnel)
WEB_APP_URL = os.getenv("WEB_APP_URL", "")

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

# Версия бота и список последних изменений (рассылается всем при перезапуске/деплое)
BOT_VERSION = "2.7.0"
RECENT_CHANGES = [
    "💾 ВЕЧНАЯ БАЗА ДАННЫХ: авто-снапшот и облачное сохранение — кормления и стрики больше никогда не сбросятся!",
    "📸 СЕМЕЙНЫЙ ФОТОАЛЬБОМ: можно прикрепить фото при кормлении (отправляется сестре в чат и сохраняется в галерею)",
    "🐾 ТАМАГОЧИ 2.0: ласка котика кликом, вылетающие сердечки, звуки мурчания, хрума корма и воды",
    "🩺 AI ВЕТ-КОНСУЛЬТАНТ: экспертные ответы по питанию, токсичной еде, травам и расчету дозировок по весу котиков (команда /ask и в Mini App)",
    "💬 МЕМНЫЕ МЫСЛИ: живые фразы Тучи и Грунтика от первого лица при каждом действии"
]

