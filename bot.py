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
    btn_quests = types.KeyboardButton("📋 Доска квестов")
    btn_feed = types.KeyboardButton("🐾 Кот покормлен")
    btn_status = types.KeyboardButton("📊 Статус")
    markup.row(btn_quests)
    markup.row(btn_feed, btn_status)
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

def build_quest_board(current_user_id: int):
    """Формирует текст доски квестов и интерактивные кнопки"""
    quests = database.get_today_quests()
    now = get_current_time()
    date_str = now.strftime("%d.%m.%Y")
    
    text = f"📋 <b>ДОСКА КВЕСТОВ НА {date_str}:</b>\n\n"
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for q in quests:
        title = q["title"]
        status = q["status"]
        
        if status == "available":
            status_text = "🟢 <b>Свободен</b> (можно взять)"
            # Кнопка взять
            btn_take = types.InlineKeyboardButton(f"✋ Взять: {title}", callback_data=f"take:{q['id']}")
            btn_done = types.InlineKeyboardButton(f"⚡ Сразу выполнено", callback_data=f"done:{q['id']}")
            markup.row(btn_take, btn_done)
            
        elif status == "taken":
            taken_name = q["taken_by_name"]
            taken_at_str = q["taken_at"].strftime("%H:%M") if q["taken_at"] else ""
            if q["taken_by_id"] == current_user_id:
                status_text = f"🟡 <b>В работе у ВАС</b> (взят в {taken_at_str})"
                btn_done = types.InlineKeyboardButton(f"✅ Выполнить: {title}", callback_data=f"done:{q['id']}")
                btn_drop = types.InlineKeyboardButton("↩️ Отказаться", callback_data=f"drop:{q['id']}")
                markup.row(btn_done, btn_drop)
            else:
                status_text = f"🟡 <b>Выполняет {taken_name}</b> (взят в {taken_at_str})"
                
        elif status == "completed":
            comp_name = q["completed_by_name"]
            comp_at_str = q["completed_at"].strftime("%H:%M") if q["completed_at"] else ""
            status_text = f"✅ <b>Выполнен ({comp_name} в {comp_at_str})</b>"
            
        elif status == "locked":
            if q["type"] == "feed_morning":
                status_text = "⏳ <i>Откроется в 08:00 утра</i>"
            elif q["type"] == "feed_evening":
                status_text = "⏳ <i>Откроется в 20:00 вечера</i>"
            elif q["type"] == "litter_deep":
                days = q.get("days_left", 14)
                status_text = f"⏳ <i>Следующая чистка через {days} дн.</i>"
            else:
                status_text = "⏳ <i>Пока недоступен</i>"
                
        text += f"{title}\n└ Статус: {status_text}\n\n"
        
    # Кнопка обновить
    btn_refresh = types.InlineKeyboardButton("🔄 Обновить доску", callback_data="refresh")
    markup.row(btn_refresh)
    
    return text, markup

def notify_other_chats(current_chat_id: int, text: str):
    """Отправляет уведомление во все остальные личные чаты"""
    all_chats = database.get_all_chats()
    for chat in all_chats:
        if chat["chat_type"] == "private" and chat["chat_id"] != current_chat_id:
            try:
                bot.send_message(chat["chat_id"], text, reply_markup=get_main_keyboard())
                logger.info(f"Notification sent to private chat {chat['chat_id']}")
            except Exception as e:
                logger.warning(f"Failed to notify chat {chat['chat_id']}: {e}")

