import math
import os
import re
from telebot import types
import telebot
import asyncio
import time
from datetime import datetime
from threading import Thread
from datetime import timedelta
from api_key import API_TOKEN
import logging
import random
from db_utils import *
from messages import *
from keyboards import *
from PIL import Image, ImageDraw, ImageFont
import io

STATE_LOSE_LOWER_BOUND = 20
STATE_RED_LOWER_BOUND = 35
STATE_YELLOW_UPPER_BOUND = 50
STATE_GREEN_LOWER_BOUND = 85
NO_STANDART_FOTO = -127
HOURS_TO_WIN = 48
HOURS_SHIFT_SERVER = 3

bot = telebot.TeleBot(API_TOKEN)
bot.delete_webhook()

logging.basicConfig(level=logging.INFO)  
logger = logging.getLogger(__name__)

# Словарь для временного хранения данных пользователей
user_data = {}
blocked_users = set()

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

@bot.message_handler(func=lambda message: message.text == 'Сколько до финиша')
def handle_time_left(message):            
    last_time_message = get_time_to_win(message)
    username = message.from_user.username or 'UnknownUser'  # Берём username, если есть, иначе используем UnknownUser
    bot.send_message(message.chat.id, last_time_message, parse_mode="HTML", reply_markup=create_keyboard_for_continue())
    logger.info(f"Бот успешно отправил пользователю {message.chat.id} - {username} сколько до финиша")

