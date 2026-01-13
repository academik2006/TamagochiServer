from telebot import types
import telebot
import asyncio
import time
import io
from datetime import datetime
from threading import Thread
from datetime import timedelta
from promotions import promotions  
from telebot.types import InputMediaPhoto
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

# Словарь для временного хранения данных пользователей
user_data = {}


async def main():    
    logger.info("Бот запущен")
    create_db()     


@bot.message_handler(commands=['start']) #обрабатываем команду старт
def start_fun(message):
    logger.info(f"Сработала команда Start")     
    add_user_on_start(message)    
       
     
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


def create_keyboard_for_choose_avatar_photo ():

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    load_button = types.InlineKeyboardButton(text="Загрузить своё", callback_data='load_own')
    select_standard_button = types.InlineKeyboardButton(text="Выбрать стандартное", callback_data='select_standard')
    keyboard.add(load_button, select_standard_button)
    
    return keyboard

def create_keyboard_for_choose_gender ():

    buttons = [
        'Мужской',
        'Женский'        
    ]
    return create_keyboard (buttons, True)    

def create_keyboard_for_new_user():

    buttons = [
        'Правила игры',
        'Условия акции',
        'Создать персонажа',
    ]
    return create_keyboard (buttons, False)

def create_keyboard_for_continue():

    buttons = [
        'Навестить персонажа'        
    ]
    return create_keyboard (buttons, False)
    

def create_keyboard(buttons, one_time):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, one_time_keyboard=one_time)    
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
        user_data[message.chat.id] = {"gender": gender}        
        bot.send_message(message.chat.id, "Теперь выбери имя своего персонажа (не более 30 символов, буквы и цифры).")
        bot.register_next_step_handler(message, process_character_name)
    elif text.startswith("создать персонажа"):        
        bot.send_message(user_id, "Выбери пол своего персонажа", reply_markup=create_keyboard_for_choose_gender())        
    elif text.startswith("навестить персонажа"):
        bot.send_message(user_id, "Вернулся голубчик")        
        check_character_and_send_status(user_id)
    elif text.startswith("кормление"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'hunger', +10)        
    elif text.startswith("посещение"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'entertainment', +5)                
    elif text.startswith("шопинг"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'money_needs', +5)
    elif text.startswith("провести время с друзьями"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'money_needs', +5)    
    elif text.startswith("угощение"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'hunger', +10) 
    elif text.startswith("перевод денег"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'money_needs', +5)
    elif text.startswith("встреча с работы"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'fatigue', +5) 
    elif text.startswith("предоставление возможности"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'entertainment', +5)         
    else:
        pass        


def ugrade_character_parameter_and_show_new_avatar (user_id, param_name, value_change):
    update_character_parameter(user_id, param_name, value_change)
    check_character_and_send_status(user_id)

def process_character_name(message):
    name = message.text.strip()
    if not is_valid_name(name):
        bot.reply_to(message, "Имя некорректно. Повторите попытку.")
        return
    
    user_data[message.chat.id]["name"] = name
    bot.send_message(message.chat.id, "Выбери фото для персонажа", reply_markup=create_keyboard_for_choose_avatar_photo())

# Функция для проверки правильности имени
def is_valid_name(name):
    """Проверяет длину имени и наличие спецсимволов."""
    return len(name.strip()) <= 30 and all(char.isalnum() or char.isspace() for char in name) 

@bot.callback_query_handler(func=lambda call: call.data == 'load_own')
def handle_load_own(call):
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "Отправьте вашу фотографию.")
    bot.register_next_step_handler_by_chat_id(chat_id, process_user_photo)

def process_user_photo(message):
    if message.content_type != 'photo':
        bot.reply_to(message, "Это не фотография. Пожалуйста, отправьте фото.")
        return
    
    # Берём самую большую версию фотографии
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # Компрессия изображения до 150х150 пикселей
    from PIL import Image
    image = Image.open(io.BytesIO(downloaded_file)).resize((150, 150))
    compressed_image_bytes = io.BytesIO()
    image.save(compressed_image_bytes, format='PNG')  # Сохраняем сжатое изображение в памяти
    compressed_image_bytes.seek(0)
    
    # Сохраняем изображение в словаре user_data
    user_data[message.chat.id]['photo'] = compressed_image_bytes.read()
    bot.send_message(message.chat.id, "Фотография принята.", reply_markup=types.ReplyKeyboardRemove())
    # Переходим к созданию персонажа
    create_character(message.chat.id)   

