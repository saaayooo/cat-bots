import http.server
import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import threading
import logging
import urllib.parse
from datetime import datetime
import database
from config import WEB_PORT, get_current_time

logger = logging.getLogger("cat_web")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "web")

class CatAppHandler(http.server.SimpleHTTPRequestHandler):
    notify_fn = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def end_headers(self):
        # CORS headers for Telegram WebApp
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Error parsing JSON body: {e}")
        return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Render Health Check & Ping
        if path in ("/health", "/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Cat Bot & Mini App are healthy! 🐱".encode("utf-8"))
            return

        # API Routes
        if path == "/api/status":
            status = database.get_tamagotchi_status()
            self._send_json(status)
            return

        if path == "/api/quests":
            quests = database.get_today_quests()
            self._send_json(quests)
            return

        if path == "/api/vet":
            records = database.get_vet_records(limit=30)
            upcoming = database.get_upcoming_vet_due(days_ahead=14)
            self._send_json({"records": records, "upcoming": upcoming})
            return

        if path == "/api/expenses":
            summary = database.get_expenses_summary()
            self._send_json(summary)
            return

        # Serve SPA static files
        if path == "/" or not os.path.exists(os.path.join(STATIC_DIR, path.lstrip("/"))):
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        # 1. Быстрое кормление
        if path == "/api/feed":
            user_id = body.get("user_id", 0)
            user_name = body.get("user_name", "С заботой")
            now = get_current_time()

            last = database.get_last_feeding()
            if last and (now - last["fed_at"]).total_seconds() < 60:
                self._send_json({"ok": False, "msg": f"Котиков уже покормил(а) {last['user_name']} меньше минуты назад!"}, 200)
                return

            database.add_feeding(user_id, user_name, now)
            today_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M")
            qtype = "feed_morning" if now.hour < 20 else "feed_evening"
            try:
                database.complete_quest(f"{qtype}_{today_str}", user_id, user_name)
            except Exception:
                pass

            database.check_and_update_streak()

            if CatAppHandler.notify_fn:
                try:
                    other_msg = (
                        f"🐾 <b>{user_name}</b> покормил(а) Тучу и Грунтика в <b>{time_str}</b>!\n"
                        f"Котики сыты и счастливо мурчат! 🐱🥣✨"
                    )
                    sender_msg = (
                        f"🥣 <b>Вы</b> отметили кормление Тучи и Грунтика в <b>{time_str}</b>!\n"
                        f"Котики сыты и довольны! (Второму человеку отправлено уведомление 📢)"
                    )
                    CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                except Exception as e:
                    logger.warning(f"Notification error: {e}")

            status = database.get_tamagotchi_status()
            self._send_json({"ok": True, "msg": "Котики сыты и довольны! 🐱🥣", "status": status})
            return

        # 2. Уход: Вода, Лоток, Игры (кликабельные кнопки из Mini App)
        if path == "/api/care":
            care_type = body.get("type") # 'water', 'litter', 'play'
            user_id = body.get("user_id", 0)
            user_name = body.get("user_name", "С заботой")
            now = get_current_time()
            today_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M")

            if care_type == "water":
                database.complete_quest(f"water_{today_str}", user_id, user_name)
                msg = "Свежая вода налита! 💧"
                other_msg = f"💧 <b>{user_name}</b> налил(а) котикам свежую воду в <b>{time_str}</b>! 🐱✨"
                sender_msg = f"💧 <b>Вы</b> налили свежую воду котикам в <b>{time_str}</b>! Чистая миска готова ✨"
            elif care_type == "litter":
                database.complete_quest(f"litter_daily_{today_str}", user_id, user_name)
                msg = "Лоток почищен! 🚽"
                other_msg = f"🚽 <b>{user_name}</b> почистил(а) лоток в <b>{time_str}</b>! Чистота и порядок ✨"
                sender_msg = f"🚽 <b>Вы</b> почистили лоток в <b>{time_str}</b>! Чистота и порядок ✨"
            elif care_type == "play":
                database.complete_quest(f"play_{today_str}", user_id, user_name)
                msg = "Поиграли с Тучей и Грунтиком! 🎾"
                other_msg = f"🎾 <b>{user_name}</b> поиграл(а) с Тучей и Грунтиком в <b>{time_str}</b>! 🐱🎈"
                sender_msg = f"🎾 <b>Вы</b> поиграли с Тучей и Грунтиком в <b>{time_str}</b>! Котики набегались и довольны 🐱🎈"
            else:
                self._send_json({"ok": False, "msg": "Неизвестное действие"}, 400)
                return

            database.check_and_update_streak()

            if CatAppHandler.notify_fn:
                try:
                    CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                except Exception as e:
                    logger.warning(f"Notification error: {e}")

            status = database.get_tamagotchi_status()
            self._send_json({"ok": True, "msg": msg, "status": status})
            return

        # 3. Действие с квестом (take, done, drop)
        if path == "/api/quests/action":
            action = body.get("action")
            qid = body.get("quest_id")
            user_id = body.get("user_id", 0)
            user_name = body.get("user_name", "Пользователь")
            now = get_current_time()
            time_str = now.strftime("%H:%M")

            if action == "take":
                ok, msg, info = database.take_quest(qid, user_id, user_name)
                if ok and CatAppHandler.notify_fn:
                    q_title = info.get("title", "Квест")
                    other_msg = (
                        f"📢 <b>Уведомление по квестам:</b>\n"
                        f"👤 <b>{user_name}</b> взял(а) квест <b>«{q_title}»</b> в <b>{time_str}</b>!\n"
                        f"Скоро всё сделает 🐱👌"
                    )
                    sender_msg = (
                        f"✋ <b>Вы</b> взяли квест <b>«{q_title}»</b> в <b>{time_str}</b>!\n"
                        f"Второму человеку отправлено уведомление. 🐱👌"
                    )
                    try:
                        CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                    except Exception as e:
                        logger.warning(f"Notification error: {e}")

            elif action == "done":
                ok, msg, info = database.complete_quest(qid, user_id, user_name)
                if ok and CatAppHandler.notify_fn:
                    q_title = info.get("title", "Квест")
                    other_msg = (
                        f"🎉 <b>Квест выполнен:</b>\n"
                        f"👤 <b>{user_name}</b> выполнил(а) квест <b>«{q_title}»</b> в <b>{time_str}</b>!\n"
                        f"Котики сыты и довольны! 🐱🥣✨"
                    )
                    sender_msg = (
                        f"✅ <b>Вы</b> выполнили квест <b>«{q_title}»</b> в <b>{time_str}</b>!\n"
                        f"Второму человеку отправлено уведомление! 🐱✨"
                    )
                    try:
                        CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                    except Exception as e:
                        logger.warning(f"Notification error: {e}")

            elif action == "drop":
                ok, msg, info = database.drop_quest(qid, user_id)
                if ok and CatAppHandler.notify_fn:
                    q_title = info.get("title", "Квест")
                    other_msg = (
                        f"ℹ️ <b>{user_name}</b> освободил(а) квест <b>«{q_title}»</b> в <b>{time_str}</b>.\n"
                        f"Он снова свободен для выполнения на доске!"
                    )
                    sender_msg = (
                        f"↩️ <b>Вы</b> отказались от квеста <b>«{q_title}»</b>.\n"
                        f"Он снова свободен для выполнения на доске."
                    )
                    try:
                        CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                    except Exception as e:
                        logger.warning(f"Notification error: {e}")
            else:
                ok, msg = False, "Неизвестное действие"

            self._send_json({"ok": ok, "msg": msg})
            return

        # 4. Добавление вет-записи
        if path == "/api/vet":
            cat_id = body.get("cat_id", 1)
            record_type = body.get("record_type", "other")
            title = body.get("title", "")
            desc = body.get("description", "")
            next_due = body.get("next_due_date")
            user_id = body.get("user_id", 0)
            user_name = body.get("user_name", "Пользователь")

            if not title:
                self._send_json({"ok": False, "msg": "Укажите название записи"}, 400)
                return

            rec_id = database.add_vet_record(cat_id, record_type, title, desc, next_due_date=next_due)

            if CatAppHandler.notify_fn:
                try:
                    cat_obj = database.get_cat(cat_id)
                    c_name = cat_obj["name"] if cat_obj else "Котик"
                    other_msg = f"🩺 <b>{user_name}</b> внес(ла) запись в вет-паспорт ({c_name}):\n<b>«{title}»</b> ({desc or 'без заметок'}) 📋"
                    sender_msg = f"🩺 <b>Вы</b> внесли запись в вет-паспорт ({c_name}): <b>«{title}»</b> 📋"
                    CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                except Exception as e:
                    logger.warning(f"Notification error: {e}")

            self._send_json({"ok": True, "id": rec_id})
            return

        # 5. Добавление расхода
        if path == "/api/expenses":
            try:
                amount = float(body.get("amount", 0))
            except Exception:
                amount = 0.0

            if amount <= 0:
                self._send_json({"ok": False, "msg": "Сумма должна быть больше 0"}, 400)
                return

            category = body.get("category", "other")
            user_id = body.get("paid_by_user_id") or body.get("user_id", 0)
            user_name = body.get("paid_by_name") or body.get("user_name", "Кто-то")
            note = body.get("note", "")

            exp_id = database.add_expense(amount, category, user_id, user_name, note)

            if CatAppHandler.notify_fn:
                try:
                    cat_label = database.EXPENSE_CATEGORIES.get(category, category)
                    note_str = f" ({note})" if note else ""
                    other_msg = f"💰 <b>{user_name}</b> записал(а) расход на котиков:\n<b>{amount:,.2f} ₽</b> — {cat_label}{note_str} 💳"
                    sender_msg = f"💰 <b>Вы</b> записали расход на котиков: <b>{amount:,.2f} ₽</b> — {cat_label}{note_str} 💳"
                    CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                except Exception as e:
                    logger.warning(f"Notification error: {e}")

            self._send_json({"ok": True, "id": exp_id})
            return

        # 6. Обновление профиля котика (имя, вес, порода, эмодзи)
        if path in ("/api/cats/update", "/api/cat/update"):
            cat_id = body.get("id") or body.get("cat_id")
            if not cat_id:
                self._send_json({"ok": False, "msg": "Не указан ID котика"}, 400)
                return

            try:
                cat_id = int(cat_id)
            except Exception:
                self._send_json({"ok": False, "msg": "Некорректный ID котика"}, 400)
                return

            name = body.get("name")
            breed = body.get("breed")
            emoji = body.get("emoji")
            raw_weight = body.get("weight")

            weight = None
            if raw_weight is not None and str(raw_weight).strip() != "":
                try:
                    weight = float(str(raw_weight).replace(",", "."))
                except Exception:
                    weight = None

            user_id = body.get("user_id", 0)
            user_name = body.get("user_name", "Кто-то")

            kwargs = {}
            if name is not None and name.strip():
                kwargs["name"] = name.strip()
            if breed is not None:
                kwargs["breed"] = breed.strip()
            if emoji is not None and emoji.strip():
                kwargs["emoji"] = emoji.strip()
            if "weight" in body:
                kwargs["weight"] = weight

            database.update_cat(cat_id, **kwargs)
            updated_cat = database.get_cat(cat_id)

            if CatAppHandler.notify_fn and updated_cat:
                try:
                    c_name = updated_cat["name"]
                    c_emoji = updated_cat["emoji"]
                    c_weight = f"{updated_cat['weight']} кг" if updated_cat["weight"] else "не указан"
                    c_breed = updated_cat["breed"]
                    other_msg = (
                        f"✨ <b>{user_name}</b> обновил(а) анкету питомца:\n"
                        f"{c_emoji} <b>{c_name}</b> (Порода: {c_breed}, Вес: {c_weight})! 🐾"
                    )
                    sender_msg = (
                        f"✨ <b>Вы</b> обновили анкету {c_emoji} <b>{c_name}</b> (Порода: {c_breed}, Вес: {c_weight})! 🐾"
                    )
                    CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                except Exception as e:
                    logger.warning(f"Notification error: {e}")

            status = database.get_tamagotchi_status()
            self._send_json({
                "ok": True,
                "msg": f"Анкета котика {updated_cat['name']} обновлена! ✨",
                "cat": updated_cat,
                "status": status
            })
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # Отключаем спам в консоль
        pass

def start_web_server(port=None, notify_fn=None):
    """Запуск встроенного HTTP-сервера для Mini App и Health Checks в фоновом потоке"""
    if notify_fn is not None:
        CatAppHandler.notify_fn = notify_fn
    target_port = port or WEB_PORT
    try:
        server = http.server.ThreadingHTTPServer(("0.0.0.0", target_port), CatAppHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print(f"🌐 Mini App & API сервер успешно запущен на порту {target_port}")
        return server
    except Exception as e:
        logger.error(f"Не удалось запустить веб-сервер на порту {target_port}: {e}")
        return None