@bot.message_handler(commands=["start", "help"])
def handle_start(message: types.Message):
    """Регистрация чата и приветствие"""
    try:
        user_name = get_user_display_name(message.from_user)
        chat_type = message.chat.type
        chat_title = message.chat.title or user_name
        
        database.register_chat(message.chat.id, chat_type, chat_title)
        
        welcome_text = (
            f"👋 Привет, <b>{user_name}</b>!\n\n"
            f"Я бот для отслеживания ухода за котиками 🐱🥣\n\n"
            f"<b>Квесты для двоих:</b>\n"
            f"• <b>🥣 Кормление</b>: утреннее (с 08:00) и вечернее (с 20:00)\n"
            f"• <b>💧 Свежая вода</b>: раз в сутки\n"
            f"• <b>🚽 Лоток</b>: быстрая чистка (раз в сутки) и генеральная (раз в 2 недели)\n"
            f"• <b>🎾 Игры</b>: поиграть с пушистыми\n\n"
            f"Когда кто-то <b>берет</b> или <b>выполняет</b> квест — второй человек сразу получает уведомление!\n\n"
            f"Нажмите кнопку ниже, чтобы открыть доску квестов:"
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in handle_start: {e}", exc_info=True)

@bot.message_handler(commands=["quests"])
@bot.message_handler(func=lambda msg: msg.text == "📋 Доска квестов")
def handle_quests(message: types.Message):
    """Показывает доску квестов"""
    try:
        user_name = get_user_display_name(message.from_user)
        database.register_chat(message.chat.id, message.chat.type, message.chat.title or user_name)
        
        text, markup = build_quest_board(message.from_user.id)
        bot.send_message(message.chat.id, text, reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in handle_quests: {e}", exc_info=True)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call: types.CallbackQuery):
    """Обработка нажатий на инлайн кнопки квестов"""
    try:
        user_name = get_user_display_name(call.from_user)
        user_id = call.from_user.id
        data = call.data
        
        if data == "refresh":
            text, markup = build_quest_board(user_id)
            try:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
            except Exception:
                pass
            bot.answer_callback_query(call.id, "Доска обновлена! 🔄")
            return
            
        action, qid = data.split(":", 1)
        
        if action == "take":
            ok, msg, info = database.take_quest(qid, user_id, user_name)
            bot.answer_callback_query(call.id, msg)
            if ok:
                # Обновляем сообщение доски
                text, markup = build_quest_board(user_id)
                try:
                    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
                except Exception:
                    pass
                # Уведомляем второго человека
                notify_text = (
                    f"📢 <b>Уведомление по квестам:</b>\n"
                    f"👤 <b>{user_name}</b> взял(а) квест <b>«{info['title']}»</b>!\n"
                    f"Скоро всё сделает 🐱👌"
                )
                notify_other_chats(call.message.chat.id, notify_text)
                
        elif action == "done":
            ok, msg, info = database.complete_quest(qid, user_id, user_name)
            bot.answer_callback_query(call.id, msg)
            if ok:
                text, markup = build_quest_board(user_id)
                try:
                    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
                except Exception:
                    pass
                time_str = info["completed_at"].strftime("%H:%M")
                notify_text = (
                    f"🎉 <b>Квест выполнен:</b>\n"
                    f"👤 <b>{user_name}</b> выполнил(а) квест <b>«{info['title']}»</b> в <b>{time_str}</b>!\n"
                    f"Котики сыты и довольны! 🐱🥣✨"
                )
                notify_other_chats(call.message.chat.id, notify_text)
                
        elif action == "drop":
            ok, msg, info = database.drop_quest(qid, user_id)
            bot.answer_callback_query(call.id, msg)
            if ok:
                text, markup = build_quest_board(user_id)
                try:
                    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
                except Exception:
                    pass
                notify_text = (
                    f"ℹ️ <b>{user_name}</b> освободил(а) квест <b>«{info['title']}»</b>.\n"
                    f"Он снова свободен для выполнения!"
                )
                notify_other_chats(call.message.chat.id, notify_text)

    except Exception as e:
        logger.error(f"Error in handle_callback: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "Произошла ошибка, попробуйте еще раз.")
        except Exception:
            pass

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
    """Быстрое кормление по кнопке"""
    try:
        user_name = get_user_display_name(message.from_user)
        user_id = message.from_user.id
        current_chat_id = message.chat.id
        current_chat_type = message.chat.type
        chat_title = message.chat.title or user_name

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

        # Автоматически закрываем актуальный квест на кормление (утренний или вечерний), если он был открыт
        today_str = now.strftime("%Y-%m-%d")
        qtype = "feed_morning" if now.hour < 20 else "feed_evening"
        qid = f"{qtype}_{today_str}"
        try:
            database.complete_quest(qid, user_id, user_name)
        except Exception:
            pass

        # Сообщение текущему пользователю
        msg_current = (
            f"🐾 <b>{user_name}</b> покормил(а) кота в <b>{time_str}</b> ({date_str})!\n"
            f"Котик сыт и счастлив! 🐱🥣✨"
        )
        bot.send_message(current_chat_id, msg_current, reply_markup=get_main_keyboard())

        # Оповещаем второго человека
        if current_chat_type == "private":
            notify_text = (
                f"📢 <b>Уведомление:</b>\n"
                f"🐾 <b>{user_name}</b> покормил(а) кота в <b>{time_str}</b> ({date_str})!\n"
                f"Кормить пока не нужно 🐱❤️"
            )
            notify_other_chats(current_chat_id, notify_text)
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
