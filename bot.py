import sys
import os

# Настройка кодировки вывода для Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import logging
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import telebot
from telebot import types

# Легковесный веб-сервер для Render (Web Service Health Check)
def start_render_health_server():
    port_str = os.getenv("PORT")
    if not port_str:
        return
    port = int(port_str)
    
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot is healthy!")
            
        def log_message(self, format, *args):
            pass # Не засорять логи

    def serve():
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        server.serve_forever()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    print(f"INFO: Render Web Service health-сервер запущен на порту {port}")

start_render_health_server()

from config import BOT_TOKEN, get_current_time, format_time
import database
from tunnel import setup_telegram_proxy

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("cat_bot")

# Инициализация туннеля (если Telegram API заблокирован провайдером)
setup_telegram_proxy()

# Инициализация БД
database.init_db()

# Настройка таймаутов telebot (для надежного long-polling)
telebot.apihelper.READ_TIMEOUT = 60
telebot.apihelper.CONNECT_TIMEOUT = 30

# Создание экземпляра бота
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Главная клавиатура
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_feed = types.KeyboardButton("🐾 Кот покормлен")
    btn_status = types.KeyboardButton("📊 Статус")
    markup.row(btn_feed)
    markup.row(btn_status)
    return markup

def get_user_display_name(user: types.User) -> str:
    """Возвращает удобное имя пользователя"""
    name = user.first_name or "Кто-то"
    if user.last_name:
        name += f" {user.last_name}"
    return name

def format_time_ago(feeding_dt: datetime) -> str:
    """Форматирует разницу во времени человекопонятно"""
    now = get_current_time()
    diff_seconds = int((now - feeding_dt).total_seconds())

    if diff_seconds < 60:
        return "только что"
    
    minutes = diff_seconds // 60
    hours = minutes // 60
    
    if hours == 0:
        return f"{minutes} мин. назад"
    
    rem_minutes = minutes % 60
    if hours < 24:
        if rem_minutes > 0:
            return f"{hours} ч. {rem_minutes} мин. назад"
        return f"{hours} ч. назад"
    
    days = hours // 24
    return f"{days} дн. назад"

@bot.message_handler(commands=["start", "help"])
def handle_start(message: types.Message):
    """Регистрация чата и приветствие"""
    try:
        user_name = get_user_display_name(message.from_user)
        chat_type = message.chat.type
        chat_title = message.chat.title or user_name
        
        # Сохраняем чат в базу
        database.register_chat(message.chat.id, chat_type, chat_title)
        
        welcome_text = (
            f"👋 Привет, <b>{user_name}</b>!\n\n"
            f"Я бот для отслеживания кормления котиков 🐱🥣\n\n"
            f"<b>Как я работаю:</b>\n"
            f"• Нажмите кнопку <b>«🐾 Кот покормлен»</b>, когда насыпали корм.\n"
            f"• Я зафиксирую точное время и автора.\n"
            f"• Если мы в общей группе — я напишу туда. Если в личке — я отправлю уведомление второму человеку, чтобы кота не перекормили!\n\n"
            f"Нажмите кнопку ниже, чтобы проверить:"
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in handle_start: {e}", exc_info=True)

@bot.message_handler(commands=["status"])
@bot.message_handler(func=lambda msg: msg.text == "📊 Статус")
def handle_status(message: types.Message):
    """Показывает статус последнего кормления и историю"""
    try:
        last = database.get_last_feeding()
        
        if not last:
            bot.send_message(
                message.chat.id,
                "🥣 Кота еще ни разу не отмечали покормленным!\nНажмите кнопку <b>«🐾 Кот покормлен»</b>.",
                reply_markup=get_main_keyboard()
            )
            return

        time_str = last["fed_at"].strftime("%H:%M")
        date_str = last["fed_at"].strftime("%d.%m.%Y")
        ago_str = format_time_ago(last["fed_at"])
        
        text = (
            f"📊 <b>Статус кормления:</b>\n\n"
            f"🐱 Последний раз кота покормил(а):\n"
            f"👤 <b>{last['user_name']}</b>\n"
            f"⏰ Время: <b>{time_str}</b> ({date_str})\n"
            f"⏳ Было: <b>{ago_str}</b>\n\n"
        )
        
        # Последние несколько записей
        recents = database.get_recent_feedings(limit=4)
        if len(recents) > 1:
            text += "📜 <b>История последних кормлений:</b>\n"
            for item in recents:
                i_time = item["fed_at"].strftime("%H:%M (%d.%m)")
                text += f"• {item['user_name']} — {i_time}\n"

        bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in handle_status: {e}", exc_info=True)

@bot.message_handler(func=lambda msg: msg.text == "🐾 Кот покормлен")
def handle_cat_fed(message: types.Message):
    """Обработка нажатия кнопки 'Кот покормлен'"""
    try:
        user_name = get_user_display_name(message.from_user)
        user_id = message.from_user.id
        current_chat_id = message.chat.id
        current_chat_type = message.chat.type
        chat_title = message.chat.title or user_name

        # Обновляем регистрацию чата
        database.register_chat(current_chat_id, current_chat_type, chat_title)

        now = get_current_time()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d.%m")

        # Защита от случайного повторного нажатия (в пределах 60 секунд)
        last = database.get_last_feeding()
        if last:
            diff_sec = (now - last["fed_at"]).total_seconds()
            if diff_sec < 60:
                bot.send_message(
                    current_chat_id,
                    f"⚠️ Кота уже только что покормил(а) <b>{last['user_name']}</b> "
                    f"в <b>{last['fed_at'].strftime('%H:%M')}</b> (меньше минуты назад)!\n"
                    f"Котик точно сыт 😺",
                    reply_markup=get_main_keyboard()
                )
                return

        # Записываем кормление в базу данных
        database.add_feeding(user_id, user_name, now)

        # Сообщение текущему пользователю / в текущий чат
        msg_current = (
            f"🐾 <b>{user_name}</b> покормил(а) кота в <b>{time_str}</b> ({date_str})!\n"
            f"Котик сыт и счастлив! 🐱🥣✨"
        )
        bot.send_message(current_chat_id, msg_current, reply_markup=get_main_keyboard())

        # Если действие произошло в личном чате, оповещаем второго человека (все другие личные чаты)
        if current_chat_type == "private":
            all_chats = database.get_all_chats()
            notify_text = (
                f"📢 <b>Уведомление:</b>\n"
                f"🐾 <b>{user_name}</b> покормил(а) кота в <b>{time_str}</b> ({date_str})!\n"
                f"Кормить пока не нужно 🐱❤️"
            )
            for chat in all_chats:
                if chat["chat_type"] == "private" and chat["chat_id"] != current_chat_id:
                    try:
                        bot.send_message(chat["chat_id"], notify_text, reply_markup=get_main_keyboard())
                        logger.info(f"Notification sent to private chat {chat['chat_id']}")
                    except Exception as e:
                        logger.warning(f"Failed to notify chat {chat['chat_id']}: {e}")
    except Exception as e:
        logger.error(f"Error in handle_cat_fed: {e}", exc_info=True)

def main():
    while True:
        try:
            me = bot.get_me()
            print(f"🤖 Бот успешно запущен: @{me.username} ({me.first_name})")
            print("🐾 Ожидание сообщений от пользователей...")
            bot.infinity_polling(timeout=10, long_polling_timeout=10)
        except Exception as e:
            logger.error(f"Polling crashed with error: {e}. Перезапуск через 3 сек...", exc_info=True)
            time.sleep(3)

if __name__ == "__main__":
    main()
