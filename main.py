from telebot import types
import telebot
import asyncio
import time
from datetime import datetime
from threading import Thread
from datetime import timedelta
from telebot.types import InputMediaPhoto
from api_key import API_TOKEN
import logging
from io import BytesIO
import random
from db_utils import *
from messages import *
from file_work_utils import *
from keyboards import *
from PIL import Image, ImageDraw, ImageFont
import io

bot = telebot.TeleBot(API_TOKEN)
bot.delete_webhook()

logging.basicConfig(level=logging.INFO)  
logger = logging.getLogger(__name__)

# Словарь для временного хранения данных пользователей
user_data = {}
# ID последнего отправленного сообщения
last_message_id = None

async def main():    
    logger.info("Бот запущен")
    create_db()     
    try:
        set_global_promo_map (await readFileToMap())                    
    except Exception as e:
        print(f"Ошибка: {e}")


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
        bot.send_message(message.chat.id, "Теперь выбери имя своего персонажа (не более 30 символов, буквы и цифры).")
        bot.register_next_step_handler(message, process_character_name)
    elif text.startswith("создать персонажа"):        
        bot.send_message(user_id, "Выбери пол своего персонажа", reply_markup=create_keyboard_for_choose_gender())        
    elif text.startswith("проведать любимку"):        
        check_character_and_send_status(user_id)

    elif text.startswith("покормить роллами"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'hunger', +40)        
    elif text.startswith("заказать"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'hunger', +40) 

    elif text.startswith("сводить в"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'fatigue', +20)
    elif text.startswith("положить на диван перед телевизором"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'fatigue', +20)
    
    elif text.startswith("отпустить с пацанами в баню"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'entertainment', +20)
    elif text.startswith("скинуть денежки на карту"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'entertainment', +20)                          

    elif text.startswith("обнять и поцеловать"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'money_needs', +20)
    elif text.startswith("похвалить и сказать"):
        ugrade_character_parameter_and_show_new_avatar(user_id, 'money_needs', +20)                
    
    else:
        pass        


def ugrade_character_parameter_and_show_new_avatar (user_id, param_name, value_change):
    need_send_message, gender = update_character_parameter(user_id, param_name, value_change)
    # Если нужно отправить сообщение, делаем это отсюда
    if need_send_message:
        send_random_message(user_id, param_name, gender)    
    
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

    # Сохраняем оригинальное изображение в словаре user_data
    user_data[message.chat.id]['photo'] = downloaded_file
    bot.send_message(message.chat.id, "Фотография принята.", reply_markup=types.ReplyKeyboardRemove())
    # Переходим к созданию персонажа
    create_character(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == 'select_standard')
def handle_select_standard(call):
    chat_id = call.message.chat.id
    gender = user_data[chat_id]['gender']
    buttons = []

    # Показ стандартных изображений
    for i in range(3):
        filename = f'men_{i}.png' if gender == 'male' else f'girl_{i}.png'
        with open(filename, 'rb') as f:
            img_data = f.read()
        
        button_text = str(i+1)
        buttons.append(types.InlineKeyboardButton(button_text, callback_data=f'select:{button_text}'))
        # Отдельно отправляем каждую картинку
        bot.send_photo(chat_id, img_data)

    # Формируем inline-клавиатуру с номерами картинок
    keyboard = types.InlineKeyboardMarkup().add(*buttons)
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
    # Размер шрифта и отступы
    font_size = 20
    bar_height = 20
    padding = 10
    margin_top = image.height - ((bar_height + padding) * 4)
    
    # Загрузка шрифта
    font = ImageFont.truetype("arial.ttf", size=font_size)
    
    # Создание копии изображения для рисования
    draw = ImageDraw.Draw(image)
    
    # Цвета
    bg_color = "#ffffff"
    fg_color = "#ff0000"
    label_color = "#000000"
    
    values = [(hunger, "Голод"), (fatigue, "Усталость"), (entertain, "Развлечения"), (money_need, "Забота")]
    
    for i, (value, label) in enumerate(values):
        y_pos = margin_top + (i * (bar_height + padding)) + padding
        
        # Рисование фона прогресс-бара
        draw.rectangle([padding, y_pos, image.width - padding, y_pos + bar_height], fill=bg_color)
        
        # Прогресс-бар заполненный цветом
        progress_width = value / 100 * (image.width - 2*padding)
        draw.rectangle([padding, y_pos, padding+progress_width, y_pos + bar_height], fill=fg_color)
        
        # Подпись над каждой полосой
        draw.text((padding, y_pos - font_size), label, font=font, fill=label_color)
    
    return image

