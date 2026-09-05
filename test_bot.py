import unittest
import os
import tempfile
from datetime import datetime, timedelta

import config
import database

class TestCatBot(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        database.DB_FILE = self.temp_db.name
        database.init_db()

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    def test_database_feedings(self):
        self.assertIsNone(database.get_last_feeding())
        t1 = datetime(2026, 9, 4, 12, 0, 0)
        id1 = database.add_feeding(1001, "Иван", t1)
        self.assertEqual(id1, 1)

        last = database.get_last_feeding()
        self.assertIsNotNone(last)
        self.assertEqual(last["user_name"], "Иван")

    def test_database_chats(self):
        database.register_chat(111, "private", "Иван")
        database.register_chat(222, "private", "Мария")

        chats = database.get_all_chats()
        self.assertGreaterEqual(len(chats), 2)
        chat_ids = [c["chat_id"] for c in chats]
        self.assertIn(111, chat_ids)
        self.assertIn(222, chat_ids)

    def test_quests_lifecycle(self):
        # 1. Generate quests
        quests = database.get_today_quests()
        self.assertGreater(len(quests), 3)

        # Find water quest
        water_q = next((q for q in quests if q["type"] == "water"), None)
        self.assertIsNotNone(water_q)
        qid = water_q["id"]
        # 2. Убеждаемся, что квест доступен (даже если тест запущен ночью до 08:00)
        with database.get_db() as conn:
            conn.cursor().execute("UPDATE quests SET status = 'available' WHERE id = ?", (qid,))
            conn.commit()

        # User 1 takes quest
        ok, msg, info = database.take_quest(qid, 1001, "Иван")
        self.assertTrue(ok)
        self.assertEqual(info["user_name"], "Иван")

        # 3. User 2 cannot take already taken quest
        ok2, msg2, _ = database.take_quest(qid, 1002, "Мария")
        self.assertFalse(ok2)

        # 4. User 2 cannot drop User 1's quest
        ok_drop_fail, _, _ = database.drop_quest(qid, 1002)
        self.assertFalse(ok_drop_fail)

        # 5. User 1 drops quest
        ok_drop, _, _ = database.drop_quest(qid, 1001)
        self.assertTrue(ok_drop)

        # 6. User 2 can now take and complete quest
        ok_take2, _, _ = database.take_quest(qid, 1002, "Мария")
        self.assertTrue(ok_take2)

        ok_comp, _, comp_info = database.complete_quest(qid, 1002, "Мария")
        self.assertTrue(ok_comp)
        self.assertEqual(comp_info["user_name"], "Мария")

        # 7. Check board state
        updated_quests = database.get_today_quests()
        completed_water = next(q for q in updated_quests if q["id"] == qid)
        self.assertEqual(completed_water["status"], "completed")
        self.assertEqual(completed_water["completed_by_name"], "Мария")

if __name__ == "__main__":
    unittest.main()
