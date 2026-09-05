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
import re
from datetime import datetime
import telebot
from telebot import types

from config import BOT_TOKEN, WEB_PORT, WEB_APP_URL, get_current_time, format_time, BOT_VERSION, RECENT_CHANGES
import database
from tunnel import setup_telegram_proxy
from web_server import start_web_server
from scheduler import start_scheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("cat_bot")

# Инициализация туннеля (если Telegram API заблокирован)
setup_telegram_proxy()

# Инициализация БД (все таблицы и профили 2 котиков)
database.init_db()

# Настройка таймаутов telebot (для надежного long-polling)
telebot.apihelper.READ_TIMEOUT = 60
telebot.apihelper.CONNECT_TIMEOUT = 30

# Создание экземпляра бота
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Главная клавиатура: только Mini App и Статус
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if WEB_APP_URL and WEB_APP_URL.startswith("https://"):
        btn_app = types.KeyboardButton("📱 Открыть Mini App", web_app=types.WebAppInfo(url=WEB_APP_URL))
    else:
        btn_app = types.KeyboardButton("📱 Mini App")
    btn_status = types.KeyboardButton("📊 Статус")
    markup.row(btn_app)
    markup.row(btn_status)
    return markup

def notify_web_action(user_id: int, user_name: str, other_text: str, sender_text: str = None):
    """Уведомляет зарегистрированные личные чаты о действиях из Mini App"""
    # Если передан валидный ID пользователя, регистрируем его в базе
    if user_id and int(user_id) > 100:
        database.register_chat(int(user_id), "private", user_name)

    all_chats = database.get_all_chats()
    if not all_chats:
        return

    # Если в базе зарегистрирован только 1 чат (например, при тестах)
    if len(all_chats) == 1:
        target_chat = all_chats[0]
        text_to_send = sender_text if (sender_text and target_chat["chat_id"] == user_id) else other_text
        try:
            bot.send_message(target_chat["chat_id"], text_to_send, reply_markup=get_main_keyboard())
        except Exception as e:
            logger.warning(f"Failed to notify single chat {target_chat['chat_id']}: {e}")
        return

    # Если зарегистрировано 2 или более чатов
    for chat in all_chats:
        cid = chat["chat_id"]
        if cid == user_id:
            if sender_text:
                try:
                    bot.send_message(cid, sender_text, reply_markup=get_main_keyboard())
                except Exception as e:
                    logger.warning(f"Failed to send confirmation to sender {cid}: {e}")
        else:
            try:
                bot.send_message(cid, other_text, reply_markup=get_main_keyboard())
            except Exception as e:
                logger.warning(f"Failed to notify partner chat {cid}: {e}")

def broadcast_restart_notification():
    """Рассылает всем зарегистрированным пользователям уведомление о перезапуске бота и внесенных изменениях"""
    try:
        now = get_current_time()
        now_str = now.strftime("%H:%M (%d.%m.%Y)")
        
        last_notified_time = database.get_bot_setting("last_restart_time")
        if last_notified_time:
            try:
                last_dt = datetime.fromisoformat(last_notified_time)
                # Защита от спама при секундных перезапусках long-polling: пауза минимум 45 сек
                if (now - last_dt).total_seconds() < 45:
                    logger.info("Restart notification skipped (already sent recently)")
                    return
            except Exception:
                pass

        database.set_bot_setting("last_restart_time", now.isoformat())
        database.set_bot_setting("last_restart_version", BOT_VERSION)

        changes_list = "\n".join([f"• {c}" for c in RECENT_CHANGES])
        cats = database.get_cats()
        cat_names = " & ".join([f"{c['emoji']} <b>{c['name']}</b>" for c in cats])

        msg = (
            f"🚀 <b>КОШАЧИЙ БОТ ОБНОВЛЕН И ПЕРЕЗАПУЩЕН! (v{BOT_VERSION})</b>\n"
            f"⏱ <i>Время перезапуска: {now_str}</i>\n\n"
            f"📌 <b>Кратко о внесенных изменениях:</b>\n"
            f"{changes_list}\n\n"
            f"🐾 Питомцы: {cat_names}\n"
            f"Все кнопки Mini App и уведомления готовы к работе! 🐱✨"
        )

        all_chats = database.get_all_chats()
        if not all_chats:
            logger.info("No registered chats to broadcast restart notification.")
            return

        for chat in all_chats:
            try:
                bot.send_message(chat["chat_id"], msg, reply_markup=get_main_keyboard())
                logger.info(f"Broadcasted restart notification to chat {chat['chat_id']}")
            except Exception as e:
                logger.warning(f"Failed to send restart broadcast to {chat['chat_id']}: {e}")
    except Exception as e:
        logger.error(f"Error in broadcast_restart_notification: {e}", exc_info=True)

