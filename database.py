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
    """Инициализация таблиц базы данных"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Таблица кормлений (история)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT,
                fed_at TEXT,
                timestamp REAL
            )
        """)
        
        # Таблица чатов (для личных сообщений и групп)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                chat_type TEXT,
                name TEXT,
                registered_at TEXT
            )
        """)

        # Таблица квестов
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
        conn.commit()

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
            
        # Если генеральная чистка еще не доступна, найдем информацию о ней
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
            
        # Можно завершить, если квест взят этим пользователем, либо если он был свободен (быстрое выполнение)
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
        
        # Если это кормление, также сохраняем в таблицу feedings для совместимости со статусом
        if qtype in ("feed_morning", "feed_evening"):
            cursor.execute("""
                INSERT INTO feedings (user_id, user_name, fed_at, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_id, user_name, now.isoformat(), now.timestamp()))

        conn.commit()
        
        return True, "Квест успешно выполнен!", {
            "id": quest_id,
            "type": qtype,
            "title": title,
            "user_id": user_id,
            "user_name": user_name,
            "completed_at": now
        }
