import sqlite3

def get_all_tables(db_path):
    # Открытие соединения с базой данных
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Запрос для получения списка всех таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    conn.close()

    return [table[0] for table in tables]  # Возвращаем список названий таблиц


def get_table_data(db_path, table_name):
    # Открытие соединения с базой данных
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Запрос для получения всех данных из таблицы
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    conn.close()

    return rows  # Возвращаем все строки данных из таблицы


def main():
    db_path = 'recruit.db'  # Путь к вашей базе данных

    # Получаем список всех таблиц
    tables = get_all_tables(db_path)
    if tables:
        print("Существующие таблицы в базе данных:")
        for table in tables:
            print(f"Таблица: {table}")
            data = get_table_data(db_path, table)
            if data:
                print(f"Данные в таблице {table}:")
                for row in data:
                    print(row)
            else:
                print(f"Нет данных в таблице {table}")
    else:
        print("Нет таблиц в базе данных.")


if __name__ == "__main__":
    main()
