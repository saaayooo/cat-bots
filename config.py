import os
from datetime import datetime
import zoneinfo

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8728753257:AAGcB2aPpp8C3CN9KxjwJkLz9wWqqg4MLmo")

# Database Path
DB_FILE = os.path.join(os.path.dirname(__file__), "cats.db")

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
BOT_VERSION = "2.6.0"
RECENT_CHANGES = [
    "🔔 Уведомления обо ВСЕХ действиях в Mini App: квесты (взять/сдать/вернуть), кормление, вода, лоток, игры",
    "✏️ Быстрое редактирование котиков (кличка, вес, порода, аватарка) прямо в Mini App по клику",
    "📋 Разделы Mini App: Тамагочи, Квесты, Вет-паспорт, Расходы",
    "🚀 Оповещение всех о перезапуске бота и кратком списке изменений",
    "🌿 Болотный зеленый стиль оформления для Тучи и Грунтика"
]