def add_user_on_start(message):        
    user_id = message.from_user.id
    result = execute_query("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not result:
        username = message.from_user.first_name 
        image_path = 'welcome_pic.jpg'  
        welcome_text = WELCOME_TEXT.format(username=username)
        with open(image_path, 'rb') as photo_file:
            bot.send_photo(chat_id=message.chat.id, photo=photo_file, caption=welcome_text, parse_mode="HTML", reply_markup=create_keyboard_for_new_user())       
        # Пользователь новый, добавляем в базу        
        add_user_to_database(user_id, message.from_user.username)                      
        logger.info(f"В базу данных добавлен новый пользователь {user_id}")
    else:        
        check_character_and_send_status(user_id)    

@bot.message_handler(func=lambda m: True)
def handle_buttons(message):
    user_id = message.from_user.id
    text = message.text.lower()
    
    if text in ["мужской", "женский"]:
        gender = "male" if text == "мужской" else "female"
        user_data[message.chat.id] = {"gender": gender}        
        bot.send_message(message.chat.id, "Теперь выбери имя своего персонажа (не более 12 символов, буквы и цифры)")
        bot.register_next_step_handler(message, process_character_name)
    elif text.startswith("создать персонажа"):        
        bot.send_message(user_id, "Выбери пол своего персонажа", reply_markup=create_keyboard_for_choose_gender())
    else:
        pass   

@bot.callback_query_handler(func=lambda call: True)
def handle_button_click(call):
    chat_id = call.message.chat.id
    callback_data = call.data    
        
    # Обрабатываем каждое действие отдельно
    if callback_data == 'action_hunger':        
        ugrade_character_parameter_and_show_new_avatar(chat_id, 'hunger', +40)                
    elif callback_data == 'action_fatigue':        
        ugrade_character_parameter_and_show_new_avatar(chat_id, 'fatigue', +20)
    elif callback_data == 'action_entertainment':        
        ugrade_character_parameter_and_show_new_avatar(chat_id, 'entertainment', +20)
    elif callback_data == 'action_kiss':        
        ugrade_character_parameter_and_show_new_avatar(chat_id, 'money_needs', +20)                
    elif callback_data == 'load_own':
        chat_id = call.message.chat.id
        bot.send_message(chat_id, "Отправьте вашу фотографию.")
        bot.register_next_step_handler_by_chat_id(chat_id, process_user_photo) 
    elif callback_data == 'visit_avatar':
        try:
            # Скрываем клавиатуру после нажатия
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        except Exception as e:
            print(f"Error removing keyboard: {e}")
        check_character_and_send_status(chat_id)
    elif callback_data == 'select_standard':
        select_standard_photo(chat_id)
    elif callback_data.startswith('select:'):       
        select_standard_photo_handler(call)
    else:        
        bot.send_message(chat_id, "Неверное действие.")

    # Подтверждение сервера о принятии нажатия кнопки
    bot.answer_callback_query(call.id)


def ugrade_character_parameter_and_show_new_avatar (user_id, param_name, value_change):
    need_send_message, gender = update_character_parameter(user_id, param_name, value_change)
    # Если нужно отправить сообщение, делаем это отсюда
    if need_send_message:
        send_random_message(user_id, param_name, gender)    
        return
    
    char_id, _, name, gender, _, hunger, fatigue, entertain, money_need, total_state, standart_photo_number, _ = get_current_avatar_param(user_id)
    new_total_state = calculate_total_state(hunger, fatigue, entertain, money_need)        
    update_character_stats(max(hunger,0), max(fatigue,0), max(entertain,0), max(money_need,0), max(new_total_state,0), char_id)       
    
    if new_total_state <= STATE_RED_LOWER_BOUND:            
        replace_avatar_foto_in_db(user_id, gender, standart_photo_number, 2, total_state)            
    elif new_total_state <= STATE_YELLOW_UPPER_BOUND:            
        replace_avatar_foto_in_db(user_id, gender, standart_photo_number, 1, total_state)            
    elif new_total_state <= STATE_GREEN_LOWER_BOUND:            
        replace_avatar_foto_in_db(user_id, gender, standart_photo_number, 1, total_state)            
    else:
        replace_avatar_foto_in_db(user_id, gender, standart_photo_number, 0, total_state)

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
    return len(name.strip()) <= 12 and all(char.isalnum() or char.isspace() for char in name) 

def resize_proportionally(img, max_width=300, max_height=446):
    """Масштабирует изображение, сохраняя пропорции, и ограничивая максимальные размеры."""
    orig_width, orig_height = img.size
    
    # Проверяем, нужно ли уменьшать изображение
    if orig_width > max_width or orig_height > max_height:
        # Рассчитываем масштабы уменьшения
        width_scale = max_width / orig_width
        height_scale = max_height / orig_height
        scale_factor = min(width_scale, height_scale)
        
        # Высчитываем новые размеры
        new_width = round(orig_width * scale_factor)
        new_height = round(orig_height * scale_factor)
    else:
        # Если изображение уже достаточно маленькое, ничего не делаем
        new_width, new_height = orig_width, orig_height
    
    # Масштабируем изображение
    resized_img = img.resize((new_width, new_height), Image.LANCZOS)
    return resized_img

def process_user_photo(message):
    if message.content_type != 'photo':
        bot.reply_to(message, "Это не фотография. Пожалуйста, отправьте фото.")
        return
    
    # Загружаем файл
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    # Открываем изображение
    img = Image.open(io.BytesIO(downloaded_file))

    # Меняем размер изображения, сохраняя пропорции
    resized_img = resize_proportionally(img, max_width=300, max_height=446)

    # Сохраняем картинку в памяти
    buffered = io.BytesIO()
    resized_img.save(buffered, format="JPEG")
    resized_image_bytes = buffered.getvalue()

    # Сохраняем фотографию в user_data
    user_data[message.chat.id]['photo'] = resized_image_bytes
    bot.send_message(message.chat.id, "Фотография принята.", reply_markup=types.ReplyKeyboardRemove())
    create_character(message.chat.id)


def select_standard_photo(chat_id):    
    gender = user_data[chat_id]['gender']
    buttons = []           

    # Показ стандартных изображений
    for i in range(4):
        filename = f'men_{i}_0.png' if gender == 'male' else f'women_{i}_0.png'
        full_path = os.path.join('pic','pic_avatar', filename)
        with open(full_path, 'rb') as f:
            img_data = f.read()
        
        button_text = str(i+1)
        buttons.append(types.InlineKeyboardButton(button_text, callback_data=f'select:{button_text}'))
        # Отдельно отправляем каждую картинку
        bot.send_photo(chat_id, img_data)

    # Формируем inline-клавиатуру с номерами картинок
    keyboard = types.InlineKeyboardMarkup().add(*buttons)
    bot.send_message(chat_id, "Выбери одну из фотографий:", reply_markup=keyboard)

def select_standard_photo_handler(call):
    selected_number = int(call.data.split(':')[1]) - 1  # Преобразование номера в индекс массива
    chat_id = call.message.chat.id
    gender = user_data[chat_id]['gender']
    user_data[chat_id]['standart_photo_number'] = selected_number
    
    filename = f'men_{selected_number}_0.png' if gender == 'male' else f'women_{selected_number}_0.png'
    full_path = os.path.join('pic','pic_avatar', filename)   

    with open(full_path, 'rb') as f:
        user_data[chat_id]['photo'] = f.read()           
    
    bot.answer_callback_query(call.id, show_alert=False, text="Фото выбрано.")
    create_character(chat_id)

def send_random_message(chat_id, param_name, gender):
    """
    Отправляет случайное сообщение пользователю в зависимости от типа параметра и пола персонажа.
    """
    messages_list = MESSAGES_BY_PARAM_AND_GENDER.get(param_name, {}).get(gender)
    if messages_list:
        message = random.choice(messages_list)
        bot.send_message(chat_id, message)

def draw_progress_bars(image, hunger, fatigue, entertain, money_need):
    """
    Рисует горизонтальные прогресс-бары поверх изображения.
    """        
    bar_height = 50
    padding = 70
    margin_top = image.height - ((bar_height + padding) * 4) - 280
            
    # Создание копии изображения для рисования
    draw = ImageDraw.Draw(image)
    
    # Цвета
    bg_color = "#ffffff"
        
    values = [(hunger, "#ff0000"), (fatigue, "#e75c0c"), (entertain, "#e6d708"), (money_need, "#0ceb2a")]
    # Иконки
    icons = ['pic/icon_hunger.png', 'pic/icon_fatigue.png', 'pic/icon_entertain.png', 'pic/icon_lovely.png']
    padding_progress_bar = 140
        
    for i, (value, color) in enumerate(values):
        y_pos = margin_top + (i * (bar_height + padding)) + 140

        #Загрузка иконки
        icon_path = icons[i]
        icon = Image.open(icon_path)        
        # Размещаем иконку перед прогресс-баром
        image.paste(icon, (padding_progress_bar - 100, y_pos - 25), icon)
               
        # Рисование фона прогресс-бара
        draw.rectangle([padding_progress_bar, y_pos, image.width - padding_progress_bar, y_pos + bar_height], fill=bg_color)
                        
        # Прогресс-бар заполненный цветом
        progress_width = value / 100 * (image.width - 2*padding_progress_bar)
        draw.rectangle([padding_progress_bar, y_pos, padding_progress_bar+progress_width, y_pos + bar_height], fill=color)        
                    
    return image


# Новый метод отправки изображения с графиками
def send_character_image_with_progress(user_id, img_bytes, keyboard=None):        
    bio = io.BytesIO(img_bytes)
    bio.seek(0)       
    bot.send_photo(user_id, bio, reply_markup=keyboard)        

def create_character(user_id):    
    data = user_data.pop(user_id)
    gender = data['gender']
    name = data.get('name', None)  # Если имя ещё не задано, оставляем None
    standart_photo_number = int(data.get('standart_photo_number', NO_STANDART_FOTO))
    photo_blob = data.get('photo', None)
      
    add_character_to_database(user_id, name, gender, photo_blob,standart_photo_number)                
    replace_avatar_foto_in_db(user_id, gender, standart_photo_number, 0, 100)
    
    bot.send_message(user_id, text="Твой персонаж успешно создан!", reply_markup = create_keyboard_for_info())
    check_character_and_send_status(user_id)  

def generate_image_with_progress_bars(user_id, name, hunger, fatigue, entertain, money_need, total_state):
        
    img_avatar_bytes = get_character_photo_from_db(user_id)
    img_avatar = convert_byte_image_to_png(img_avatar_bytes)
    
    # Загружаем фоновый файл    
    background_path = os.path.join('pic', 'back_big.png')    
    background_img = Image.open(background_path)
    x_avatar = background_img.width // 2 - img_avatar.width // 2 
    y_avatar = 100
    
    # Размещаем уменьшенное изображение на фоне
    background_img.paste(img_avatar, (x_avatar, y_avatar))

    # Рисуем имя персонажа над аватаром
    font_size = 54
    font = ImageFont.truetype("commissioner_bold.ttf", size=font_size)
    draw = ImageDraw.Draw(background_img)

    # Получаем размер текста с помощью getbbox
    text_rect = font.getbbox(name)

    if text_rect is not None:
        text_w = text_rect[2] - text_rect[0]
        text_h = text_rect[3] - text_rect[1]
    else:
        # Если getbbox не смог определить размеры, используем textsize
        text_w, text_h = draw.textsize(name, font=font)

    # Если и textsize вернул None, задаём минимальный размер
    if text_w is None or text_h is None:
        text_w, text_h = 8, 8

    # Центрируем текст по ширине
    text_position = (
    (background_img.width - text_w) // 2,  # Центрирование по горизонтали
    y_avatar - 90                         # Оставляем прежнюю вертикальную позицию
    )

    # Отображаем текст
    draw.text(text_position, name, font=font, fill="#C11719")
    
    # Применяем функцию рисования шкал
    final_img_with_progress_bars = draw_progress_bars(background_img, hunger, fatigue, entertain, money_need)
    
    # Преобразовываем изображение в байтовый объект для отправки
    output_buffer = io.BytesIO()
    final_img_with_progress_bars.save(output_buffer, format='PNG')
    output_buffer.seek(0)
    
    return output_buffer.read()

def convert_byte_image_to_png (image_byte):
    return Image.open(io.BytesIO(image_byte))

def get_avatar_image_with_frame_color(user_id, gender, standart_photo_number, level, new_total_state):
    original_img = get_character_photo_from_db(user_id)
    img_avatar = Image.open(io.BytesIO(original_img))

    if new_total_state <= STATE_RED_LOWER_BOUND:
        frame_color = "#FF0000"  # Красный
    elif new_total_state <= STATE_YELLOW_UPPER_BOUND:
        frame_color = "#FFFF00"  # Желтый
    elif new_total_state <= STATE_GREEN_LOWER_BOUND:
        frame_color = "#FFFF00"  # Желтый
    else:
        frame_color = "#00FF00"  # Зеленый

    framed_avatar = add_frame_to_image(img_avatar.copy(), frame_color)

    # Сохраняем обработанное изображение в BytesIO
    buffered = io.BytesIO()
    framed_avatar.save(buffered, format="PNG")
    return buffered.getvalue()  # Вернем байтовые данные

def add_frame_to_image(img_avatar, color):
    draw = ImageDraw.Draw(img_avatar)
    width = 15  # Ширина рамки в пикселях
    size = img_avatar.size  # Размер изображения
    
    # Рисование рамки по краям изображения
    draw.rectangle([(0, 0), (size[0], width)], fill=color)          # Верхняя граница
    draw.rectangle([(0, size[1]-width), (size[0], size[1])], fill=color)  # Нижняя граница
    draw.rectangle([(0, 0), (width, size[1])], fill=color)           # Левая граница
    draw.rectangle([(size[0]-width, 0), (size[0], size[1])], fill=color)  # Правая граница    
    return img_avatar
   

def check_character_and_send_status(user_id): 

    result = get_current_avatar_param(user_id)
    if result is None:
        print("Не найден персонаж")
        bot.send_message(user_id, "Не найден персонаж",reply_markup=create_keyboard_for_new_user())       
        return
    else: 
        char_id, _, name, gender, _, hunger, fatigue, entertain, money_need, total_state, standart_photo_number, _ = result        
        keyboard = create_keyboard_for_chatacter_avatar(gender)    
        img_bytes = generate_image_with_progress_bars(user_id, name, hunger, fatigue, entertain, money_need, total_state)
    
        if total_state == 100:        
            send_character_image_with_progress(user_id, img_bytes,None)  
            text = "Сейчас всё хорошо – редкий, но приятный момент" if gender == "male" else "Я довольна, сыта, спокойна и немножко счастлива"        
            bot.send_message(user_id,text,reply_markup=create_keyboard_for_info(), parse_mode="HTML") 
        else:
            send_character_image_with_progress(user_id, img_bytes,keyboard)        
   
def hourly_update_characters_chanked():
    result = execute_query("SELECT * FROM characters")
    all_chars = result
    num_results = len(all_chars)
    logger.info(f"При обновлении персонажей найдено {num_results} записей")

    # Проверяем, есть ли созданные персонажи
    if not all_chars:
        print("Активных персонажей нет")
        return
    
    CHUNK_SIZE = math.ceil(num_results / 20)  # Округляем вверх
    INTERVAL_SECONDS = 60  # Интервал между партиями в секундах (1 минута)    

    # Начинаем обработку партиями
    for i in range(0, len(all_chars), CHUNK_SIZE):
        chars_batch = all_chars[i:i + CHUNK_SIZE]
        
        for char_id, user_id, name, gender, _, hunger, fatigue, entertain, money_need, total_state, standart_photo_number, created_at in chars_batch:

            # Пропускаем заблокированного пользователя
            if user_id in blocked_users:
                continue
            
            logger.info(f"Стартовала отправка порции сообщений {datetime.now()}")            

            hunger -= 10
            fatigue -= 5
            entertain -= 7
            money_need -= 6

            new_total_state = calculate_total_state(hunger, fatigue, entertain, money_need)
            update_character_stats(max(hunger, 0), max(fatigue, 0), max(entertain, 0), max(money_need, 0), max(new_total_state, 0), char_id)

            check_hunger(user_id, gender, hunger)
            check_entertain(user_id, gender, hunger)
            check_fatigue(user_id, gender, hunger)
            check_money_need(user_id, gender, hunger)

            check_total_state(user_id, char_id, name, gender, max(new_total_state, 0), standart_photo_number)
            hours_left = check_character_old(user_id, char_id, created_at, gender)
            logger.info(f"hourly_update_characters run for user {user_id}, hours_left = {hours_left}, total_state = {total_state}")

            # Если персонаж старше требуемого времени, выдаём награду
            if hours_left < 1:
                win(user_id, char_id, gender)

        # Пауза между партиями (1 минута)
        time.sleep(INTERVAL_SECONDS)                              
        

def calculate_total_state(hunger, fatigue, entertain, money_need):
    return sum([hunger, fatigue, entertain, money_need]) / 4                                                
        

def check_total_state(user_id, char_id, name, gender, new_total_state,standart_photo_number):
        
    # Проверка общего уровня здоровья
        logger.info(f"Уровень стресса {new_total_state}")    
        if new_total_state <= STATE_LOSE_LOWER_BOUND:
            lose(user_id, char_id, gender)    
        elif new_total_state <= STATE_RED_LOWER_BOUND:
            phrases = [
            "Последнее предупреждение.Дальше – чемоданы.",
            "Это уже тревожный звоночек.Очень тревожный!",
            "Мы почти на грани.Я серьезно."            
            ]
            replace_avatar_foto_in_db(user_id, gender, standart_photo_number, 2, new_total_state)
            try:
                bot.send_message(user_id, random.choice(phrases), reply_markup=create_keyboard_for_continue(), parse_mode="HTML")            
            except Exception as e:
                if 'User has blocked this bot' in str(e):
                    blocked_users.add(user_id)
                    logger.warning(f"Пользователь {user_id} заблокировал бота.")
                else:                
                    logger.warning(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
            
        elif new_total_state <= STATE_YELLOW_UPPER_BOUND:
            phrases = [
            "Я еще держусь, но это уже не мой лучший день.",
            "Я не паникую. Но повода для радости тоже мало.",
            "Так… у нас тут уже не идеально. Я начинаю чувствовать себя одиноко."
            ]
            replace_avatar_foto_in_db(user_id, gender, standart_photo_number, 1, new_total_state)
            try:
                bot.send_message(user_id, random.choice(phrases), reply_markup=create_keyboard_for_continue(), parse_mode="HTML")
            except Exception as e:
                if 'User has blocked this bot' in str(e):
                    blocked_users.add(user_id)
                    logger.warning(f"Пользователь {user_id} заблокировал бота.")
                else:                
                    logger.warning(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
        elif new_total_state <= STATE_GREEN_LOWER_BOUND:
            phrases = [
            "Хмм… кажется, у нас тут легкий эмоциональный сквозняк.\nНичего критичного, но лучше заглянуть.",
            "Алло! Всё ок, но не на 100%.\nПроверь, как я там, пожалуйста.",
            "Мне вроде нормально. Но с тобой было бы лучше 😢"
            ]
            replace_avatar_foto_in_db(user_id, gender, standart_photo_number, 1, new_total_state)
            try:
                bot.send_message(user_id, random.choice(phrases), reply_markup=create_keyboard_for_continue(), parse_mode="HTML")
            except Exception as e:
                if 'User has blocked this bot' in str(e):
                    blocked_users.add(user_id)
                    logger.warning(f"Пользователь {user_id} заблокировал бота.")
                else:                
                    logger.warning(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
        else:
            replace_avatar_foto_in_db(user_id, gender, standart_photo_number, 0, new_total_state)



def replace_avatar_foto_in_db(user_id, gender, standart_photo_number, level, new_total_state):
    try:
        # Если выбрано нестандартное фото (-127), загружаем пользовательское фото с рамкой
        if standart_photo_number == NO_STANDART_FOTO:
            avatar_data = get_avatar_image_with_frame_color(user_id, gender, standart_photo_number, level, new_total_state)
            update_or_insert_character_photo(user_id, avatar_data)
        else:
            # Если выбрано стандартное фото, формируем название файла и обновляем
            standart_foto_number_int = int(standart_photo_number)
            filename = f'men_{standart_foto_number_int}_{level}.png' if gender == 'male' else f'women_{standart_foto_number_int}_{level}.png'
            full_path = os.path.join('pic', 'pic_avatar', filename)

            # Чтение стандартного фото
            with open(full_path, 'rb') as f:
                new_photo_bytes = f.read()
                update_or_insert_character_photo(user_id, new_photo_bytes)

            # Добавляем рамку к стандартному фото
            framed_avatar_data = get_avatar_image_with_frame_color(user_id, gender, standart_photo_number, level, new_total_state)
            update_or_insert_character_photo(user_id, framed_avatar_data)

    except FileNotFoundError:
        print(f'Ошибка: файл "{full_path}" не найден.')
    except Exception as e:
        print(f'Общая ошибка обновления аватара: {e}')


def check_character_old(user_id, char_id, created_at_str, gender):
    # Парсим timestamp из строки
        created_at = datetime.strptime(created_at_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
        # Текущее время минус HOURS_SHIFT_SERVER часов (для компенсации разницы)
        now_adjusted = datetime.now() - timedelta(hours=HOURS_SHIFT_SERVER)     

        # Время необходимое для возможности выиграть (переводим дни в часы)
        required_time = timedelta(hours=HOURS_TO_WIN)
        
        # Остаточное время до достижения нужного периода
        remaining_time = required_time - (now_adjusted - created_at)
        hours_left = max(int(remaining_time.total_seconds() // 3600), 0)
        return hours_left    

def get_time_to_win(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    character_data = get_current_avatar_param(user_id)
    if character_data is None:
        bot.send_message(chat_id, "Персонаж не найден")
    else:
        char_id, _, name, gender, _, hunger, fatigue, entertain, money_need, total_state, standart_photo_number, created_at_str = character_data
        hours_left = check_character_old(user_id, char_id, created_at_str, gender)
                      
        logger.info(f"До финиша осталось {hours_left}")

        # Если персонаж старше требуемого времени, выдаём награду
        if hours_left < 1:
            win(user_id, char_id, gender)
            return "Победа"
        else:
            return f"До финиша осталось {hours_left} часа(ов)"


def win(user_id, char_id, gender):
    delete_character_from_db(char_id)    
    congratulation_text = random.choice(CONGRATS_OPTIONS)
    picture_path = "pic/men_win.jpg" if gender == "male" else "pic/women_win.jpg"

    try:
        # Попытка отправки фотографии
        with open(picture_path, 'rb') as photo:
            bot.send_photo(user_id, photo)
    except Exception as e:
        logger.warning(f"Ошибка при отправке фотографии победителю пользователю {user_id}: {e}")

    try:
        # Попытка отправки текста поздравления
        bot.send_message(user_id, congratulation_text, reply_markup=create_keyboard_for_new_user(), parse_mode="HTML")
    except Exception as e:
            if 'User has blocked this bot' in str(e):
                blocked_users.add(user_id)
                logger.warning(f"Пользователь {user_id} заблокировал бота.")
            else:
                logger.warning(f"Ошибка при отправке поздравления пользователю {user_id}: {e}")                 
    

def lose(user_id, char_id, gender):
      delete_character_from_db(char_id)
      fail_text = FAIL_TEXT_MAN if gender == "male" else FAIL_TEXT_WOMEN              
      picture_path = "pic/women_lose.jpg" if gender == "female" else "pic/men_lose.jpg"

      try:
          # Открываем фотографию и пытаемся отправить пользователю
          with open(picture_path, 'rb') as photo:
              bot.send_photo(
                  user_id,
                  photo,
                  caption=fail_text,
                  reply_markup=create_keyboard_for_new_user(),
                  parse_mode="HTML"
              )                
      except Exception as e:
                if 'User has blocked this bot' in str(e):
                    blocked_users.add(user_id)
                    logger.warning(f"Пользователь {user_id} заблокировал бота.")
                else:
                    logger.warning(f"Ошибка при отправке фотографии проигрыша пользователю {user_id}: {e}")       


def check_hunger(user_id, gender, hunger):
    # Проверка уровня голода
    if hunger < 50:
        message = ""
        if gender == 'female':
            message = "🍣 Я не ела уже целую вечность!\nРоллы бы сейчас спасли эту историю любви."
        elif gender == 'male':
            message = "🍜 Я думаю о еде больше, чем о смысле жизни.\nНам срочно нужен вок."        
        try:        
          bot.send_message(user_id, message, parse_mode="HTML")
        except Exception as e:
                if 'User has blocked this bot' in str(e):
                    blocked_users.add(user_id)
                    logger.warning(f"Пользователь {user_id} заблокировал бота.")
                else:
                    logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
        

def check_fatigue(user_id, gender, fatigue):
    if fatigue < 60:
        message = ""
        if gender == 'female':
            message = "🛀 Я устала.\nОчень.\nСПА. СРОЧНО."
        elif gender == 'male':
            message = "📺 Я морально на диване...\nА физически – еще нет."
        try:        
          bot.send_message(user_id, message, parse_mode="HTML")
        except Exception as e:
                if 'User has blocked this bot' in str(e):
                    blocked_users.add(user_id)
                    logger.warning(f"Пользователь {user_id} заблокировал бота.")
                else:
                    logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")    

def check_entertain(user_id, gender, entertain):
    if entertain <= 40:
        message = ""
        if gender == 'female':
            message = "💸 Мне срочно нужно немного денег на развлечения…\nЯ держусь, но карта – нет."
        elif gender == 'male':
            message = "🏖️ Мне нужно к пацанам в баню.\nЭто не побег, это… профилактика усталости."
        try:        
          bot.send_message(user_id, message, parse_mode="HTML")
        except Exception as e:
                if 'User has blocked this bot' in str(e):
                    blocked_users.add(user_id)
                    logger.warning(f"Пользователь {user_id} заблокировал бота.")
                else:
                    logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")    

def check_money_need(user_id, gender, money_need):
    if money_need < 55:
        message = ""
        if gender == 'female':
            message = "😘 Алло, а где мои обнимашки?\nИсправь."
        elif gender == 'male':
            message = "Алло, а где мои обнимашки?\nИсправь."
        try:        
          bot.send_message(user_id, message, parse_mode="HTML")
        except Exception as e:
                if 'User has blocked this bot' in str(e):
                    blocked_users.add(user_id)
                    logger.warning(f"Пользователь {user_id} заблокировал бота.")
                else:
                    logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")    
            

def run_timer():
    while True:
        current_time = datetime.now()
        hour = current_time.hour                
        #Работаем только с 7:00 до 22:00
        if 7 <= hour < 22:
            logger.info(f"Время в основном таймере {current_time}")                        
            hourly_update_characters_chanked()
            time.sleep(3600)  # Ждем ровно 1 час (3600 секунд)            
        else:
            logger.info(f"Время в маленьком таймере  {current_time}")            
            time.sleep(600) # Просыпаемся раз в 10 минут для проверки интервала (600 секунд)                   
        

# Запускаем таймер в отдельном потоке
timer_thread = Thread(target=run_timer)
timer_thread.start()  
           

if __name__ == "__main__":
    asyncio.run(main())
    bot.infinity_polling()