from aiogram import types
from aiogram.filters import Command
import os
from loguru import logger
from .keyboards import get_admin_keyboard

async def check_admin(user_id: int) -> bool:
    admin_ids = os.getenv('ADMIN_ID', '').split(',')
    return str(user_id) in admin_ids

async def admin_command(message: types.Message):
    user_id = message.from_user.id
    
    if not await check_admin(user_id):
        logger.warning(f"Unauthorized admin access attempt from user {user_id}")
        await message.answer("⛔️ У вас нет доступа к админ-панели.")
        return
        
    logger.info(f"Admin menu accessed by user {user_id}")
    await message.answer(
        "👨‍💼 <b>Админ меню:</b>\n"
        "Выберите действие:\n\n"
        "📊 <b>Статистика</b> — просмотр статистики аренды по автомобилям\n"
        "👥 <b>Пользователи</b> — поиск и редактирование пользователей, отмена бронирований\n"
        "🚗 <b>Управление авто</b> — добавление, редактирование и удаление автомобилей в автопарке\n"
        "📢 <b>Рассылка</b> — массовая рассылка сообщений пользователям",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
 