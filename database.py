import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from config import DB_FILE, get_current_time

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_FILE)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Инициализация и миграция всех таблиц базы данных"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Таблица кормлений (история)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT,
                fed_at TEXT,
                timestamp REAL
            )
        """)
        
        # 2. Таблица чатов (для личных сообщений и групп)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                chat_type TEXT,
                name TEXT,
                registered_at TEXT
            )
        """)

        # 3. Таблица квестов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                id TEXT PRIMARY KEY,
                quest_type TEXT,
                title TEXT,
                target_date TEXT,
                status TEXT,
                taken_by_id INTEGER,
                taken_by_name TEXT,
                taken_at TEXT,
                completed_by_id INTEGER,
                completed_by_name TEXT,
                completed_at TEXT
            )
        """)

        # 4. Таблица профилей котиков (по умолчанию 2 котика)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                breed TEXT,
                birth_date TEXT,
                weight REAL DEFAULT 4.0,
                emoji TEXT DEFAULT '🐱'
            )
        """)

        # 5. Таблица стриков (дней без пропусков)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS streaks (
                id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_completed_date TEXT
            )
        """)

        # 6. Таблица вет-паспорта (прививки, обработки, визиты, замеры)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vet_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat_id INTEGER,
                record_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                record_date TEXT NOT NULL,
                next_due_date TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (cat_id) REFERENCES cats(id)
            )
        """)

        # 7. Таблица расходов на котиков
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                paid_by_user_id INTEGER,
                paid_by_name TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                expense_date TEXT NOT NULL
            )
        """)

        # 8. Лог напоминаний (для исключения повторов)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders_log (
                reminder_key TEXT PRIMARY KEY,
                sent_at TEXT NOT NULL
            )
        """)

        # Инициализация профилей 2-х котиков
        cursor.execute("SELECT COUNT(*) FROM cats")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO cats (id, name, breed, weight, emoji)
                VALUES 
                    (1, 'Туча', 'Черный котик', NULL, '🐈‍⬛'),
                    (2, 'Грунтик', 'Черный котик', NULL, '🐈‍⬛')
            """)
        else:
            # Обновляем дефолтные имена, если они были старыми
            cursor.execute("""
                UPDATE cats SET name = 'Туча', breed = 'Черный котик', emoji = '🐈‍⬛' WHERE id = 1 AND name IN ('Барсик', 'Котик 1');
            """)
            cursor.execute("""
                UPDATE cats SET name = 'Грунтик', breed = 'Черный котик', emoji = '🐈‍⬛' WHERE id = 2 AND name IN ('Мурка', 'Котик 2');
            """)

        # Инициализация записи стриков
        cursor.execute("SELECT COUNT(*) FROM streaks")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO streaks (id, current_streak, best_streak, last_completed_date)
                VALUES (1, 0, 0, NULL)
            """)

        conn.commit()

# ================= ЧАТЫ =================

def register_chat(chat_id: int, chat_type: str, name: str):
    """Регистрирует чат или обновляет информацию о нем"""
    with get_db() as conn:
        cursor = conn.cursor()
        now_str = get_current_time().isoformat()
        cursor.execute("""
            INSERT INTO chats (chat_id, chat_type, name, registered_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                chat_type = excluded.chat_type,
                name = excluded.name
        """, (chat_id, chat_type, name, now_str))
        conn.commit()

def get_all_chats():
    """Возвращает список всех зарегистрированных чатов"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, chat_type, name FROM chats")
        rows = cursor.fetchall()
        return [{"chat_id": r[0], "chat_type": r[1], "name": r[2]} for r in rows]

# ================= КОРМЛЕНИЯ =================

def add_feeding(user_id: int, user_name: str, dt: datetime = None) -> int:
    """Добавляет запись о кормлении кота"""
    if dt is None:
        dt = get_current_time()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO feedings (user_id, user_name, fed_at, timestamp)
            VALUES (?, ?, ?, ?)
        """, (user_id, user_name, dt.isoformat(), dt.timestamp()))
        conn.commit()
        return cursor.lastrowid

