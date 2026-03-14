from aiogram import types
from loguru import logger
from handlers.admin.keyboards import get_admin_keyboard

async def show_stats(callback: types.CallbackQuery, db):
    """Показывает статистику использования сервиса"""
    try:
        total_users = await db.get_users_count()
        total_cars = await db.get_cars_count()
        most_booked_car = await db.get_most_booked_car()
        most_active_user = await db.get_most_active_user()
        
        text = (
            "📊 <b>Статистика сервиса</b>\n\n"
            f"👥 Всего пользователей: <b>{total_users}</b>\n"
            f"🚗 Всего автомобилей: <b>{total_cars}</b>\n\n"
        )
        
        if most_booked_car:
            text += (
                "🏆 <b>Самый арендуемый автомобиль:</b>\n"
                f"• Модель: <b>{most_booked_car['model']}</b>\n"
                f"• Номер: <b>{most_booked_car['number_plate']}</b>\n"
                f"• Количество бронирований: <b>{most_booked_car['booking_count']}</b>\n\n"
            )
        
        if most_active_user:
            text += (
                "👑 <b>Самый активный пользователь:</b>\n"
                f"• Имя: <b>{most_active_user['full_name']}</b>\n"
                f"• Телефон: <b>{most_active_user['phone_number']}</b>\n"
                f"• Описание: <i>{most_active_user['description'] or 'Нет описания'}</i>\n"
                f"• Количество бронирований: <b>{most_active_user['booking_count']}</b>"
            )
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin:back")]
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        logger.debug(f"Showed statistics to admin {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error showing statistics: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при получении статистики",
            reply_markup=get_admin_keyboard()
        ) 