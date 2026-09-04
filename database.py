import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
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
        
        # Таблица кормлений
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