def get_last_feeding():
    """Возвращает последнюю запись о кормлении или None"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, user_name, fed_at, timestamp
            FROM feedings
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "user_name": row[2],
            "fed_at": datetime.fromisoformat(row[3]),
            "timestamp": row[4]
        }

def get_recent_feedings(limit: int = 5):
    """Возвращает список последних N кормлений"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, user_name, fed_at, timestamp
            FROM feedings
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [{
            "id": r[0],
            "user_id": r[1],
            "user_name": r[2],
            "fed_at": datetime.fromisoformat(r[3]),
            "timestamp": r[4]
        } for r in rows]

# ================= КВЕСТЫ =================

QUEST_DEFINITIONS = [
    {
        "type": "feed_morning",
        "title": "🥣 Утренний корм",
        "open_hour": 8,
        "is_daily": True
    },
    {
        "type": "feed_evening",
        "title": "🥣 Вечерний корм",
        "open_hour": 20,
        "is_daily": True
    },
    {
        "type": "water",
        "title": "💧 Поменять воду",
        "open_hour": 8,
        "is_daily": True
    },
    {
        "type": "litter_daily",
        "title": "🚽 Почистить лоток (быстрая)",
        "open_hour": 8,
        "is_daily": True
    },
    {
        "type": "play",
        "title": "🎾 Поиграть с котиками",
        "open_hour": 8,
        "is_daily": True
    }
]

def ensure_today_quests():
    """Создает или обновляет квесты на текущий день"""
    now = get_current_time()
    today_str = now.strftime("%Y-%m-%d")
    current_hour = now.hour

    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Ежедневные квесты
        for qdef in QUEST_DEFINITIONS:
            qid = f"{qdef['type']}_{today_str}"
            cursor.execute("SELECT status FROM quests WHERE id = ?", (qid,))
            row = cursor.fetchone()
            
            should_be_open = current_hour >= qdef["open_hour"]
            
            if not row:
                status = "available" if should_be_open else "locked"
                cursor.execute("""
                    INSERT INTO quests (id, quest_type, title, target_date, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (qid, qdef["type"], qdef["title"], today_str, status))
            elif row[0] == "locked" and should_be_open:
                cursor.execute("UPDATE quests SET status = 'available' WHERE id = ?", (qid,))

        # 2. Квест "Генеральная чистка лотка (раз в 2 недели)"
        cursor.execute("""
            SELECT id, completed_at, status FROM quests 
            WHERE quest_type = 'litter_deep' 
            ORDER BY target_date DESC LIMIT 1
        """)
        last_deep = cursor.fetchone()
        
        create_new_deep = False
        if not last_deep:
            create_new_deep = True
        else:
            last_id, last_comp_at, last_status = last_deep
            if last_status == "completed" and last_comp_at:
                try:
                    comp_dt = datetime.fromisoformat(last_comp_at)
                    if (now - comp_dt).days >= 14:
                        create_new_deep = True
                except Exception:
                    pass

        if create_new_deep:
            deep_id = f"litter_deep_{today_str}"
            cursor.execute("SELECT id FROM quests WHERE id = ?", (deep_id,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO quests (id, quest_type, title, target_date, status)
                    VALUES (?, 'litter_deep', '🧼 Генеральная чистка лотка', ?, 'available')
                """, (deep_id, today_str))

        conn.commit()

