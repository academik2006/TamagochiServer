import sqlite3

def connect_db():    
    return sqlite3.connect('users.db')

def execute_query(query, params=None):
    """
    Выполняет SQL-запрос и возвращает результат (для SELECT).
    
    :param query: строка с SQL-запросом
    :param params: кортеж с параметрами для подставления в запрос
    :return: список кортежей с результатами (если применимо)
    """
    conn = connect_db()
    result = []
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        # Проверяем, является ли запрос SELECT
        if query.strip().upper().startswith("SELECT"):
            result = cursor.fetchall()  # Получаем все записи
            
        conn.commit()  # Сохраняем изменения для остальных типов запросов
    except Exception as e:
        print(f'Ошибка при выполнении запроса: {e}')
    finally:
        close_connection(conn)
    
    return result

def add_user_to_database(user_id, username):
    """
    Добавляет пользователя в таблицу users.
    
    :param user_id: уникальный ID пользователя
    :param username: имя пользователя
    """
    # Формулируем запрос с использованием плейсхолдеров
    query = "INSERT INTO users (user_id, username) VALUES (?, ?)"
    
    # Передаем параметры через tuple
    execute_query(query, (user_id, username))

def add_character_to_database(user_id, name, gender, bio):
    """
    Добавляет персонаж в таблицу characters.
    
    :param user_id: ID пользователя, которому принадлежит персонаж
    :param name: Имя персонажа
    :param gender: Пол персонажа
    :param bio: Биография персонажа (предполагаю, что это фотография или описание)
    """
    query = """
        INSERT INTO characters (user_id, name, gender, photo) VALUES (?,?,?,?)
    """
    execute_query(query, (user_id, name, gender, bio))

def update_character_parameter(user_id, param_name, value_change):
    """
    Обновляет числовую характеристику персонажа в базе данных.
    
    :param user_id: ID пользователя, чей персонаж обновляется
    :param param_name: Название характеристики (например, голод, усталость и т.п.)
    :param value_change: Значение, на которое изменится характеристика
    """
    query = f"""
        UPDATE characters SET {param_name}=({param_name}+?) WHERE user_id=?
    """
    execute_query(query, (value_change, user_id)) 

def delete_character_from_db(char_id):
    """
    Удаляет персонажа из таблицы characters по уникальному идентификатору.
    
    :param char_id: Уникальный идентификатор персонажа
    """
    query = "DELETE FROM characters WHERE character_id=?"
    execute_query(query, (char_id,))    

def update_character_stats(char_id, hunger, fatigue, entertainment, money_needs, total_state):
    """
    Обновляет характеристики персонажа в базе данных.
    
    :param char_id: Уникальный идентификатор персонажа
    :param hunger: Уровень голода
    :param fatigue: Уровень усталости
    :param entertainment: Уровень развлечения
    :param money_needs: Потребность в финансах
    :param total_state: Общий показатель состояния
    """
    query = """
        UPDATE characters SET hunger=?, fatigue=?, entertainment=?, money_needs=?, total_state=? WHERE character_id=?
    """
    # Ограничиваем значения характеристик неотрицательными числами
    execute_query(query, (max(hunger, 0), max(fatigue, 0), max(entertainment, 0), max(money_needs, 0), total_state, char_id))


def close_connection(conn):    
    if conn is not None:
        conn.close()

def create_db():
    # Таблица users хранит список зарегистрированных пользователей
    execute_query('''
        CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
    # Таблица characters хранит персонажей и их характеристики
    execute_query('''
        CREATE TABLE IF NOT EXISTS characters (
            character_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            gender TEXT CHECK(gender IN ('male', 'female')),
            photo BLOB,
            hunger REAL DEFAULT 100,
            fatigue REAL DEFAULT 100,
            entertainment REAL DEFAULT 100,
            money_needs REAL DEFAULT 100,
            total_state REAL DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
)
''')   
