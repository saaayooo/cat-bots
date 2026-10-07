import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import unittest
import urllib.request
import urllib.error
import urllib.parse
import json
import time
import hashlib
import hmac
import tempfile
import shutil

# Ensure import from current dir
sys.path.insert(0, os.path.dirname(__file__))

# Изолированные тестовые credentials; production-секреты берутся только из окружения.
TEST_DATA_DIR = tempfile.mkdtemp(prefix="cat-bot-tests-")
os.environ["BOT_TOKEN"] = "123456:test-token"
os.environ["ALLOWED_USER_IDS"] = "999"
os.environ["DATA_DIR"] = TEST_DATA_DIR

import config
import database
import web_server

def make_test_init_data(user_id=999):
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "test-query",
        "user": json.dumps({"id": user_id, "first_name": "API", "last_name": "Tester"}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(values)

class TelegramAuthHeader(urllib.request.BaseHandler):
    def http_request(self, request):
        request.add_unredirected_header("X-Telegram-Init-Data", make_test_init_data())
        return request

    https_request = http_request

class TestCatApp(unittest.TestCase):
    server = None

    @classmethod
    def setUpClass(cls):
        # Initialize DB
        database.init_db()
        urllib.request.install_opener(urllib.request.build_opener(TelegramAuthHeader()))

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)

    def test_01_cats_profiles(self):
        cats = database.get_cats()
        self.assertGreaterEqual(len(cats), 2, "Должно быть как минимум 2 котика")
        cat_names = [c["name"] for c in cats]
        self.assertIn("Туча", cat_names)
        self.assertIn("Грунтик", cat_names)
        print(f"✅ Профили котиков инициализированы: {cat_names}")

    def test_02_tamagotchi_status(self):
        status = database.get_tamagotchi_status()
        self.assertIn("mood_title", status)
        self.assertIn("satiety_percent", status)
        self.assertIn("water_percent", status)
        self.assertIn("litter_percent", status)
        self.assertIn("streak", status)
        self.assertGreaterEqual(status["satiety_percent"], 0)
        self.assertLessEqual(status["satiety_percent"], 100)
        print(f"✅ Тамагочи статус: {status['mood_emoji']} {status['mood_title']} (Сытость: {status['satiety_percent']}%)")

    def test_03_quests(self):
        quests = database.get_today_quests()
        self.assertGreaterEqual(len(quests), 5, "Должно быть минимум 5 типов квестов")
        q_types = [q["type"] for q in quests]
        self.assertIn("feed_morning", q_types)
        self.assertIn("water", q_types)
        self.assertIn("litter_daily", q_types)
        print(f"✅ Доска квестов на сегодня сформирована ({len(quests)} квестов)")

    def test_04_vet_records(self):
        rec_id = database.add_vet_record(
            cat_id=1,
            record_type="vaccine",
            title="Тестовая вакцинация",
            description="Проверка работы модуля",
            next_due_date="2026-10-01"
        )
        self.assertIsNotNone(rec_id)
        records = database.get_vet_records(cat_id=1)
        found = any(r["id"] == rec_id for r in records)
        self.assertTrue(found, "Вет-запись должна сохраниться в БД")
        print("✅ Вет-паспорт: добавление и чтение записей работает")

    def test_05_expenses(self):
        exp_id = database.add_expense(
            amount=1250.50,
            category="food",
            paid_by_user_id=123,
            paid_by_name="Тестер",
            note="Тестовый влажный корм"
        )
        self.assertIsNotNone(exp_id)
        summary = database.get_expenses_summary()
        self.assertGreaterEqual(summary["total_month"], 1250.50)
        cat_keys = [c["category"] for c in summary["by_category"]]
        self.assertIn("food", cat_keys)
        print(f"✅ Учет расходов: суммирование за месяц ({summary['total_month']} руб) работает")

    def test_06_web_api_endpoints(self):
        test_port = 8189
        self.__class__.server = web_server.start_web_server(port=test_port)
        time.sleep(0.5)

        base_url = f"http://127.0.0.1:{test_port}"

        # API без подписанных Telegram initData закрыт.
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.build_opener().open(f"{base_url}/api/status")
        self.assertEqual(ctx.exception.code, 401)
        
        # 1. GET /api/status
        req = urllib.request.urlopen(f"{base_url}/api/status")
        self.assertEqual(req.status, 200)
        data = json.loads(req.read().decode("utf-8"))
        self.assertIn("cats", data)
        self.assertIn("mood_title", data)

        # 2. GET /api/quests
        req = urllib.request.urlopen(f"{base_url}/api/quests")
        self.assertEqual(req.status, 200)
        quests_data = json.loads(req.read().decode("utf-8"))
        self.assertIsInstance(quests_data, list)

        # 3. POST /api/feed
        feed_payload = json.dumps({"user_id": 999, "user_name": "API Tester"}).encode("utf-8")
        post_req = urllib.request.Request(
            f"{base_url}/api/feed",
            data=feed_payload,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(post_req)
        self.assertEqual(resp.status, 200)
        feed_res = json.loads(resp.read().decode("utf-8"))
        self.assertIn("ok", feed_res)

        # 4. POST /api/care (water, litter, play)
        for ctype in ["water", "litter", "play"]:
            care_payload = json.dumps({"type": ctype, "user_id": 999, "user_name": "API Tester"}).encode("utf-8")
            care_req = urllib.request.Request(
                f"{base_url}/api/care",
                data=care_payload,
                headers={"Content-Type": "application/json"}
            )
            care_resp = urllib.request.urlopen(care_req)
            self.assertEqual(care_resp.status, 200)
            care_data = json.loads(care_resp.read().decode("utf-8"))
            self.assertTrue(care_data.get("ok"))
            self.assertIn("status", care_data)

        # 5. POST /api/cats/update (name, weight, breed, emoji)
        cat_update_payload = json.dumps({
            "id": 1,
            "name": "Туча",
            "breed": "Шотландский черныш",
            "weight": 4.5,
            "emoji": "🐈‍⬛",
            "user_id": 999,
            "user_name": "API Tester"
        }).encode("utf-8")
        cat_req = urllib.request.Request(
            f"{base_url}/api/cats/update",
            data=cat_update_payload,
            headers={"Content-Type": "application/json"}
        )
        cat_resp = urllib.request.urlopen(cat_req)
        self.assertEqual(cat_resp.status, 200)
        cat_res = json.loads(cat_resp.read().decode("utf-8"))
        self.assertTrue(cat_res.get("ok"))
        self.assertEqual(cat_res["cat"]["name"], "Туча")
        self.assertEqual(cat_res["cat"]["weight"], 4.5)
        self.assertEqual(cat_res["cat"]["breed"], "Шотландский черныш")

        # 6. POST /api/quests/action (take, drop, done)
        today_quests = database.get_today_quests()
        if today_quests:
            avail = next((q for q in today_quests if q["status"] == "available"), today_quests[0])
            qid = avail["id"]
            # Take
            take_req = urllib.request.Request(
                f"{base_url}/api/quests/action",
                data=json.dumps({"action": "take", "quest_id": qid, "user_id": 999, "user_name": "API Tester"}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            take_resp = urllib.request.urlopen(take_req)
            self.assertEqual(take_resp.status, 200)
            
            # Done
            done_req = urllib.request.Request(
                f"{base_url}/api/quests/action",
                data=json.dumps({"action": "done", "quest_id": qid, "user_id": 999, "user_name": "API Tester"}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            done_resp = urllib.request.urlopen(done_req)
            self.assertEqual(done_resp.status, 200)

        # 7. Bot settings (restart notification state)
        database.set_bot_setting("test_key", "test_val")
        self.assertEqual(database.get_bot_setting("test_key"), "test_val")

        # 8. GET / (index.html) with all tabs and edit modal
        html_req = urllib.request.urlopen(f"{base_url}/")
        self.assertEqual(html_req.status, 200)
        html_text = html_req.read().decode("utf-8")
        self.assertIn("Кошачий Хаб", html_text)
        self.assertIn("btn-care-water", html_text)
        self.assertIn("btn-care-litter", html_text)
        self.assertIn("btn-care-play", html_text)
        self.assertIn("tab-quests", html_text)
        self.assertIn("tab-gallery", html_text)
        self.assertIn("tab-vet", html_text)
        self.assertIn("tab-expenses", html_text)
        self.assertIn("modal-cat-edit", html_text)
        self.assertIn("vet-ai-card", html_text)

        # 9. GET /api/photos & POST /api/photos/upload
        photo_req = urllib.request.Request(
            f"{base_url}/api/photos/upload",
            data=json.dumps({
                "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "caption": "Тестовый котик",
                "category": "feeding",
                "user_id": 999,
                "user_name": "API Tester"
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        photo_resp = urllib.request.urlopen(photo_req)
        self.assertEqual(photo_resp.status, 200)
        photo_res_data = json.loads(photo_resp.read().decode("utf-8"))
        self.assertTrue(photo_res_data.get("ok"))

        # 10. POST /api/vet/ask
        vet_req = urllib.request.Request(
            f"{base_url}/api/vet/ask",
            data=json.dumps({"question": "можно ли котам шоколад?"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        vet_resp = urllib.request.urlopen(vet_req)
        self.assertEqual(vet_resp.status, 200)
        vet_res_data = json.loads(vet_resp.read().decode("utf-8"))
        self.assertIn("Шоколад", vet_res_data.get("answer", ""))

        # 11. POST /api/cats/weight
        w_req = urllib.request.Request(
            f"{base_url}/api/cats/weight",
            data=json.dumps({"cat_id": 1, "weight": 4.35, "user_name": "API Tester", "user_id": 999}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        w_resp = urllib.request.urlopen(w_req)
        self.assertEqual(w_resp.status, 200)
        w_res_data = json.loads(w_resp.read().decode("utf-8"))
        self.assertTrue(w_res_data.get("ok"))

        # 12. Persistent state export/import
        state = database.export_full_state()
        self.assertIn("feedings", state)
        self.assertIn("cats", state)
        self.assertIn("cat_photos", state)
        self.assertIn("cat_weight_history", state)

        print("✅ Встроенный веб-сервер, REST API, фотоальбом, AI вет-консультант, замеры веса и бэкап функционируют штатно")

if __name__ == "__main__":
    unittest.main()