@bot.callback_query_handler(func=lambda call: call.data == 'select_standard')
def handle_select_standard(call):
    chat_id = call.message.chat.id
    gender = user_data[chat_id]['gender']
    images = []
    buttons = []
    
    # Показ стандартных изображений
    for i in range(3):
        filename = f'men_{i}.png' if gender == 'male' else f'girl_{i}.png'
        with open(filename, 'rb') as f:
            img_data = f.read()
            
        button_text = str(i+1)
        buttons.append(types.InlineKeyboardButton(button_text, callback_data=f'select:{button_text}'))
        images.append(img_data)
    
    # Формируем inline-клавиатуру с номерами картинок
    keyboard = types.InlineKeyboardMarkup().add(*buttons)
    bot.send_media_group(chat_id, [InputMediaPhoto(image) for image in images])
    bot.send_message(chat_id, "Выберите одну из фотографий:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('select:'))
def handle_select_standard_photo(call):
    selected_number = int(call.data.split(':')[1]) - 1  # Преобразование номера в индекс массива
    chat_id = call.message.chat.id
    gender = user_data[chat_id]['gender']
    filename = f'men_{selected_number}.png' if gender == 'male' else f'girl_{selected_number}.png'
    
    with open(filename, 'rb') as f:
        user_data[chat_id]['photo'] = f.read()
    
    bot.answer_callback_query(call.id, show_alert=False, text="Фото выбрано.")
    create_character(chat_id)


def create_character(user_id):    
    data = user_data.pop(user_id)
    gender = data['gender']
    name = data.get('name', None)  # Если имя ещё не задано, оставляем None
    photo_blob = data.get('photo', None)
    
    # Генерация стандартного имени, если имя не было предварительно определено
    if not name:
        name = f"{gender.capitalize()} #{random.randint(1000, 9999)}"
    
    # Добавление персонажа в базу данных
    add_character_to_database(user_id, name, gender, photo_blob)            
    bot.send_message(user_id, f"Персонаж успешно создан!")
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
    
    keyboard = create_keyboard(buttons, False)
    
    send_character_image(user_id, char_id, name, gender, hunger, fatigue, entertain, money_need, total_state, keyboard)

def generate_avatar(gender):
    width, height = 200, 200
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arial.ttf", size=20)
    
    text = f'{gender.capitalize()} Avatar'
    w, h = font.getbbox(text)[2:]
    x = (width - w) / 2
    y = (height - h) / 2
    draw.text((x, y), text, fill='black', font=font)
    
    bio = BytesIO()
    img.save(bio, format='PNG')
    return bio.getvalue()

def send_character_image(user_id, char_id, name, gender, hunger, fatigue, entertain, money_need, total_state, keyboard=None):
    conn = sqlite3.connect('users.db')  # Подключение к базе данных
    cursor = conn.cursor()
    
    # Получаем изображение персонажа из базы данных
    cursor.execute("SELECT photo FROM characters WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    
    if row is None:
        # Если персонажа нет в базе данных, генерируем аватар
        img_bytes = generate_avatar(gender)
    elif row[0] is None:
        # Если изображение отсутствует в базе данных, тоже генерируем аватар
        img_bytes = generate_avatar(gender)
    else:
        img_bytes = row[0]  # Получаем BLOB-данные изображения
    
    # Закрываем соединение с базой данных
    conn.close()
    
    # Готовим изображение для отправки
    bio = BytesIO(img_bytes)
    bio.seek(0)
    
    # Формирование подписи к картинке
    caption = (
        f"{name}\n"
        f"Голод: {hunger:.0f}%\n"
        f"Усталость: {fatigue:.0f}%\n"
        f"Потребность в развлечениях: {entertain:.0f}%\n"
        f"Необходимость в финансах: {money_need:.0f}%"
    )
    
    # Отправляем изображение
    bot.send_photo(user_id, bio, caption=caption, reply_markup=keyboard)     

def hourly_update_characters():   
        
    result = execute_query("SELECT * FROM characters")
    all_chars = result
        
    for char_id, user_id, _, name, _, hunger, fatigue, entertain, money_need, total_state, created_at in all_chars:
        hunger -= 10
        fatigue -= 5
        entertain -= 5
        money_need -= 5
        
        new_total_state = sum([hunger, fatigue, entertain, money_need]) / 4
        logger.info(f"Результат расчета состояния {new_total_state} - {name} - {char_id} - {hunger} - {fatigue} - {entertain} - {money_need}")
        update_character_stats(max(hunger,0), max(fatigue,0), max(entertain,0), max(money_need,0), max(new_total_state,0), char_id)     
        check_total_state(user_id,char_id,name,max(new_total_state,0))        
        check_character_old(user_id, char_id, created_at)                                          
        
        logger.info(f"Запущена функция обновления статистики персонажа в БД для {char_id} - {new_total_state}")

def check_total_state(user_id, char_id, name, new_total_state):
    # Проверка уровня здоровья
        if new_total_state <= 20:
            bot.send_message(user_id, f"Ваш персонаж {name} покинул вас :(")
            delete_character_from_db(char_id)            
        elif new_total_state <= 30:            
            bot.send_message(user_id, f"Состояние Вашего персонажа ухудшилось до {new_total_state}, вам лучше проверить его состояние!", reply_markup=create_keyboard_for_continue(), parse_mode="HTML") 
        elif new_total_state <= 50:
            bot.send_message(user_id, f"Состояние Вашего персонажа ухудшилось до {new_total_state}, вам лучше проверить его состояние!", reply_markup=create_keyboard_for_continue(), parse_mode="HTML") 

def check_character_old (user_id, char_id, created_at):
    # Проверка возраста персонажа
        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        created_dt = datetime.strptime(created_at.split('.')[0], "%Y-%m-%d %H:%M:%S")
        if created_dt < five_days_ago:
            bot.send_message(user_id, f"Поздравляю! Ваш персонаж достиг 5-дневного рубежа и получил специальный приз!")
            delete_character_from_db(char_id)             
            

# Функция для запуска таймера
def run_timer():
    while True:
        current_time = datetime.now()

        #send_daily_reminder()
        #hourly_update_characters()
                        
        # Выбираем диапазон часов, в течение которого будем обновлять персонажей
        #if 9 <= current_time.hour <= 16 and current_time.minute == 0:
        #    send_daily_reminder()
        #    hourly_update_characters()
        hourly_update_characters()
        
        time.sleep(20)  # Проверяем каждую минуту      

# Запускаем таймер в отдельном потоке
timer_thread = Thread(target=run_timer)
timer_thread.start()
  
           

if __name__ == "__main__":
    asyncio.run(main())
    bot.infinity_polling()