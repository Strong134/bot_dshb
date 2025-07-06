import sqlite3
from datetime import datetime, timedelta


# База данных SQLite
DB_NAME = "recruit.db"

# Функция для создания базы данных и таблицы
def create_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recruits (
            discord_id INTEGER PRIMARY KEY,
            time_added TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Функция для добавления записи в базу данных
def add_recruit_to_db(discord_id):
    # Сохраняем текущее время в формате 'YYYY-MM-DD HH:MM:SS'
    time_added = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Вставляем discord_id и время в базу данных
    cursor.execute("""
            INSERT OR REPLACE INTO recruits (discord_id, time_added) 
            VALUES (?, ?)
        """, (discord_id, time_added))
    conn.commit()
    conn.close()

# Функция для получения всех записей из базы данных
def get_all_recruits():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT discord_id, time_added FROM recruits")
    recruits = cursor.fetchall()
    conn.close()
    return recruits

# Функция для удаления записи из базы данных
def remove_recruit_from_db(discord_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recruits WHERE discord_id = ?", (discord_id,))
    conn.commit()
    conn.close()

# Функция для получения времени добавления рекрута
def get_recruit_time(discord_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT time_added FROM recruits WHERE discord_id = ?", (discord_id,))
    recruit = cursor.fetchone()
    conn.close()
    return recruit