# Пример использования
def generate_image_with_progress_bars(user_id, name, hunger, fatigue, entertain, money_need):
    original_img = fetch_character_photo(user_id)
    img = Image.open(io.BytesIO(original_img))
    
    # Применяем функцию рисования шкал
    final_img = draw_progress_bars(img, hunger, fatigue, entertain, money_need)
    
    # Преобразовываем изображение в байтовый объект для отправки
    output_buffer = io.BytesIO()
    final_img.save(output_buffer, format='PNG')
    output_buffer.seek(0)
    
    return output_buffer.read()

# Новый метод отправки изображения с графиками
def send_character_image_with_progress(user_id, name, hunger, fatigue, entertain, money_need, keyboard=None):
    global last_message_id
    
    img_bytes = generate_image_with_progress_bars(user_id, name, hunger, fatigue, entertain, money_need)
    
    if img_bytes is None:
        bot.send_message(user_id, "Персонаж или изображение не найдены")
    else:
        bio = io.BytesIO(img_bytes)
        bio.seek(0)
        
        # Отправляем изображение с шкалами
        sent_message = bot.send_photo(user_id, bio, reply_markup=keyboard)
        last_message_id = sent_message.message_id


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
        return bot.send_message(user_id, "Ваш персонаж отсутствует.", reply_markup=create_keyboard_for_new_user())
    
    character_data = result[0]    
    char_id, _, name, gender, _, hunger, fatigue, entertain, money_need, total_state, _ = character_data      
    keyboard = create_keyboard_for_chatacter_avatar(gender)
    send_character_image_with_progress(user_id, name, hunger, fatigue, entertain, money_need)
    #send_character_image(user_id, name, hunger, fatigue, entertain, money_need, keyboard)
    
    
# Отправка изображения с подписью (аналогично вашему примеру)
def send_character_image(user_id, name, hunger, fatigue, entertain, money_need, keyboard=None):
    global last_message_id
    
    img_bytes = fetch_character_photo(user_id)
    
    if img_bytes is None:
        bot.send_message(user_id, "Персонаж или изображение не найдены")
    else:
        bio = BytesIO(img_bytes)
        bio.seek(0)
        
        # Объединяем изображение и подпись в одном вызове
        text = "%s \nГолод: %.0f%% \nУсталость: %.0f%% \nПотребность развлечься: %.0f%% \nПотребность в заботе: %.0f%%" % (
            name, hunger, fatigue, entertain, money_need
        )

        if last_message_id is None:
            sent_message = bot.send_photo(user_id, bio, caption=text, reply_markup=keyboard)
            last_message_id = sent_message.message_id
        else:
            update_caption(user_id, name, hunger, fatigue, entertain, money_need)
       

# Обновление подписи изображения (без перезагрузки самого изображения)
def update_caption(user_id, name, hunger, fatigue, entertain, money_need):
    global last_message_id
    
    new_text = "%s \nГолод: %.0f%% \nУсталость: %.0f%% \nПотребность развлечься: %.0f%% \nПотребность в заботе: %.0f%%" % (
        name, hunger, fatigue, entertain, money_need
    )
    
    try:
        # Используем edit_message_caption для изменения подписи под изображением
        bot.edit_message_caption(
            caption=new_text,
            chat_id=user_id,
            message_id=last_message_id
        )
    except telebot.apihelper.ApiException as e:
        logging.error(f"Ошибка редактирования: {e}")
    

def hourly_update_characters():   
        
    result = execute_query("SELECT * FROM characters")
    all_chars = result
        
    for char_id, user_id, name, gender, _, hunger, fatigue, entertain, money_need, total_state, created_at in all_chars:
        hunger -= 10
        fatigue -= 5
        entertain -= 5
        money_need -= 5
        
        new_total_state = sum([hunger, fatigue, entertain, money_need]) / 4
        logger.info(f"Результат расчета состояния {new_total_state} - {name} - {char_id} - {hunger} - {fatigue} - {entertain} - {money_need}")
        update_character_stats(max(hunger,0), max(fatigue,0), max(entertain,0), max(money_need,0), max(new_total_state,0), char_id)     

        check_hunger(user_id,gender,hunger)
        check_entertain(user_id,gender,hunger)
        check_fatigue(user_id,gender,hunger)
        check_money_need(user_id,gender,hunger)

        check_total_state(user_id,char_id,name,gender,max(new_total_state,0))        
        check_character_old(user_id, char_id, created_at)                                                 
        

