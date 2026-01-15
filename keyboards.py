from telebot import types


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

def create_keyboard_for_chatacter_avatar(gender):

    buttons = []
    
    # Формирование клавиатуры действий
    if gender == 'female':
        buttons.extend([
        "Покормить роллами 🍣",
        "Сводить в SPA 🛀",
        "Скинуть денежки на карту 💳",
        "Обнять и поцеловать 😘"
    ])
    else:
        buttons.extend([
        "Заказать WOK 🍜",
        "Положить на диван перед телевизором 📺",
        "Отпустить с пацанами в баню / на расслабон 🏖️",
        "Похвалить и сказать «ты лучший» 👌"
    ])
   
    return create_keyboard(buttons, False)
    
    

def create_keyboard(buttons, one_time):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, one_time_keyboard=one_time)    
    for text in buttons:
        btn = types.KeyboardButton(text=text)
        keyboard.add(btn)

    return keyboard  