# Запуск встроенного веб-сервера для Mini App и Render Health Check
start_web_server(WEB_PORT, notify_fn=notify_web_action)

# Запуск фонового планировщика умных напоминаний
start_scheduler(bot, get_main_keyboard)

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

def notify_other_chats(current_chat_id: int, text: str):
    """Отправляет уведомление во все остальные зарегистрированные личные чаты"""
    all_chats = database.get_all_chats()
    for chat in all_chats:
        if chat["chat_type"] == "private" and chat["chat_id"] != current_chat_id:
            try:
                bot.send_message(chat["chat_id"], text, reply_markup=get_main_keyboard())
                logger.info(f"Notification sent to private chat {chat['chat_id']}")
            except Exception as e:
                logger.warning(f"Failed to notify chat {chat['chat_id']}: {e}")

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
            btn_take = types.InlineKeyboardButton(f"✋ Взять: {title}", callback_data=f"take:{q['id']}")
            btn_done = types.InlineKeyboardButton("⚡ Сразу выполнено", callback_data=f"done:{q['id']}")
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
        
    btn_refresh = types.InlineKeyboardButton("🔄 Обновить доску", callback_data="refresh")
    markup.row(btn_refresh)
    
    return text, markup

# ================= КОМАНДЫ И ОБРАБОТЧИКИ =================

