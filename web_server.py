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
                    notify_msg = (
                        f"🐾 <b>{user_name}</b> покормил(а) Тучу и Грунтика в <b>{time_str}</b>!\n"
                        f"Котики сыты и счастливы! 🐱🥣✨"
                    )
                    CatAppHandler.notify_fn(user_id, user_name, notify_msg)
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
                notify_msg = f"💧 <b>{user_name}</b> налил(а) котикам свежую воду в <b>{time_str}</b>! 🐱✨"
            elif care_type == "litter":
                database.complete_quest(f"litter_daily_{today_str}", user_id, user_name)
                msg = "Лоток почищен! 🚽"
                notify_msg = f"🚽 <b>{user_name}</b> почистил(а) лоток в <b>{time_str}</b>! Чистота и порядок ✨"
            elif care_type == "play":
                database.complete_quest(f"play_{today_str}", user_id, user_name)
                msg = "Поиграли с Тучей и Грунтиком! 🎾"
                notify_msg = f"🎾 <b>{user_name}</b> поиграл(а) с Тучей и Грунтиком в <b>{time_str}</b>! 🐱🎈"
            else:
                self._send_json({"ok": False, "msg": "Неизвестное действие"}, 400)
                return

            database.check_and_update_streak()

            if CatAppHandler.notify_fn:
                try:
                    CatAppHandler.notify_fn(user_id, user_name, notify_msg)
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

            if action == "take":
                ok, msg, info = database.take_quest(qid, user_id, user_name)
            elif action == "done":
                ok, msg, info = database.complete_quest(qid, user_id, user_name)
            elif action == "drop":
                ok, msg, info = database.drop_quest(qid, user_id)
            else:
                ok, msg = False, "Неизвестное действие"

            self._send_json({"ok": ok, "msg": msg})
            return

        # 3. Добавление вет-записи
        if path == "/api/vet":
            cat_id = body.get("cat_id", 1)
            record_type = body.get("record_type", "other")
            title = body.get("title", "")
            desc = body.get("description", "")
            next_due = body.get("next_due_date")

            if not title:
                self._send_json({"ok": False, "msg": "Укажите название записи"}, 400)
                return

            rec_id = database.add_vet_record(cat_id, record_type, title, desc, next_due_date=next_due)
            self._send_json({"ok": True, "id": rec_id})
            return

        # 4. Добавление расхода
        if path == "/api/expenses":
            try:
                amount = float(body.get("amount", 0))
            except Exception:
                amount = 0.0

            if amount <= 0:
                self._send_json({"ok": False, "msg": "Сумма должна быть больше 0"}, 400)
                return

            category = body.get("category", "other")
            user_id = body.get("paid_by_user_id", 0)
            user_name = body.get("paid_by_name", "Кто-то")
            note = body.get("note", "")

            exp_id = database.add_expense(amount, category, user_id, user_name, note)
            self._send_json({"ok": True, "id": exp_id})
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
