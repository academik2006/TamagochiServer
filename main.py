from telebot import types
import telebot
import asyncio
import time
from datetime import datetime
from threading import Thread
import sqlite3
from datetime import datetime
from datetime import timedelta
from promotions import promotions  
from api_key import API_TOKEN
import logging
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import schedule
import random
from messages import WELCOME_TEXT
from messages import RULES_TEXT
from messages import CONDITIONS_TEXT



bot = telebot.TeleBot(API_TOKEN)
bot.delete_webhook()

logging.basicConfig(level=logging.INFO)  
logger = logging.getLogger(__name__)


def create_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Таблица users хранит список зарегистрированных пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

    # Таблица characters хранит персонажей и их характеристики
    cursor.execute('''
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
    conn.commit()
    conn.close()

async def main():    
    logger.info("Бот запущен")
    create_db()     


@bot.message_handler(commands=['start']) #обрабатываем команду старт
def start_fun(message):            
    add_user_on_start(message)       
    

@bot.message_handler(commands=['iaposhka']) #обрабатываем команду iaposhka
def start_fun(message):   
   bot.send_message(message.chat.id, f"В списке пользователей бота {len(get_users())} пользователей")
       
     
@bot.message_handler(func=lambda message: message.text == 'Правила игры')
def handle_game_rules(message):            
    bot.send_message(message.chat.id, RULES_TEXT, parse_mode="HTML")
    logger.info(f"Бот успешно отправил пользователю {message.chat.id} правила игры")

@bot.message_handler(func=lambda message: message.text == 'Условия акции')
def handle_promotion_conditions(message):
    bot.send_message(message.chat.id, CONDITIONS_TEXT, parse_mode="HTML")
    logger.info(f"Бот успешно отправил пользователю {message.chat.id} условия акции")    

def add_user_on_start(message):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    user_id = message.from_user.id
    
    
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))

    if not cursor.fetchone():
        username = message.from_user.first_name 
        image_path = 'event_cal_cat.png'  
        welcome_text = WELCOME_TEXT.format(username=username)
        with open(image_path, 'rb') as photo_file:
            bot.send_photo(chat_id=message.chat.id, photo=photo_file, caption=welcome_text, parse_mode="HTML")       
        # Пользователь новый, добавляем в базу        
        cursor.execute(
           "INSERT INTO users (user_id, username) VALUES (?, ?)",
            (user_id, message.from_user.username)
        )
        conn.commit()

        bot.send_message(user_id, "Приветствуем тебя!\n Изучи правила и условия акции и создавай персонажа:", reply_markup=create_keyboard_for_new_user())        
                
        logger.info(f"В базу данных добавлен новый пользователь {user_id}")
    else:
        check_character_and_send_status(user_id)  
      
    conn.close()  

def create_keyboard_for_choose_gender ():
    keyboard = telebot.types.ReplyKeyboardMarkup(row_width=2)
    btn_create_male = telebot.types.KeyboardButton(text="Создать мужчину")
    btn_create_female = telebot.types.KeyboardButton(text="Создать женщину")
    keyboard.add(btn_create_male, btn_create_female)
    return keyboard

def create_keyboard_for_new_user():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        'Правила игры',
        'Условия акции',
        'Создать персонажа',
    ]

    for text in buttons:
        btn = types.KeyboardButton(text=text)
        keyboard.add(btn)

    return keyboard  
  

@bot.message_handler(func=lambda m: True)
def handle_buttons(message):
    user_id = message.from_user.id
    text = message.text.lower()
    
    if text in ["создать мужчину", "создать женщину"]:
        gender = "male" if text == "создать мужчину" else "female"
        create_character(user_id, gender)
    elif text.startswith("создать персонажа"):
        bot.send_message(user_id, "Выбери пол своего персонажа:", reply_markup=create_keyboard_for_choose_gender())        
    elif text.startswith("кормление"):
        update_character_parameter(user_id, 'hunger', +10)
    elif text.startswith("посещение"):
        update_character_parameter(user_id, 'entertainment', +5)
    elif text.startswith("шопинг") or text.startswith("провести время с друзьями"):
        update_character_parameter(user_id, 'money_needs', +5)
    elif text.startswith("угощение"):
        update_character_parameter(user_id, 'entertainment', +5)
    elif text.startswith("перевод денег"):
        update_character_parameter(user_id, 'money_needs', +5)
    elif text.startswith("встреча с работы"):
        update_character_parameter(user_id, 'entertainment', +5)
    elif text.startswith("предоставление возможности"):
        update_character_parameter(user_id, 'entertainment', +5)
    else:
        pass        

def create_character(user_id, gender):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Генерируем стандартный аватар
    img = generate_avatar(gender)
    bio = img.getvalue()  # Получаем байтовое представление изображения
    
    # Добавляем персонажа в базу
    name = f"{gender.capitalize()} #{random.randint(1000, 9999)}"
    cursor.execute("""
        INSERT INTO characters (user_id, name, gender, photo) VALUES (?,?,?,?)
    """, (user_id, name, gender, bio))
    conn.commit()
    
    bot.send_message(user_id, f"Персонаж {name} успешно создан!")
    check_character_and_send_status(user_id)  

def update_character_parameter(user_id, param_name, value_change):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE characters SET {param_name}=({param_name}+?) WHERE user_id=?
    """, (value_change, user_id))
    conn.commit()

def check_character_and_send_status(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM characters WHERE user_id=?", (user_id,))
    character_data = cursor.fetchone()
    
    if character_data is None:
        return bot.send_message(user_id, "Ваш персонаж отсутствует.")
    
    char_id, _, name, gender, _, hunger, fatigue, entertain, money_need, total_state, _ = character_data
    
    # Формирование клавиатуры действий
    buttons = []
    if gender == 'female':
        buttons.extend(["Кормление роллами", "Посещение кинотеатра", "Шопинг", "Угощение коктейлем"])
    else:
        buttons.extend(["Посещение футбольного матча", "Угощение домашним обедом", "Встреча с работы", "Проведение времени с друзьями"])
    
    keyboard = telebot.types.ReplyKeyboardMarkup(row_width=2)
    for button_text in buttons:
        keyboard.add(button_text)
    
    send_character_image(user_id, char_id, name, gender, hunger, fatigue, entertain, money_need, total_state, keyboard)

def send_character_image(user_id, char_id, name, gender, hunger, fatigue, entertain, money_need, total_state, keyboard=None):
    img_bytes = draw_character(char_id, name, gender, hunger, fatigue, entertain, money_need, total_state)
    bio = BytesIO(img_bytes)
    bio.seek(0)
    bot.send_photo(user_id, bio, caption=f"{name}\nHunger: {hunger:.0f}%\nFatigue: {fatigue:.0f}%\nEntertainment: {entertain:.0f}%\nMoney Needs: {money_need:.0f}%",
                  reply_markup=keyboard)

def generate_avatar(gender):
    width, height = 200, 200
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", size=20)
    
    text = f'{gender.capitalize()} Avatar'
    w, h = font.getbbox(text)[2:]  # Возвращает ширину и высоту текста
    x = (width - w) / 2
    y = (height - h) / 2
    draw.text((x,y), text, fill='black', font=font)
    
    bio = BytesIO()
    img.save(bio, format='PNG')
    return bio

def draw_character(char_id, name, gender, hunger, fatigue, entertain, money_need, total_state):
    # Генерация изображения персонажа (можно заменить на реальные рендеры или анимации)
    img = generate_avatar(gender)
    return img.getvalue()    
  
@bot.message_handler(content_types="web_app_data")
def answer(webAppMes):
    today = datetime.now().day  # получаем сегодняшний день месяца (целое число)
    data = webAppMes.web_app_data.data
    card_number = int(str(data).strip())  # конвертируем в целое число
    
    # Проверяем, открыта ли карточка на текущий день
    if card_number > today:
        bot.send_message(webAppMes.chat.id, "❗️ Карточка ещё закрыта! Ждите наступления нужной даты.", parse_mode="HTML")
        return

    # остальная логика остается прежней...
    found_promotion = next((p for p in promotions if p.get("number") == str(card_number)), None)

    if found_promotion:
        promo_name = found_promotion.get("name")
        condition = found_promotion.get("сondition")
        code = found_promotion.get("promotional_code")

        response_text = (
            f"🎉 Номер карточки в календаре событий: <b>{data}</b>\n\n"
            f"🎉 Твоя акция: <b>{promo_name}</b>\n\n"
            f"✨ Промокод: <code>{code}</code>\n\n"
            f"👍 Условия акции:\n{condition}"
        )
        bot.send_message(webAppMes.chat.id, response_text, parse_mode="HTML")
        logger.info(f"Бот успешно отправил пользователю {webAppMes.chat.id} условия карточки {card_number} ")
    else:
        bot.send_message(webAppMes.chat.id, "❌ Акция не найдена :(", parse_mode="HTML")
        logger.error(f"Бот сообщил пользователю {webAppMes.chat.id} карточка {card_number} не найдена")
  
def get_users():
    try:
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            
            # Выполняем запрос на выборку всех записей
            cursor.execute("SELECT user_id, chat_id FROM users")
            rows = cursor.fetchall()
            
            # Формируем список пар 'user_id' и 'chat_id'
            users = [(row[0]) for row in rows]
            logger.info(f"Бот сформировал список для ежедневного уведомления в {len(users)} пользователей")            
            return users
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        logger.error(f"При запросе списка пользователей произошла ошибка: {e}")
        return []

# Функция для отправки сообщения всем пользователям
def send_daily_reminder():        
    dailyReminderText = """
Просыпайся, герой декабря! 
<b>Новый день — новое окошко в адвенте от Суши Мастер.</b> 
Зайди, открой, получи дозу позитива и сюрприз.
Потому что, кто рано открывает календарь — у того Всё получается"""
    users = get_users()   # Получаем список пользователей
    for chat_id in users:
        try:
            bot.send_message(chat_id, dailyReminderText, parse_mode="HTML")
            logger.info(f"Отправлено ежедневное напоминание {chat_id}")
        except Exception as e:
            logger.error(f"Произошла ошибка при отправке сообщения пользователю {chat_id}: {e}")
            print(f"Произошла ошибка при отправке сообщения пользователю {chat_id}: {e}")
    
    current_time = datetime.now()
    print(f"{current_time} - Напоминание отправлено.")


# Функция для запуска таймера
def run_timer():
    while True:
        current_time = datetime.now()
        if current_time.hour == 9 and current_time.minute == 0:  # Время отправки сообщения (09:00)
            send_daily_reminder()
        time.sleep(60)  # Проверять каждую минуту        

# Запускаем таймер в отдельном потоке
timer_thread = Thread(target=run_timer)
timer_thread.start()


def hourly_update_characters():
    now = datetime.now()
    five_days_ago = now - timedelta(days=5)

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM characters")
    all_chars = cursor.fetchall()
    
    for char_id, user_id, _, _, _, hunger, fatigue, entertain, money_need, total_state, created_at in all_chars:
        hunger -= 10
        fatigue -= 5
        entertain -= 5
        money_need -= 5
        
        new_total_state = sum([hunger, fatigue, entertain, money_need]) / 4
        
        # Проверка уровня здоровья
        if new_total_state <= 20:
            bot.send_message(user_id, f"Ваш персонаж {char_id} покинул вас :(")
            cursor.execute("DELETE FROM characters WHERE character_id=?", (char_id,))
        elif new_total_state <= 30:
            bot.send_message(user_id, f"Состояние Вашего персонажа ухудшилось, вам лучше проверить его состояние!")
        elif new_total_state <= 50:
            bot.send_message(user_id, f"Ухудшение состояния персонажа, пожалуйста, уделите внимание своему питомцу!")
            
        # Проверка возраста персонажа
        created_dt = datetime.strptime(created_at.split('.')[0], "%Y-%m-%d %H:%M:%S")
        if created_dt < five_days_ago:
            bot.send_message(user_id, f"Поздравляю! Ваш персонаж достиг 5-дневного рубежа и получил специальный приз!")
            cursor.execute("DELETE FROM characters WHERE character_id=?", (char_id,))
        
        cursor.execute("""
            UPDATE characters SET hunger=?, fatigue=?, entertainment=?, money_needs=?, total_state=? WHERE character_id=?
        """, (max(hunger, 0), max(fatigue, 0), max(entertain, 0), max(money_need, 0), new_total_state, char_id))
    
    conn.commit()

schedule.every().hour.do(hourly_update_characters)

       
        

if __name__ == "__main__":
    asyncio.run(main())
    bot.infinity_polling()