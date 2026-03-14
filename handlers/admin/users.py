from aiogram import types
from loguru import logger
from ..db.database import Database
from .admin import check_admin
from .keyboards import get_users_keyboard, get_admin_keyboard

async def show_users_list(callback: types.CallbackQuery, db: Database):
    """Показывает список зарегистрированных пользователей"""
    user_id = callback.from_user.id
    
    if not await check_admin(user_id):
        logger.warning(f"Unauthorized admin access attempt from user {user_id}")
        await callback.answer("⛔️ У вас нет доступа к админ-панели.")
        return
        
    users_count = await db.get_users_count()
    users = await db.get_users_list()
    
    text = [
        "📋 Список зарегистрированных пользователей",
        f"👥 Всего пользователей: {users_count}\n",
        "🔽 Подробная информация:\n"
    ]
    
    for user in users:
        user_info = [
            f"<blockquote>"
            f"🆔 Telegram ID: {user['telegram_id']}",
            f"🙍‍♂️ Имя пользователя: {user['full_name']}",
            f"📝 ФИО: {user['description'] or 'Не указано'}",
            f"📞 Номер телефона: {user['phone_number'] or 'Не указан'}"
            f"</blockquote>"
        ]
        text.extend(user_info)
    
    try:
        await callback.message.edit_text(
            "\n".join(text),
            reply_markup=get_users_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        await callback.message.answer(
            "\n".join(text),
            reply_markup=get_users_keyboard(),
            parse_mode="HTML"
        )

async def handle_admin_back(callback: types.CallbackQuery, db: Database):
    """Обработчик кнопки Назад в админ-панели"""
    user_id = callback.from_user.id
    
    if not await check_admin(user_id):
        logger.warning(f"Unauthorized admin access attempt from user {user_id}")
        await callback.answer("⛔️ У вас нет доступа к админ-панели.")
        return
        
    await callback.message.edit_text(
        "👨‍💼 <b>Админ меню:</b>\n"
        "Выберите действие:\n\n"
        "📊 <b>Статистика</b> — просмотр статистики аренды по автомобилям\n"
        "👥 <b>Пользователи</b> — поиск и редактирование пользователей, отмена бронирований\n"
        "🚗 <b>Управление авто</b> — добавление, редактирование и удаление автомобилей в автопарке\n"
        "📢 <b>Рассылка</b> — массовая рассылка сообщений пользователям",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )