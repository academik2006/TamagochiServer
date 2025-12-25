from telebot import types
import telebot
import asyncio
import time
from datetime import datetime
from threading import Thread
from datetime import timedelta
from promotions import promotions  
from api_key import API_TOKEN
import logging
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import random
from messages import *
from db_utils import *

bot = telebot.TeleBot(API_TOKEN)
bot.delete_webhook()

logging.basicConfig(level=logging.INFO)  
logger = logging.getLogger(__name__)


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
    user_id = message.from_user.id
    result = execute_query("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not result:
        username = message.from_user.first_name 
        image_path = 'event_cal_cat.png'  
        welcome_text = WELCOME_TEXT.format(username=username)
        with open(image_path, 'rb') as photo_file:
            bot.send_photo(chat_id=message.chat.id, photo=photo_file, caption=welcome_text, parse_mode="HTML")       
        # Пользователь новый, добавляем в базу        
        add_user_to_database(user_id, message.from_user.username)              
        bot.send_message(user_id, "Приветствуем тебя!\n Изучи правила и условия акции и создавай персонажа", reply_markup=create_keyboard_for_new_user())                        
        logger.info(f"В базу данных добавлен новый пользователь {user_id}")
    else:
        check_character_and_send_status(user_id)    

def create_keyboard_for_choose_gender ():

    buttons = [
        'Мужской',
        'Женский'        
    ]
    return create_keyboard (buttons)    

def create_keyboard_for_new_user():

    buttons = [
        'Правила игры',
        'Условия акции',
        'Создать персонажа',
    ]
    return create_keyboard (buttons)
    

def create_keyboard(buttons):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)    
    for text in buttons:
        btn = types.KeyboardButton(text=text)
        keyboard.add(btn)

    return keyboard  
  

@bot.message_handler(func=lambda m: True)
def handle_buttons(message):
    user_id = message.from_user.id
    text = message.text.lower()
    
    if text in ["мужской", "женский"]:
        gender = "male" if text == "мужской" else "female"
        create_character(user_id, gender)
    elif text.startswith("создать персонажа"):
        bot.send_message(user_id, "Выбери пол своего персонажа:", reply_markup=create_keyboard_for_choose_gender())        
    elif text.startswith("кормление"):
        update_character_parameter(user_id, 'hunger', +10)
    elif text.startswith("посещение"):
        update_character_parameter(user_id, 'entertainment', 5)
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
    # Генерируем стандартный аватар
    img = generate_avatar(gender)
    bio = img.getvalue()  # Получаем байтовое представление изображения
    
    # Добавляем персонажа в базу
    name = f"{gender.capitalize()} #{random.randint(1000, 9999)}"
    add_character_to_database(user_id, name, gender, bio)    
    
    bot.send_message(user_id, f"Персонаж {name} успешно создан!")
    check_character_and_send_status(user_id)  

def check_character_and_send_status(user_id):
    result = execute_query("SELECT * FROM characters WHERE user_id=?", (user_id,))
    
    # Проверяем, есть ли результат вообще
    if not result or len(result) == 0:
        return bot.send_message(user_id, "Ваш персонаж отсутствует.")
    
    character_data = result[0]
    
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

  
def get_users():
    try:                                
            # Выполняем запрос на выборку всех записей
            result = execute_query("SELECT user_id, chat_id FROM users")                        
            # Формируем список пар 'user_id' и 'chat_id'
            users = [(row[0]) for row in result]
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
                        
        # Выбираем диапазон часов, в течение которого будем обновлять персонажей
        if 9 <= current_time.hour <= 16 and current_time.minute == 0:
            hourly_update_characters()
        
        time.sleep(60)  # Проверяем каждую минуту      

# Запускаем таймер в отдельном потоке
timer_thread = Thread(target=run_timer)
timer_thread.start()


def hourly_update_characters():
    now = datetime.now()
    five_days_ago = now - timedelta(days=5)
        
    result = execute_query("SELECT * FROM characters")
    all_chars = result
    
    for char_id, user_id, _, _, _, hunger, fatigue, entertain, money_need, total_state, created_at in all_chars:
        hunger -= 10
        fatigue -= 5
        entertain -= 5
        money_need -= 5
        
        new_total_state = sum([hunger, fatigue, entertain, money_need]) / 4
        
        # Проверка уровня здоровья
        if new_total_state <= 20:
            bot.send_message(user_id, f"Ваш персонаж {char_id} покинул вас :(")
            delete_character_from_db(char_id)            
        elif new_total_state <= 30:
            bot.send_message(user_id, f"Состояние Вашего персонажа ухудшилось, вам лучше проверить его состояние!")
        elif new_total_state <= 50:
            bot.send_message(user_id, f"Ухудшение состояния персонажа, пожалуйста, уделите внимание своему питомцу!")
            
        # Проверка возраста персонажа
        created_dt = datetime.strptime(created_at.split('.')[0], "%Y-%m-%d %H:%M:%S")
        if created_dt < five_days_ago:
            bot.send_message(user_id, f"Поздравляю! Ваш персонаж достиг 5-дневного рубежа и получил специальный приз!")
            delete_character_from_db(char_id)            
        
        update_character_stats(max(hunger, 0), max(fatigue, 0), max(entertain, 0), max(money_need, 0), new_total_state, char_id)        
           

if __name__ == "__main__":
    asyncio.run(main())
    bot.infinity_polling()