def get_today_quests():
    """Возвращает список всех квестов на сегодня"""
    ensure_today_quests()
    now = get_current_time()
    today_str = now.strftime("%Y-%m-%d")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, quest_type, title, target_date, status, 
                   taken_by_id, taken_by_name, taken_at,
                   completed_by_id, completed_by_name, completed_at
            FROM quests
            WHERE target_date = ? OR (quest_type = 'litter_deep' AND status != 'completed')
            ORDER BY 
                CASE quest_type
                    WHEN 'feed_morning' THEN 1
                    WHEN 'feed_evening' THEN 2
                    WHEN 'water' THEN 3
                    WHEN 'litter_daily' THEN 4
                    WHEN 'litter_deep' THEN 5
                    WHEN 'play' THEN 6
                    ELSE 7
                END
        """, (today_str,))
        rows = cursor.fetchall()
        
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "type": r[1],
                "title": r[2],
                "target_date": r[3],
                "status": r[4],
                "taken_by_id": r[5],
                "taken_by_name": r[6],
                "taken_at": datetime.fromisoformat(r[7]) if r[7] else None,
                "completed_by_id": r[8],
                "completed_by_name": r[9],
                "completed_at": datetime.fromisoformat(r[10]) if r[10] else None
            })
            
        # Генеральная чистка лотка (информация если закрыта)
        has_deep = any(q["type"] == "litter_deep" for q in result)
        if not has_deep:
            cursor.execute("""
                SELECT completed_at, target_date FROM quests
                WHERE quest_type = 'litter_deep' AND status = 'completed'
                ORDER BY completed_at DESC LIMIT 1
            """)
            deep_row = cursor.fetchone()
            if deep_row and deep_row[0]:
                try:
                    c_dt = datetime.fromisoformat(deep_row[0])
                    days_left = max(0, 14 - (now - c_dt).days)
                    result.append({
                        "id": "litter_deep_countdown",
                        "type": "litter_deep",
                        "title": "🧼 Генеральная чистка лотка",
                        "target_date": deep_row[1],
                        "status": "locked",
                        "days_left": days_left,
                        "taken_by_id": None, "taken_by_name": None, "taken_at": None,
                        "completed_by_id": None, "completed_by_name": None, "completed_at": None
                    })
                except Exception:
                    pass

        return result

def take_quest(quest_id: str, user_id: int, user_name: str) -> tuple[bool, str, dict]:
    """Пользователь забирает квест"""
    ensure_today_quests()
    now = get_current_time()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, status, taken_by_name FROM quests WHERE id = ?", (quest_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, "Квест не найден!", {}
        
        qid, title, status, taken_by = row
        
        if status == "completed":
            return False, "Этот квест уже выполнен!", {}
        if status == "taken":
            return False, f"Этот квест уже забрал(а) {taken_by}!", {}
        if status == "locked":
            return False, "Этот квест еще не открыт по времени!", {}

        cursor.execute("""
            UPDATE quests
            SET status = 'taken',
                taken_by_id = ?,
                taken_by_name = ?,
                taken_at = ?
            WHERE id = ?
        """, (user_id, user_name, now.isoformat(), quest_id))
        conn.commit()
        
        return True, "Квест успешно взят!", {
            "id": quest_id,
            "title": title,
            "user_id": user_id,
            "user_name": user_name,
            "taken_at": now
        }

def drop_quest(quest_id: str, user_id: int) -> tuple[bool, str, dict]:
    """Пользователь отказывается от квеста (возвращает в доступные)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, status, taken_by_id, taken_by_name FROM quests WHERE id = ?", (quest_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, "Квест не найден!", {}
        
        qid, title, status, taken_id, taken_name = row
        
        if status != "taken":
            return False, "Квест не находится в работе!", {}
        if taken_id != user_id:
            return False, "Вы не можете отказаться от чужого квеста!", {}

        cursor.execute("""
            UPDATE quests
            SET status = 'available',
                taken_by_id = NULL,
                taken_by_name = NULL,
                taken_at = NULL
            WHERE id = ?
        """, (quest_id,))
        conn.commit()
        
        return True, "Вы отказались от квеста.", {
            "id": quest_id,
            "title": title,
            "user_name": taken_name
        }

def complete_quest(quest_id: str, user_id: int, user_name: str) -> tuple[bool, str, dict]:
    """Пользователь завершает квест"""
    now = get_current_time()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, quest_type, title, status, taken_by_id, taken_by_name FROM quests WHERE id = ?", (quest_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, "Квест не найден!", {}
            
        qid, qtype, title, status, taken_id, taken_name = row
        
        if status == "completed":
            return False, "Квест уже завершен!", {}
            
        if status == "taken" and taken_id != user_id:
            return False, f"Этот квест выполняет {taken_name}!", {}

        cursor.execute("""
            UPDATE quests
            SET status = 'completed',
                completed_by_id = ?,
                completed_by_name = ?,
                completed_at = ?
            WHERE id = ?
        """, (user_id, user_name, now.isoformat(), quest_id))
        
        # Если это кормление, также сохраняем в таблицу feedings
        if qtype in ("feed_morning", "feed_evening"):
            cursor.execute("""
                INSERT INTO feedings (user_id, user_name, fed_at, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_id, user_name, now.isoformat(), now.timestamp()))

        conn.commit()
        
        # Проверяем обновление стрика
        check_and_update_streak()

        return True, "Квест успешно выполнен!", {
            "id": quest_id,
            "type": qtype,
            "title": title,
            "user_id": user_id,
            "user_name": user_name,
            "completed_at": now
        }

# ================= КОТИКИ (2 КОТА) =================

def get_cats():
    """Возвращает список всех зарегистрированных котиков"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, breed, birth_date, weight, emoji FROM cats ORDER BY id ASC")
        rows = cursor.fetchall()
        return [{
            "id": r[0],
            "name": r[1],
            "breed": r[2] or "Неизвестна",
            "birth_date": r[3] or "Не указана",
            "weight": r[4],
            "emoji": r[5] or "🐈‍⬛"
        } for r in rows]