def check_total_state(user_id, char_id, name, gender, new_total_state):
    # Проверка общего уровня здоровья
        if new_total_state <= 20:            
            delete_character_from_db(char_id)
            fail_text = FAIL_TEXT_MAN if gender == "male" else FAIL_TEXT_WOMEN
            bot.send_message(user_id, fail_text, parse_mode="HTML")
            bot.send_message(user_id, f"Ваш персонаж {name} покинул Вас", reply_markup=create_keyboard_for_new_user(), parse_mode="HTML")
        elif new_total_state <= 30:
            phrases = [
            "Последнее предупреждение.Дальше – чемоданы.",
            "Это уже тревожный звоночек.Очень тревожный!",
            "Мы почти на грани.Я серьезно."            
            ]
            bot.send_message(user_id, random.choice(phrases), reply_markup=create_keyboard_for_continue(), parse_mode="HTML")            
        elif new_total_state <= 50:
            phrases = [
            "Я еще держусь, но это уже не мой лучший день.",
            "Я не паникую.Но повода для радости тоже мало.",
            "Так… у нас тут уже не идеально.Я начинаю чувствовать себя забытым."
            ]
            bot.send_message(user_id, random.choice(phrases), reply_markup=create_keyboard_for_continue(), parse_mode="HTML")
        elif new_total_state <= 80:
            phrases = [
            "Хмм… кажется, у нас тут легкий эмоциональный сквозняк.\nНичего критичного, но лучше заглянуть.",
            "Алло! Всё ок, но не на 100%.\nПроверь, как я там, пожалуйста.",
            "Мне вроде нормально. Но с тобой было бы лучше 😢"
            ]
            bot.send_message(user_id, random.choice(phrases), reply_markup=create_keyboard_for_continue(), parse_mode="HTML")            

def check_character_old (user_id, char_id, created_at):
    # Проверка возраста персонажа
        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        created_dt = datetime.strptime(created_at.split('.')[0], "%Y-%m-%d %H:%M:%S")
        if created_dt < five_days_ago:
            delete_character_from_db(char_id)
            element=getPromo()
            сongratulation_text = CONGRATULATION_TEXT.format(element)           
            bot.send_message(user_id, сongratulation_text, reply_markup=create_keyboard_for_new_user(), parse_mode="HTML")   

def check_hunger(user_id, gender, hunger):
    # Проверка уровня голода
    if hunger < 50:
        message = ""
        if gender == 'female':
            message = "🍣 Я не ела уже целую вечность!\nРоллы бы сейчас спасли эту историю любви."
        elif gender == 'male':
            message = "🍜 Я думаю о еде больше, чем о смысле жизни.\nНам срочно нужен вок."
        bot.send_message(user_id, message, parse_mode="HTML")

def check_fatigue(user_id, gender, fatigue):
    if fatigue < 60:
        message = ""
        if gender == 'female':
            message = "🛀 Я устала.\nОчень.\nСПА. СРОЧНО."
        elif gender == 'male':
            message = "📺 Я морально на диване...\nА физически – еще нет."
        bot.send_message(user_id, message, parse_mode="HTML")

def check_entertain(user_id, gender, entertain):
    if entertain <= 40:
        message = ""
        if gender == 'female':
            message = "💸 Мне срочно нужно немного денег на развлечения…\nЯ держусь, но карта – нет."
        elif gender == 'male':
            message = "🏖️ Мне нужно к пацанам в баню.\nЭто не побег, это… профилактика усталости."
        bot.send_message(user_id, message, parse_mode="HTML")

def check_money_need(user_id, gender, money_need):
    if money_need < 55:
        message = ""
        if gender == 'female':
            message = "😘 Алло, а где мои обнимашки?\nИсправь."
        elif gender == 'male':
            message = "🙃 Алло, а где мои обнимашки?\nИсправь."
        bot.send_message(user_id, message, parse_mode="HTML")
            

# Функция для запуска таймера
def run_timer():
    while True:
        current_time = datetime.now()       
        # Выбираем диапазон часов, в течение которого будем обновлять персонажей
        #if 9 <= current_time.hour <= 16 and current_time.minute == 0:
        hourly_update_characters()
        time.sleep(60)  # Проверяем каждую минуту      
        #time.sleep(7200)  # Проверяем каждые два часа

# Запускаем таймер в отдельном потоке
timer_thread = Thread(target=run_timer)
timer_thread.start()
  
           

if __name__ == "__main__":
    asyncio.run(main())
    bot.infinity_polling()