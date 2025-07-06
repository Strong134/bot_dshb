import sqlite3

# Подключение к базе данных
def connect_db():
    return sqlite3.connect('discord_steam.db')

# Функция для внесения данных в базу
def insert_data(discord_id, steam_id):
    if len(str(steam_id)) != 17:
        return 0
    conn = connect_db()
    cursor = conn.cursor()
    
    # Вставка данных в таблицу
    cursor.execute('''
    INSERT OR REPLACE INTO users (discord_id, steam_id)
    VALUES (?, ?)
    ''', (discord_id, steam_id))

    conn.commit()  # Подтверждение изменений
    conn.close()   # Закрытие соединения

# Функция для получения Steam ID по Discord ID
def get_steam_id(discord_id):
    conn = connect_db()
    cursor = conn.cursor()
    
    # Выполнение запроса для поиска Steam ID
    cursor.execute('''
    SELECT steam_id FROM users WHERE discord_id = ?
    ''', (discord_id,))
    result = cursor.fetchone()
    
    conn.close()  # Закрытие соединения
    
    if result:
        return result[0]  # Возвращаем Steam ID
    else:
        return 343  # Если Discord ID не найден

# Пример использования:
# Вставляем данные
insert_data("648270145151696899", "76561199247164460")


# Получаем Steam ID по Discord ID
discord_id_input = "648270145151696899"
steam_id = get_steam_id(discord_id_input)
print(f"Steam ID для Discord ID {discord_id_input}: {steam_id}")