def update_cat(cat_id: int, name: str = None, weight: float = None, emoji: str = None, breed: str = None):
    """Обновляет данные котика"""
    with get_db() as conn:
        cursor = conn.cursor()
        fields = []
        params = []
        if name is not None:
            fields.append("name = ?")
            params.append(name)
        if weight is not None:
            fields.append("weight = ?")
            params.append(weight)
        if emoji is not None:
            fields.append("emoji = ?")
            params.append(emoji)
        if breed is not None:
            fields.append("breed = ?")
            params.append(breed)
            
        if fields:
            params.append(cat_id)
            cursor.execute(f"UPDATE cats SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()

# ================= СТРИКИ (ГЕЙМИФИКАЦИЯ) =================

def get_streak_info():
    """Возвращает текущую и лучшую серию идеальных дней"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_streak, best_streak, last_completed_date FROM streaks WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            return {"current_streak": 0, "best_streak": 0, "last_completed_date": None}
        return {
            "current_streak": row[0] or 0,
            "best_streak": row[1] or 0,
            "last_completed_date": row[2]
        }

def check_and_update_streak():
    """Проверяет, закрыты ли все обязательные квесты за сегодня, и обновляет стрик"""
    now = get_current_time()
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    
    with get_db() as conn:
        cursor = conn.cursor()
        # Обязательные квесты: утренний корм, вечерний корм, вода, лоток
        required_types = ("feed_morning", "feed_evening", "water", "litter_daily")
        cursor.execute("""
            SELECT COUNT(*) FROM quests 
            WHERE target_date = ? AND quest_type IN (?, ?, ?, ?) AND status = 'completed'
        """, (today_str, *required_types))
        completed_count = cursor.fetchone()[0]

        if completed_count >= len(required_types):
            # Все обязательные квесты закрыты!
            cursor.execute("SELECT current_streak, best_streak, last_completed_date FROM streaks WHERE id = 1")
            row = cursor.fetchone()
            curr = row[0] if row else 0
            best = row[1] if row else 0
            last_date = row[2] if row else None

            if last_date != today_str:
                if last_date == yesterday_str:
                    new_curr = curr + 1
                else:
                    new_curr = 1 # Стрик начат заново
                
                new_best = max(best, new_curr)
                cursor.execute("""
                    UPDATE streaks 
                    SET current_streak = ?, best_streak = ?, last_completed_date = ?
                    WHERE id = 1
                """, (new_curr, new_best, today_str))
                conn.commit()
                return True, new_curr
        return False, 0

# ================= ТАМАГОЧИ И НАСТРОЕНИЕ =================

def get_tamagotchi_status():
    """Рассчитывает процент сытости, жажды, чистоты и общее настроение для 2-х котиков"""
    now = get_current_time()
    today_str = now.strftime("%Y-%m-%d")
    last_feed = get_last_feeding()
    quests = get_today_quests()
    streak = get_streak_info()
    cats = get_cats()

    # 1. Сытость (Hunger): от 100% (покормлен только что) до 0% (прошло >= 12 часов)
    if last_feed:
        hours_since_feed = max(0.0, (now - last_feed["fed_at"]).total_seconds() / 3600.0)
        satiety_percent = max(0, int(100 - (hours_since_feed / 12.0) * 100))
    else:
        hours_since_feed = 12.0
        satiety_percent = 10

    # 2. Вода (Hydration)
    water_quest = next((q for q in quests if q["type"] == "water"), None)
    water_percent = 100 if (water_quest and water_quest["status"] == "completed") else (70 if now.hour < 14 else 35)

    # 3. Чистота лотка (Cleanliness)
    litter_quest = next((q for q in quests if q["type"] == "litter_daily"), None)
    litter_percent = 100 if (litter_quest and litter_quest["status"] == "completed") else (80 if now.hour < 14 else 40)

    # 4. Игры (Fun)
    play_quest = next((q for q in quests if q["type"] == "play"), None)
    play_percent = 100 if (play_quest and play_quest["status"] == "completed") else 60

    # Общий индекс счастья котиков (0-100)
    overall_score = int(satiety_percent * 0.45 + water_percent * 0.25 + litter_percent * 0.20 + play_percent * 0.10)

    # Настроение и эмодзи
    if overall_score >= 85:
        mood_title = "Счастливы и мурчат"
        mood_emoji = "🥰"
        mood_desc = "Оба котика сыты, вода свежая, а лоток сияет чистотой!"
    elif overall_score >= 65:
        mood_title = "Довольны жизнью"
        mood_emoji = "😺"
        mood_desc = "Котики сладко потягиваются и дремлют на солнышке."
    elif overall_score >= 40:
        mood_title = "Проголодались"
        mood_emoji = "🥣"
        mood_desc = "Котики сидят у пустых мисок и вопросительно смотрят на вас."
    else:
        mood_title = "Очень голодны!"
        mood_emoji = "😾"
        mood_desc = "Котики громко мяукают и требуют немедленно наполнить миски!"

    return {
        "cats": cats,
        "satiety_percent": satiety_percent,
        "water_percent": water_percent,
        "litter_percent": litter_percent,
        "play_percent": play_percent,
        "overall_score": overall_score,
        "mood_title": mood_title,
        "mood_emoji": mood_emoji,
        "mood_desc": mood_desc,
        "hours_since_feed": round(hours_since_feed, 1) if last_feed else None,
        "last_feeding": last_feed,
        "streak": streak
    }

# ================= ВЕТ-ПАСПОРТ =================

def add_vet_record(cat_id: int, record_type: str, title: str, description: str = "", record_date: str = None, next_due_date: str = None):
    """Добавляет запись в вет-паспорт"""
    now = get_current_time()
    if not record_date:
        record_date = now.strftime("%Y-%m-%d")
    created_at = now.isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vet_records (cat_id, record_type, title, description, record_date, next_due_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cat_id, record_type, title, description, record_date, next_due_date, created_at))
        conn.commit()
        return cursor.lastrowid

def get_vet_records(cat_id: int = None, limit: int = 30):
    """Возвращает историю записей вет-паспорта"""
    with get_db() as conn:
        cursor = conn.cursor()
        if cat_id:
            cursor.execute("""
                SELECT vr.id, vr.cat_id, c.name, vr.record_type, vr.title, vr.description, 
                       vr.record_date, vr.next_due_date, vr.created_at
                FROM vet_records vr
                LEFT JOIN cats c ON vr.cat_id = c.id
                WHERE vr.cat_id = ?
                ORDER BY vr.record_date DESC, vr.id DESC
                LIMIT ?
            """, (cat_id, limit))
        else:
            cursor.execute("""
                SELECT vr.id, vr.cat_id, c.name, vr.record_type, vr.title, vr.description, 
                       vr.record_date, vr.next_due_date, vr.created_at
                FROM vet_records vr
                LEFT JOIN cats c ON vr.cat_id = c.id
                ORDER BY vr.record_date DESC, vr.id DESC
                LIMIT ?
            """, (limit,))
        rows = cursor.fetchall()
        return [{
            "id": r[0],
            "cat_id": r[1],
            "cat_name": r[2] or "Общее",
            "record_type": r[3],
            "title": r[4],
            "description": r[5] or "",
            "record_date": r[6],
            "next_due_date": r[7],
            "created_at": r[8]
        } for r in rows]

def get_upcoming_vet_due(days_ahead: int = 7):
    """Возвращает запланированные процедуры на ближайшие N дней"""
    now = get_current_time()
    today_str = now.strftime("%Y-%m-%d")
    future_str = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT vr.id, vr.cat_id, c.name, vr.record_type, vr.title, vr.next_due_date
            FROM vet_records vr
            LEFT JOIN cats c ON vr.cat_id = c.id
            WHERE vr.next_due_date IS NOT NULL AND vr.next_due_date BETWEEN ? AND ?
            ORDER BY vr.next_due_date ASC
        """, (today_str, future_str))
        rows = cursor.fetchall()
        return [{
            "id": r[0],
            "cat_id": r[1],
            "cat_name": r[2] or "Котики",
            "record_type": r[3],
            "title": r[4],
            "next_due_date": r[5]
        } for r in rows]

