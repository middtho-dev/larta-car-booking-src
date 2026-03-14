from aiogram import types

def get_admin_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="📊 Статистика",callback_data="admin:stats"),
            types.InlineKeyboardButton(text="🚗 Управление авто",callback_data="admin:cars")
        ],
        [
            types.InlineKeyboardButton(text="👥 Пользователи",callback_data="admin:users"),
            types.InlineKeyboardButton(text="📢 Рассылка",callback_data="admin:mailing")
        ]
    ])

def get_users_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🔍 Поиск", callback_data="admin:users:search"),
            types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin:back")
        ]
    ])

def get_user_details_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin:users:edit:{user_id}"),
            types.InlineKeyboardButton(text="📋 Брони", callback_data=f"admin:users:bookings:{user_id}")
        ],
        [
            types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin:users")
        ]
    ])

def get_user_bookings_keyboard(booking_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="❌ Отменить бронь", callback_data=f"admin:booking:cancel:{booking_id}")
        ],
        [
            types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin:users")
        ]
    ])

def get_cars_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="➕ Добавить", callback_data="admin:cars:add"),
            types.InlineKeyboardButton(text="✏️ Редактировать", callback_data="admin:cars:edit")
        ],
        [
            types.InlineKeyboardButton(text="🗑 Удалить", callback_data="admin:cars:delete"),
            types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin:back")
        ]
    ])

def get_car_edit_keyboard(car_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✏️ Изменить модель", callback_data=f"admin:cars:edit:model:{car_id}"),
            types.InlineKeyboardButton(text="🔄 Изменить номер", callback_data=f"admin:cars:edit:number:{car_id}")
        ],
        [
            types.InlineKeyboardButton(text="📊 Изменить статус", callback_data=f"admin:cars:edit:status:{car_id}")
        ],
        [
            types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin:cars")
        ]
    ])

def get_car_status_keyboard(car_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Доступен", callback_data=f"admin:cars:status:{car_id}:available"),
            types.InlineKeyboardButton(text="❌ В ремонте", callback_data=f"admin:cars:status:{car_id}:unavailable")
        ],
        [
            types.InlineKeyboardButton(text="📅 Забронирован", callback_data=f"admin:cars:status:{car_id}:booked"),
            types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin:cars:edit:{car_id}")
        ]
    ]) 