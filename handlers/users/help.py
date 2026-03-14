from aiogram import types
from loguru import logger
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from handlers.users.keyboards import get_start_keyboard

async def show_help(callback: types.CallbackQuery):
    """Показывает информацию о помощи"""
    logger.info(f"User {callback.from_user.id} requested help")
    
    help_text = """
📱 <b>Помощь по использованию бота</b>

<b>Основные функции:</b>

🚗 <b>Забронировать авто</b> - позволяет выбрать и забронировать доступный автомобиль на определенное время.

📋 <b>Мои бронирования</b> - показывает историю ваших бронирований с подробной информацией.

<b>Процесс бронирования:</b>

1️⃣ Выберите автомобиль из списка доступных
2️⃣ Укажите дату и время начала аренды (формат: ДД.ММ.ГГГГ ЧЧ:ММ)
3️⃣ Укажите дату и время окончания аренды
4️⃣ Перед началом использования сделайте 6 фотографий автомобиля
5️⃣ После завершения аренды сделайте ещё 6 фотографий

<b>Важно:</b>
• Бот отправит уведомление за 10 минут до начала бронирования
• Бот отправит уведомление за 10 минут до окончания бронирования

Если у вас возникли вопросы, обратитесь к администратору.
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")]
    ])
    
    if callback.message.photo:
        try:
            await callback.message.edit_caption(
                caption=help_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not edit caption: {e}")
            await callback.message.answer(
                help_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    else:
        try:
            await callback.message.edit_text(
                help_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not edit message: {e}")
            await callback.message.answer(
                help_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    
    logger.debug(f"Showed help information to user {callback.from_user.id}") 