import sqlite3
from datetime import datetime  # Импортируем datetime

def init_db():
    """Инициализация базы данных и создание таблицы для голосований"""
    conn = sqlite3.connect('votes.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS vote_sessions (
            message_id TEXT PRIMARY KEY,
            discord_id TEXT,
            vote_yes INTEGER DEFAULT 0,
            vote_no INTEGER DEFAULT 0,
            voted BOOLEAN DEFAULT FALSE,
            result TEXT,
            created_at TEXT  -- Добавим дату создания голосования
        )
    """)
    conn.commit()
    conn.close()

def add_vote_session(message_id, discord_id):
    """Добавление нового голосования в базу данных"""
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Сохраняем дату создания голосования
    conn = sqlite3.connect('votes.db')
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO vote_sessions (message_id, discord_id, vote_yes, vote_no, voted, result, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (message_id, discord_id, 0, 0, False, None, created_at))
    conn.commit()
    conn.close()

def get_votes(message_id):
    """Получение голосов за и против из базы данных"""
    conn = sqlite3.connect('votes.db')
    c = conn.cursor()
    c.execute("SELECT vote_yes, vote_no FROM vote_sessions WHERE message_id = ?", (message_id,))
    result = c.fetchone()
    conn.close()
    return result

def remove_vote_session(message_id):
    """Удаление записи о голосовании из базы данных"""
    conn = sqlite3.connect('votes.db')
    c = conn.cursor()
    c.execute("DELETE FROM vote_sessions WHERE message_id = ?", (message_id,))
    conn.commit()
    conn.close()

# Функция для получения всех рекрутов из базы
def get_all_recruits1():
    """Получение всех рекрутов из базы данных"""
    conn = sqlite3.connect('votes.db')
    c = conn.cursor()
    c.execute("SELECT discord_id, created_at FROM vote_sessions")
    recruits = c.fetchall()
    conn.close()
    return recruits

def update_vote_result(message_id, result):
    """Обновляет результат голосования в базе данных"""
    conn = sqlite3.connect('votes.db')
    c = conn.cursor()
    
    c.execute("""
        UPDATE vote_sessions 
        SET result = ? 
        WHERE message_id = ?
    """, (result, message_id))
    
    conn.commit()
    conn.close()