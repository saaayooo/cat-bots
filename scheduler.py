import time
import threading
import logging
from datetime import datetime
import database
from config import get_current_time

logger = logging.getLogger("cat_scheduler")

def check_and_send_reminders(bot, get_main_keyboard_func):
    """Проверяет условия и отправляет умные уведомления в чаты"""
    now = get_current_time()
    today_str = now.strftime("%Y-%m-%d")
    hour = now.hour
    minute = now.minute

    all_chats = database.get_all_chats()
    private_chats = [c["chat_id"] for c in all_chats if c["chat_type"] == "private"]

    if not private_chats:
        return

    def broadcast(text):
        for cid in private_chats:
            try:
                bot.send_message(cid, text, reply_markup=get_main_keyboard_func())
                logger.info(f"Reminder sent to {cid}")
            except Exception as e:
                logger.warning(f"Failed to send reminder to {cid}: {e}")

    # 1. Утренний корм (с 09:30 до 12:00)
    if hour >= 9 and hour < 12 and (hour > 9 or minute >= 30):
        key = f"morning_feed_{today_str}"
        if database.should_send_reminder(key):
            quests = database.get_today_quests()
            q_feed = next((q for q in quests if q["type"] == "feed_morning"), None)
            if q_feed and q_feed["status"] == "available":
                msg = (
                    "🔔 <b>Мяу-напоминание:</b>\n\n"
                    "Котики ждут утренний завтрак! 🥣🐱\n"
                    "Кто сегодня шеф-повар? Нажмите «🐾 Кот покормлен» или возьмите квест!"
                )
                broadcast(msg)
                database.mark_reminder_sent(key)

    # 2. Вода и лоток (с 21:00 до 22:00)
    if hour == 21 and minute >= 0 and minute < 30:
        key = f"hygiene_{today_str}"
        if database.should_send_reminder(key):
            quests = database.get_today_quests()
            water_q = next((q for q in quests if q["type"] == "water"), None)
            litter_q = next((q for q in quests if q["type"] == "litter_daily"), None)
            
            missing = []
            if water_q and water_q["status"] == "available":
                missing.append("💧 Поменять воду")
            if litter_q and litter_q["status"] == "available":
                missing.append("🚽 Почистить лоток")

            if missing:
                tasks_text = "\n• " + "\n• ".join(missing)
                msg = (
                    "🔔 <b>Вечерний уют для котиков:</b>\n"
                    f"Остались незавершенные дела:{tasks_text}\n\n"
                    "Котики будут очень благодарны за заботу ✨"
                )
                broadcast(msg)
                database.mark_reminder_sent(key)

    # 3. Вечерний корм (с 21:30 до 23:30)
    if (hour == 21 and minute >= 30) or (hour == 22) or (hour == 23 and minute <= 30):
        key = f"evening_feed_{today_str}"
        if database.should_send_reminder(key):
            quests = database.get_today_quests()
            q_feed = next((q for q in quests if q["type"] == "feed_evening"), None)
            if q_feed and q_feed["status"] == "available":
                msg = (
                    "🔔 <b>Пора ужинать!</b>\n\n"
                    "Котики сидят возле мисок и ждут вечерний корм 🥣😺\n"
                    "Не забудьте покормить пушистых!"
                )
                broadcast(msg)
                database.mark_reminder_sent(key)

    # 4. Проверка вет-паспорта (раз в сутки в 12:00)
    if hour == 12 and minute < 10:
        key = f"vet_due_{today_str}"
        if database.should_send_reminder(key, hours_cooldown=20):
            upcoming = database.get_upcoming_vet_due(days_ahead=3)
            if upcoming:
                items_txt = "\n".join([f"• <b>{u['title']}</b> ({u['cat_name']}) — до {u['next_due_date']}" for u in upcoming])
                msg = (
                    "🩺 <b>Напоминание из вет-паспорта:</b>\n\n"
                    f"Приближаются процедуры для котиков:\n{items_txt}\n\n"
                    "Подробности доступны во вкладке «Вет-паспорт»."
                )
                broadcast(msg)
                database.mark_reminder_sent(key)

    # 5. Проверка стрика в конце дня (23:55)
    if hour == 23 and minute >= 55:
        database.check_and_update_streak()

def start_scheduler(bot, get_main_keyboard_func):
    """Запускает планировщик в фоновом потоке"""
    def loop():
        while True:
            try:
                check_and_send_reminders(bot, get_main_keyboard_func)
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            time.sleep(35)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("⏰ Фоновый планировщик умных напоминаний запущен.")
    return t
