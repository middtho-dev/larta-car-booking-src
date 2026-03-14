from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import os


def _can_use_telegram_webapp(url: str) -> bool:
    """Telegram WebApp кнопки принимают только HTTPS (и localhost для разработки)."""
    if not url:
        return False

    lowered = url.lower()
    if lowered.startswith("https://"):
        return True

    # Telegram допускает localhost для локальной разработки
    return lowered.startswith("http://localhost") or lowered.startswith("http://127.0.0.1")


def get_start_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🧭 Открыть мини-приложение", callback_data="calendar")
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cars_keyboard(cars: list) -> InlineKeyboardMarkup:
    buttons = []
    
    for car in cars:
        buttons.append([
            InlineKeyboardButton(
                text=f"{car['model']} ({car['number_plate']})",
                callback_data=f"select_car:{car['id']}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_keyboard() -> InlineKeyboardMarkup:
    buttons = [[
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")
    ]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    buttons = [[
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking")
    ]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_calendar_keyboard(token: str | None = None) -> InlineKeyboardMarkup:
    base_url = (os.getenv("CAR_BOOKING_URL") or "").rstrip("/")
    calendar_url = f"{base_url}/?token={token}" if token else base_url

    if _can_use_telegram_webapp(calendar_url):
        open_btn = InlineKeyboardButton(
            text="🌐 Открыть мини-приложение",
            web_app=WebAppInfo(url=calendar_url),
        )
    else:
        # Fallback: обычная URL-кнопка, чтобы не падать на не-HTTPS окружении
        open_btn = InlineKeyboardButton(
            text="🌐 Открыть веб-версию",
            url=calendar_url,
        )

    buttons = [
        [open_btn],
        [
            InlineKeyboardButton(text="🔁 Обновить", callback_data="refresh_calendar")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_ending_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✍️ Оставить заметку", callback_data=f"add_reviews:{booking_id}"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)