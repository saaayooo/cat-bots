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
import uuid
import base64
import hashlib
import hmac
import shutil
import time
from datetime import datetime
import database
import backups
import vet_ai
from config import (
    ALLOWED_USER_IDS,
    BOT_TOKEN,
    UPLOAD_DIR,
    WEBAPP_AUTH_MAX_AGE_SECONDS,
    WEB_PORT,
    get_current_time,
)

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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Telegram-Init-Data")
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

    def _authenticate_api_request(self) -> bool:
        """Проверяет подпись Telegram Mini App и семейный allowlist."""
        if not BOT_TOKEN:
            self._send_json({"ok": False, "msg": "Сервер не настроен: отсутствует BOT_TOKEN"}, 503)
            return False

        init_data = self.headers.get("X-Telegram-Init-Data", "")
        try:
            values = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
            supplied_hash = next(value for key, value in values if key == "hash")
            data_check_string = "\n".join(
                f"{key}={value}" for key, value in sorted(values) if key != "hash"
            )
            secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
            expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_hash, supplied_hash):
                raise ValueError("invalid signature")

            parsed = dict(values)
            auth_date = int(parsed.get("auth_date", "0"))
            if auth_date <= 0 or abs(int(time.time()) - auth_date) > WEBAPP_AUTH_MAX_AGE_SECONDS:
                raise ValueError("expired init data")

            user = json.loads(parsed.get("user", "{}"))
            user_id = int(user["id"])
            if not ALLOWED_USER_IDS or user_id not in ALLOWED_USER_IDS:
                self._send_json({"ok": False, "msg": "Нет доступа к семейному боту"}, 403)
                return False

            name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])).strip()
            self.auth_user = {"id": user_id, "name": name or user.get("username") or "Пользователь"}
            return True
        except Exception as exc:
            logger.warning("Rejected Mini App request from %s: %s", self.client_address[0], exc)
            self._send_json({"ok": False, "msg": "Откройте приложение из Telegram"}, 401)
            return False

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

        if path.startswith("/api/") and not self._authenticate_api_request():
            return

        # API Routes
        if path == "/api/backup":
            try:
                archive = backups.create_backup()
            except Exception:
                logger.exception("Backup creation failed")
                self._send_json({"ok": False, "msg": "Не удалось собрать архив"}, 500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(archive)}"')
            self.send_header("Content-Length", str(os.path.getsize(archive)))
            self.end_headers()
            with open(archive, "rb") as source:
                shutil.copyfileobj(source, self.wfile)
            return

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

        if path == "/api/photos":
            photos = database.get_cat_photos(limit=60)
            self._send_json({"photos": photos})
            return

        if path == "/api/cats/weights":
            weights = database.get_weight_history(limit=30)
            self._send_json({"weights": weights})
            return

        if path == "/api/thoughts":
            ctx = urllib.parse.parse_qs(parsed.query).get("context", ["general"])[0]
            thought = database.get_cat_thought(ctx)
            self._send_json({"thought": thought})
            return

        if path.startswith("/uploads/"):
            filename = os.path.basename(path)
            filepath = os.path.join(UPLOAD_DIR, filename)
            if not os.path.isfile(filepath):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(os.path.getsize(filepath)))
            self.end_headers()
            with open(filepath, "rb") as source:
                shutil.copyfileobj(source, self.wfile)
            return

        # Serve SPA static files
        if path == "/" or not os.path.exists(os.path.join(STATIC_DIR, path.lstrip("/"))):
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/") and not self._authenticate_api_request():
            return

        body = self._read_json_body()
        # Никогда не доверяем личности, присланной браузером в JSON.
        body["user_id"] = self.auth_user["id"]
        body["user_name"] = self.auth_user["name"]
        body["paid_by_user_id"] = self.auth_user["id"]
        body["paid_by_name"] = self.auth_user["name"]

        # 1. Быстрое кормление
        if path == "/api/feed":
            user_id = body.get("user_id", 0)
            user_name = body.get("user_name", "С заботой")
            now = get_current_time()

            ok, msg = database.record_pair_feeding(user_id, user_name, now)
            if not ok:
                self._send_json({"ok": False, "msg": msg, "status": database.get_tamagotchi_status()}, 200)
                return

            time_str = now.strftime("%H:%M")

            database.check_and_update_streak()
            database.save_persistent_backup()

            thought = database.get_cat_thought("feed")
            if CatAppHandler.notify_fn:
                try:
                    other_msg = (
                        f"🐾 <b>{user_name}</b> покормил(а) Тучу и Грунтика в <b>{time_str}</b>!\n"
                        f"💬 {thought}\n\n"
                        f"📸 <i>Можно скинуть фоточку сытых котиков в ответ!</i>"
                    )
                    sender_msg = (
                        f"🥣 <b>Вы</b> отметили кормление Тучи и Грунтика в <b>{time_str}</b>!\n"
                        f"💬 {thought}\n\n"
                        f"📸 <i>Второму человеку отправлено уведомление. Можно скинуть фотоотчет в чат!</i>"
                    )
                    CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                except Exception as e:
                    logger.warning(f"Notification error: {e}")

            status = database.get_tamagotchi_status()
            self._send_json({"ok": True, "msg": f"Котики сыты и довольны! 🐱🥣\n{thought}", "status": status})
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
            database.save_persistent_backup()
            self._send_json({
                "ok": True,
                "msg": f"Анкета котика {updated_cat['name']} обновлена! ✨",
                "cat": updated_cat,
                "status": status
            })
            return

        # 7. Загрузка фото в галерею (с фотоотчетом)
        if path == "/api/photos/upload":
            img_b64 = body.get("image_base64")
            caption = body.get("caption", "")
            category = body.get("category", "feeding")
            user_id = body.get("user_id", 0)
            user_name = body.get("user_name", "С заботой")

            if not img_b64:
                self._send_json({"ok": False, "msg": "Файл изображения не передан"}, 400)
                return

            try:
                # Отсекаем префикс data:image/...;base64, если передан Data URL
                if "," in img_b64:
                    img_b64 = img_b64.split(",", 1)[1]
                img_bytes = base64.b64decode(img_b64)

                if len(img_bytes) > 10 * 1024 * 1024:
                    self._send_json({"ok": False, "msg": "Фото должно быть меньше 10 МБ"}, 413)
                    return

                os.makedirs(UPLOAD_DIR, exist_ok=True)
                filename = f"cat_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}.jpg"
                filepath = os.path.join(UPLOAD_DIR, filename)
                with open(filepath + ".tmp", "wb") as f:
                    f.write(img_bytes)
                os.replace(filepath + ".tmp", filepath)

                web_path = f"/uploads/{filename}"
                photo_id = database.add_cat_photo(web_path, caption, user_id, user_name, category)
                database.save_persistent_backup()

                thought = database.get_cat_thought("photo")
                if CatAppHandler.notify_fn:
                    cap_text = f"<i>«{caption}»</i>\n" if caption else ""
                    other_msg = (
                        f"📸 <b>{user_name}</b> добавил(а) новое фото в семейный альбом!\n"
                        f"{cap_text}\n"
                        f"💬 {thought}\n"
                        f"🖼 Фото уже доступно в галерее Mini App!"
                    )
                    sender_msg = (
                        f"📸 <b>Вы</b> добавили фото в семейный альбом!\n"
                        f"{cap_text}Второму человеку отправлено уведомление."
                    )
                    try:
                        CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                    except Exception as e:
                        logger.warning(f"Notification error: {e}")

                self._send_json({
                    "ok": True,
                    "photo_id": photo_id,
                    "file_path": web_path,
                    "msg": "Фото успешно добавлено в альбом! 📸✨"
                })
            except Exception as e:
                logger.error(f"Error saving uploaded photo: {e}", exc_info=True)
                self._send_json({"ok": False, "msg": f"Ошибка сохранения фото: {e}"}, 500)
            return

        # 8. Вопрос к AI Вет-консультанту
        if path == "/api/vet/ask":
            question = body.get("question", "")
            ans_dict = vet_ai.ask_vet_ai(question)
            self._send_json(ans_dict)
            return

        # 9. Сохранение замера веса
        if path == "/api/cats/weight":
            cat_id = int(body.get("cat_id", 1))
            raw_w = body.get("weight")
            try:
                weight = float(str(raw_w).replace(",", "."))
            except Exception:
                weight = 4.0

            user_name = body.get("user_name", "С заботой")
            user_id = body.get("user_id", 0)

            database.add_weight_entry(cat_id, weight, user_name)
            database.save_persistent_backup()

            cat = database.get_cat(cat_id)
            cname = cat.get("name", f"Котик {cat_id}") if cat else f"Котик {cat_id}"

            if CatAppHandler.notify_fn:
                other_msg = f"⚖️ <b>{user_name}</b> зафиксировал(а) вес котика <b>{cname}</b>: <b>{weight} кг</b>!"
                sender_msg = f"⚖️ Вес котика <b>{cname}</b> ({weight} кг) сохранен в медкарту!"
                try:
                    CatAppHandler.notify_fn(user_id, user_name, other_msg, sender_msg)
                except Exception as e:
                    logger.warning(f"Notification error: {e}")

            self._send_json({"ok": True, "msg": f"Вес котика {cname} обновлен: {weight} кг!"})
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