@bot.message_handler(commands=["start", "help"])
def handle_start(message: types.Message):
    """Регистрация чата и расширенное приветствие"""
    try:
        user_name = get_user_display_name(message.from_user)
        chat_type = message.chat.type
        chat_title = message.chat.title or user_name
        
        database.register_chat(message.chat.id, chat_type, chat_title)
        cats = database.get_cats()
        cat_names = " & ".join([f"{c['emoji']} {c['name']}" for c in cats])
        
        welcome_text = (
            f"👋 Привет, <b>{user_name}</b>!\n\n"
            f"Я бот для совместного ухода за нашими любимыми котиками: <b>{cat_names}</b>! 🐱✨\n\n"
            f"<b>Как ухаживать за котиками:</b>\n"
            f"• 📱 <b>Открыть Mini App</b> — красивый Тамагочи с нашими котиками. В 1 тап можно покормить, налить воду, убрать лоток и поиграть!\n"
            f"• 📊 <b>Статус</b> — быстрая сводка о настроении, сытости и последнем кормлении прямо в чате.\n\n"
            f"При любом действии в Mini App бот сразу пришлет уведомление второму человеку, чтобы вы всегда знали, что котики окружены заботой! ❤️\n\n"
            f"Выберите действие на кнопках ниже:"
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in handle_start: {e}", exc_info=True)

@bot.message_handler(commands=["app"])
@bot.message_handler(func=lambda msg: msg.text in ("📱 Mini App", "📱 Открыть Mini App"))
def handle_miniapp_button(message: types.Message):
    """Открывает или отправляет ссылку на Telegram Mini App"""
    try:
        markup = types.InlineKeyboardMarkup()
        if WEB_APP_URL and WEB_APP_URL.startswith("https://"):
            markup.add(types.InlineKeyboardButton("✨ Открыть Кошачий Хаб", web_app=types.WebAppInfo(url=WEB_APP_URL)))
            msg = (
                "📱 <b>Telegram Mini App «Кошачий Хаб»</b>\n\n"
                "Нажмите кнопку ниже, чтобы открыть интерактивный дашборд с тамагочи, квестами, вет-паспортом и расходами:"
            )
        else:
            msg = (
                "📱 <b>Telegram Mini App</b>\n\n"
                f"Локальный веб-интерфейс доступен по адресу: <code>http://localhost:{WEB_PORT}</code>\n\n"
                "💡 <i>Чтобы открывать Mini App прямо в Telegram через кнопку, укажите публичную HTTPS-ссылку (ngrok, localtunnel или URL с Render) в переменной окружения WEB_APP_URL.</i>"
            )
            markup.add(types.InlineKeyboardButton("🌐 Открыть в браузере (локально)", url=f"http://localhost:{WEB_PORT}"))

        bot.send_message(message.chat.id, msg, reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in handle_miniapp_button: {e}", exc_info=True)

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
    """Обработка инлайн-кнопок"""
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
            
        if ":" in data:
            action, qid = data.split(":", 1)
            
            if action == "take":
                ok, msg, info = database.take_quest(qid, user_id, user_name)
                bot.answer_callback_query(call.id, msg)
                if ok:
                    text, markup = build_quest_board(user_id)
                    try:
                        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
                    except Exception:
                        pass
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
    """Показывает Тамагочи-статус настроения котиков, сытость, стрики и историю"""
    try:
        t_status = database.get_tamagotchi_status()
        last = t_status["last_feeding"]
        streak = t_status["streak"]
        cats = t_status["cats"]

        cat_names = " и ".join([f"{c['name']} ({c['weight']} кг)" for c in cats])

        text = (
            f"📊 <b>ТАМАГОЧИ-СТАТУС КОТИКОВ:</b>\n\n"
            f"🐾 Питомцы: <b>{cat_names}</b>\n"
            f"{t_status['mood_emoji']} Настроение: <b>{t_status['mood_title']}</b>\n"
            f"<i>{t_status['mood_desc']}</i>\n\n"
            f"<b>Жизненные показатели:</b>\n"
            f"🥣 Сытость: <b>{t_status['satiety_percent']}%</b>\n"
            f"💧 Вода: <b>{t_status['water_percent']}%</b>\n"
            f"🚽 Чистота лотка: <b>{t_status['litter_percent']}%</b>\n"
            f"🎾 Игры: <b>{t_status['play_percent']}%</b>\n\n"
            f"🔥 <b>Стрик идеального ухода:</b> {streak['current_streak']} дн. (рекорд: {streak['best_streak']} дн.)\n\n"
        )

        if last:
            time_str = last["fed_at"].strftime("%H:%M")
            date_str = last["fed_at"].strftime("%d.%m.%Y")
            ago_str = format_time_ago(last["fed_at"])
            text += f"🐱 Последнее кормление: <b>{last['user_name']}</b> в {time_str} ({ago_str})\n\n"
        else:
            text += "🐱 Котиков еще не кормили сегодня!\n\n"

        recents = database.get_recent_feedings(limit=3)
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
                    f"⚠️ Котиков уже только что покормил(а) <b>{last['user_name']}</b> "
                    f"в <b>{last['fed_at'].strftime('%H:%M')}</b> (меньше минуты назад)!\n"
                    f"Котики сыты и довольно мурчат 😺",
                    reply_markup=get_main_keyboard()
                )
                return

        database.add_feeding(user_id, user_name, now)

        today_str = now.strftime("%Y-%m-%d")
        qtype = "feed_morning" if now.hour < 20 else "feed_evening"
        qid = f"{qtype}_{today_str}"
        try:
            database.complete_quest(qid, user_id, user_name)
        except Exception:
            pass

        msg_current = (
            f"🐾 <b>{user_name}</b> покормил(а) котиков в <b>{time_str}</b> ({date_str})!\n"
            f"Оба котика сыты, счастливы и мурчат! 🐱🥣✨"
        )
        bot.send_message(current_chat_id, msg_current, reply_markup=get_main_keyboard())

        if current_chat_type == "private":
            notify_text = (
                f"📢 <b>Уведомление:</b>\n"
                f"🐾 <b>{user_name}</b> покормил(а) котиков в <b>{time_str}</b> ({date_str})!\n"
                f"Кормить пока не нужно 🐱❤️"
            )
            notify_other_chats(current_chat_id, notify_text)
    except Exception as e:
        logger.error(f"Error in handle_cat_fed: {e}", exc_info=True)

# ================= ВЕТ-ПАСПОРТ =================

@bot.message_handler(commands=["vet"])
@bot.message_handler(func=lambda msg: msg.text == "🩺 Вет-паспорт")
def handle_vet(message: types.Message):
    """Отображение данных вет-паспорта"""
    try:
        cats = database.get_cats()
        upcoming = database.get_upcoming_vet_due(days_ahead=30)
        recent_records = database.get_vet_records(limit=6)

        text = "🩺 <b>ВЕТ-ПАСПОРТ И ЗДОРОВЬЕ КОТИКОВ</b>\n\n"
        
        # Профили
        for c in cats:
            text += f"{c['emoji']} <b>{c['name']}</b> ({c['breed']}): вес <b>{c['weight']} кг</b>\n"
        text += "\n"

        # Предстоящие процедуры
        if upcoming:
            text += "⏰ <b>Ближайшие процедуры:</b>\n"
            for u in upcoming:
                text += f"• {u['title']} ({u['cat_name']}) — <b>{u['next_due_date']}</b>\n"
            text += "\n"
        else:
            text += "✅ На ближайший месяц запланированных процедур нет.\n\n"

        # История
        if recent_records:
            text += "📜 <b>Последние записи:</b>\n"
            for r in recent_records:
                desc = f" ({r['description']})" if r['description'] else ""
                text += f"• <i>{r['record_date']}</i>: {r['title']} [{r['cat_name']}]{desc}\n"
            text += "\n"

        text += (
            "💡 <i>Чтобы добавить запись через бот, отправьте команду:\n"
            "<code>/vet_add 1 vaccine Мультифел-4 15.09.2026</code>\n"
            "Или добавьте в 1 клик через Mini App!</i>"
        )

        bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in handle_vet: {e}", exc_info=True)

@bot.message_handler(commands=["vet_add"])
def handle_vet_add(message: types.Message):
    """Добавление записи в вет-паспорт через команду: /vet_add <cat_id> <type> <title> [next_due_date]"""
    try:
        parts = message.text.split(maxsplit=4)
        if len(parts) < 4:
            bot.reply_to(message, "Формат команды:\n<code>/vet_add &lt;cat_id 1 или 2&gt; &lt;vaccine|parasite|visit|weight&gt; &lt;название&gt; [дата_следующей YYYY-MM-DD]</code>")
            return
        
        cat_id = int(parts[1])
        rec_type = parts[2]
        title = parts[3]
        next_due = parts[4] if len(parts) > 4 else None

        database.add_vet_record(cat_id, rec_type, title, next_due_date=next_due)
        bot.reply_to(message, f"✅ Запись <b>«{title}»</b> успешно внесена в вет-паспорт!")
    except Exception as e:
        bot.reply_to(message, f"Ошибка добавления: {e}")

# ================= РАСХОДЫ =================

@bot.message_handler(commands=["expenses", "expense"])
@bot.message_handler(func=lambda msg: msg.text == "💰 Расходы")
def handle_expenses(message: types.Message):
    """Сводка расходов за месяц"""
    try:
        summary = database.get_expenses_summary()
        month_str = summary["month"]
        total = summary["total_month"]

        text = (
            f"💰 <b>РАСХОДЫ НА КОТИКОВ ({month_str}):</b>\n\n"
            f"Всего за месяц: <b>{total:,.2f} ₽</b>\n\n"
        )

        if summary["by_category"]:
            text += "<b>По категориям:</b>\n"
            for c in summary["by_category"]:
                text += f"• {c['label']}: <b>{c['amount']:,.2f} ₽</b> ({c['count']} шт.)\n"
            text += "\n"

        if summary["recent"]:
            text += "📜 <b>Последние покупки:</b>\n"
            for r in summary["recent"]:
                note_str = f" ({r['note']})" if r['note'] else ""
                text += f"• {r['amount']} ₽ — {r['category_label']}{note_str} [{r['paid_by_name']}]\n"
            text += "\n"

        text += (
            "💡 <b>Быстро записать расход:</b>\n"
            "Напишите сообщение вида:\n"
            "<code>/buy 1500 корм Pro Plan</code>\n"
            "или <code>/buy 600 наполнитель</code>"
        )

        bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in handle_expenses: {e}", exc_info=True)

@bot.message_handler(commands=["buy"])
def handle_quick_buy(message: types.Message):
    """Быстрая запись расхода: /buy <сумма> <категория/описание>"""
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            bot.reply_to(message, "Используйте: <code>/buy 1500 корм Royal Canin</code>")
            return

        amount = float(parts[1].replace(",", "."))
        desc = parts[2] if len(parts) > 2 else "Покупка"

        # Автоматическое определение категории
        desc_lower = desc.lower()
        if any(w in desc_lower for w in ("корм", "еда", "вкусняш", "пауч", "паштет")):
            cat = "food"
        elif any(w in desc_lower for w in ("наполнитель", "лоток", "песок", "гранул")):
            cat = "litter"
        elif any(w in desc_lower for w in ("вет", "врач", "клиник", "таблетк", "привив", "капл")):
            cat = "vet"
        elif any(w in desc_lower for w in ("игрушк", "когтеточ", "дразнил", "мышка")):
            cat = "toys"
        else:
            cat = "other"

        user_name = get_user_display_name(message.from_user)
        user_id = message.from_user.id

        database.add_expense(amount, cat, user_id, user_name, desc)
        cat_label = database.EXPENSE_CATEGORIES.get(cat, cat)

        bot.reply_to(
            message,
            f"✅ Записано: <b>{amount:,.2f} ₽</b> в категорию <b>{cat_label}</b> ({desc})!\n"
            f"👤 Оплатил(а): {user_name}"
        )
    except Exception as e:
        bot.reply_to(message, f"Ошибка при записи расхода: {e}")

# ================= ПРОФИЛИ КОТИКОВ =================

@bot.message_handler(commands=["cats"])
def handle_cats(message: types.Message):
    """Информация о котиках и команды изменения"""
    try:
        cats = database.get_cats()
        text = "🐱 <b>НАШИ ПИТОМЦЫ:</b>\n\n"
        for c in cats:
            text += (
                f"{c['emoji']} <b>{c['name']}</b> (ID: {c['id']})\n"
                f"• Порода: {c['breed']}\n"
                f"• Вес: {c['weight']} кг\n\n"
            )
        text += (
            "💡 Чтобы обновить вес котика:\n"
            "<code>/weight 1 4.6</code> (где 1 — ID котика, 4.6 — вес в кг)\n\n"
            "💡 Чтобы изменить имя:\n"
            "<code>/rename 1 Симба</code>"
        )
        bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in handle_cats: {e}", exc_info=True)

@bot.message_handler(commands=["weight"])
def handle_weight(message: types.Message):
    """Обновление веса котика"""
    try:
        parts = message.text.split()
        cat_id = int(parts[1])
        weight = float(parts[2].replace(",", "."))
        database.update_cat(cat_id, weight=weight)
        bot.reply_to(message, f"⚖️ Вес котика ID {cat_id} обновлен: <b>{weight} кг</b>!")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: используйте <code>/weight &lt;ID 1 или 2&gt; &lt;вес&gt;</code>")

@bot.message_handler(commands=["rename"])
def handle_rename(message: types.Message):
    """Переименование котика"""
    try:
        parts = message.text.split(maxsplit=2)
        cat_id = int(parts[1])
        new_name = parts[2]
        database.update_cat(cat_id, name=new_name)
        bot.reply_to(message, f"🐱 Котик ID {cat_id} переименован в <b>{new_name}</b>!")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: используйте <code>/rename &lt;ID 1 или 2&gt; &lt;новое имя&gt;</code>\nПример: <code>/rename 1 Симба</code>")

@bot.message_handler(commands=["setemoji"])
def handle_set_emoji(message: types.Message):
    """Смена эмодзи/аватарки котика"""
    try:
        parts = message.text.split(maxsplit=2)
        cat_id = int(parts[1])
        new_emoji = parts[2].strip()
        database.update_cat(cat_id, emoji=new_emoji)
        bot.reply_to(message, f"✨ Аватарка котика ID {cat_id} изменена на: {new_emoji}!")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: используйте <code>/setemoji &lt;ID 1 или 2&gt; &lt;эмодзи&gt;</code>\nПример: <code>/setemoji 1 🦁</code>")

@bot.message_handler(commands=["changelog", "updates", "version"])
def handle_changelog(message: types.Message):
    """Показывает список последних изменений и версию бота"""
    try:
        changes_list = "\n".join([f"• {c}" for c in RECENT_CHANGES])
        msg = (
            f"🚀 <b>Кошачий бот (версия {BOT_VERSION})</b>\n\n"
            f"📌 <b>Список последних изменений:</b>\n"
            f"{changes_list}\n\n"
            f"📱 Все действия можно выполнять через Mini App!"
        )
        bot.send_message(message.chat.id, msg, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in handle_changelog: {e}", exc_info=True)

# ================= ЗАПУСК =================

def main():
    # Отправляем уведомление о перезапуске бота и внесенных изменениях
    broadcast_restart_notification()
    
    while True:
        try:
            me = bot.get_me()
            print(f"🤖 Бот успешно запущен: @{me.username} ({me.first_name})")
            print("🐾 Доступные модули: Mini App, Тамагочи, Квесты, Вет-паспорт, Расходы, Напоминания.")
            bot.infinity_polling(timeout=10, long_polling_timeout=10)
        except Exception as e:
            logger.error(f"Polling crashed with error: {e}. Перезапуск через 3 сек...", exc_info=True)
            time.sleep(3)

if __name__ == "__main__":
    main()