# ================= РАСХОДЫ =================

EXPENSE_CATEGORIES = {
    "food": "🥣 Корм и лакомства",
    "litter": "🚽 Наполнитель",
    "vet": "🩺 Ветеринар и аптека",
    "toys": "🎾 Игрушки и когтеточки",
    "other": "📦 Другое"
}

def add_expense(amount: float, category: str, paid_by_user_id: int, paid_by_name: str, note: str = "", expense_date: str = None):
    """Добавляет запись о расходах на котиков"""
    now = get_current_time()
    if not expense_date:
        expense_date = now.strftime("%Y-%m-%d")
    created_at = now.isoformat()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expenses (amount, category, paid_by_user_id, paid_by_name, note, created_at, expense_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (amount, category, paid_by_user_id, paid_by_name, note, created_at, expense_date))
        conn.commit()
        return cursor.lastrowid

def get_expenses_summary(month_str: str = None):
    """Возвращает сводку расходов за месяц (по умолчанию текущий месяц YYYY-MM)"""
    now = get_current_time()
    if not month_str:
        month_str = now.strftime("%Y-%m")

    with get_db() as conn:
        cursor = conn.cursor()
        
        # Общая сумма за месяц
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE expense_date LIKE ?
        """, (f"{month_str}%",))
        total_month = cursor.fetchone()[0]

        # Сумма по категориям
        cursor.execute("""
            SELECT category, COALESCE(SUM(amount), 0), COUNT(*)
            FROM expenses
            WHERE expense_date LIKE ?
            GROUP BY category
            ORDER BY SUM(amount) DESC
        """, (f"{month_str}%",))
        cat_rows = cursor.fetchall()
        by_category = []
        for r in cat_rows:
            cat_key = r[0]
            label = EXPENSE_CATEGORIES.get(cat_key, cat_key)
            by_category.append({
                "category": cat_key,
                "label": label,
                "amount": round(r[1], 2),
                "count": r[2]
            })

        # Последние 10 расходов
        cursor.execute("""
            SELECT id, amount, category, paid_by_name, note, expense_date
            FROM expenses
            ORDER BY expense_date DESC, id DESC
            LIMIT 10
        """)
        recent_rows = cursor.fetchall()
        recent = [{
            "id": r[0],
            "amount": r[1],
            "category": r[2],
            "category_label": EXPENSE_CATEGORIES.get(r[2], r[2]),
            "paid_by_name": r[3],
            "note": r[4] or "",
            "expense_date": r[5]
        } for r in recent_rows]

        return {
            "month": month_str,
            "total_month": round(total_month, 2),
            "by_category": by_category,
            "recent": recent
        }

# ================= УМНЫЕ НАПОМИНАНИЯ (ЛОГ) =================

def should_send_reminder(reminder_key: str, hours_cooldown: int = 12) -> bool:
    """Проверяет, можно ли отправить напоминание с данным ключом (защита от спама)"""
    now = get_current_time()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT sent_at FROM reminders_log WHERE reminder_key = ?", (reminder_key,))
        row = cursor.fetchone()
        if not row:
            return True
        try:
            sent_dt = datetime.fromisoformat(row[0])
            if (now - sent_dt).total_seconds() >= hours_cooldown * 3600:
                return True
        except Exception:
            return True
        return False

def mark_reminder_sent(reminder_key: str):
    """Помечает напоминание как отправленное"""
    now_str = get_current_time().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reminders_log (reminder_key, sent_at)
            VALUES (?, ?)
            ON CONFLICT(reminder_key) DO UPDATE SET sent_at = excluded.sent_at
        """, (reminder_key, now_str))
        conn.commit()
